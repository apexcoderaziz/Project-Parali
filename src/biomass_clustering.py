"""
Biomass Collection Clustering
=============================

Groups nearby Sangrur fields into collection clusters so a small individual
field load is treated as part of an aggregated biomass supply.

This module is intentionally transparent:
- field biomass is estimated from field area and the existing residue model
- clustering uses a configurable straight-line radius
- truckloads use a configurable truck-capacity assumption
- no road routing or transporter quote is claimed

Default assumptions are model parameters, not universal market facts.
"""

from __future__ import annotations

import json
import math
import os
from collections import deque
from typing import Any, Dict, List, Optional

try:
    from .field_grouping import group_summary, resolve_field_ids
except ImportError:
    from field_grouping import group_summary, resolve_field_ids


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

GEOJSON_PATH = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "sangrur_fields.geojson",
)

# Configurable collection-cluster radius.
DEFAULT_CLUSTER_RADIUS_KM = 5.0

# Configurable truck capacity for an MVP planning estimate.
DEFAULT_TRUCK_CAPACITY_TONNES = 10.0

# Existing residue-estimation assumptions used by Project Parali.
DEFAULT_CROP = "paddy"
DEFAULT_YIELD_TONNES_PER_HECTARE = 4.132
DEFAULT_RESIDUE_TO_PRODUCT_RATIO = 1.10
DEFAULT_COLLECTION_EFFICIENCY = 0.70


# ============================================================
# BASIC HELPERS
# ============================================================

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if math.isfinite(number):
            return number
    except (TypeError, ValueError):
        pass

    return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _field_id(properties: Dict[str, Any], index: int) -> str:
    raw = (
        properties.get("field_id")
        or properties.get("id")
        or properties.get("ID")
        or properties.get("Id")
        or f"field_{index + 1}"
    )

    return str(raw)


