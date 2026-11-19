
import math

from django.shortcuts import get_object_or_404

from rest_framework.response import Response
from rest_framework.views import APIView

from api.geoserver import GeoServer, PublishError
from api.models import Layer
from api.physical_tables import (
    get_geojson_rows,
    get_attribute_rows,
)

from ..common import error, MAX_MAP_FEATURES


class FeaturesView(APIView):
    def get(self, request, layer_id):
        layer = get_object_or_404(Layer, pk=layer_id)

        if not layer.table_name and not layer.publication:
            return error(
                "Layer table has not been created. Run python manage.py migrate.",
                409,
            )

        bbox_value = request.query_params.get("bbox")
        bbox = None

        if bbox_value:
            try:
                bbox = [float(n) for n in bbox_value.split(",")]

                if len(bbox) != 4 or any(
                    not math.isfinite(n) for n in bbox
                ):
                    raise ValueError()

                minx, miny, maxx, maxy = bbox

                if not (
                    -180 <= minx <= maxx <= 180
                    and -90 <= miny <= maxy <= 90
                ):
                    raise ValueError()

            except (ValueError, TypeError):
                return error(
                    "bbox must be minLon,minLat,maxLon,maxLat in EPSG:4326."
                )

        if layer.publication.get("kind") == "wms":
            return error("Raster layers use the WMS tile endpoint.")

        if layer.publication.get("kind") == "wfs":
            try:
                result = GeoServer().features(
                    layer.publication,
                    bbox=bbox,
                    count=MAX_MAP_FEATURES,
                )

                features = result["features"]
                count = result.get(
                    "numberMatched",
                    result.get("totalFeatures"),
                )

                total = (
                    int(count)
                    if str(count).isdigit()
                    else len(features)
                )

                return Response({
                    "type": "FeatureCollection",
                    "features": features,
                    "meta": {
                        "total_matching": total,
                        "returned": len(features),
                        "truncated": (
                            total > len(features)
                            or len(features) >= MAX_MAP_FEATURES
                        ),
                        "service": "WFS",
                    },
                })

            except PublishError as exc:
                return error(exc, 502)

        total, features = get_geojson_rows(
            layer,
            bbox,
            MAX_MAP_FEATURES,
        )

        return Response({
            "type": "FeatureCollection",
            "features": features,
            "meta": {
                "total_matching": total,
                "returned": len(features),
                "truncated": total > MAX_MAP_FEATURES,
                "table_name": layer.table_name,
            },
        })


class AttributesView(APIView):
    def get(self, request, layer_id):
        layer = get_object_or_404(Layer, pk=layer_id)

        if not layer.table_name and not layer.publication:
            return error(
                "Layer table has not been created. Run python manage.py migrate.",
                409,
            )

        try:
            page = int(request.query_params.get("page", "1"))
            page_size = int(
                request.query_params.get("page_size", "25")
            )
        except ValueError:
            return error("Page and page_size must be integers.")

        if page < 1 or not 1 <= page_size <= 100:
            return error(
                "Page must be positive and page_size must be 1-100."
            )

        fields = [
            field
            for field in layer.attribute_fields
            if field in layer.field_names
        ]

        if not layer.show_attributes:
            return Response({
                "fields": [],
                "rows": [],
                "count": layer.feature_count,
                "page": page,
                "page_size": page_size,
                "total_pages": 0,
                "disabled": True,
            })

        if layer.publication.get("kind") == "wfs":
            try:
                result = GeoServer().features(
                    layer.publication,
                    count=page_size,
                    start=(page - 1) * page_size,
                )

                records = [
                    {
                        **{
                            field: item.get("properties", {}).get(field)
                            for field in fields
                        },
                        "_row_id": item.get("id", i),
                    }
                    for i, item in enumerate(result["features"])
                ]

            except PublishError as exc:
                return error(exc, 502)

        else:
            records = get_attribute_rows(
                layer,
                fields,
                (page - 1) * page_size,
                page_size,
            )

        return Response({
            "fields": fields,
            "rows": records,
            "count": layer.feature_count,
            "page": page,
            "page_size": page_size,
            "total_pages": (
                math.ceil(layer.feature_count / page_size)
                if layer.feature_count
                else 0
            ),
            "disabled": False,
        })
