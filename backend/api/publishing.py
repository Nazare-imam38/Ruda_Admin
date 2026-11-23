"""Reuse the generic Layer registry for immutable, versioned GeoServer publications."""
import io
import json
import logging
import math
import tempfile
import zipfile
import re
import shapefile
from pyproj import CRS, Transformer
from shapely import make_valid
from shapely.geometry import MultiPolygon, MultiLineString, MultiPoint, mapping, shape
from shapely.ops import transform
from pathlib import Path
from .geoserver import GeoServer, PublishError
from .importer import (
    parse_shapefile, get_archive_files, ImportValidationError, MAX_ZIP_SIZE,
    SUPPORTED_GEOMETRY,
)
from .raster import save_upload, inspect_raster, optimize

logger = logging.getLogger(__name__)

# GeoJSON preview budget, separate from the uploaded ZIP limit.
# The importer already enforces MAX_FEATURES (50,000).
MAX_PREVIEW_BYTES = 20 * 1024 * 1024

DATA_FIELDS = ('geometry_type', 'source_crs', 'source_filename', 'field_names', 'field_schema', 'bbox', 'feature_count', 'publication')


def _same_family(geometry, family):
    """Keep the original geometry family, without splitting the DBF record."""
    names = {'Polygon': 'Polygon', 'Line': 'LineString', 'Point': 'Point'}
    target = names[family]
    parts = []
    omitted = 0

    def collect(item):
        nonlocal omitted
        if item.is_empty:
            return
        if item.geom_type == target:
            parts.append(item)
        elif hasattr(item, 'geoms'):
            for member in item.geoms:
                collect(member)
        else:
            omitted += 1

    collect(geometry)
    if not parts:
        raise ValueError('geometry collapsed; no non-empty geometry of the original type remains')
    constructor = {'Polygon': MultiPolygon, 'Line': MultiLineString, 'Point': MultiPoint}[family]
    result = parts[0] if len(parts) == 1 else constructor(parts)
    if not result.is_valid or result.is_empty:
        raise ValueError('geometry remains invalid after repair')
    return result, omitted


def _repair_vector_archive(data):
    """Repair 2D geometry records and rebuild SHP/SHX; preserve DBF and CRS bytes.

    Never drop feature records or rewrite their attributes. Z/M files requiring
    repair are rejected rather than silently losing elevations or measures.
    """
    parts = get_archive_files(data)
    reader = None
    changed = 0
    omitted = 0
    repaired_indices = []
    try:
        source = CRS.from_wkt(parts['.prj'].decode('utf-8-sig').strip())
        forward = Transformer.from_crs(source, CRS.from_epsg(4326), always_xy=True)
        inverse = Transformer.from_crs(CRS.from_epsg(4326), source, always_xy=True)
        reader = shapefile.Reader(shp=io.BytesIO(parts['.shp']), shx=io.BytesIO(parts['.shx']),
                                  dbf=io.BytesIO(parts['.dbf']))
        # PyShp 2.3 pairs shape/DBF iterators; deleted DBF records may otherwise
        # misalign attributes. Don't repair such files without explicit cleanup.
        dbf = parts['.dbf']
        header_size = int.from_bytes(dbf[8:10], 'little')
        record_size = int.from_bytes(dbf[10:12], 'little')
        if reader.numShapes != reader.numRecords or record_size < 1 or header_size + record_size * reader.numRecords > len(dbf):
            raise ImportValidationError('Shapefile geometry and attribute record counts do not match.')
        if any(dbf[header_size + i * record_size] != 32 for i in range(reader.numRecords)):
            raise ImportValidationError('Shapefile has deleted or malformed DBF records; re-export before geometry repair.')
        shape_type = reader.shapeType
        shp, shx = io.BytesIO(), io.BytesIO()
        with shapefile.Writer(shp=shp, shx=shx, shapeType=shape_type) as writer:
            for index, raw in enumerate(reader.iterShapes(), 1):
                try:
                    original = shape(raw.__geo_interface__)
                    if original.is_empty:
                        raise ValueError('empty geometry; no feature will be silently removed')
                    family = SUPPORTED_GEOMETRY.get(original.geom_type)
                    if family is None:
                        raise ValueError('unsupported source geometry type')
                    projected = transform(forward.transform, original)
                    if not all(math.isfinite(v) for v in projected.bounds):
                        raise ValueError('non-finite coordinates after CRS transformation')
                    if original.is_valid and projected.is_valid:
                        writer.shape(raw)
                        continue
                    if shape_type not in (shapefile.POINT, shapefile.MULTIPOINT, shapefile.POLYLINE, shapefile.POLYGON):
                        raise ValueError('invalid Z/M or unsupported geometry; re-export as a valid 2D dataset to avoid losing elevation or measure values')
                    fixed = original
                    removed = 0
                    if not fixed.is_valid:
                        fixed, removed = _same_family(make_valid(fixed), family)
                    projected = transform(forward.transform, fixed)
                    if not projected.is_valid:
                        adjusted, extra = _same_family(make_valid(projected), family)
                        fixed = transform(inverse.transform, adjusted)
                        removed += extra
                    if (fixed.is_empty or not fixed.is_valid or
                            not transform(forward.transform, fixed).is_valid):
                        raise ValueError('geometry remains invalid after repair and CRS transformation')
                    # Keep the shape record's type, including single-member MultiPoint.
                    if shape_type == shapefile.MULTIPOINT and fixed.geom_type == 'Point':
                        fixed = MultiPoint([fixed])
                    writer.shape(mapping(fixed))
                    changed += 1
                    omitted += removed
                    if len(repaired_indices) < 20:
                        repaired_indices.append(index)
                except Exception as exc:
                    raise ImportValidationError(f'Feature {index}: {exc}') from exc
        if not changed:
            raise ImportValidationError('Geometry validation failed but no safely repairable geometry was found.')
        parts['.shp'], parts['.shx'] = shp.getvalue(), shx.getvalue()
        rebuilt = io.BytesIO()
        with zipfile.ZipFile(rebuilt, 'w', zipfile.ZIP_DEFLATED) as archive:
            for suffix in ('.shp', '.shx', '.dbf', '.prj', '.cpg'):
                if suffix in parts:
                    archive.writestr('repaired' + suffix, parts[suffix])
        result = rebuilt.getvalue()
        # Re-read the actual publication payload strictly; never publish if any
        # repaired record is still invalid or the feature count changed.
        parsed = parse_shapefile(result, repair=False)
        if len(parsed.features) != reader.numRecords:
            raise ImportValidationError('Geometry repair changed the feature count; publication stopped.')
        report = {'repaired_features': changed, 'feature_indices_sample': repaired_indices,
                  'discarded_lower_dimension_parts': omitted}
        logger.warning('Shapefile geometry repair: %s', report)
        return result, parsed, report
    except ImportValidationError:
        raise
    except Exception as exc:
        raise ImportValidationError(f'Automatic geometry repair failed: {exc}') from exc
    finally:
        if reader is not None:
            reader.close()


