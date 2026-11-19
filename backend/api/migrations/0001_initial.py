# Initial schema for the standalone GIS Automation Lab.
import uuid
import django.db.models.deletion
from django.db import migrations, models
import api.models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name='Layer',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=120)),
                ('group', models.CharField(default='Uploaded Layers', max_length=80)),
                ('project_id', models.IntegerField(blank=True, db_index=True, null=True)),
                ('geometry_type', models.CharField(max_length=16)),
                ('source_crs', models.CharField(max_length=160)),
                ('source_filename', models.CharField(max_length=255)),
                ('field_names', models.JSONField(default=list)),
                ('field_schema', models.JSONField(default=list)),
                ('bbox', models.JSONField(blank=True, null=True)),
                ('feature_count', models.PositiveIntegerField(default=0)),
                ('style', models.JSONField(default=api.models.default_style)),
                ('label_field', models.CharField(blank=True, default='', max_length=128)),
                ('show_labels', models.BooleanField(default=False)),
                ('show_popup', models.BooleanField(default=True)),
                ('is_visible', models.BooleanField(default=True)),
                ('label_min_zoom', models.PositiveSmallIntegerField(default=10)),
                ('label_size', models.PositiveSmallIntegerField(default=12)),
                ('version', models.PositiveIntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='Feature',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_index', models.PositiveIntegerField()),
                ('properties', models.JSONField(default=dict)),
                ('layer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='features', to='layers.layer')),
            ],
        ),
        migrations.AddConstraint(
            model_name='feature',
            constraint=models.UniqueConstraint(fields=('layer', 'source_index'), name='unique_layer_source_index'),
        ),
        migrations.AddIndex(
            model_name='feature',
            index=models.Index(fields=['layer', 'source_index'], name='layers_feat_layer_i_76109d_idx'),
        ),
        # Real native PostGIS geometry is stored in PostgreSQL. Standard Django ORM
        # manages the attribute records, and parameterized SQL handles geometries.
        # This avoids GDAL/GeoDjango installation on Windows.
        migrations.RunSQL(
            sql=[
                ('ALTER TABLE layers_feature ADD COLUMN geometry geometry(Geometry,4326) NOT NULL', None),
                ('CREATE INDEX layers_feature_geometry_gix ON layers_feature USING GIST (geometry)', None),
            ],
            reverse_sql=[
                ('DROP INDEX IF EXISTS layers_feature_geometry_gix', None),
                ('ALTER TABLE layers_feature DROP COLUMN IF EXISTS geometry', None),
            ],
        ),
    ]
