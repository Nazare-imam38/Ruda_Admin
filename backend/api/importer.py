"""One reusable shapefile parser, independent of any specific layer name or schema.

WARNING: for a private, local training lab. Large production imports should run
in a job queue with background workers, quotas and stronger operational controls.
"""
import io
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import PurePosixPath

import shapefile
from pyproj import CRS, Transformer
from shapely import force_2d, make_valid
from shapely.geometry import mapping, shape
from shapely.ops import transform

MAX_ZIP_SIZE = 40 * 1024 * 1024
MAX_UNCOMPRESSED_SIZE = 200 * 1024 * 1024
MAX_FILES = 40
MAX_FEATURES = 50000
SUPPORTED_GEOMETRY = {
    'Point': 'Point', 'MultiPoint': 'Point',
    'LineString': 'Line', 'MultiLineString': 'Line',
    'Polygon': 'Polygon', 'MultiPolygon': 'Polygon',
}


class ImportValidationError(ValueError):
    pass


@dataclass
class ParsedShapefile:
    geometry_type: str
    source_crs: str
    fields: list
    field_schema: list
    features: list  # tuples: (GeoJSON-compatible geometry, original attribute dict)
    bbox: list
    sample: list


def safe_json_value(value):
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    if isinstance(value, (tuple, list)):
        return [safe_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): safe_json_value(item) for key, item in value.items()}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def get_archive_files(content):
    if not content or len(content) > MAX_ZIP_SIZE:
        raise ImportValidationError('ZIP must be nonempty and at most 40 MB.')
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except (zipfile.BadZipFile, OSError) as exc:
        raise ImportValidationError('Upload a valid .zip archive containing shapefile components.') from exc
    with archive:
        infos = [item for item in archive.infolist() if not item.is_dir()]
        if len(infos) > MAX_FILES:
            raise ImportValidationError('ZIP contains too many files (maximum 40).')
        total_size = 0
        for info in infos:
            path = PurePosixPath(info.filename.replace('\\', '/'))
            if path.is_absolute() or '..' in path.parts or ':' in info.filename:
                raise ImportValidationError('Unsafe path inside ZIP archive.')
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ImportValidationError('ZIP symbolic links are not supported.')
            total_size += info.file_size
            if total_size > MAX_UNCOMPRESSED_SIZE:
                raise ImportValidationError('ZIP expands beyond the 200 MB training limit.')
        shp_files = [i for i in infos if i.filename.lower().endswith('.shp')]
        if len(shp_files) != 1:
            raise ImportValidationError('ZIP must contain exactly one .shp file (with matching .shx, .dbf and .prj).')
        shp_path = PurePosixPath(shp_files[0].filename.replace('\\', '/'))
        stem = str(shp_path.with_suffix('')).lower()
        matching = {}
        for info in infos:
            p = PurePosixPath(info.filename.replace('\\', '/'))
            if str(p.with_suffix('')).lower() == stem:
                ext = p.suffix.lower()
                if ext in matching:
                    raise ImportValidationError('Duplicate shapefile component: ' + ext)
                matching[ext] = info
        missing = [ext for ext in ('.shp', '.shx', '.dbf', '.prj') if ext not in matching]
        if missing:
            raise ImportValidationError('Missing required shapefile part(s): ' + ', '.join(missing))
        try:
            return {ext: archive.read(info) for ext, info in matching.items()}
        except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
            raise ImportValidationError('Cannot read archive content safely.') from exc


