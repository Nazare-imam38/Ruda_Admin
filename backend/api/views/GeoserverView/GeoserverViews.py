
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from rest_framework.response import Response
from rest_framework.views import APIView

from api.geoserver import GeoServer, PublishError
from api.models import Layer

from ..common import error


class GeoServerHealthView(APIView):
    def get(self, request):
        try:
            return Response({
                "status": "ok",
                "workspace": GeoServer().health(),
            })
        except PublishError as exc:
            return error(exc, 503)


class RasterTileView(APIView):
    def get(self, request, layer_id):
        layer = get_object_or_404(Layer, pk=layer_id)

        if layer.publication.get("kind") != "wms":
            return error("Not a WMS raster layer.", 404)

        try:
            bbox = [
                float(value)
                for value in request.query_params.get(
                    "bbox", ""
                ).split(",")
            ]

            limit = 20037508.35

            if (
                len(bbox) != 4
                or not all(
                    __import__("math").isfinite(value)
                    and abs(value) <= limit
                    for value in bbox
                )
                or not (
                    bbox[0] < bbox[2]
                    and bbox[1] < bbox[3]
                )
            ):
                raise ValueError()

        except ValueError:
            return error("Invalid Web Mercator tile bounds.")

        if request.query_params.get("v") != str(layer.version):
            return error("Stale tile version.", 409)

        try:
            response = HttpResponse(
                GeoServer().image(layer.publication, bbox),
                content_type="image/png",
            )

            response["Cache-Control"] = "private, max-age=300"
            return response

        except PublishError as exc:
            return error(exc, 502)
