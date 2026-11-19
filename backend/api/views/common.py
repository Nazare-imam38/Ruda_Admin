
import math
import re

from rest_framework.response import Response

from api.importer import (
    ImportValidationError,
    parse_shapefile,
    MAX_ZIP_SIZE,
)


MAX_MAP_FEATURES = 10000


def error(message, status=400):
    return Response({"error": str(message)}, status=status)


def read_zip(request):
    upload = request.FILES.get("file")

    if upload is None:
        raise ImportValidationError(
            "Choose a ZIP shapefile in the file field."
        )

    if not upload.name.lower().endswith(".zip"):
        raise ImportValidationError(
            "Only ZIP shapefiles are supported."
        )

    if upload.size > MAX_ZIP_SIZE:
        raise ImportValidationError(
            "ZIP must be at most 40 MB."
        )

    return parse_shapefile(upload.read(MAX_ZIP_SIZE + 1))


def read_basic_metadata(request):
    name = str(request.data.get("name", "")).strip()
    group = (
        str(request.data.get("group", "Uploaded Layers")).strip()
        or "Uploaded Layers"
    )

    project = request.data.get("project_id")

    if not (1 <= len(name) <= 120):
        raise ImportValidationError(
            "Layer name is required (1-120 characters)."
        )

    if len(group) > 80:
        raise ImportValidationError(
            "Group must be 80 characters or fewer."
        )

    if project is None or str(project).strip() == "":
        project = None
    else:
        try:
            project = int(project)
        except (ValueError, TypeError):
            raise ImportValidationError(
                "Project ID must be an integer."
            )

        if project < 1:
            raise ImportValidationError(
                "Project ID must be positive."
            )

    return name, group, project


def apply_settings(layer, data):
    editable = {
        "name",
        "group",
        "project_id",
        "is_visible",
        "show_labels",
        "show_popup",
        "label_field",
        "label_min_zoom",
        "label_size",
        "style",
        "show_attributes",
        "attribute_fields",
        "popup_fields",
    }

    extra = set(data) - editable

    if extra:
        raise ImportValidationError(
            "Unsupported setting(s): " + ", ".join(sorted(extra))
        )

    for field in ("name", "group"):
        if field in data:
            value = str(data[field]).strip()
            maximum = 120 if field == "name" else 80

            if not value or len(value) > maximum:
                raise ImportValidationError(
                    f"{field} must be 1-{maximum} characters."
                )

            setattr(layer, field, value)

    if "project_id" in data:
        value = data["project_id"]
        layer.project_id = (
            int(value) if value is not None and value != "" else None
        )

        if layer.project_id is not None and layer.project_id <= 0:
            raise ImportValidationError(
                "Project ID must be positive."
            )

    for field in (
        "is_visible",
        "show_labels",
        "show_popup",
        "show_attributes",
    ):
        if field in data:
            value = data[field]

            if not isinstance(value, bool):
                raise ImportValidationError(
                    f"{field} must be true or false."
                )

            setattr(layer, field, value)

    for collection in ("attribute_fields", "popup_fields"):
        if collection in data:
            value = data[collection]

            if (
                not isinstance(value, list)
                or not all(isinstance(v, str) for v in value)
            ):
                raise ImportValidationError(
                    f"{collection} must be a list of field names."
                )

            if (
                len(set(value)) != len(value)
                or any(v not in layer.field_names for v in value)
            ):
                raise ImportValidationError(
                    f"{collection} contains duplicate or unknown field names."
                )

            setattr(layer, collection, value)

    if "label_field" in data:
        value = str(data["label_field"])

        if value and value not in layer.field_names:
            raise ImportValidationError(
                "Choose a field that exists in the uploaded shapefile."
            )

        layer.label_field = value

    for field, low, high in [
        ("label_min_zoom", 0, 22),
        ("label_size", 8, 26),
    ]:
        if field in data:
            value = int(data[field])

            if not low <= value <= high:
                raise ImportValidationError(
                    f"{field} must be between {low} and {high}."
                )

            setattr(layer, field, value)

    if "style" in data:
        style = data["style"]

        if not isinstance(style, dict):
            raise ImportValidationError(
                "Style must be a JSON object."
            )

        allowed = {
            "color",
            "fill_opacity",
            "line_width",
            "point_radius",
            "raster_opacity",
        }

        if set(style) - allowed:
            raise ImportValidationError(
                "Unknown style property."
            )

        new_style = dict(layer.style)

        if "color" in style:
            if (
                not isinstance(style["color"], str)
                or not re.fullmatch(
                    r"#[0-9a-fA-F]{6}",
                    style["color"],
                )
            ):
                raise ImportValidationError(
                    "Color must be a six-digit hex value, e.g. #2563eb."
                )

            new_style["color"] = style["color"]

        for key, low, high in [
            ("fill_opacity", 0, 1),
            ("raster_opacity", 0, 1),
            ("line_width", 0.5, 12),
            ("point_radius", 2, 18),
        ]:
            if key in style:
                val = float(style[key])

                if not math.isfinite(val) or not low <= val <= high:
                    raise ImportValidationError(
                        f"{key} must be between {low} and {high}."
                    )

                new_style[key] = val

        layer.style = new_style

    if layer.geometry_type == "Raster" and (
        layer.show_labels
        or layer.show_attributes
        or layer.show_popup
    ):
        raise ImportValidationError(
            "Raster layers cannot enable vector labels or attributes."
        )

    if (
        layer.publication
        and layer.group.strip().lower() == "cadastral"
    ):
        raise ImportValidationError(
            "Cadastral layers require a relationship-managed workflow."
        )

    if layer.show_labels and not layer.label_field:
        raise ImportValidationError(
            "Select a label field before enabling labels."
        )

    return layer
