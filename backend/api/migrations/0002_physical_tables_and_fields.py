"""Backfill already uploaded layers into standalone PostGIS tables.

When applied after 0001, this also converts an already-uploaded Projects layer.
It is intentionally limited to the isolated GIS Automation Lab database.
"""
from types import SimpleNamespace
from django.db import migrations, models


def backfill_existing_layers(apps, schema_editor):
    from api.physical_tables import make_table_for_layer
    Layer = apps.get_model('layers', 'Layer')
    conn = schema_editor.connection
    for layer in Layer.objects.using(conn.alias).all().iterator():
        with conn.cursor() as cursor:
            cursor.execute(
                'SELECT ST_AsGeoJSON(geometry), properties FROM layers_feature '
                'WHERE layer_id = %s ORDER BY source_index', [str(layer.pk)]
            )
            records = cursor.fetchall()
        import json
        entries = [(json.loads(geom), props if isinstance(props, dict) else json.loads(props))
                   for geom, props in records]
        if not entries:
            # No geometry to migrate; future replacement is still supported.
            continue
        parsed = SimpleNamespace(field_schema=layer.field_schema, features=entries)
        table_name, column_map = make_table_for_layer(layer, parsed)
        layer.table_name = table_name
        layer.column_map = column_map
        layer.attribute_fields = list(layer.field_names)
        layer.popup_fields = list(layer.field_names)
        layer.show_attributes = True
        layer.save(update_fields=['table_name', 'column_map', 'attribute_fields',
                                  'popup_fields', 'show_attributes'])


class Migration(migrations.Migration):
    dependencies = [('layers', '0001_initial')]
    operations = [
        migrations.AddField(
            model_name='layer', name='table_name',
            field=models.CharField(blank=True, default=None, max_length=63, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='layer', name='column_map', field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name='layer', name='show_attributes', field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='layer', name='attribute_fields', field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name='layer', name='popup_fields', field=models.JSONField(default=list),
        ),
        migrations.RunPython(backfill_existing_layers, migrations.RunPython.noop),
    ]
