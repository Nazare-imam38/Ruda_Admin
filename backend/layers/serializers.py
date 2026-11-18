from rest_framework import serializers
from .models import Layer

class LayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Layer
        fields = [
            'id', 'name', 'group', 'project_id', 'geometry_type', 'source_crs',
            'source_filename', 'field_names', 'field_schema', 'bbox', 'feature_count',
            'table_name', 'column_map', 'show_attributes', 'attribute_fields', 'popup_fields',
            'style', 'label_field', 'show_labels', 'show_popup', 'is_visible',
            'label_min_zoom', 'label_size', 'version', 'publication', 'created_at', 'updated_at',
        ]
        read_only_fields = fields
