import json
import math
import re

from django.db import connection, transaction
from django.http import HttpResponse
from .geoserver import GeoServer, PublishError
from . import publishing
from django.shortcuts import get_object_or_404
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .importer import ImportValidationError, import_into_layer, parse_shapefile, MAX_ZIP_SIZE
from .models import Layer
from .physical_tables import drop_layer_table, get_geojson_rows, get_attribute_rows
from .serializers import LayerSerializer

MAX_MAP_FEATURES = 10000


def error(message, status=400):
    return Response({'error': str(message)}, status=status)


def read_zip(request):
    upload = request.FILES.get('file')
    if upload is None:
        raise ImportValidationError('Choose a ZIP shapefile in the file field.')
    if not upload.name.lower().endswith('.zip'):
        raise ImportValidationError('Only ZIP shapefiles are supported.')
    if upload.size > MAX_ZIP_SIZE:
        raise ImportValidationError('ZIP must be at most 40 MB.')
    return parse_shapefile(upload.read(MAX_ZIP_SIZE + 1))


def read_basic_metadata(request):
    name = str(request.data.get('name', '')).strip()
    group = str(request.data.get('group', 'Uploaded Layers')).strip() or 'Uploaded Layers'
    project = request.data.get('project_id')
    if not (1 <= len(name) <= 120):
        raise ImportValidationError('Layer name is required (1-120 characters).')
    if len(group) > 80:
        raise ImportValidationError('Group must be 80 characters or fewer.')
    if project is None or str(project).strip() == '':
        project = None
    else:
        try:
            project = int(project)
        except (ValueError, TypeError):
            raise ImportValidationError('Project ID must be an integer.')
        if project < 1:
            raise ImportValidationError('Project ID must be positive.')
    return name, group, project


