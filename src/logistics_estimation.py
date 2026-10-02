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
