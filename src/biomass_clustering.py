"""Biomass Collection Clustering for Project Parali.

Phase 5 architecture:

    logical field ID
          |
          v
    field_context.py
          |
          +--> source-year records (2020_34 + 2021_34)
          |
          +--> combined area / centroid / geometry context
          |
          v
    residue_estimation.py
          |
          v
    logical-field biomass supply
          |
          v
    collection clustering

The clustering layer groups logical fields rather than treating historical
source-year records as independent physical fields. This prevents a field
such as 34 from being double-counted when both 2020_34 and 2021_34 exist.

The module remains an MVP planning model:
- clustering uses straight-line Haversine distance between logical-field
  representative centroids;
- field biomass comes from the shared residue-estimation module;
- truckloads use a configurable capacity assumption;
- no road routing, transporter quotation, farmer participation, or confirmed
  collection contract is claimed.
"""

from __future__ import annotations

import json
import math
import os
from collections import deque
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from .field_context import get_field_context, extract_field_number
    from .residue_estimation import estimate_residue
except ImportError:
    from field_context import get_field_context, extract_field_number
    from residue_estimation import estimate_residue


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

DEFAULT_CLUSTER_RADIUS_KM = 5.0
DEFAULT_TRUCK_CAPACITY_TONNES = 10.0


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


def _normalise_positive(value: Any, default: float) -> float:
    number = _safe_float(value, default)
    if number <= 0:
        return default
    return number


def _field_number_from_source_id(source_field_id: str) -> Optional[str]:
    """Return the logical numeric field component from a source ID."""

    try:
        value = extract_field_number(str(source_field_id))
        return str(value) if value is not None else None
    except Exception:
        text = str(source_field_id).strip()
        if "_" in text:
            suffix = text.split("_")[-1].strip()
            return suffix or None
        return text or None


def _logical_ids_from_geojson(geojson_path: str = GEOJSON_PATH) -> List[str]:
    """Return unique logical field IDs represented by the GeoJSON source rows."""

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

    logical_ids = set()

    for feature in geojson.get("features", []):
        properties = feature.get("properties") or {}
        source_id = (
            properties.get("field_id")
            or properties.get("id")
            or properties.get("ID")
            or properties.get("Id")
        )

        if source_id is None:
            continue

        logical_number = _field_number_from_source_id(str(source_id))
        if logical_number:
            logical_ids.add(logical_number)

    def sort_key(value: str):
        try:
            return (0, int(value))
        except (TypeError, ValueError):
            return (1, str(value))

    return sorted(logical_ids, key=sort_key)


def _iter_points(coordinates: Any) -> Iterable[Tuple[float, float]]:
    """Yield (longitude, latitude) coordinate pairs from nested GeoJSON."""

    if not isinstance(coordinates, (list, tuple)):
        return

    if (
        len(coordinates) >= 2
        and isinstance(coordinates[0], (int, float))
        and isinstance(coordinates[1], (int, float))
    ):
        yield float(coordinates[0]), float(coordinates[1])
        return

    for child in coordinates:
        yield from _iter_points(child)


def _geometry_centroid(
    geometry: Optional[Dict[str, Any]],
) -> Optional[Dict[str, float]]:
    """Return a lightweight coordinate-average centroid."""

    if not geometry:
        return None

    points = list(
        _iter_points(
            geometry.get("coordinates")
        )
    )

    if not points:
        return None

    longitude = sum(point[0] for point in points) / len(points)
    latitude = sum(point[1] for point in points) / len(points)

    return {
        "latitude": latitude,
        "longitude": longitude,
    }


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
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1)
        * math.cos(phi2)
        * math.sin(delta_lambda / 2) ** 2
    )

    a = min(1.0, max(0.0, a))

    return 2 * radius * math.asin(math.sqrt(a))


# ============================================================
# LOGICAL FIELD LOAD / BIOMASS
# ============================================================

