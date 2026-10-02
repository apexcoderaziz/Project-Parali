"""Shared logical-field context for Project Parali.

This module is the single source of truth for resolving a logical field ID
such as ``34`` to its source-year records (for example ``2020_34`` and
``2021_34``) and for deriving common geometry/area metadata.

Downstream intelligence modules should consume this context instead of
independently reading GeoJSON and re-implementing field resolution.

The module intentionally returns plain dictionaries so it can be used by
FastAPI services without introducing a new serialization dependency.
"""

from __future__ import annotations

import math
import os
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from .field_grouping import (
        extract_field_number,
        load_field_features,
    )
except ImportError:
    from field_grouping import (
        extract_field_number,
        load_field_features,
    )


BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

GEOJSON_PATH = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "sangrur_fields.geojson",
)


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def clean_field_id(value: Any) -> str:
    """Normalize a field identifier into a trimmed string."""

    if value is None:
        return ""
    return str(value).strip()


def _source_field_id(properties: Dict[str, Any]) -> str:
    """Return the canonical source field ID from a feature's properties."""

    return clean_field_id(
        properties.get("field_id")
        or properties.get("id")
        or properties.get("ID")
        or properties.get("Id")
    )


def _number(value: Any) -> Optional[float]:
    try:
        number = float(value)
        if math.isfinite(number):
            return number
    except (TypeError, ValueError):
        pass
    return None


def _nested_indicators(properties: Dict[str, Any]) -> Dict[str, Any]:
    """Return the most specific embedded indicator dictionary."""

    value = properties.get("field_indicators")
    if isinstance(value, dict):
        return value

    value = properties.get("indicators")
    if isinstance(value, dict):
        return value

    return {}


def _feature_area_hectares(properties: Dict[str, Any], geometry: Dict[str, Any]) -> Tuple[Optional[float], str]:
    """Get feature area, preferring stored indicator/property values."""

    indicators = _nested_indicators(properties)

    for key in ("area_hectares", "area_ha"):
        value = _number(indicators.get(key))
        if value is not None and value > 0:
            return value, "field_indicators"

    for key in ("area_hectares", "area_ha"):
        value = _number(properties.get(key))
        if value is not None and value > 0:
            return value, "feature_properties"

    geometry_area_m2 = _geometry_area_m2(geometry)
    if geometry_area_m2 > 0:
        return geometry_area_m2 / 10000.0, "geometry_fallback"

    return None, "unavailable"


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _iter_coordinate_pairs(coordinates: Any) -> Iterable[Tuple[float, float]]:
    """Yield ``(longitude, latitude)`` pairs from nested GeoJSON coordinates."""

    if not isinstance(coordinates, (list, tuple)):
        return

    if (
        len(coordinates) >= 2
        and isinstance(coordinates[0], (int, float))
        and isinstance(coordinates[1], (int, float))
    ):
        yield float(coordinates[0]), float(coordinates[1])
        return

    for item in coordinates:
        yield from _iter_coordinate_pairs(item)


def _ring_area_m2(ring: Any) -> float:
    """Approximate a longitude/latitude polygon ring area in square metres."""

    if not isinstance(ring, (list, tuple)) or len(ring) < 3:
        return 0.0

    points = []
    for point in ring:
        if (
            isinstance(point, (list, tuple))
            and len(point) >= 2
        ):
            try:
                lon = float(point[0])
                lat = float(point[1])
            except (TypeError, ValueError):
                continue
            if math.isfinite(lon) and math.isfinite(lat):
                points.append((lon, lat))

    if len(points) < 3:
        return 0.0

    mean_lat = math.radians(
        sum(lat for _, lat in points) / len(points)
    )
    earth_radius_m = 6_378_137.0
    cos_lat = max(math.cos(mean_lat), 1e-9)

    projected = [
        (
            math.radians(lon) * earth_radius_m * cos_lat,
            math.radians(lat) * earth_radius_m,
        )
        for lon, lat in points
    ]

    area = 0.0
    for index, (x1, y1) in enumerate(projected):
        x2, y2 = projected[(index + 1) % len(projected)]
        area += x1 * y2 - x2 * y1

    return abs(area) * 0.5


def _geometry_area_m2(geometry: Optional[Dict[str, Any]]) -> float:
    """Approximate Polygon/MultiPolygon area in square metres."""

    if not isinstance(geometry, dict):
        return 0.0

    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")

    if geometry_type == "Polygon" and isinstance(coordinates, list):
        if not coordinates:
            return 0.0
        outer = _ring_area_m2(coordinates[0])
        holes = sum(_ring_area_m2(ring) for ring in coordinates[1:])
        return max(0.0, outer - holes)

    if geometry_type == "MultiPolygon" and isinstance(coordinates, list):
        return sum(
            _geometry_area_m2(
                {"type": "Polygon", "coordinates": polygon}
            )
            for polygon in coordinates
            if isinstance(polygon, list)
        )

    return 0.0


def _geometry_centroid(geometry: Optional[Dict[str, Any]]) -> Optional[Tuple[float, float]]:
    """Return a coordinate-average centroid as ``(latitude, longitude)``."""

    if not isinstance(geometry, dict):
        return None

    points = list(_iter_coordinate_pairs(geometry.get("coordinates")))
    if not points:
        return None

    longitude = sum(point[0] for point in points) / len(points)
    latitude = sum(point[1] for point in points) / len(points)
    return latitude, longitude


