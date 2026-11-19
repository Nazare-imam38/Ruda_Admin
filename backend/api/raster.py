"""GDAL command-line adapter; no native Python GDAL bindings needed on Windows."""
import json
import math
import os
import subprocess
from pathlib import Path
from pyproj import CRS, Transformer
from .importer import ImportValidationError

MAX_RASTER_BYTES = 250 * 1024 * 1024


def gdal(tool, *args):
    directory = os.environ.get('GDAL_BIN', '').strip()
    exe = str(Path(directory) / (tool + ('.exe' if os.name == 'nt' else ''))) if directory else tool
    try:
        result = subprocess.run([exe, *map(str, args)], capture_output=True, text=True, timeout=600, check=True)
        return result.stdout
    except FileNotFoundError as exc:
        raise ImportValidationError('GDAL is not available. Use an OSGeo4W/QGIS shell or configure GDAL_BIN.') from exc
    except subprocess.TimeoutExpired as exc:
        raise ImportValidationError('GDAL processing timed out (lab limit).') from exc
    except subprocess.CalledProcessError as exc:
        raise ImportValidationError(f'{tool} failed; check the input GeoTIFF and GDAL environment.') from exc


def save_upload(upload, path):
    if not upload.name.lower().endswith(('.tif', '.tiff')) or not 0 < upload.size <= MAX_RASTER_BYTES:
        raise ImportValidationError('Choose a GeoTIFF (.tif/.tiff), up to 250 MB in this lab.')
    with open(path, 'wb') as out:
        for chunk in upload.chunks():
            out.write(chunk)


def inspect_raster(path):
    try:
        with open(path, 'rb') as stream:
            if stream.read(4) not in (b'II*\x00', b'MM\x00*', b'II+\x00', b'MM\x00+'):
                raise ValueError('The file does not have a TIFF header.')
        info = json.loads(gdal('gdalinfo', '-if', 'GTiff', '-json', path))
        if info.get('driverShortName') != 'GTiff':
            raise ValueError('Only GeoTIFF is supported.')
        crs = CRS.from_wkt(info['coordinateSystem']['wkt'])
        gt = info['geoTransform']
        width, height = info['size']
        if width <= 0 or height <= 0 or width * height > 100_000_000:
            raise ValueError('Raster exceeds the 100-million-pixel lab limit.')
        t = Transformer.from_crs(crs, 4326, always_xy=True)
        coords = [t.transform(gt[0] + x*gt[1] + y*gt[2], gt[3] + x*gt[4] + y*gt[5]) for x,y in [(0,0),(width,0),(0,height),(width,height)]]
        bbox = [min(x for x,y in coords), min(y for x,y in coords), max(x for x,y in coords), max(y for x,y in coords)]
        if not all(math.isfinite(v) for v in bbox) or not (-180 <= bbox[0] < bbox[2] <= 180 and -90 <= bbox[1] < bbox[3] <= 90):
            raise ValueError('Invalid raster geographic extent.')
        return {'geometry_type': 'Raster', 'source_crs': crs.to_string()[:160], 'bbox': bbox,
                'field_names': [], 'field_schema': [], 'feature_count': 0,
                'raster': {'width': width, 'height': height, 'bands': len(info['bands']), 'pixel_size': [math.hypot(gt[1],gt[4]),math.hypot(gt[2],gt[5])], 'data_types': [b['type'] for b in info['bands']]}}
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ImportValidationError):
            raise
        raise ImportValidationError('GeoTIFF must have valid georeferencing and a CRS. ' + str(exc)) from exc


def optimize(source, output):
    # Lossless for the full resolution data; nearest overview works for categorical rasters too.
    gdal('gdal_translate', '-of', 'GTiff', '-co', 'TILED=YES', '-co', 'COMPRESS=DEFLATE', '-co', 'BIGTIFF=IF_SAFER', source, output)
    gdal('gdaladdo', '-r', 'nearest', output, 2, 4, 8, 16)
    if Path(output).stat().st_size > 500 * 1024 * 1024:
        raise ImportValidationError('Optimized raster exceeds 500 MB lab limit.')