def apply_settings(layer, data):
    editable = {'name', 'group', 'project_id', 'is_visible', 'show_labels',
                'show_popup', 'label_field', 'label_min_zoom', 'label_size', 'style',
                'show_attributes', 'attribute_fields', 'popup_fields'}
    extra = set(data) - editable
    if extra:
        raise ImportValidationError('Unsupported setting(s): ' + ', '.join(sorted(extra)))
    for field in ('name', 'group'):
        if field in data:
            value = str(data[field]).strip()
            maximum = 120 if field == 'name' else 80
            if not value or len(value) > maximum:
                raise ImportValidationError(f'{field} must be 1-{maximum} characters.')
            setattr(layer, field, value)
    if 'project_id' in data:
        value = data['project_id']
        layer.project_id = int(value) if value is not None and value != '' else None
        if layer.project_id is not None and layer.project_id <= 0:
            raise ImportValidationError('Project ID must be positive.')
    for field in ('is_visible', 'show_labels', 'show_popup', 'show_attributes'):
        if field in data:
            value = data[field]
            if not isinstance(value, bool):
                raise ImportValidationError(f'{field} must be true or false.')
            setattr(layer, field, value)
    for collection in ('attribute_fields', 'popup_fields'):
        if collection in data:
            value = data[collection]
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise ImportValidationError(f'{collection} must be a list of field names.')
            if len(set(value)) != len(value) or any(v not in layer.field_names for v in value):
                raise ImportValidationError(f'{collection} contains duplicate or unknown field names.')
            setattr(layer, collection, value)
    if 'label_field' in data:
        value = str(data['label_field'])
        if value and value not in layer.field_names:
            raise ImportValidationError('Choose a field that exists in the uploaded shapefile.')
        layer.label_field = value
    for field, low, high in [('label_min_zoom', 0, 22), ('label_size', 8, 26)]:
        if field in data:
            value = int(data[field])
            if not low <= value <= high:
                raise ImportValidationError(f'{field} must be between {low} and {high}.')
            setattr(layer, field, value)
    if 'style' in data:
        style = data['style']
        if not isinstance(style, dict):
            raise ImportValidationError('Style must be a JSON object.')
        allowed = {'color', 'fill_opacity', 'line_width', 'point_radius', 'raster_opacity'}
        if set(style) - allowed:
            raise ImportValidationError('Unknown style property.')
        new_style = dict(layer.style)
        if 'color' in style:
            if not isinstance(style['color'], str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', style['color']):
                raise ImportValidationError('Color must be a six-digit hex value, e.g. #2563eb.')
            new_style['color'] = style['color']
        for key, low, high in [('fill_opacity', 0, 1), ('raster_opacity', 0, 1), ('line_width', 0.5, 12), ('point_radius', 2, 18)]:
            if key in style:
                val = float(style[key])
                if not math.isfinite(val) or not low <= val <= high:
                    raise ImportValidationError(f'{key} must be between {low} and {high}.')
                new_style[key] = val
        layer.style = new_style
    if layer.geometry_type == 'Raster' and (layer.show_labels or layer.show_attributes or layer.show_popup):
        raise ImportValidationError('Raster layers cannot enable vector labels or attributes.')
    if layer.publication and layer.group.strip().lower() == 'cadastral':
        raise ImportValidationError('Cadastral layers require a relationship-managed workflow.')
    if layer.show_labels and not layer.label_field:
        raise ImportValidationError("Select a label field before enabling labels.")
    return layer


class HealthView(APIView):
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()
            return Response({'status': 'ok', 'database': 'connected'})
        except Exception:
            return error('Database unavailable.', 503)


class PreviewView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        try:
            return Response(publishing.preview(request.FILES.get('file')))
        except ImportValidationError as exc:
            return error(exc)


class LayersView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        query = Layer.objects.all()
        project = request.query_params.get('project_id')
        if project:
            try:
                query = query.filter(project_id=int(project))
            except ValueError:
                return error('Project ID must be numeric.')
        return Response(LayerSerializer(query, many=True).data)

    def post(self, request):
        try:
            name, group, project = read_basic_metadata(request)
            layer = Layer(name=name, group=group, project_id=project)
            config = json.loads(request.data.get('configuration', '{}'))
            if not isinstance(config, dict) or {'name', 'group', 'project_id'} & set(config):
                raise ImportValidationError('Configuration must be an object containing display settings only.')
            publishing.publish_upload(layer, request.FILES.get('file'), configure=lambda item: apply_settings(item, config))
            return Response(LayerSerializer(layer).data, status=201)
        except PublishError as exc:
            return error(exc, 502)
        except (ValueError, TypeError) as exc:
            return error(exc)


class LayerDetailView(APIView):
    def get(self, request, layer_id):
        return Response(LayerSerializer(get_object_or_404(Layer, pk=layer_id)).data)

    def patch(self, request, layer_id):
        layer = get_object_or_404(Layer, pk=layer_id)
        try:
            with transaction.atomic():
                layer = get_object_or_404(Layer.objects.select_for_update(), pk=layer_id)
                apply_settings(layer, request.data)
                layer.save()
            return Response(LayerSerializer(layer).data)
        except (ValueError, TypeError, ImportValidationError) as exc:
            return error(str(exc))

    def delete(self, request, layer_id):
        with transaction.atomic():
            layer = get_object_or_404(Layer.objects.select_for_update(), pk=layer_id)
            if not layer.publication:
                drop_layer_table(layer)
            # Remote publications are deliberately retained for recovery/audit.
            # Removing the catalog entry does not purge GeoServer storage.
            layer.delete()
        return Response(status=204)


class ReplaceView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, layer_id):
        try:
            with transaction.atomic():
                locked = get_object_or_404(Layer.objects.select_for_update(), pk=layer_id)
                if locked.publication:
                    publishing.publish_upload(locked, request.FILES.get('file'), replace=True)
                else:
                    parsed = read_zip(request)
                    publishing.ensure_compatible(locked, {'geometry_type': parsed.geometry_type, 'field_names': parsed.fields})
                    import_into_layer(parsed, locked, replace=True)
                    locked.source_filename = request.FILES['file'].name
                    locked.save(update_fields=['source_filename', 'updated_at'])
            return Response(LayerSerializer(locked).data)
        except PublishError as exc:
            return error(exc, 502)
        except (ImportValidationError, ValueError) as exc:
            return error(exc)


class RollbackView(APIView):
    def post(self, request, layer_id):
        try:
            with transaction.atomic():
                layer = get_object_or_404(Layer.objects.select_for_update(), pk=layer_id)
                publishing.rollback(layer)
            return Response(LayerSerializer(layer).data)
        except PublishError as exc:
            return error(exc, 502)
        except ImportValidationError as exc:
            return error(exc)


class GeoServerHealthView(APIView):
    def get(self, request):
        try:
            return Response({'status': 'ok', 'workspace': GeoServer().health()})
        except PublishError as exc:
            return error(exc, 503)


