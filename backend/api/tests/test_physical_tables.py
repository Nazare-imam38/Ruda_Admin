from django.test import SimpleTestCase
from api.physical_tables import (
    normalize_identifier, column_map_for_schema, column_type, adapt_value,
)


class DedicatedPostGISTableTests(SimpleTestCase):
    def test_projects_name_creates_lowercase_sql_table_name(self):
        self.assertEqual(normalize_identifier('Projects'), 'projects')
        self.assertEqual(normalize_identifier('Sewerage Lines / Phase 1'), 'sewerage_lines_phase_1')

    def test_reserved_and_repeated_attributes_have_safe_column_names(self):
        mapping = column_map_for_schema([
            {'name': 'Name'}, {'name': 'name!'}, {'name': 'geom'}, {'name': 'Brief_Name'},
        ])
        self.assertEqual(mapping['Name'], 'name')
        self.assertEqual(mapping['name!'], 'name_2')
        self.assertEqual(mapping['geom'], 'attr_geom')
        self.assertEqual(mapping['Brief_Name'], 'brief_name')

    def test_attribute_columns_preserve_numeric_types(self):
        self.assertEqual(column_type({'name': 'zz', 'type': 'N', 'width': 12, 'decimals': 2}), 'DOUBLE PRECISION')
        self.assertEqual(column_type({'name': 'objectid', 'type': 'N', 'width': 9, 'decimals': 0}), 'BIGINT')
        self.assertEqual(column_type({'name': 'name', 'type': 'C', 'width': 50, 'decimals': 0}), 'TEXT')
        self.assertEqual(adapt_value('2026-11-10', 'DATE').isoformat(), '2026-11-10')
