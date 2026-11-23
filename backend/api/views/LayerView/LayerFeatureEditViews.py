
from django.db import connection, transaction
from django.shortcuts import get_object_or_404

from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import Layer, Feature
from api.physical_tables import (
    full_table,
    quote,
    adapt_value,
    column_type,
)

from ..common import error


def get_editable_layer(layer_id):
    layer = get_object_or_404(Layer, pk=layer_id)

    if not layer.table_name:
        return None, error(
            "This layer does not have a managed PostGIS table and cannot be edited.",
            409,
        )

    return layer, None


def get_field_schema(layer, field_name):
    for field in layer.field_schema:
        if field.get("name") == field_name:
            return field

    return None


class FeatureUpdateView(APIView):
    def patch(self, request, layer_id, feature_id):
        layer, response = get_editable_layer(layer_id)
        if response:
            return response

        values = request.data

        if not isinstance(values, dict) or not values:
            return error("Provide at least one attribute to update.")

        updates = []

        for field_name, value in values.items():
            if field_name not in layer.field_names:
                return error(f"Unknown field: {field_name}")

            db_column = layer.column_map.get(field_name)
            if not db_column:
                return error(f"Column mapping not found for {field_name}.")

            schema = get_field_schema(layer, field_name)
            if not schema:
                return error(f"Field schema not found for {field_name}.")

            try:
                converted = adapt_value(value, column_type(schema))
            except (TypeError, ValueError, OverflowError):
                return error(f"Invalid value for field {field_name}.")

            updates.append((db_column, converted))

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    set_clause = ", ".join(
                        f"{quote(column)} = %s"
                        for column, value in updates
                    )

                    params = [value for column, value in updates]
                    params.append(feature_id)

                    cursor.execute(
                        f"""
                        UPDATE {full_table(layer.table_name)}
                        SET {set_clause}
                        WHERE gid = %s
                        RETURNING gid
                        """,
                        params,
                    )

                    updated = cursor.fetchone()

                    if not updated:
                        return error("Feature not found.", 404)

            return Response({
                "message": "Feature updated successfully.",
                "id": updated[0],
            })

        except Exception:
            return error("Unable to update feature.", 500)


class FeatureDeleteView(APIView):
    def delete(self, request, layer_id, feature_id):
        layer, response = get_editable_layer(layer_id)
        if response:
            return response

        try:
            with transaction.atomic():
                locked_layer = Layer.objects.select_for_update().get(
                    pk=layer_id
                )

                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                        DELETE FROM {full_table(locked_layer.table_name)}
                        WHERE gid = %s
                        RETURNING source_index
                        """,
                        [feature_id],
                    )

                    deleted = cursor.fetchone()

                    if not deleted:
                        return error("Feature not found.", 404)

                # Remove the corresponding legacy Feature record, if present.
                Feature.objects.filter(
                    layer=locked_layer,
                    source_index=deleted[0],
                ).delete()

                with connection.cursor() as cursor:
                    cursor.execute(
                        f"SELECT COUNT(*) FROM {full_table(locked_layer.table_name)}"
                    )
                    locked_layer.feature_count = cursor.fetchone()[0]

                locked_layer.save(update_fields=["feature_count"])

            return Response({
                "message": "Feature deleted successfully.",
                "id": feature_id,
                "remaining_features": locked_layer.feature_count,
            })

        except Exception:
            return error("Unable to delete feature.", 500)
