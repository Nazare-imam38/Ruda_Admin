"""Offline parser smoke-test for the bundled synthetic shapefiles."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'backend'))
from layers.importer import parse_shapefile  # noqa: E402

EXPECTED = [
    ('01_Spot_Level_Points.zip', 'Point', 'zz'),
    ('02_Water_Lines.zip', 'Line', 'dia_mm'),
    ('03_Mauza_Polygons.zip', 'Polygon', 'mauza_name'),
]

for name, geometry_type, field in EXPECTED:
    parsed = parse_shapefile((ROOT / 'sample_data' / name).read_bytes())
    assert parsed.geometry_type == geometry_type, name
    assert field in parsed.fields, name
    assert len(parsed.features) > 0, name
    print(f'PASS {name}: {parsed.geometry_type}, {len(parsed.features)} features, {field}')
print('All three sample shapefiles can be parsed without a Docker container.')