def _combined_geometry(features: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build the combined geometry while preserving source geometries."""

    polygons: List[Any] = []
    single_geometry: Optional[Dict[str, Any]] = None

    for feature in features:
        geometry = feature.get("geometry") or {}
        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates")

        if geometry_type == "Polygon":
            if coordinates:
                polygons.append(coordinates)
                if single_geometry is None:
                    single_geometry = {
                        "type": "Polygon",
                        "coordinates": coordinates,
                    }
        elif geometry_type == "MultiPolygon":
            if coordinates:
                polygons.extend(coordinates)
                if single_geometry is None:
                    single_geometry = {
                        "type": "MultiPolygon",
                        "coordinates": coordinates,
                    }
        else:
            raise ValueError(
                f"Unsupported geometry type '{geometry_type}' for selected field"
            )

    if not polygons:
        raise ValueError("Selected field has no usable polygon geometry")

    if len(features) == 1 and single_geometry is not None:
        return single_geometry

    return {
        "type": "MultiPolygon",
        "coordinates": polygons,
    }


# ---------------------------------------------------------------------------
# Public shared context
# ---------------------------------------------------------------------------


def resolve_field_context(
    field_id: str,
    geojson_path: str = GEOJSON_PATH,
) -> Dict[str, Any]:
    """Resolve a logical or source field into one shared context object.

    Examples:
        ``34`` -> ``2020_34`` + ``2021_34`` when both exist.
        ``343`` -> ``2021_343`` when it is the only matching source record.
        ``2021_343`` -> the exact source record.

    The returned dictionary is intentionally stable and can be passed between
    downstream modules without requiring them to reopen the GeoJSON file.
    """

    requested = clean_field_id(field_id)
    if not requested:
        raise ValueError("field_id cannot be empty")

    features = load_field_features(requested, geojson_path)

    source_field_ids: List[str] = []
    source_fields: List[Dict[str, Any]] = []
    source_indicators: List[Dict[str, Any]] = []
    categories: List[str] = []
    total_area_hectares = 0.0
    total_area_acres = 0.0

    weighted_latitude = 0.0
    weighted_longitude = 0.0
    centroid_weight = 0.0

    for feature in features:
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        source_id = _source_field_id(properties)

        if source_id:
            source_field_ids.append(source_id)

        area_hectares, area_source = _feature_area_hectares(
            properties,
            geometry,
        )
        area_value = float(area_hectares or 0.0)
        area_acres = _number(properties.get("area_acres"))

        if area_acres is None or area_acres <= 0:
            area_acres = area_value * 2.47105 if area_value > 0 else 0.0

        total_area_hectares += area_value
        total_area_acres += float(area_acres)

        centroid = _geometry_centroid(geometry)
        if centroid and area_value > 0:
            weighted_latitude += centroid[0] * area_value
            weighted_longitude += centroid[1] * area_value
            centroid_weight += area_value

        indicators = _nested_indicators(properties)
        category = (
            indicators.get("category")
            or properties.get("field_category")
            or properties.get("category")
        )
        if category is not None and str(category).strip():
            categories.append(str(category).strip())

        source_fields.append(
            {
                "field_id": source_id,
                "source_year": properties.get("source_year"),
                "source_file": properties.get("source_file"),
                "field_name": properties.get("field_name"),
                "category": category,
                "original_field_id": properties.get("original_field_id"),
                "area_hectares": round(area_value, 6),
                "area_acres": round(float(area_acres), 6),
                "area_source": area_source,
                "centroid": (
                    {
                        "latitude": round(centroid[0], 8),
                        "longitude": round(centroid[1], 8),
                    }
                    if centroid
                    else None
                ),
            }
        )

        if indicators:
            source_indicators.append(
                {
                    "field_id": source_id,
                    **indicators,
                }
            )

    geometry = _combined_geometry(features)

    if centroid_weight > 0:
        centroid = {
            "latitude": round(
                weighted_latitude / centroid_weight,
                8,
            ),
            "longitude": round(
                weighted_longitude / centroid_weight,
                8,
            ),
            "method": "area_weighted_source_geometry_centroids",
        }
    else:
        fallback = _geometry_centroid(geometry)
        centroid = (
            {
                "latitude": round(fallback[0], 8),
                "longitude": round(fallback[1], 8),
                "method": "coordinate_average_geometry_centroid",
            }
            if fallback
            else None
        )

    if len(source_field_ids) == 1:
        geometry_mode = "single_source_geometry"
    else:
        geometry_mode = "combined_source_year_multipolygon"

    unique_categories = sorted(set(categories))

    return {
        "logical_field_id": requested,
        "logical_field_number": extract_field_number(requested),
        "source_field_ids": source_field_ids,
        "source_field_count": len(source_field_ids),
        "geometry_mode": geometry_mode,
        "geometry": geometry,
        "centroid": centroid,
        "area": {
            "hectares": round(total_area_hectares, 6),
            "acres": round(total_area_acres, 6),
            "source": (
                "sum_of_source_field_areas"
                if len(source_field_ids) > 1
                else "source_field_area"
            ),
        },
        "categories": unique_categories,
        "source_fields": source_fields,
        "source_indicators": source_indicators,
    }


def get_field_context(
    field_id: str,
    geojson_path: str = GEOJSON_PATH,
) -> Dict[str, Any]:
    """Alias kept as the preferred name for downstream modules."""

    return resolve_field_context(field_id, geojson_path)
