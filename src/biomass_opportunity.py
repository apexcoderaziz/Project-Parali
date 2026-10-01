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


def _load_geojson() -> Dict[str, Any]:
    with open(GEOJSON_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def _field_geometry(field_id: str) -> Dict[str, Any]:
    geojson = _load_geojson()
    for feature in geojson.get("features", []):
        properties = feature.get("properties", {})
        if str(properties.get("field_id", "")).strip() == field_id:
            return feature.get("geometry") or {}
    raise KeyError(f"Field {field_id} not found")


def _coordinate_pairs(coords: Any):
    if isinstance(coords, (list, tuple)):
        if len(coords) >= 2 and all(isinstance(v, (int, float)) for v in coords[:2]):
            yield float(coords[0]), float(coords[1])
            return
        for item in coords:
            yield from _coordinate_pairs(item)


def _centroid_from_geometry(geometry: Dict[str, Any]) -> Tuple[float, float]:
    coordinates = geometry.get("coordinates")
    pairs = list(_coordinate_pairs(coordinates))
    if not pairs:
        raise ValueError("Field geometry has no usable coordinates")

    lon = sum(pair[0] for pair in pairs) / len(pairs)
    lat = sum(pair[1] for pair in pairs) / len(pairs)
    return lat, lon


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


def match_facilities(
    field_id: str,
    recoverable_biomass_tonnes: float,
    search_radius_km: float = DEFAULT_SEARCH_RADIUS_KM,
) -> Dict[str, Any]:
    """
    Match a field against every registered biomass facility.

    Every facility is evaluated and ranked. The search radius is used only
    for screening/classification; it does not hide the nearest facility.
    Distances are straight-line Haversine estimates, not road distances.
    """
    field_id = str(field_id).strip()
    geometry = _field_geometry(field_id)
    field_lat, field_lon = _centroid_from_geometry(geometry)

    recoverable = max(0.0, float(recoverable_biomass_tonnes))

    ranked_facilities = []

    for facility in FACILITIES:
        distance = haversine_km(
            field_lat,
            field_lon,
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
            "straight-line haversine distance from field geometry centroid"
        )

        ranked_facilities.append(item)

    ranked_facilities.sort(key=lambda item: item["distance_km"])

    within_radius = [
        item
        for item in ranked_facilities
        if item["distance_km"] <= search_radius_km
    ]

    nearest = ranked_facilities[0] if ranked_facilities else None

    return {
        "field_id": field_id,
        "field_centroid": {
            "latitude": round(field_lat, 6),
            "longitude": round(field_lon, 6),
        },
        "recoverable_biomass_tonnes": round(recoverable, 3),
        "search_radius_km": search_radius_km,
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
        "methodology": (
            "Every registered facility is evaluated using straight-line "
            "Haversine distance from the field geometry centroid. Facilities "
            "are ranked by distance. The search radius is a screening "
            "boundary and does not hide the nearest facility."
        ),
        "limitations": [
            "The facility registry is still limited to the currently sourced facilities.",
            "Some facility coordinates are approximate village/site references rather than exact plant-gate coordinates.",
            "Road distance, travel time, transport cost, seasonal accessibility, and facility spare capacity are not yet modeled.",
            "Estimated supply is the field's recoverable biomass estimate; it is not a confirmed purchase quantity.",
        ],
    }

