
import json

from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from api import publishing
from api.geoserver import PublishError
from api.importer import ImportValidationError

from ..common import error, apply_settings, read_basic_metadata


class PreviewView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        try:
            return Response(
                publishing.preview(request.FILES.get("file"))
            )
        except ImportValidationError as exc:
            return error(exc)


def upload_layer(request):
    try:
        from api.models import Layer
        from api.serializers import LayerSerializer

        name, group, project = read_basic_metadata(request)

        # Prevent duplicate layer names within the same project.
        existing_layer = Layer.objects.filter(
            name__iexact=name.strip(),
            project_id=project,
        ).first()

        if existing_layer:
            return error(
                f'A layer named "{existing_layer.name}" already exists. '
                'Please choose another layer name.',
                409,
            )

        layer = Layer(
            name=name.strip(),
            group=group,
            project_id=project,
            is_visible=False,
        )

        config = json.loads(
            request.data.get("configuration", "{}")
        )

        if (
            not isinstance(config, dict)
            or {"name", "group", "project_id"} & set(config)
        ):
            raise ImportValidationError(
                "Configuration must be an object containing display settings only."
            )

        publishing.publish_upload(
            layer,
            request.FILES.get("file"),
            configure=lambda item: apply_settings(item, config),
        )

        return Response(
            LayerSerializer(layer).data,
            status=201,
        )

    except PublishError as exc:
        return error(exc, 502)
    except (ValueError, TypeError) as exc:
        return error(exc)
