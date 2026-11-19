
from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework.response import Response
from rest_framework.views import APIView

from api import publishing
from api.geoserver import PublishError
from api.importer import ImportValidationError, import_into_layer
from api.models import Layer
from api.physical_tables import drop_layer_table
from api.serializers import LayerSerializer

from ..common import error, read_zip
from .LayerUploadViews import upload_layer


class LayersView(APIView):
    def get(self, request):
        query = Layer.objects.all()
        project = request.query_params.get("project_id")

        if project:
            try:
                query = query.filter(project_id=int(project))
            except ValueError:
                return error("Project ID must be numeric.")

        return Response(LayerSerializer(query, many=True).data)

    def post(self, request):
        return upload_layer(request)


class LayerDetailView(APIView):
    def get(self, request, layer_id):
        layer = get_object_or_404(Layer, pk=layer_id)
        return Response(LayerSerializer(layer).data)

    def patch(self, request, layer_id):
        from ..common import apply_settings

        try:
            with transaction.atomic():
                layer = get_object_or_404(
                    Layer.objects.select_for_update(),
                    pk=layer_id,
                )
                apply_settings(layer, request.data)
                layer.save()

            return Response(LayerSerializer(layer).data)

        except (ValueError, TypeError, ImportValidationError) as exc:
            return error(str(exc))

    def delete(self, request, layer_id):
        with transaction.atomic():
            layer = get_object_or_404(
                Layer.objects.select_for_update(),
                pk=layer_id,
            )

            if not layer.publication:
                drop_layer_table(layer)

            # Keep remote GeoServer publications for recovery and audit.
            layer.delete()

        return Response(status=204)


class ReplaceView(APIView):
    def post(self, request, layer_id):
        try:
            with transaction.atomic():
                layer = get_object_or_404(
                    Layer.objects.select_for_update(),
                    pk=layer_id,
                )

                if layer.publication:
                    publishing.publish_upload(
                        layer,
                        request.FILES.get("file"),
                        replace=True,
                    )
                else:
                    parsed = read_zip(request)

                    publishing.ensure_compatible(
                        layer,
                        {
                            "geometry_type": parsed.geometry_type,
                            "field_names": parsed.fields,
                        },
                    )

                    import_into_layer(
                        parsed,
                        layer,
                        replace=True,
                    )

                    layer.source_filename = request.FILES["file"].name
                    layer.save(
                        update_fields=["source_filename", "updated_at"]
                    )

            return Response(LayerSerializer(layer).data)

        except PublishError as exc:
            return error(exc, 502)
        except (ImportValidationError, ValueError) as exc:
            return error(exc)


class RollbackView(APIView):
    def post(self, request, layer_id):
        try:
            with transaction.atomic():
                layer = get_object_or_404(
                    Layer.objects.select_for_update(),
                    pk=layer_id,
                )
                publishing.rollback(layer)

            return Response(LayerSerializer(layer).data)

        except PublishError as exc:
            return error(exc, 502)
        except ImportValidationError as exc:
            return error(exc)
