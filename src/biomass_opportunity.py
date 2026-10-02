"""Biomass facility matching for Project Parali.

This module matches an estimated field biomass supply to a small, sourced
facility registry. Facility coordinates are approximate when only a village
location is available; therefore distances are straight-line estimates, not
road transport distances.
"""

import json
import math
import os
from typing import Any, Dict, List, Tuple

from .field_context import resolve_field_context


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GEOJSON_PATH = os.path.join(
    BASE_DIR, "data", "processed", "sangrur_fields.geojson"
)

# Approximate location of Bhutal Kalan / Verbio plant area.
# The government documents identify the plant at Village Bhutal Kalan,
# Lehragaga-Raidharana Road. The available public map coordinate is for
# Bhutal Kalan village, so it must NOT be presented as an exact plant pin.
FACILITIES: List[Dict[str, Any]] = [
    {
        "facility_id": "verbio_bhutal_kalan",
        "name": "Verbio India Pvt. Ltd. CBG Plant",
        "type": "Compressed Bio Gas (CBG)",
        "district": "Sangrur",
        "location": "Bhutal Kalan, Lehragaga, Sangrur, Punjab",
        "latitude": 29.90739,
        "longitude": 75.87456,
        "coordinate_quality": "approximate village-level location",
        "reported_annual_straw_input_tonnes": 100000,
        "reported_max_daily_straw_input_tonnes": 300,
        "source_notes": [
            "Punjab Pollution Control Board records the Verbio facility at Village Bhutal Kalan, Lehragaga-Raidharana Road.",
            "MNRE BioUrja lists Verbio India Pvt. Ltd. in Sangrur as commissioned with 33,000 kg/day CBG capacity.",
            "Government of India reported a planned maximum processing rate of 300 tonnes/day of paddy straw.",
        ],
    },
    {
        "facility_id": "sangrur_rng_fatehgarh_panjgraian",
        "name": "Sangrur RNG Private Limited CBG Plant",
        "type": "Compressed Bio Gas (CBG)",
        "district": "Sangrur",
        "location": "Fatehgarh Panjgraian, Dhuri, Sangrur, Punjab",
        "latitude": 30.524054,
        "longitude": 75.703790,
        "coordinate_quality": "approximate village-level location",
        "reported_capacity_tpd": 14840 / 1000,
        "source_notes": [
            "Forest Clearance documentation places the plant at Village Fatehgarh Panjgraian, Tehsil Dhuri, District Sangrur.",
            "MNRE BioUrja lists Sangrur RNG Private Limited in Sangrur as commissioned with 14,840 kg/day CBG capacity.",
            "The coordinate is a village-level reference, not an exact plant-gate coordinate.",
        ],
    },
    {
        "facility_id": "patiala_rng_jaikhar",
        "name": "Patiala RNG Private Limited CBG Plant",
        "type": "Compressed Bio Gas (CBG)",
        "district": "Patiala",
        "location": "Jaikhar, Patran, Patiala, Punjab",
        "latitude": 29.945092,
        "longitude": 76.145144,
        "coordinate_quality": "project-reported coordinates",
        "reported_paddy_straw_input_tpd": 200,
        "reported_cbg_output_tpd": 20,
        "source_notes": [
            "Project environmental/social due-diligence documentation gives coordinates 29.945092, 76.145144 for the Jaikhar site.",
            "The same project documentation reports 200 tonnes/day paddy straw intake capacity and 20 tonnes/day CBG output.",
            "MNRE BioUrja lists Patiala RNG Private Limited in Patiala as commissioned with 14,800 kg/day CBG capacity.",
        ],
    },
]

