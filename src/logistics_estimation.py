"""Logistics and transport screening for Project Parali.

This module estimates transport requirements between a field and its nearest
registered biomass facility.

Important:
- Facility distance comes from the biomass opportunity module.
- Road distance is an explicit screening assumption derived from straight-line
  distance; it is NOT a route returned by a mapping/routing service.
- Transport cost is an assumption-based estimate, not an actual transporter
  quotation.
"""

import math
from typing import Any, Dict

from .biomass_opportunity import match_facilities
from .field_grouping import group_summary, resolve_field_ids


# ---------------------------------------------------------------------------
# Transparent logistics assumptions
# ---------------------------------------------------------------------------

# Road routes are usually longer than straight-line distance. This is only a
# screening factor until an actual routing API is integrated.
DEFAULT_ROAD_DISTANCE_FACTOR = 1.30

# Assumption for screening transport economics.
# This is deliberately configurable and must not be presented as a market quote.
DEFAULT_TRANSPORT_RATE_PER_TONNE_KM = 4.50

# A small field load should be flagged because a real truck may have a minimum
# economical load / trip cost that this simple tonne-km model does not capture.
SMALL_LOAD_THRESHOLD_TONNES = 2.0


def _number(value: Any) -> float:
    try:
        number = float(value)
        if math.isfinite(number):
            return number
    except (TypeError, ValueError):
        pass
    return 0.0


