"""Create and query dedicated PostGIS tables for each uploaded shapefile.

This test-lab module does *not* create new Django models or API routes. Layer
metadata remains in layers_layer; each dataset gets a real spatial table under
public, with typed attribute columns and a GiST-indexed geometry column.

Only names saved in our managed Layer registry may be dropped/replaced. Dynamic
SQL identifiers are normalized and quoted; feature values are bound parameters.
"""
import json
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal

from django.db import connection

IDENTIFIER = re.compile(r'^[a-z_][a-z0-9_]{0,62}$')
SYSTEM_COLS = {'gid', 'geom', 'geometry', 'source_index'}


def normalize_identifier(value, fallback='field', limit=54):
    ascii_name = unicodedata.normalize('NFKD', str(value)).encode('ascii', 'ignore').decode('ascii')
    name = re.sub(r'[^a-z0-9_]+', '_', ascii_name.lower()).strip('_')[:limit]
    if not name:
        name = fallback
    if name[0].isdigit() or name.startswith('pg_'):
        name = 'f_' + name
    return name[:limit]


def quote(identifier):
    if not IDENTIFIER.fullmatch(identifier):
        raise ValueError('Invalid managed PostGIS identifier')
    return connection.ops.quote_name(identifier)


def full_table(table_name):
    return 'public.' + quote(table_name)


def table_exists(cursor, table_name):
    cursor.execute('SELECT to_regclass(%s)', [f'public.{table_name}'])
    return cursor.fetchone()[0] is not None


def choose_table_name(cursor, display_name):
    base = normalize_identifier(display_name, fallback='uploaded_layer', limit=49)
    if base in ('layers', 'django_migrations'):
        base += '_data'
    candidate = base
    count = 2
    while table_exists(cursor, candidate):
        candidate = f'{base}_{count}'
        count += 1
    return candidate


def column_map_for_schema(field_schema):
    result = {}
    reserved = set(SYSTEM_COLS)
    for field in field_schema:
        original = field['name']
        base = normalize_identifier(original)
        if base in SYSTEM_COLS:
            base = ('attr_' + base)[:54]
        candidate = base
        suffix = 2
        while candidate in reserved:
            candidate = f'{base[:48]}_{suffix}'
            suffix += 1
        reserved.add(candidate)
        result[original] = candidate
    return result


def column_type(field):
    kind = str(field.get('type', 'C')).upper()
    decimals = int(field.get('decimals', 0))
    width = int(field.get('width', 0))
    if kind == 'D':
        return 'DATE'
    if kind == 'L':
        return 'BOOLEAN'
    if kind == 'F' or (kind == 'N' and decimals > 0):
        return 'DOUBLE PRECISION'
    if kind == 'N' and width and width <= 18:
        return 'BIGINT'
    if kind == 'N':
        return 'NUMERIC'
    return 'TEXT'


def write_table(cursor, table_name, field_schema, field_map):
    name = full_table(table_name)
    if table_exists(cursor, table_name):
        raise ValueError(f'Table public.{table_name} already exists; never overwrite an unrelated table.')
    columns = [
        'gid BIGSERIAL PRIMARY KEY',
        'source_index INTEGER NOT NULL UNIQUE',
        'geom geometry(Geometry,4326) NOT NULL',
    ]
    columns += [f'{quote(field_map[f["name"]])} {column_type(f)}' for f in field_schema]
    cursor.execute(f'CREATE TABLE {name} ({", ".join(columns)})')
    index_name = table_name[:50] + '_geom_gix'
    cursor.execute(f'CREATE INDEX {quote(index_name)} ON {name} USING GIST (geom)')


def adapt_value(value, sql_type):
    if value is None or value == '':
        return None
    if sql_type == 'DATE':
        if isinstance(value, (date, datetime)):
            return value.date() if isinstance(value, datetime) else value
        return date.fromisoformat(str(value))
    if sql_type == 'BOOLEAN':
        if isinstance(value, str):
            return value.strip().lower() in ('true', 't', 'yes', 'y', '1')
        return bool(value)
    if sql_type == 'BIGINT':
        return int(value)
    if sql_type == 'NUMERIC':
        return Decimal(str(value))
    if sql_type == 'DOUBLE PRECISION':
        return float(value)
    return str(value)