DEFAULT_SEARCH_RADIUS_KM = 50.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = (
        math.sin(dp / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    )
    a = min(1.0, max(0.0, a))
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _opportunity_status(distance_km: float, recoverable_tonnes: float) -> str:
    if recoverable_tonnes <= 0:
        return "no_recoverable_biomass"
    if distance_km <= 10:
        return "high_logistics_potential"
    if distance_km <= 25:
        return "nearby_facility"
    if distance_km <= 50:
        return "regional_facility"
    return "outside_default_radius"


def _match_source_field(
    source_field_id: str,
    recoverable_biomass_tonnes: float,
    search_radius_km: float,
) -> Dict[str, Any]:
    """Match one concrete source-year field to every registered facility."""
    context = resolve_field_context(source_field_id, GEOJSON_PATH)
    centroid = context.get("centroid") or {}

    latitude = centroid.get("latitude")
    longitude = centroid.get("longitude")

    if latitude is None or longitude is None:
        raise ValueError(
            f"Field {source_field_id} has no usable centroid"
        )

    recoverable = max(0.0, float(recoverable_biomass_tonnes))
    ranked_facilities = []

    for facility in FACILITIES:
        distance = haversine_km(
            float(latitude),
            float(longitude),
            facility["latitude"],
            facility["longitude"],
        )

        item = dict(facility)
        item["distance_km"] = round(distance, 2)
        item["estimated_supply_tonnes"] = round(recoverable, 3)
        item["opportunity_status"] = _opportunity_status(
            distance,
            recoverable,
        )
        item["screening_status"] = (
            "within_search_radius"
            if distance <= search_radius_km
            else "outside_search_radius"
        )
        item["distance_method"] = (
            "straight-line Haversine distance from source-year field geometry centroid"
        )
        item["source_field_id"] = source_field_id
        ranked_facilities.append(item)

    ranked_facilities.sort(key=lambda item: item["distance_km"])

    within_radius = [
        item
        for item in ranked_facilities
        if item["distance_km"] <= search_radius_km
    ]

    nearest = ranked_facilities[0] if ranked_facilities else None

    return {
        "field_id": source_field_id,
        "field_centroid": {
            "latitude": round(float(latitude), 6),
            "longitude": round(float(longitude), 6),
        },
        "recoverable_biomass_tonnes": round(recoverable, 3),
        "search_radius_km": search_radius_km,
        "nearest_facility": nearest,
        "facilities": ranked_facilities,
        "facilities_within_search_radius": within_radius,
        "facility_count": len(ranked_facilities),
        "within_radius_count": len(within_radius),
        "nearest_distance_km": nearest["distance_km"] if nearest else None,
        "matching_status": (
            "facility_found_within_radius"
            if within_radius
            else "nearest_facility_outside_radius"
            if nearest
            else "no_registered_facilities"
        ),
        "source_field_ids": context["source_field_ids"],
        "source_field_count": context["source_field_count"],
        "geometry_mode": context["geometry_mode"],
    }


def match_facilities(
    field_id: str,
    recoverable_biomass_tonnes: float,
    search_radius_km: float = DEFAULT_SEARCH_RADIUS_KM,
) -> Dict[str, Any]:
    """
    Match a logical or source field against every registered biomass facility.

    The shared field context is the only source of truth for logical-field
    resolution. For a multi-source logical field such as ``34``, each source
    geometry is evaluated independently for facility distance, while the
    caller-provided recoverable biomass total is allocated across source fields
    in proportion to source-field area.
    """
    normalized_id = str(field_id).strip()
    if not normalized_id:
        raise ValueError("field_id cannot be empty")

    try:
        search_radius = float(search_radius_km)
    except (TypeError, ValueError):
        search_radius = DEFAULT_SEARCH_RADIUS_KM

    if not math.isfinite(search_radius) or search_radius <= 0:
        raise ValueError("search_radius_km must be greater than 0")

    total_recoverable = max(
        0.0,
        float(recoverable_biomass_tonnes),
    )

    context = resolve_field_context(
        normalized_id,
        GEOJSON_PATH,
    )

    source_fields = context.get("source_fields") or []
    source_ids = context.get("source_field_ids") or []

    if not source_ids:
        raise ValueError(
            f"Field {normalized_id} has no source-year field records"
        )

    total_area = sum(
        max(0.0, float(source.get("area_hectares") or 0.0))
        for source in source_fields
    )

    member_results: List[Dict[str, Any]] = []
    source_allocation: List[Dict[str, Any]] = []

    for index, source_id in enumerate(source_ids):
        source = source_fields[index] if index < len(source_fields) else {}
        source_area = max(
            0.0,
            float(source.get("area_hectares") or 0.0),
        )

        if total_area > 0:
            member_supply = total_recoverable * source_area / total_area
        else:
            member_supply = total_recoverable / len(source_ids)

        source_allocation.append(
            {
                "field_id": source_id,
                "area_hectares": round(source_area, 6),
                "recoverable_biomass_tonnes": round(member_supply, 3),
                "allocation_method": (
                    "proportional_to_source_field_area"
                    if total_area > 0
                    else "equal_split_fallback"
                ),
            }
        )

        member_results.append(
            _match_source_field(
                source_field_id=source_id,
                recoverable_biomass_tonnes=member_supply,
                search_radius_km=search_radius,
            )
        )

    facility_map: Dict[str, Dict[str, Any]] = {}

    for member_match in member_results:
        source_id = member_match["field_id"]
        member_supply = float(
            member_match.get("recoverable_biomass_tonnes") or 0.0
        )

        for facility in member_match.get("facilities", []):
            facility_id = str(facility.get("facility_id"))

            if facility_id not in facility_map:
                facility_map[facility_id] = {
                    key: value
                    for key, value in facility.items()
                    if key not in {
                        "estimated_supply_tonnes",
                        "source_field_id",
                    }
                }
                facility_map[facility_id]["estimated_supply_tonnes"] = 0.0
                facility_map[facility_id]["member_distances"] = []

            aggregate = facility_map[facility_id]
            aggregate["estimated_supply_tonnes"] += member_supply
            aggregate["member_distances"].append(
                {
                    "field_id": source_id,
                    "distance_km": facility.get("distance_km"),
                    "screening_status": facility.get("screening_status"),
                    "allocated_supply_tonnes": round(
                        member_supply,
                        3,
                    ),
                }
            )

            distance = float(
                facility.get("distance_km") or 0.0
            )
            current_min = float(
                aggregate.get("distance_km") or distance
            )
            aggregate["distance_km"] = min(
                current_min,
                distance,
            )

    ranked_facilities = list(facility_map.values())
    ranked_facilities.sort(
        key=lambda item: item["distance_km"]
    )

    for facility in ranked_facilities:
        facility["estimated_supply_tonnes"] = round(
            facility["estimated_supply_tonnes"],
            3,
        )
        facility["opportunity_status"] = _opportunity_status(
            facility["distance_km"],
            total_recoverable,
        )
        facility["screening_status"] = (
            "within_search_radius"
            if facility["distance_km"] <= search_radius
            else "outside_search_radius"
        )
        facility["distance_method"] = (
            "minimum straight-line Haversine distance across source-year field geometries"
            if len(source_ids) > 1
            else "straight-line Haversine distance from source-year field geometry centroid"
        )

    within_radius = [
        item
        for item in ranked_facilities
        if item["distance_km"] <= search_radius
    ]

    nearest = ranked_facilities[0] if ranked_facilities else None
    centroid = context.get("centroid")

    return {
        "field_id": normalized_id,
        "field_centroid": (
            {
                "latitude": round(float(centroid["latitude"]), 6),
                "longitude": round(float(centroid["longitude"]), 6),
            }
            if centroid
            else None
        ),
        "recoverable_biomass_tonnes": round(total_recoverable, 3),
        "search_radius_km": search_radius,
        "nearest_facility": nearest,
        "facilities": ranked_facilities,
        "facilities_within_search_radius": within_radius,
        "facility_count": len(ranked_facilities),
        "within_radius_count": len(within_radius),
        "nearest_distance_km": (
            nearest["distance_km"] if nearest else None
        ),
        "matching_status": (
            "facility_found_within_radius"
            if within_radius
            else "nearest_facility_outside_radius"
            if nearest
            else "no_registered_facilities"
        ),
        "source_field_ids": context["source_field_ids"],
        "source_field_count": context["source_field_count"],
        "geometry_mode": context["geometry_mode"],
        "source_field_allocation": source_allocation,
        "member_centroids": [
            item["field_centroid"] | {"field_id": item["field_id"]}
            for item in member_results
            if item.get("field_centroid")
        ],
        "member_opportunities": member_results,
        "aggregation": {
            "method": (
                "Evaluate each source-year field separately and aggregate facility supply"
            ),
            "distance_rule": (
                "Minimum member-to-facility distance for aggregate facility screening"
            ),
            "supply_rule": (
                "Caller-provided logical-field recoverable biomass allocated "
                "proportionally by source-field area"
            ),
            "centroid_rule": (
                context.get("centroid", {}).get("method")
                if context.get("centroid")
                else None
            ),
        },
        "methodology": (
            "Every registered facility is evaluated for each source-year field "
            "using straight-line Haversine distance. Logical-field biomass is "
            "aggregated across source-year records, while distance remains tied "
            "to the actual source geometry. The shared field context provides "
            "field resolution, geometry, area, and centroid metadata."
        ),
        "limitations": [
            "The facility registry is limited to the currently sourced facilities.",
            "Some facility coordinates are approximate village/site references rather than exact plant-gate coordinates.",
            "Road distance, travel time, transport cost, seasonal accessibility, and facility spare capacity are not yet modeled.",
            "Estimated supply is the field group's recoverable biomass estimate; it is not a confirmed purchase quantity.",
            "Proportional source-field biomass allocation is a modeling assumption used only for facility-level screening of multi-source fields.",
        ],
    }