def estimate_logistics(
    field_id: str,
    recoverable_biomass_tonnes: float,
    search_radius_km: float = 50.0,
    road_distance_factor: float = DEFAULT_ROAD_DISTANCE_FACTOR,
    transport_rate_per_tonne_km: float = DEFAULT_TRANSPORT_RATE_PER_TONNE_KM,
) -> Dict[str, Any]:
    """Return a transparent logistics screening estimate for one field."""

    if road_distance_factor < 1.0:
        raise ValueError("road_distance_factor must be >= 1.0")

    if transport_rate_per_tonne_km < 0:
        raise ValueError("transport_rate_per_tonne_km must be >= 0")

    recoverable = max(0.0, _number(recoverable_biomass_tonnes))

    target_id = str(field_id).strip()
    source_field_ids = resolve_field_ids(target_id)

    # For a logical field number such as "34", calculate transport for each
    # source-year field separately and then aggregate the planning totals.
    # This avoids inventing a route from an artificial midpoint between
    # historical geometries.
    if target_id not in source_field_ids and len(source_field_ids) > 1:
        try:
            from .residue_estimation import estimate_residue
        except ImportError:
            from residue_estimation import estimate_residue

        member_logistics = []
        total_recoverable = 0.0
        total_cost = 0.0

        for source_id in source_field_ids:
            member_residue = estimate_residue(source_id)
            member_recoverable = float(
                member_residue.get("recoverable_biomass_tonnes", 0.0)
            )

            member_result = estimate_logistics(
                field_id=source_id,
                recoverable_biomass_tonnes=member_recoverable,
                search_radius_km=search_radius_km,
                road_distance_factor=road_distance_factor,
                transport_rate_per_tonne_km=transport_rate_per_tonne_km,
            )

            member_logistics.append(member_result)
            total_recoverable += member_recoverable
            total_cost += _number(
                (member_result.get("transport") or {}).get(
                    "estimated_transport_cost_inr"
                )
            )

        available_member_facilities = [
            member["nearest_facility"]
            for member in member_logistics
            if member.get("nearest_facility")
        ]
        nearest = (
            min(
                available_member_facilities,
                key=lambda item: item.get("straight_line_distance_km", float("inf")),
            )
            if available_member_facilities
            else None
        )

        shortest_road_distance = (
            min(
                _number(
                    (member.get("transport") or {}).get(
                        "estimated_road_distance_km"
                    )
                )
                for member in member_logistics
                if member.get("transport")
            )
            if any(member.get("transport") for member in member_logistics)
            else 0.0
        )

        cost_per_tonne = (
            total_cost / total_recoverable
            if total_recoverable > 0
            else 0.0
        )

        any_outside = any(
            member.get("logistics_status")
            == "nearest_facility_outside_screening_radius"
            for member in member_logistics
        )

        if total_recoverable <= 0:
            logistics_status = "no_recoverable_biomass"
        elif any_outside:
            logistics_status = "multi_source_group_with_member_outside_radius"
        else:
            logistics_status = "multi_source_group_aggregated"

        warnings = []
        for member in member_logistics:
            for warning in member.get("warnings", []):
                if warning not in warnings:
                    warnings.append(warning)

        if len(source_field_ids) > 1:
            warnings.append(
                "This logical field combines separate source-year field records. "
                "Transport cost is aggregated from member fields rather than from "
                "a single artificial centroid route."
            )

        summary = group_summary(target_id)

        return {
            "success": True,
            "field_id": target_id,
            "prediction_type": "assumption-based logistics screening",
            "logistics_status": logistics_status,
            "recoverable_biomass_tonnes": round(total_recoverable, 3),
            "nearest_facility": nearest,
            "transport": (
                {
                    "estimated_road_distance_km": round(shortest_road_distance, 2),
                    "road_distance_factor": road_distance_factor,
                    "transport_rate_per_tonne_km": transport_rate_per_tonne_km,
                    "estimated_transport_cost_inr": round(total_cost, 2),
                    "estimated_cost_per_tonne_inr": round(cost_per_tonne, 2),
                }
                if any(member.get("transport") for member in member_logistics)
                else None
            ),
            "warnings": warnings,
            "methodology": (
                "Each source-year field is matched to its nearest registered facility and "
                "transport is estimated independently. Total biomass and transport cost "
                "are then aggregated for the logical field group."
            ),
            "assumptions": {
                "road_distance_factor": road_distance_factor,
                "transport_rate_per_tonne_km_inr": transport_rate_per_tonne_km,
                "small_load_threshold_tonnes": SMALL_LOAD_THRESHOLD_TONNES,
            },
            "validation_note": (
                "This is a logistics screening estimate. Road distance is not obtained "
                "from a routing service, and the transport rate is a configurable assumption."
            ),
            "facility_matching": {
                "search_radius_km": search_radius_km,
                "member_count": len(source_field_ids),
                "member_logistics": member_logistics,
            },
            "source_field_ids": summary["source_field_ids"],
            "source_field_count": summary["source_field_count"],
            "straight_line_distance_km": (
                nearest.get("straight_line_distance_km") if nearest else None
            ),
            "estimated_road_distance_km": round(shortest_road_distance, 2),
            "estimated_transport_cost_inr": round(total_cost, 2),
            "cost_per_tonne_inr": round(cost_per_tonne, 2),
            "search_radius_km": search_radius_km,
            "methodology_note": (
                "For multi-source groups, transport cost is the sum of member-field "
                "screening costs; the displayed distance is the shortest member-to-nearest-facility distance."
            ),
        }

    opportunity = match_facilities(
        field_id=field_id,
        recoverable_biomass_tonnes=recoverable,
        search_radius_km=search_radius_km,
    )

    nearest = opportunity.get("nearest_facility")

    if not nearest:
        return {
            "success": True,
            "field_id": str(field_id).strip(),
            "prediction_type": "assumption-based logistics screening",
            "logistics_status": "no_registered_facility",
            "recoverable_biomass_tonnes": round(recoverable, 3),
            "nearest_facility": None,
            "transport": None,
            "methodology": (
                "No registered biomass facility is available for distance "
                "calculation. Add a sourced facility to the registry."
            ),
            "validation_note": (
                "This module does not provide actual road routing or a "
                "transporter quotation."
            ),
        }

    straight_line_km = _number(nearest.get("distance_km"))
    estimated_road_km = straight_line_km * road_distance_factor

    estimated_transport_cost = (
        recoverable
        * estimated_road_km
        * transport_rate_per_tonne_km
    )

    cost_per_tonne = (
        estimated_transport_cost / recoverable
        if recoverable > 0
        else 0.0
    )

    within_radius = (
        nearest.get("screening_status") == "within_search_radius"
    )

    if recoverable <= 0:
        logistics_status = "no_recoverable_biomass"
    elif not within_radius:
        logistics_status = "nearest_facility_outside_screening_radius"
    elif straight_line_km <= 10:
        logistics_status = "short_distance"
    elif straight_line_km <= 25:
        logistics_status = "local_logistics"
    elif straight_line_km <= 50:
        logistics_status = "regional_logistics"
    else:
        logistics_status = "long_distance_screening"

    warnings = []

    if recoverable < SMALL_LOAD_THRESHOLD_TONNES:
        warnings.append(
            "Field biomass is below the small-load threshold; a real truck "
            "may have a minimum trip/load cost that is not captured by this "
            "tonne-kilometre estimate."
        )

    if nearest.get("coordinate_quality") != "exact plant-gate location":
        warnings.append(
            "Facility coordinates may be approximate, so the distance is a "
            "screening estimate rather than an exact plant-gate route."
        )

    return {
        "success": True,
        "field_id": str(field_id).strip(),
        "prediction_type": "assumption-based logistics screening",
        "logistics_status": logistics_status,
        "recoverable_biomass_tonnes": round(recoverable, 3),
        "nearest_facility": {
            "facility_id": nearest.get("facility_id"),
            "name": nearest.get("name"),
            "type": nearest.get("type"),
            "district": nearest.get("district"),
            "location": nearest.get("location"),
            "straight_line_distance_km": round(straight_line_km, 2),
            "screening_status": nearest.get("screening_status"),
            "opportunity_status": nearest.get("opportunity_status"),
        },
        "transport": {
            "estimated_road_distance_km": round(estimated_road_km, 2),
            "road_distance_factor": road_distance_factor,
            "transport_rate_per_tonne_km": transport_rate_per_tonne_km,
            "estimated_transport_cost_inr": round(
                estimated_transport_cost,
                2,
            ),
            "estimated_cost_per_tonne_inr": round(
                cost_per_tonne,
                2,
            ),
        },
        "warnings": warnings,
        "methodology": (
            "Estimated road distance = straight-line Haversine distance × "
            "road-distance factor. Estimated transport cost = recoverable "
            "biomass × estimated road distance × transport rate per tonne-km."
        ),
        "assumptions": {
            "road_distance_factor": road_distance_factor,
            "transport_rate_per_tonne_km_inr": transport_rate_per_tonne_km,
            "small_load_threshold_tonnes": SMALL_LOAD_THRESHOLD_TONNES,
        },
        "validation_note": (
            "This is a logistics screening estimate. The road distance is "
            "not obtained from a routing service, and the transport rate is "
            "a configurable assumption rather than a live market quote. "
            "Actual cost depends on vehicle type, loading, route, tolls, "
            "fuel, contractor pricing, and minimum trip charges."
        ),
        "facility_matching": {
            "search_radius_km": opportunity.get("search_radius_km"),
            "facility_count": opportunity.get("facility_count", 0),
            "within_radius_count": opportunity.get(
                "within_radius_count",
                0,
            ),
        },

        # Backward-compatible flat fields for older frontend components.
        # The canonical values remain available in nearest_facility/transport.
        "straight_line_distance_km": round(straight_line_km, 2),
        "estimated_road_distance_km": round(estimated_road_km, 2),
        "estimated_transport_cost_inr": round(
            estimated_transport_cost,
            2,
        ),
        "cost_per_tonne_inr": round(cost_per_tonne, 2),
        "search_radius_km": opportunity.get("search_radius_km"),
        "methodology_note": (
            "Logistics values are screening estimates. "
            "Road distance uses a configurable factor rather than live routing."
        ),
    }