def load_fields(
    geojson_path: str = GEOJSON_PATH,
) -> List[Dict[str, Any]]:
    """Load unique logical fields with shared context and residue supply."""

    logical_ids = _logical_ids_from_geojson(geojson_path)
    fields: List[Dict[str, Any]] = []

    for logical_id in logical_ids:
        context = get_field_context(
            logical_id,
            geojson_path,
        )

        centroid = context.get("centroid")
        if not centroid:
            centroid = _geometry_centroid(context.get("geometry"))

        if not centroid:
            continue

        try:
            residue = estimate_residue(logical_id)
        except Exception as exc:
            # Keep the logical field available for clustering only when its
            # context can be resolved; a failed biomass calculation should be
            # explicit rather than silently inventing mass.
            residue = {
                "success": False,
                "gross_residue_tonnes": 0.0,
                "recoverable_biomass_tonnes": 0.0,
                "error": str(exc),
            }

        gross_residue = max(
            0.0,
            _safe_float(
                residue.get("gross_residue_tonnes")
            ),
        )
        recoverable = max(
            0.0,
            _safe_float(
                residue.get("recoverable_biomass_tonnes")
            ),
        )

        source_fields = context.get("source_fields") or []
        source_field_ids = context.get("source_field_ids") or []
        categories = context.get("categories") or []

        source_estimates = residue.get("source_estimates") or []

        fields.append(
            {
                "field_id": str(logical_id),
                "logical_field_id": str(logical_id),
                "field_name": (
                    source_fields[0].get("field_name")
                    if source_fields
                    else None
                ),
                "category": (
                    categories[0]
                    if len(categories) == 1
                    else "mixed"
                    if categories
                    else "unknown"
                ),
                "source_field_ids": [
                    str(value)
                    for value in source_field_ids
                ],
                "source_field_count": len(source_field_ids),
                "geometry_mode": context.get("geometry_mode"),
                "area_hectares": _safe_float(
                    (context.get("area") or {}).get("hectares")
                ),
                "area_acres": _safe_float(
                    (context.get("area") or {}).get("acres")
                ),
                "latitude": _safe_float(
                    centroid.get("latitude")
                ),
                "longitude": _safe_float(
                    centroid.get("longitude")
                ),
                "gross_residue_tonnes": gross_residue,
                "recoverable_biomass_tonnes": recoverable,
                "residue_estimate_success": bool(
                    residue.get("success", False)
                ),
                "residue_estimate_error": residue.get("error"),
                "source_estimates": source_estimates,
            }
        )

    return fields


# ============================================================
# CLUSTER GRAPH
# ============================================================

def _build_adjacency(
    fields: List[Dict[str, Any]],
    radius_km: float,
) -> List[List[int]]:
    """Connect logical fields whose representative centroids are close."""

    adjacency = [
        []
        for _ in fields
    ]

    for index in range(len(fields)):
        for other_index in range(index + 1, len(fields)):
            distance = _haversine_km(
                fields[index]["latitude"],
                fields[index]["longitude"],
                fields[other_index]["latitude"],
                fields[other_index]["longitude"],
            )

            if distance <= radius_km:
                adjacency[index].append(other_index)
                adjacency[other_index].append(index)

    return adjacency


def _connected_components(
    adjacency: List[List[int]],
) -> List[List[int]]:
    """Return connected components of the field proximity graph."""

    visited = set()
    components: List[List[int]] = []

    for start in range(len(adjacency)):
        if start in visited:
            continue

        queue = deque([start])
        visited.add(start)
        component: List[int] = []

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
    """Return a recoverable-biomass-weighted cluster centroid."""

    weights = [
        max(
            0.0,
            _safe_float(
                member.get("recoverable_biomass_tonnes")
            ),
        )
        for member in members
    ]

    total_weight = sum(weights)

    if total_weight <= 0:
        weights = [1.0 for _ in members]
        total_weight = float(len(members) or 1)

    latitude = sum(
        member["latitude"] * weight
        for member, weight in zip(members, weights)
    ) / total_weight

    longitude = sum(
        member["longitude"] * weight
        for member, weight in zip(members, weights)
    ) / total_weight

    return {
        "latitude": latitude,
        "longitude": longitude,
    }


# ============================================================
# CLUSTER CONSTRUCTION
# ============================================================

