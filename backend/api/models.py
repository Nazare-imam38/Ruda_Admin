import uuid
from django.db import models


def default_style():
    return {'color': '#2563eb', 'fill_opacity': 0.30, 'line_width': 3, 'point_radius': 6}


class Layer(models.Model):
    """A generic dataset definition, independent of any shapefile's field schema."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    group = models.CharField(max_length=80, default='Uploaded Layers')
    project_id = models.IntegerField(null=True, blank=True, db_index=True)
    geometry_type = models.CharField(max_length=16)  # Point / Line / Polygon family
    source_crs = models.CharField(max_length=160)
    source_filename = models.CharField(max_length=255)
    field_names = models.JSONField(default=list)
    field_schema = models.JSONField(default=list)
    bbox = models.JSONField(null=True, blank=True)
    feature_count = models.PositiveIntegerField(default=0)
    table_name = models.CharField(max_length=63, blank=True, null=True, unique=True, default=None)
    column_map = models.JSONField(default=dict)
    show_attributes = models.BooleanField(default=True)
    attribute_fields = models.JSONField(default=list)
    popup_fields = models.JSONField(default=list)
    style = models.JSONField(default=default_style)
    label_field = models.CharField(max_length=128, blank=True, default='')
    show_labels = models.BooleanField(default=False)
    show_popup = models.BooleanField(default=True)
    is_visible = models.BooleanField(default=False)
    label_min_zoom = models.PositiveSmallIntegerField(default=10)
    label_size = models.PositiveSmallIntegerField(default=12)
    publication = models.JSONField(default=dict, blank=True)
    relationship = models.JSONField(default=dict, blank=True)
    publication_history = models.JSONField(default=list, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Feature(models.Model):
    """Store all imported feature geometries + original shapefile attributes."""
    layer = models.ForeignKey(Layer, related_name='features', on_delete=models.CASCADE)
    source_index = models.PositiveIntegerField()
    # PostGIS geometry column created by migration RunSQL.
    # Left out of the Django ORM so Windows needs no native GeoDjango/GDAL binaries.
    properties = models.JSONField(default=dict)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['layer', 'source_index'], name='unique_layer_source_index')]
        indexes = [models.Index(fields=['layer', 'source_index'])]