def read_vector(upload):
    if upload.size > MAX_ZIP_SIZE or not upload.name.lower().endswith('.zip'):
        raise ImportValidationError('Choose a shapefile ZIP up to 40 MB.')
    data = upload.read(MAX_ZIP_SIZE + 1)
    report = {'repaired_features': 0, 'feature_indices_sample': [],
              'discarded_lower_dimension_parts': 0}
    try:
        # Valid files are published unchanged. The strict pass also checks CRS,
        # required parts, limits and geometry family before any repair is tried.
        parsed = parse_shapefile(data, repair=False)
    except ImportValidationError as exc:
        if 'invalid geometry; repair the source shapefile before publishing' not in str(exc):
            raise
        data, parsed, report = _repair_vector_archive(data)
    meta = {'geometry_type': parsed.geometry_type, 'source_crs': parsed.source_crs,
            'field_names': parsed.fields, 'field_schema': parsed.field_schema,
            'bbox': parsed.bbox, 'feature_count': len(parsed.features),
            'geometry_repair': report}
    return data, parsed, meta


def preview(upload):
    if upload is None:
        raise ImportValidationError('Choose a shapefile ZIP or GeoTIFF.')
    if upload.name.lower().endswith('.zip'):
        _, parsed, meta = read_vector(upload)
        meta['sample_attributes'] = parsed.sample
        # Return the complete dataset whenever it fits the preview budget.
        # Keep geometry and attributes intact; never truncate the published file.
        features = []
        remaining = MAX_PREVIEW_BYTES - 64  # reserve FeatureCollection wrapper
        for geometry, props in parsed.features:
            f = {'type': 'Feature', 'geometry': geometry, 'properties': props}
            try:
                # ASCII escaping + default spacing gives a conservative JSON size.
                size = len(json.dumps(f, allow_nan=False, ensure_ascii=True)) + 2
            except ValueError as exc:
                raise ImportValidationError('Non-finite attribute value in shapefile.') from exc
            if size <= remaining:
                remaining -= size
                features.append(f)
        meta['preview_geojson'] = {'type': 'FeatureCollection', 'features': features}
        meta['preview_feature_count'] = len(features)
        meta['preview_truncated'] = len(features) != len(parsed.features)
        meta['preview_limit_bytes'] = MAX_PREVIEW_BYTES
        return meta
    with tempfile.TemporaryDirectory(prefix='gis_lab_') as directory:
        path = Path(directory) / 'source.tif'
        save_upload(upload, path)
        return inspect_raster(path)