def build_clusters(
    fields: List[Dict[str, Any]],
    radius_km: float = DEFAULT_CLUSTER_RADIUS_KM,
    truck_capacity_tonnes: float = DEFAULT_TRUCK_CAPACITY_TONNES,
) -> List[Dict[str, Any]]:
    """Create collection clusters from logical-field centroids."""

    radius_km = _normalise_positive(
        radius_km,
        DEFAULT_CLUSTER_RADIUS_KM,
    )
    truck_capacity_tonnes = _normalise_positive(
        truck_capacity_tonnes,
        DEFAULT_TRUCK_CAPACITY_TONNES,
    )

    if not fields:
        return []

    adjacency = _build_adjacency(
        fields,
        radius_km,
    )
    components = _connected_components(adjacency)

    clusters: List[Dict[str, Any]] = []

    for cluster_index, component in enumerate(
        components,
        start=1,
    ):
        members = [
            fields[index]
            for index in component
        ]

        total_area = sum(
            _safe_float(member.get("area_hectares"))
            for member in members
        )

        gross_residue = sum(
            _safe_float(member.get("gross_residue_tonnes"))
            for member in members
        )

        recoverable = sum(
            _safe_float(member.get("recoverable_biomass_tonnes"))
            for member in members
        )

        estimated_truckloads = (
            math.ceil(
                recoverable / truck_capacity_tonnes
            )
            if recoverable > 0
            else 0
        )

        member_ids = [
            str(member["field_id"])
            for member in members
        ]

        clusters.append(
            {
                "cluster_id": f"cluster_{cluster_index:03d}",
                "radius_km": round(radius_km, 3),
                "field_count": len(members),
                "field_ids": member_ids,
                "total_area_hectares": round(total_area, 6),
                "total_area_acres": round(
                    total_area * 2.47105,
                    6,
                ),
                "gross_residue_tonnes": round(
                    gross_residue,
                    6,
                ),
                "recoverable_biomass_tonnes": round(
                    recoverable,
                    6,
                ),
                "estimated_truckloads": estimated_truckloads,
                "truck_capacity_tonnes": round(
                    truck_capacity_tonnes,
                    3,
                ),
                "collection_centroid": _cluster_centroid(members),
                "members": members,
            }
        )

    clusters.sort(
        key=lambda cluster: (
            -cluster["recoverable_biomass_tonnes"],
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
    """Return all logical-field collection clusters."""

    fields = load_fields(geojson_path)
    clusters = build_clusters(
        fields,
        radius_km=radius_km,
        truck_capacity_tonnes=truck_capacity_tonnes,
    )

    total_area = sum(
        _safe_float(field.get("area_hectares"))
        for field in fields
    )
    total_recoverable = sum(
        _safe_float(field.get("recoverable_biomass_tonnes"))
        for field in fields
    )
    total_gross = sum(
        _safe_float(field.get("gross_residue_tonnes"))
        for field in fields
    )

    return {
        "success": True,
        "field_count": len(fields),
        "cluster_count": len(clusters),
        "total_area_hectares": round(total_area, 6),
        "total_area_acres": round(total_area * 2.47105, 6),
        "total_gross_residue_tonnes": round(total_gross, 6),
        "total_recoverable_biomass_tonnes": round(
            total_recoverable,
            6,
        ),
        "cluster_radius_km": radius_km,
        "truck_capacity_tonnes": truck_capacity_tonnes,
        "fields": fields,
        "clusters": clusters,
        "methodology": {
            "field_unit": (
                "Logical field ID resolved through shared field_context; "
                "source-year records are not double-counted as separate fields."
            ),
            "clustering": (
                "Connected components using logical-field representative "
                "centroid distance."
            ),
            "distance": "Haversine straight-line distance",
            "biomass": (
                "Shared residue_estimation module using logical-field area "
                "and configured agronomic assumptions."
            ),
            "truckloads": (
                "Ceiling of cluster recoverable biomass divided by the "
                "configurable truck capacity."
            ),
        },
        "validation_note": (
            "Collection clusters are an MVP planning model. They do not "
            "confirm farmer participation, actual collection routes, road "
            "distances, transporter availability, or facility acceptance."
        ),
    }


def get_field_cluster(
    field_id: str,
    radius_km: float = DEFAULT_CLUSTER_RADIUS_KM,
    truck_capacity_tonnes: float = DEFAULT_TRUCK_CAPACITY_TONNES,
    geojson_path: str = GEOJSON_PATH,
) -> Dict[str, Any]:
    """Return the logical collection cluster containing one field."""

    normalized_id = str(field_id).strip()
    if not normalized_id:
        raise ValueError("field_id cannot be empty")

    fields = load_fields(geojson_path)

    # Resolve any exact source-year ID into its logical field number.
    try:
        context = get_field_context(
            normalized_id,
            geojson_path,
        )
        logical_target_id = str(
            context.get("logical_field_number")
            or context.get("logical_field_id")
            or normalized_id
        )
    except Exception:
        logical_target_id = normalized_id

    target = next(
        (
            field
            for field in fields
            if str(field["field_id"]) == logical_target_id
        ),
        None,
    )

    if target is None:
        # A non-numeric/custom ID can still be matched directly.
        target = next(
            (
                field
                for field in fields
                if str(field["field_id"]) == normalized_id
            ),
            None,
        )
        logical_target_id = normalized_id if target else logical_target_id

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
            if logical_target_id in [
                str(member_id)
                for member_id in cluster["field_ids"]
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
        "field_id": normalized_id,
        "logical_field_id": logical_target_id,
        "field": target,
        "collection_cluster": selected_cluster,
        "cluster_radius_km": radius_km,
        "truck_capacity_tonnes": truck_capacity_tonnes,
        "aggregation_effect": {
            "individual_field_recoverable_tonnes": target[
                "recoverable_biomass_tonnes"
            ],
            "cluster_recoverable_tonnes": selected_cluster[
                "recoverable_biomass_tonnes"
            ],
            "additional_logical_fields_aggregated": max(
                0,
                selected_cluster["field_count"] - 1,
            ),
            "estimated_truckloads": selected_cluster[
                "estimated_truckloads"
            ],
        },
        "validation_note": (
            "Aggregation combines nearby logical fields for planning. It does "
            "not establish farmer participation or guarantee that a single "
            "truck will collect the entire cluster."
        ),
    }


if __name__ == "__main__":
    result = get_field_cluster("34")
    print(
        json.dumps(
            result,
            indent=2,
            default=str,
        )
    )