def parse_shapefile(content, repair=True):
    parts = get_archive_files(content)
    try:
        prj = parts['.prj'].decode('utf-8-sig', errors='replace').strip()
        if not prj:
            raise ValueError('empty .prj')
        source_crs = CRS.from_wkt(prj)
        transformer = Transformer.from_crs(source_crs, CRS.from_epsg(4326), always_xy=True)
    except Exception as exc:
        raise ImportValidationError('Cannot identify CRS from .prj. Re-export with a valid projection file.') from exc

    encoding = 'utf-8'
    if '.cpg' in parts:
        encoding = parts['.cpg'].decode('ascii', errors='ignore').strip() or 'utf-8'
        if re.fullmatch(r'\d{3,5}', encoding):
            encoding = 'cp' + encoding

    try:
        reader = shapefile.Reader(
            shp=io.BytesIO(parts['.shp']),
            shx=io.BytesIO(parts['.shx']),
            dbf=io.BytesIO(parts['.dbf']),
            encoding=encoding,
            encodingErrors='replace',
        )
        fields_meta = reader.fields[1:]
        fields = [str(f[0]) for f in fields_meta]
        if len(reader) > MAX_FEATURES:
            raise ImportValidationError(f'Shapefile contains more than {MAX_FEATURES:,} features, above the lab limit.')
        if not fields:
            raise ImportValidationError('Shapefile must contain an attribute table with at least one column.')
        if len(set(fields)) != len(fields):
            raise ImportValidationError('Shapefile has duplicate field names.')
        schema = [
            {'name': str(f[0]), 'type': str(f[1]), 'width': int(f[2]), 'decimals': int(f[3])}
            for f in fields_meta
        ]
        parsed_features = []
        bounds = None
        kind = None
        sample = []
        for index, item in enumerate(reader.iterShapeRecords(), 1):
            try:
                raw_geometry = item.shape.__geo_interface__
                if not raw_geometry or raw_geometry.get('type') == 'Null':
                    raise ValueError('empty or null geometry')
                geom = shape(raw_geometry)
                geom = transform(transformer.transform, geom)
                geom = force_2d(geom)
                if not geom.is_valid:
                    if not repair:
                        raise ValueError("invalid geometry; repair the source shapefile before publishing")
                    geom = make_valid(geom)
                if geom.is_empty or not geom.is_valid:
                    raise ValueError('cannot repair geometry')
                geo_family = SUPPORTED_GEOMETRY.get(geom.geom_type)
                if geo_family is None:
                    raise ValueError(f'unsupported geometry type {geom.geom_type}')
                if kind is None:
                    kind = geo_family
                if geo_family != kind:
                    raise ValueError('mixed point/line/polygon geometries in one file')
                extent = geom.bounds
                if not all(map(lambda v: v == v and abs(v) != float('inf'), extent)):
                    raise ValueError('non-finite geometry coordinates')
                if extent[0] < -180 or extent[2] > 180 or extent[1] < -90 or extent[3] > 90:
                    raise ValueError('coordinates outside longitude/latitude range after CRS transformation')
                bounds = list(extent) if bounds is None else [
                    min(bounds[0], extent[0]), min(bounds[1], extent[1]),
                    max(bounds[2], extent[2]), max(bounds[3], extent[3])
                ]
                props = {k: safe_json_value(v) for k, v in item.record.as_dict().items()}
                geojson_geom = mapping(geom)
                parsed_features.append((geojson_geom, props))
                if len(sample) < 3:
                    sample.append(props)
            except Exception as exc:
                raise ImportValidationError(f'Feature {index}: {exc}') from exc
        if not parsed_features:
            raise ImportValidationError('No non-empty geometries were found.')
        return ParsedShapefile(
            geometry_type=kind,
            source_crs=source_crs.to_string(),
            fields=fields,
            field_schema=schema,
            features=parsed_features,
            bbox=bounds,
            sample=sample,
        )
    except (shapefile.ShapefileException, UnicodeError, ValueError) as exc:
        if isinstance(exc, ImportValidationError):
            raise
        raise ImportValidationError('Shapefile data is unreadable: ' + str(exc)) from exc
    finally:
        if 'reader' in locals():
            reader.close()


def import_into_layer(parsed, layer, replace=False):
    """Write a dedicated physical PostGIS table for every layer, atomically.

    Existing shared-table imports are converted by migration 0002; new uploads
    never write to layers_feature. The layer UUID remains the generic API key.
    """
    from .physical_tables import make_table_for_layer

    table_name, column_map = make_table_for_layer(layer, parsed, replace=replace)
    if replace:
        layer.version += 1
    layer.table_name = table_name
    layer.column_map = column_map
    layer.geometry_type = parsed.geometry_type
    layer.source_crs = parsed.source_crs
    layer.field_names = parsed.fields
    layer.field_schema = parsed.field_schema
    layer.feature_count = len(parsed.features)
    layer.bbox = parsed.bbox
    if layer.label_field not in parsed.fields:
        layer.label_field = parsed.fields[0]
    if replace:
        layer.attribute_fields = [field for field in layer.attribute_fields if field in parsed.fields]
        layer.popup_fields = [field for field in layer.popup_fields if field in parsed.fields]
    else:
        layer.attribute_fields = list(parsed.fields)
        layer.popup_fields = list(parsed.fields)
    layer.save()
    return layer
