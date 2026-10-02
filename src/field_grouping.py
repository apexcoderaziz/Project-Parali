"""Logical Sangrur field grouping helpers for Project Parali.

The Sangrur source data contains year-qualified field IDs such as
2020_34 and 2021_34.  The application can now treat the shorter field
number (34) as a logical multi-year field group while preserving the
original source IDs and geometries.

For a full source ID such as 2021_34, the behavior remains single-field.
For a logical ID such as 34, all matching source-year features are used.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GEOJSON_PATH = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "sangrur_fields.geojson",
)


def clean_field_id(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def extract_field_number(field_id: Any) -> str:
    """Return the logical field number from 2020_34 / 2021_34 / 34."""

    value = clean_field_id(field_id)
    if not value:
        return ""

    match = re.match(r"^\d{4}_(.+)$", value)
    if match:
        return match.group(1).strip()

    return value


def _load_geojson(geojson_path: str = GEOJSON_PATH) -> Dict[str, Any]:
    if not os.path.exists(geojson_path):
        raise FileNotFoundError(f"Sangrur GeoJSON not found: {geojson_path}")

    with open(geojson_path, "r", encoding="utf-8") as file:
        return json.load(file)


def load_field_features(
    field_id: str,
    geojson_path: str = GEOJSON_PATH,
) -> List[Dict[str, Any]]:
    """Resolve a full field ID or logical field number to source features."""

    requested = clean_field_id(field_id)
    if not requested:
        raise ValueError("field_id cannot be empty")

    geojson = _load_geojson(geojson_path)
    features = geojson.get("features", [])

    exact_matches: List[Dict[str, Any]] = []

    for feature in features:
        properties = feature.get("properties") or {}
        candidate = clean_field_id(
            properties.get("field_id")
            or properties.get("id")
            or properties.get("ID")
            or properties.get("Id")
        )

        if candidate.lower() == requested.lower():
            exact_matches.append(feature)

    # Preserve existing behavior for a globally unique full ID.
    if exact_matches:
        return exact_matches[:1]

    logical_number = extract_field_number(requested).lower()
    matches: List[Dict[str, Any]] = []

    for feature in features:
        properties = feature.get("properties") or {}
        candidate = clean_field_id(
            properties.get("field_id")
            or properties.get("id")
            or properties.get("ID")
            or properties.get("Id")
        )
        original_id = clean_field_id(properties.get("original_field_id"))
        candidate_number = extract_field_number(candidate).lower()

        if (
            candidate_number == logical_number
            or original_id.lower() == logical_number
        ):
            matches.append(feature)

    def sort_key(feature: Dict[str, Any]):
        properties = feature.get("properties") or {}
        source_year = properties.get("source_year")
        try:
            year = int(source_year)
        except (TypeError, ValueError):
            year = 0
        return (year, clean_field_id(properties.get("field_id")))

    matches.sort(key=sort_key)

    if not matches:
        raise KeyError(f"Field '{requested}' was not found in Sangrur GeoJSON")

    return matches


def resolve_field_ids(
    field_id: str,
    geojson_path: str = GEOJSON_PATH,
) -> List[str]:
    """Return the source IDs used by a request."""

    features = load_field_features(field_id, geojson_path)
    ids: List[str] = []

    for feature in features:
        properties = feature.get("properties") or {}
        source_id = clean_field_id(
            properties.get("field_id")
            or properties.get("id")
            or properties.get("ID")
            or properties.get("Id")
        )
        if source_id:
            ids.append(source_id)

    return ids


def is_logical_group(
    field_id: str,
    geojson_path: str = GEOJSON_PATH,
) -> bool:
    """Return True when the request resolves to multiple source-year fields."""

    requested = clean_field_id(field_id)
    members = resolve_field_ids(requested, geojson_path)
    return len(members) > 1 and requested not in members


def combined_geometry(
    field_id: str,
    geojson_path: str = GEOJSON_PATH,
) -> Dict[str, Any]:
    """Return all source geometries as one GeoJSON MultiPolygon region."""

    features = load_field_features(field_id, geojson_path)
    polygons: List[Any] = []

    for feature in features:
        geometry = feature.get("geometry") or {}
        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates")

        if geometry_type == "Polygon":
            if coordinates:
                polygons.append(coordinates)
        elif geometry_type == "MultiPolygon":
            if coordinates:
                polygons.extend(coordinates)
        else:
            raise ValueError(
                f"Unsupported geometry type '{geometry_type}' for field "
                f"{field_id}"
            )

    if not polygons:
        raise ValueError(f"Field '{field_id}' has no usable geometry")

    if len(features) == 1 and (features[0].get("geometry") or {}).get("type") in {
        "Polygon",
        "MultiPolygon",
    }:
        geometry = features[0].get("geometry") or {}
        if geometry.get("type") == "Polygon":
            return {
                "type": "Polygon",
                "coordinates": geometry.get("coordinates"),
            }
        return {
            "type": "MultiPolygon",
            "coordinates": geometry.get("coordinates"),
        }

    return {
        "type": "MultiPolygon",
        "coordinates": polygons,
    }


def group_summary(
    field_id: str,
    geojson_path: str = GEOJSON_PATH,
) -> Dict[str, Any]:
    """Return source metadata for the selected logical field."""

    features = load_field_features(field_id, geojson_path)
    source_fields = []

    for feature in features:
        properties = feature.get("properties") or {}
        source_id = clean_field_id(
            properties.get("field_id")
            or properties.get("id")
            or properties.get("ID")
            or properties.get("Id")
        )
        source_fields.append(
            {
                "field_id": source_id,
                "source_year": properties.get("source_year"),
                "source_file": properties.get("source_file"),
                "original_field_id": properties.get("original_field_id"),
            }
        )

    return {
        "logical_field_id": clean_field_id(field_id),
        "logical_field_number": extract_field_number(field_id),
        "source_field_ids": [item["field_id"] for item in source_fields],
        "source_field_count": len(source_fields),
        "source_fields": source_fields,
        "geometry_mode": (
            "combined_source_year_multipolygon"
            if len(source_fields) > 1
            else "single_source_geometry"
        ),
    }