def insert_features(cursor, table_name, field_schema, field_map, features):
    """features: iterable of (geojson geometry, attribute dict); 0-based index."""
    cols = ['source_index', 'geom'] + [field_map[f['name']] for f in field_schema]
    fields_sql = ', '.join(quote(col) for col in cols)
    placeholders = ['%s', 'ST_SetSRID(ST_GeomFromGeoJSON(%s),4326)']
    for f in field_schema:
        dtype = column_type(f)
        placeholders.append(f'%s::{dtype}')
    statement = f'INSERT INTO {full_table(table_name)} ({fields_sql}) VALUES ({", ".join(placeholders)})'
    for start in range(0, len(features), 350):
        batch = []
        for index in range(start, min(start + 350, len(features))):
            geometry, props = features[index]
            params = [index, json.dumps(geometry, allow_nan=False)]
            for f in field_schema:
                field_name = f['name']
                try:
                    params.append(adapt_value(props.get(field_name), column_type(f)))
                except (TypeError, ValueError, OverflowError) as exc:
                    raise ValueError(f'Feature {index+1}, field {field_name}: invalid {column_type(f)} value') from exc
            batch.append(params)
        cursor.executemany(statement, batch)


def make_table_for_layer(layer, parsed, replace=False):
    """Call inside transaction.atomic(). Replace drops only this layer's registered table."""
    with connection.cursor() as cursor:
        if replace:
            if not layer.table_name:
                raise ValueError('Layer has no managed spatial table; run migrations first.')
            cursor.execute(f'DROP TABLE {full_table(layer.table_name)}')
            table_name = layer.table_name
        else:
            table_name = choose_table_name(cursor, layer.name)
        mapping = column_map_for_schema(parsed.field_schema)
        write_table(cursor, table_name, parsed.field_schema, mapping)
        insert_features(cursor, table_name, parsed.field_schema, mapping, parsed.features)
    return table_name, mapping


def drop_layer_table(layer):
    if not layer.table_name:
        return
    with connection.cursor() as cursor:
        # No CASCADE: foreign/unrelated tables can never be removed by a layer delete.
        cursor.execute(f'DROP TABLE IF EXISTS {full_table(layer.table_name)}')


def get_geojson_rows(layer, bbox, limit):
    params = []
    where = ''
    if bbox:
        where = ' WHERE geom && ST_MakeEnvelope(%s,%s,%s,%s,4326)'
        params.extend(bbox)
    cols = ', '.join(quote(layer.column_map[f]) for f in layer.field_names)
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT COUNT(*) FROM {full_table(layer.table_name)}{where}', params)
        total = cursor.fetchone()[0]
        cursor.execute(
            f'SELECT gid, ST_AsGeoJSON(geom), {cols} FROM {full_table(layer.table_name)}'
            + where + ' ORDER BY source_index LIMIT %s', params + [limit],
        )
        rows = cursor.fetchall()
    features = [
        {'type': 'Feature', 'id': row[0], 'geometry': json.loads(row[1]),
         'properties': {field: row[i+2] if not isinstance(row[i+2], (date, datetime))
                        else row[i+2].isoformat() for i, field in enumerate(layer.field_names)}}
        for row in rows
    ]
    return total, features


def get_attribute_rows(layer, fields, start, page_size):
    with connection.cursor() as cursor:
        if fields:
            cols = ', '.join(quote(layer.column_map[f]) for f in fields)
            cursor.execute(
                f'SELECT gid, {cols} FROM {full_table(layer.table_name)} '
                'ORDER BY source_index LIMIT %s OFFSET %s', [page_size, start],
            )
        else:
            cursor.execute(
                f'SELECT gid FROM {full_table(layer.table_name)} '
                'ORDER BY source_index LIMIT %s OFFSET %s', [page_size, start],
            )
        rows = cursor.fetchall()
    return [
        {'id': row[0], **{field: (row[i+1].isoformat() if isinstance(row[i+1], (date, datetime))
                          else row[i+1]) for i, field in enumerate(fields)}}
        for row in rows
    ]