class RasterTileView(APIView):
    def get(self, request, layer_id):
        layer = get_object_or_404(Layer, pk=layer_id)
        if layer.publication.get('kind') != 'wms':
            return error('Not a WMS raster layer.', 404)
        try:
            bbox = [float(v) for v in request.query_params.get('bbox', '').split(',')]
            limit = 20037508.35
            if len(bbox) != 4 or not all(math.isfinite(v) and abs(v) <= limit for v in bbox) or not (bbox[0] < bbox[2] and bbox[1] < bbox[3]):
                raise ValueError()
        except ValueError:
            return error('Invalid Web Mercator tile bounds.')
        try:
            # Explicit version prevents old browser tile URLs from serving new data.
            if request.query_params.get('v') != str(layer.version):
                return error('Stale tile version.', 409)
            response = HttpResponse(GeoServer().image(layer.publication, bbox), content_type='image/png')
            response['Cache-Control'] = 'private, max-age=300'
            return response
        except PublishError as exc:
            return error(exc, 502)


class FeaturesView(APIView):
    def get(self, request, layer_id):
        layer = get_object_or_404(Layer, pk=layer_id)
        if not layer.table_name and not layer.publication:
            return error('Layer table has not been created. Run python manage.py migrate.', 409)
        bbox_value = request.query_params.get('bbox')
        bbox = None
        if bbox_value:
            try:
                bbox = [float(n) for n in bbox_value.split(',')]
                if len(bbox) != 4 or any(not math.isfinite(n) for n in bbox):
                    raise ValueError()
                minx, miny, maxx, maxy = bbox
                if not (-180 <= minx <= maxx <= 180 and -90 <= miny <= maxy <= 90):
                    raise ValueError()
            except (ValueError, TypeError):
                return error('bbox must be minLon,minLat,maxLon,maxLat in EPSG:4326.')
        if layer.publication.get('kind') == 'wms':
            return error('Raster layers use the WMS tile endpoint.')
        if layer.publication.get('kind') == 'wfs':
            try:
                result = GeoServer().features(layer.publication, bbox=bbox, count=MAX_MAP_FEATURES)
                features = result['features']
                count = result.get('numberMatched', result.get('totalFeatures'))
                total = int(count) if str(count).isdigit() else len(features)
                truncated = total > len(features) or len(features) >= MAX_MAP_FEATURES
                return Response({'type': 'FeatureCollection', 'features': features, 'meta': {'total_matching': total, 'returned': len(features), 'truncated': truncated, 'service': 'WFS'}})
            except PublishError as exc:
                return error(exc, 502)
        total, features = get_geojson_rows(layer, bbox, MAX_MAP_FEATURES)
        return Response({
            'type': 'FeatureCollection', 'features': features,
            'meta': {'total_matching': total, 'returned': len(features),
                     'truncated': total > MAX_MAP_FEATURES, 'table_name': layer.table_name},
        })


class AttributesView(APIView):
    def get(self, request, layer_id):
        layer = get_object_or_404(Layer, pk=layer_id)
        if not layer.table_name and not layer.publication:
            return error('Layer table has not been created. Run python manage.py migrate.', 409)
        try:
            page = int(request.query_params.get('page', '1'))
            page_size = int(request.query_params.get('page_size', '25'))
        except ValueError:
            return error('Page and page_size must be integers.')
        if page < 1 or not 1 <= page_size <= 100:
            return error('Page must be positive and page_size must be 1-100.')
        fields = [field for field in layer.attribute_fields if field in layer.field_names]
        if not layer.show_attributes:
            return Response({'fields': [], 'rows': [], 'count': layer.feature_count,
                             'page': page, 'page_size': page_size, 'total_pages': 0,
                             'disabled': True})
        if layer.publication.get('kind') == 'wfs':
            try:
                result = GeoServer().features(layer.publication, count=page_size, start=(page-1)*page_size)
                records = [{**{f: item.get('properties', {}).get(f) for f in fields}, '_row_id': item.get('id', i)} for i,item in enumerate(result['features'])]
            except PublishError as exc:
                return error(exc, 502)
        else:
            records = get_attribute_rows(layer, fields, (page-1)*page_size, page_size)
        return Response({
            'fields': fields,
            'rows': records,
            'count': layer.feature_count,
            'page': page,
            'page_size': page_size,
            'total_pages': math.ceil(layer.feature_count / page_size) if layer.feature_count else 0,
            'disabled': False,
        })