def ensure_compatible(layer, meta):
    if layer.geometry_type != meta['geometry_type']:
        raise ImportValidationError('Replacement geometry type must match the existing layer.')
    required = set(layer.attribute_fields) | set(layer.popup_fields)
    if layer.label_field:
        required.add(layer.label_field)
    missing = required - set(meta['field_names'])
    if missing:
        raise ImportValidationError('Replacement is missing configured fields: ' + ', '.join(sorted(missing)) + '. Adjust layer settings first.')


def snapshot(layer):
    return {k: getattr(layer, k) for k in DATA_FIELDS}


def apply_metadata(layer, meta, filename):
    for k in DATA_FIELDS:
        if k in meta:
            setattr(layer, k, meta[k])
    layer.source_filename = filename[:255]


def verify(gs, publication, meta):
    if publication['kind'] == 'wfs':
        data = gs.features(publication, count=1)
        if not data['features']:
            raise PublishError('Published WFS layer contains no features.')
        fields = data['features'][0].get('properties') or {}
        missing = set(meta['field_names']) - set(fields)
        if missing:
            raise PublishError('GeoServer WFS did not preserve source fields: ' + ', '.join(sorted(missing)))
        total = data.get('numberMatched', data.get('totalFeatures'))
        if str(total).isdigit() and int(total) != meta['feature_count']:
            raise PublishError('Published WFS feature count does not match the upload.')
        a,b,c,d = meta['bbox']
        expanded = [max(-180,a-1e-5),max(-90,b-1e-5),min(180,c+1e-5),min(90,d+1e-5)]
        if not gs.features(publication, bbox=expanded, count=1)['features']:
            raise PublishError('WFS extent verification failed. Check CRS and axis order.')
    else:
        gs.image(publication, meta['bbox'], crs='EPSG:4326', size=128)


def publish_upload(layer, upload, configure=None, replace=False):
    if upload is None:
        raise ImportValidationError('Choose a dataset file.')
    if layer.group.strip().lower() == 'cadastral':
        raise ImportValidationError('Cadastral publishing requires explicit relationship management. This file-based path does not support it.')
    gs = GeoServer()
    publication = None
    previous = snapshot(layer) if replace else None
    try:
        with tempfile.TemporaryDirectory(prefix='gis_lab_') as directory:
            if upload.name.lower().endswith('.zip'):
                data, _, meta = read_vector(upload)
                kind = 'wfs'
            else:
                source, output = Path(directory) / 'source.tif', Path(directory) / 'optimized.tif'
                save_upload(upload, source)
                meta = inspect_raster(source)
                kind = 'wms'
                if replace:
                    ensure_compatible(layer, meta)
                optimize(source, output)
                data = output
            if replace:
                ensure_compatible(layer, meta)
            apply_metadata(layer, meta, upload.name)
            if not replace:
                layer.attribute_fields = list(layer.field_names)
                layer.popup_fields = list(layer.field_names)
                layer.label_field = layer.field_names[0] if layer.field_names else ''
                if kind == 'wms':
                    layer.show_attributes = layer.show_popup = layer.show_labels = False
                if configure:
                    configure(layer)
                if kind == 'wms' and (layer.show_attributes or layer.show_labels or layer.show_popup):
                    raise ImportValidationError('Raster layers do not support vector labels or attributes.')
            safe_layer_name = re.sub(
                r'[^A-Za-z0-9_]+',
                '_',
                layer.name.strip()
            ).strip('_')

            if not safe_layer_name or not safe_layer_name[0].isalpha():
                safe_layer_name = 'layer_' + safe_layer_name

            safe_layer_name = safe_layer_name[:60]

            publication = gs.publish(
                kind,
                data,
                layer_name=safe_layer_name,
                title=layer.name,
            )
            if kind == 'wms':
                publication['raster'] = meta['raster']
            elif meta['geometry_repair']['repaired_features']:
                publication['geometry_repair'] = meta['geometry_repair']
            verify(gs, publication, meta)
            layer.publication = publication
            if replace:
                layer.publication_history = [*layer.publication_history, previous]
                layer.version += 1
            layer.save()
        return layer
    except Exception:
        if publication:
            gs.discard(publication)
        raise


def rollback(layer):
    if not layer.publication_history:
        raise ImportValidationError('No previous published version is available.')
    previous = layer.publication_history[-1]
    ensure_compatible(layer, previous)
    verify(GeoServer(), previous['publication'], previous)
    # Keep the current version archived too, so rollback can be reversed.
    current = snapshot(layer)
    apply_metadata(layer, previous, previous['source_filename'])
    layer.publication_history = [*layer.publication_history[:-1], current]
    layer.version += 1
    layer.save()
    return layer
