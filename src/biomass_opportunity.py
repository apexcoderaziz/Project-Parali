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

from .field_grouping import group_summary, resolve_field_ids


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

    source_field_ids = resolve_field_ids(
        field_id,
        GEOJSON_PATH,
    )

    # A bare field number such as "34" is a logical field group. It can
    # resolve to multiple source-year records (2020_34 + 2021_34) or to only
    # one source-year record (for example 343 -> 2021_343). Both cases must
    # use the source-field aggregation path so the bare logical ID is never
    # passed to _field_geometry(), which only knows source IDs.
    #
    # Evaluate each source field separately so distance-sensitive logistics
    # remain tied to the actual source-year geometry.
    if field_id not in source_field_ids and source_field_ids:
        try:
            from .residue_estimation import estimate_residue
        except ImportError:
            from residue_estimation import estimate_residue

        member_results = []
        facility_map: Dict[str, Dict[str, Any]] = {}
        total_recoverable = 0.0

        for source_id in source_field_ids:
            residue = estimate_residue(source_id)
            recoverable_member = float(
                residue.get("recoverable_biomass_tonnes", 0.0)
            )
            total_recoverable += recoverable_member

            member_match = match_facilities(
                field_id=source_id,
                recoverable_biomass_tonnes=recoverable_member,
                search_radius_km=search_radius_km,
            )

            member_results.append(member_match)

            for facility in member_match.get("facilities", []):
                facility_id = str(facility.get("facility_id"))
                if facility_id not in facility_map:
                    facility_map[facility_id] = dict(facility)
                    facility_map[facility_id]["estimated_supply_tonnes"] = 0.0
                    facility_map[facility_id]["member_distances"] = []

                aggregate = facility_map[facility_id]
                aggregate["estimated_supply_tonnes"] += recoverable_member
                aggregate["member_distances"].append({
                    "field_id": source_id,
                    "distance_km": facility.get("distance_km"),
                    "screening_status": facility.get("screening_status"),
                })

                current_distance = float(facility.get("distance_km", 0.0))
                previous_distance = float(aggregate.get("distance_km", current_distance))
                if current_distance < previous_distance:
                    aggregate["distance_km"] = current_distance

                if any(
                    item.get("screening_status") == "within_search_radius"
                    for item in aggregate["member_distances"]
                ):
                    aggregate["screening_status"] = "within_search_radius"
                else:
                    aggregate["screening_status"] = "outside_search_radius"

        ranked_facilities = list(facility_map.values())
        ranked_facilities.sort(key=lambda item: item["distance_km"])

        for facility in ranked_facilities:
            facility["estimated_supply_tonnes"] = round(
                facility["estimated_supply_tonnes"],
                3,
            )
            facility["opportunity_status"] = _opportunity_status(
                facility["distance_km"],
                total_recoverable,
            )
            facility["distance_method"] = (
                "minimum straight-line Haversine distance across source-year field geometries"
            )

        within_radius = [
            item
            for item in ranked_facilities
            if item["distance_km"] <= search_radius_km
        ]

        nearest = ranked_facilities[0] if ranked_facilities else None

        # A representative centroid is retained for compatibility with the
        # existing response shape. It is not used for the member distance
        # calculations above.
        total_weight = 0.0
        weighted_lat = 0.0
        weighted_lon = 0.0
        member_centroids = []

        for member_match in member_results:
            centroid = member_match.get("field_centroid") or {}
            member_supply = float(
                member_match.get("recoverable_biomass_tonnes", 0.0)
            )
            lat = centroid.get("latitude")
            lon = centroid.get("longitude")
            if lat is None or lon is None:
                continue
            weight = member_supply if member_supply > 0 else 1.0
            total_weight += weight
            weighted_lat += float(lat) * weight
            weighted_lon += float(lon) * weight
            member_centroids.append({
                "field_id": member_match.get("field_id"),
                "latitude": lat,
                "longitude": lon,
            })

        field_centroid = (
            {
                "latitude": round(weighted_lat / total_weight, 6),
                "longitude": round(weighted_lon / total_weight, 6),
            }
            if total_weight > 0
            else None
        )

        summary = group_summary(field_id, GEOJSON_PATH)

        return {
            "field_id": field_id,
            "field_centroid": field_centroid,
            "recoverable_biomass_tonnes": round(total_recoverable, 3),
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
            "source_field_ids": summary["source_field_ids"],
            "source_field_count": summary["source_field_count"],
            "member_centroids": member_centroids,
            "member_opportunities": member_results,
            "aggregation": {
                "method": (
                    "evaluate each source-year field separately and aggregate facility supply"
                    if len(source_field_ids) > 1
                    else "evaluate the single resolved source-year field"
                ),
                "distance_rule": "minimum member-to-facility distance for facility screening",
                "centroid_note": (
                    "The representative aggregate centroid is retained for response compatibility; "
                    "distance and logistics decisions use each source field separately."
                ),
            },
            "methodology": (
                "Every registered facility is evaluated for each resolved source-year field "
                "using straight-line Haversine distance. Supply is aggregated across all "
                "resolved source-year records, while distance remains tied to the actual "
                "member geometry. If only one source-year record exists, that record is used "
                "directly without inventing a second year."
            ),
            "limitations": [
                "The facility registry is still limited to the currently sourced facilities.",
                "Some facility coordinates are approximate village/site references rather than exact plant-gate coordinates.",
                "Road distance, travel time, transport cost, seasonal accessibility, and facility spare capacity are not yet modeled.",
                "Estimated supply is the group's recoverable biomass estimate; it is not a confirmed purchase quantity.",
            ],
        }

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