def _haversine_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Return great-circle distance in kilometres."""

    radius = 6371.0088

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1)
        * math.cos(phi2)
        * math.sin(d_lambda / 2) ** 2
    )

    a = min(1.0, max(0.0, a))

    return 2 * radius * math.asin(math.sqrt(a))


# ============================================================
# GEOJSON GEOMETRY
# ============================================================

def _iter_points(coordinates: Any):
    """
    Recursively yield [longitude, latitude] coordinate pairs from
    Polygon/MultiPolygon-style GeoJSON coordinates.
    """

    if not isinstance(coordinates, list):
        return

    if (
        len(coordinates) >= 2
        and isinstance(coordinates[0], (int, float))
        and isinstance(coordinates[1], (int, float))
    ):
        yield (
            _safe_float(coordinates[0]),
            _safe_float(coordinates[1]),
        )
        return

    for child in coordinates:
        yield from _iter_points(child)


def _geometry_centroid(geometry: Optional[Dict[str, Any]]):
    """
    Calculate a lightweight vertex-average centroid.

    This is sufficient for collection clustering at kilometre scale.
    It is not a survey-grade polygon centroid.
    """

    if not geometry:
        return None

    coordinates = geometry.get("coordinates")

    points = list(_iter_points(coordinates))

    if not points:
        return None

    lon = sum(point[0] for point in points) / len(points)
    lat = sum(point[1] for point in points) / len(points)

    return {
        "latitude": lat,
        "longitude": lon,
    }


def _ring_area_m2(ring: Any) -> float:
    """
    Approximate a GeoJSON polygon-ring area in square metres using a
    local equirectangular projection.

    This is a fallback only. Existing field metadata is preferred when
    it contains a valid positive area.
    """
    if not isinstance(ring, list) or len(ring) < 3:
        return 0.0

    points = []

    for point in ring:
        if (
            isinstance(point, list)
            and len(point) >= 2
            and isinstance(point[0], (int, float))
            and isinstance(point[1], (int, float))
        ):
            points.append(
                (
                    _safe_float(point[0]),
                    _safe_float(point[1]),
                )
            )

    if len(points) < 3:
        return 0.0

    mean_lat = sum(lat for _, lat in points) / len(points)

    meters_per_degree_lat = 111_320.0
    meters_per_degree_lon = (
        111_320.0 * math.cos(math.radians(mean_lat))
    )

    projected = [
        (
            lon * meters_per_degree_lon,
            lat * meters_per_degree_lat,
        )
        for lon, lat in points
    ]

    area = 0.0

    for i in range(len(projected)):
        x1, y1 = projected[i]
        x2, y2 = projected[(i + 1) % len(projected)]
        area += x1 * y2 - x2 * y1

    return abs(area) / 2.0


def _geometry_area_m2(
    geometry: Optional[Dict[str, Any]],
) -> float:
    """
    Calculate approximate Polygon/MultiPolygon area in square metres.

    Polygon holes are subtracted. MultiPolygon parts are summed.
    """
    if not geometry:
        return 0.0

    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")

    if geometry_type == "Polygon":
        if not isinstance(coordinates, list) or not coordinates:
            return 0.0

        outer = _ring_area_m2(coordinates[0])
        holes = sum(
            _ring_area_m2(ring)
            for ring in coordinates[1:]
        )

        return max(0.0, outer - holes)

    if geometry_type == "MultiPolygon":
        if not isinstance(coordinates, list):
            return 0.0

        total = 0.0

        for polygon in coordinates:
            if not isinstance(polygon, list) or not polygon:
                continue

            outer = _ring_area_m2(polygon[0])
            holes = sum(
                _ring_area_m2(ring)
                for ring in polygon[1:]
            )

            total += max(0.0, outer - holes)

        return total

    return 0.0


# ============================================================
# BIOMASS ESTIMATION
# ============================================================

def _estimate_biomass(area_hectares: float) -> Dict[str, float]:
    """
    Apply the same assumption-based residue model used by
    Project Parali's residue_estimation module.
    """

    gross = (
        area_hectares
        * DEFAULT_YIELD_TONNES_PER_HECTARE
        * DEFAULT_RESIDUE_TO_PRODUCT_RATIO
    )

    recoverable = (
        gross
        * DEFAULT_COLLECTION_EFFICIENCY
    )

    return {
        "gross_residue_tonnes": gross,
        "recoverable_biomass_tonnes": recoverable,
    }


# ============================================================
# LOAD FIELDS
# ============================================================

def load_fields(
    geojson_path: str = GEOJSON_PATH,
) -> List[Dict[str, Any]]:
    """Load field geometry, centroid, area and estimated biomass."""

    if not os.path.exists(geojson_path):
        raise FileNotFoundError(
            f"Sangrur GeoJSON not found: {geojson_path}"
        )

    with open(
        geojson_path,
        "r",
        encoding="utf-8",
    ) as file:
        geojson = json.load(file)

    fields: List[Dict[str, Any]] = []

    for index, feature in enumerate(
        geojson.get("features", [])
    ):
        properties = feature.get(
            "properties",
            {},
        )

        geometry = feature.get(
            "geometry"
        )

        centroid = _geometry_centroid(
            geometry
        )

        if centroid is None:
            continue

        indicators = properties.get(
            "field_indicators",
            {},
        )

        area_hectares = _safe_float(
            indicators.get(
                "area_hectares"
            ),
            _safe_float(
                properties.get(
                    "area_hectares"
                ),
                0.0,
            ),
        )

        # IMPORTANT:
        # Some runtime GeoJSON records do not contain the enriched
        # area metadata even though their polygon geometry is valid.
        # Never silently turn such fields into zero-biomass members.
        if area_hectares <= 0:
            area_m2 = _geometry_area_m2(
                geometry
            )
            area_hectares = (
                area_m2 / 10_000.0
                if area_m2 > 0
                else 0.0
            )

        biomass = _estimate_biomass(
            area_hectares
        )

        fields.append(
            {
                "field_id": _field_id(
                    properties,
                    index,
                ),
                "field_name": (
                    properties.get(
                        "field_name"
                    )
                ),
                "category": (
                    properties.get(
                        "field_category"
                    )
                    or properties.get(
                        "category"
                    )
                    or "unknown"
                ),
                "field_status": (
                    properties.get(
                        "field_status"
                    )
                    or indicators.get(
                        "field_status"
                    )
                ),
                "area_hectares": area_hectares,
                "area_acres": (
                    area_hectares
                    * 2.47105
                ),
                "area_source": (
                    "field_indicators"
                    if _safe_float(
                        indicators.get("area_hectares")
                    ) > 0
                    else (
                        "properties.area_hectares"
                        if _safe_float(
                            properties.get("area_hectares")
                        ) > 0
                        else "geometry_area_fallback"
                    )
                ),
                "latitude": centroid[
                    "latitude"
                ],
                "longitude": centroid[
                    "longitude"
                ],
                "gross_residue_tonnes": (
                    biomass[
                        "gross_residue_tonnes"
                    ]
                ),
                "recoverable_biomass_tonnes": (
                    biomass[
                        "recoverable_biomass_tonnes"
                    ]
                ),
            }
        )

    return fields


# ============================================================
# CLUSTERING
# ============================================================

def _build_adjacency(
    fields: List[Dict[str, Any]],
    radius_km: float,
) -> List[List[int]]:
    """
    Build a proximity graph.

    Two fields are connected when their centroids are within
    radius_km. Connected components form collection clusters.
    """

    adjacency = [
        []
        for _ in fields
    ]

    for i in range(len(fields)):
        for j in range(i + 1, len(fields)):
            distance = _haversine_km(
                fields[i]["latitude"],
                fields[i]["longitude"],
                fields[j]["latitude"],
                fields[j]["longitude"],
            )

            if distance <= radius_km:
                adjacency[i].append(j)
                adjacency[j].append(i)

    return adjacency


def _connected_components(
    adjacency: List[List[int]],
) -> List[List[int]]:
    visited = set()
    components: List[List[int]] = []

    for start in range(len(adjacency)):
        if start in visited:
            continue

        queue = deque([start])
        visited.add(start)

        component = []

        while queue:
            current = queue.popleft()
            component.append(current)

            for neighbour in adjacency[current]:
                if neighbour in visited:
                    continue

                visited.add(neighbour)
                queue.append(neighbour)

        components.append(component)

    return components


def _cluster_centroid(
    members: List[Dict[str, Any]],
) -> Dict[str, float]:
    """
    Biomass-weighted centroid.

    Larger estimated biomass fields contribute more to the
    representative collection point.
    """

    total_biomass = sum(
        max(
            0.0,
            _safe_float(
                field[
                    "recoverable_biomass_tonnes"
                ]
            ),
        )
        for field in members
    )

    if total_biomass <= 0:
        total_biomass = float(
            len(members)
        )

        weights = [
            1.0
            for _ in members
        ]
    else:
        weights = [
            max(
                0.0,
                _safe_float(
                    field[
                        "recoverable_biomass_tonnes"
                    ]
                ),
            )
            for field in members
        ]

    latitude = (
        sum(
            field["latitude"] * weight
            for field, weight
            in zip(members, weights)
        )
        / total_biomass
    )

    longitude = (
        sum(
            field["longitude"] * weight
            for field, weight
            in zip(members, weights)
        )
        / total_biomass
    )

    return {
        "latitude": latitude,
        "longitude": longitude,
    }


def build_clusters(
    fields: List[Dict[str, Any]],
    radius_km: float = DEFAULT_CLUSTER_RADIUS_KM,
    truck_capacity_tonnes: float = DEFAULT_TRUCK_CAPACITY_TONNES,
) -> List[Dict[str, Any]]:
    """Create collection clusters from field centroids."""

    radius_km = max(
        0.1,
        _safe_float(
            radius_km,
            DEFAULT_CLUSTER_RADIUS_KM,
        ),
    )

    truck_capacity_tonnes = max(
        0.1,
        _safe_float(
            truck_capacity_tonnes,
            DEFAULT_TRUCK_CAPACITY_TONNES,
        ),
    )

    if not fields:
        return []

    adjacency = _build_adjacency(
        fields,
        radius_km,
    )

    components = _connected_components(
        adjacency
    )

    clusters = []

    for cluster_index, component in enumerate(
        components,
        start=1,
    ):
        members = [
            fields[index]
            for index in component
        ]

        total_area = sum(
            field["area_hectares"]
            for field in members
        )

        gross_residue = sum(
            field[
                "gross_residue_tonnes"
            ]
            for field in members
        )

        recoverable = sum(
            field[
                "recoverable_biomass_tonnes"
            ]
            for field in members
        )

        centroid = _cluster_centroid(
            members
        )

        estimated_truckloads = (
            math.ceil(
                recoverable
                / truck_capacity_tonnes
            )
            if recoverable > 0
            else 0
        )

        clusters.append(
            {
                "cluster_id": (
                    f"cluster_{cluster_index:03d}"
                ),
                "radius_km": radius_km,
                "field_count": len(members),
                "field_ids": [
                    field["field_id"]
                    for field in members
                ],
                "total_area_hectares": (
                    total_area
                ),
                "total_area_acres": (
                    total_area * 2.47105
                ),
                "gross_residue_tonnes": (
                    gross_residue
                ),
                "recoverable_biomass_tonnes": (
                    recoverable
                ),
                "estimated_truckloads": (
                    estimated_truckloads
                ),
                "truck_capacity_tonnes": (
                    truck_capacity_tonnes
                ),
                "collection_centroid": centroid,
                "members": members,
            }
        )

    clusters.sort(
        key=lambda cluster: (
            -cluster[
                "recoverable_biomass_tonnes"
            ],
            cluster["cluster_id"],
        )
    )

    return clusters


# ============================================================
# PUBLIC API
# ============================================================

def get_all_clusters(
    radius_km: float = DEFAULT_CLUSTER_RADIUS_KM,
    truck_capacity_tonnes: float = DEFAULT_TRUCK_CAPACITY_TONNES,
    geojson_path: str = GEOJSON_PATH,
) -> Dict[str, Any]:
    """Return all collection clusters."""

    fields = load_fields(
        geojson_path
    )

    clusters = build_clusters(
        fields,
        radius_km=radius_km,
        truck_capacity_tonnes=truck_capacity_tonnes,
    )

    total_recoverable = sum(
        field[
            "recoverable_biomass_tonnes"
        ]
        for field in fields
    )

    return {
        "success": True,
        "field_count": len(fields),
        "cluster_count": len(clusters),
        "total_recoverable_biomass_tonnes": (
            total_recoverable
        ),
        "cluster_radius_km": radius_km,
        "truck_capacity_tonnes": (
            truck_capacity_tonnes
        ),
        "clusters": clusters,
        "methodology": {
            "clustering": (
                "Connected components using "
                "field-centroid distance"
            ),
            "distance": (
                "Haversine straight-line distance"
            ),
            "biomass": (
                "Area × assumed paddy yield × "
                "residue-to-product ratio × "
                "collection efficiency"
            ),
            "truckloads": (
                "Ceiling of cluster recoverable "
                "biomass divided by configurable "
                "truck capacity"
            ),
        },
        "validation_note": (
            "Collection clusters are an MVP planning "
            "model. They do not represent confirmed "
            "farmer participation, actual collection "
            "routes, road distances, or transporter "
            "capacity."
        ),
    }


def get_field_cluster(
    field_id: str,
    radius_km: float = DEFAULT_CLUSTER_RADIUS_KM,
    truck_capacity_tonnes: float = DEFAULT_TRUCK_CAPACITY_TONNES,
    geojson_path: str = GEOJSON_PATH,
) -> Dict[str, Any]:
    """Return the collection cluster for one source field or logical field group."""

    fields = load_fields(
        geojson_path
    )

    target_id = str(field_id).strip()
    source_ids = resolve_field_ids(target_id, geojson_path)

    # Logical-field behavior: a request such as "34" combines all
    # resolved source-year cluster results while keeping each source
    # field's real spatial cluster intact. A logical field with only one
    # source-year record (for example 343 -> 2021_343) is returned through
    # the same aggregation path without inventing another year.
    if target_id not in source_ids and source_ids:
        source_clusters = []

        for source_id in source_ids:
            source_clusters.append(
                get_field_cluster(
                    field_id=source_id,
                    radius_km=radius_km,
                    truck_capacity_tonnes=truck_capacity_tonnes,
                    geojson_path=geojson_path,
                )
            )

        combined_field_ids = []
        combined_members = []
        seen_ids = set()
        total_area = 0.0
        total_gross = 0.0
        total_recoverable = 0.0
        centroid_weight = 0.0
        weighted_lat = 0.0
        weighted_lon = 0.0

        for source_result in source_clusters:
            cluster = source_result.get("collection_cluster") or {}
            total_area += float(cluster.get("total_area_hectares", 0.0))
            total_gross += float(cluster.get("gross_residue_tonnes", 0.0))
            total_recoverable += float(
                cluster.get("recoverable_biomass_tonnes", 0.0)
            )

            cluster_centroid = cluster.get("collection_centroid") or {}
            weight = max(0.0, float(cluster.get("recoverable_biomass_tonnes", 0.0)))
            if weight > 0 and cluster_centroid.get("latitude") is not None:
                centroid_weight += weight
                weighted_lat += float(cluster_centroid["latitude"]) * weight
                weighted_lon += float(cluster_centroid["longitude"]) * weight

            for member_id in cluster.get("field_ids", []):
                member_id = str(member_id)
                if member_id not in seen_ids:
                    seen_ids.add(member_id)
                    combined_field_ids.append(member_id)

            combined_members.extend(cluster.get("members") or [])

        combined_members.sort(
            key=lambda member: str(member.get("field_id", ""))
        )

        combined_cluster = {
            "cluster_id": f"group_{target_id}",
            "radius_km": radius_km,
            "field_count": len(combined_field_ids),
            "field_ids": combined_field_ids,
            "total_area_hectares": total_area,
            "total_area_acres": total_area * 2.47105,
            "gross_residue_tonnes": total_gross,
            "recoverable_biomass_tonnes": total_recoverable,
            "estimated_truckloads": (
                math.ceil(total_recoverable / truck_capacity_tonnes)
                if total_recoverable > 0
                else 0
            ),
            "truck_capacity_tonnes": truck_capacity_tonnes,
            "collection_centroid": (
                {
                    "latitude": weighted_lat / centroid_weight,
                    "longitude": weighted_lon / centroid_weight,
                }
                if centroid_weight > 0
                else None
            ),
            "members": combined_members,
            "member_clusters": [
                result.get("collection_cluster")
                for result in source_clusters
            ],
            "aggregation_note": (
                "The logical field combines the independent source-year collection clusters. "
                "The subclusters remain spatially separate; no artificial cross-year adjacency is created."
            ),
        }

        summary = group_summary(target_id, geojson_path)

        source_recoverable = sum(
            float(
                (result.get("aggregation_effect") or {}).get(
                    "individual_field_recoverable_tonnes",
                    0.0,
                )
            )
            for result in source_clusters
        )

        return {
            "success": True,
            "field_id": target_id,
            "field": {
                "field_id": target_id,
                "field_name": f"Logical Field {target_id}",
                "category": "combined_source_year_group",
                "source_field_ids": summary["source_field_ids"],
            },
            "collection_cluster": combined_cluster,
            "cluster_radius_km": radius_km,
            "truck_capacity_tonnes": truck_capacity_tonnes,
            "source_field_ids": summary["source_field_ids"],
            "source_field_count": summary["source_field_count"],
            "member_clusters": source_clusters,
            "aggregation_effect": {
                "individual_field_recoverable_tonnes": source_recoverable,
                "cluster_recoverable_tonnes": total_recoverable,
                "additional_fields_aggregated": max(
                    0,
                    len(combined_field_ids) - len(source_ids),
                ),
                "estimated_truckloads": combined_cluster["estimated_truckloads"],
            },
            "validation_note": (
                "Collection clusters are an MVP planning model. For a logical multi-year field, "
                "each source-year geometry is clustered independently and the resulting supplies "
                "are aggregated; this does not confirm farmer participation, collection routes, "
                "road distances, or transporter capacity."
            ),
        }

    target = next(
        (
            field
            for field in fields
            if str(field["field_id"]) == target_id
        ),
        None,
    )

    if target is None:
        raise ValueError(
            f"Field {field_id} not found"
        )

    clusters = build_clusters(
        fields,
        radius_km=radius_km,
        truck_capacity_tonnes=truck_capacity_tonnes,
    )

    selected_cluster = next(
        (
            cluster
            for cluster in clusters
            if target_id
            in [
                str(member_id)
                for member_id
                in cluster["field_ids"]
            ]
        ),
        None,
    )

    if selected_cluster is None:
        raise ValueError(
            f"No cluster found for field {field_id}"
        )

    return {
        "success": True,
        "field_id": target_id,
        "field": target,
        "collection_cluster": selected_cluster,
        "cluster_radius_km": radius_km,
        "truck_capacity_tonnes": (
            truck_capacity_tonnes
        ),
        "aggregation_effect": {
            "individual_field_recoverable_tonnes": (
                target[
                    "recoverable_biomass_tonnes"
                ]
            ),
            "cluster_recoverable_tonnes": (
                selected_cluster[
                    "recoverable_biomass_tonnes"
                ]
            ),
            "additional_fields_aggregated": (
                max(
                    0,
                    selected_cluster[
                        "field_count"
                    ] - 1,
                )
            ),
            "estimated_truckloads": (
                selected_cluster[
                    "estimated_truckloads"
                ]
            ),
        },
        "validation_note": (
            "Aggregation reduces the small-load problem conceptually by combining nearby fields. "
            "It does not confirm that farmers will participate or that a single truck will collect "
            "the entire cluster."
        ),
    }


if __name__ == "__main__":
    result = get_field_cluster(
        "2021_34"
    )

    print(
        json.dumps(
            result,
            indent=2,
            default=str,
        )
    )
