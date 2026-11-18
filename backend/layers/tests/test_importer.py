import io
import zipfile
from pathlib import Path
from django.test import SimpleTestCase
from layers.importer import ImportValidationError, parse_shapefile

DATA = Path(__file__).resolve().parents[3] / 'sample_data'


class ShapefileImportTests(SimpleTestCase):
    def test_point_attributes_and_elevation(self):
        parsed = parse_shapefile((DATA / '01_Spot_Level_Points.zip').read_bytes())
        self.assertEqual(parsed.geometry_type, 'Point')
        self.assertEqual(len(parsed.features), 8)
        self.assertEqual(parsed.features[0][1]['zz'], 212.45)
        self.assertIn('zz', parsed.fields)

    def test_line_geometry(self):
        parsed = parse_shapefile((DATA / '02_Water_Lines.zip').read_bytes())
        self.assertEqual(parsed.geometry_type, 'Line')
        self.assertEqual(len(parsed.features), 3)
        self.assertEqual(parsed.features[0][1]['dia_mm'], 350)

    def test_polygon_geometry_and_bounds(self):
        parsed = parse_shapefile((DATA / '03_Mauza_Polygons.zip').read_bytes())
        self.assertEqual(parsed.geometry_type, 'Polygon')
        self.assertEqual(len(parsed.features), 4)
        self.assertTrue(74 < parsed.bbox[0] < 75)
        self.assertEqual(parsed.features[0][1]['mauza_name'], 'Demo Mauza A')

    def test_zip_without_prj_is_rejected(self):
        original = DATA / '01_Spot_Level_Points.zip'
        output = io.BytesIO()
        with zipfile.ZipFile(original) as src, zipfile.ZipFile(output, 'w') as dst:
            for file in src.namelist():
                if not file.endswith('.prj'):
                    dst.writestr(file, src.read(file))
        with self.assertRaisesRegex(ImportValidationError, 'Missing required'):
            parse_shapefile(output.getvalue())
