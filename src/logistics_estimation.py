"""Logistics and transport screening for Project Parali.

This module estimates transport requirements between a logical field and its
nearest registered biomass facilities.

Architecture:
    logical field -> field_context -> residue estimate -> biomass opportunity
    -> logistics screening

Important:
- Facility distance comes from biomass_opportunity.
- Road distance is a configurable screening assumption derived from
  straight-line distance; it is NOT a live routing result.
- Transport cost is an assumption-based estimate, not a transporter quote.
- For a multi-source logical field such as 34 (2020_34 + 2021_34), transport
  is calculated per source-year field and then aggregated, so the total cost
  is not incorrectly based on one minimum distance applied to every tonne.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

try:
    from .biomass_opportunity import match_facilities
    from .field_context import resolve_field_context
    from .residue_estimation import estimate_residue
except ImportError:
    from biomass_opportunity import match_facilities
    from field_context import resolve_field_context
    from residue_estimation import estimate_residue


# ---------------------------------------------------------------------------
# Transparent logistics assumptions
# ---------------------------------------------------------------------------

DEFAULT_SEARCH_RADIUS_KM = 50.0
DEFAULT_ROAD_DISTANCE_FACTOR = 1.30
DEFAULT_TRANSPORT_RATE_PER_TONNE_KM = 4.50
SMALL_LOAD_THRESHOLD_TONNES = 2.0

# Configurable biomass sale-price assumption. This is not a live market quote.
DEFAULT_BIOMASS_SALE_PRICE_INR_PER_TONNE = 2500.0


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if math.isfinite(number):
            return number
    except (TypeError, ValueError):
        pass
    return default


def _safe_round(value: Any, digits: int = 2) -> float:
    return round(_number(value), digits)


def _source_logistics(
    source_field_id: str,
    recoverable_biomass_tonnes: float,
    search_radius_km: float,
    road_distance_factor: float,
    transport_rate_per_tonne_km: float,
    biomass_sale_price_inr_per_tonne: float,
) -> Dict[str, Any]:
    """Calculate logistics for one physical source-year field."""

    recoverable = max(0.0, _number(recoverable_biomass_tonnes))
    sale_price = max(0.0, _number(biomass_sale_price_inr_per_tonne))

    opportunity = match_facilities(
        field_id=source_field_id,
        recoverable_biomass_tonnes=recoverable,
        search_radius_km=search_radius_km,
    )

    nearest = opportunity.get("nearest_facility")

    if not nearest:
        gross_revenue = recoverable * sale_price

        return {
            "field_id": str(source_field_id).strip(),
            "recoverable_biomass_tonnes": round(recoverable, 3),
            "logistics_status": "no_registered_facility",
            "nearest_facility": None,
            "transport": None,
            "economics": {
                "biomass_sale_price_inr_per_tonne": round(sale_price, 2),
                "gross_revenue_inr": round(gross_revenue, 2),
                "transport_cost_inr": None,
                "net_profit_inr": None,
                "net_profit_per_tonne_inr": None,
                "profit_margin_percent": None,
                "profit_status": "not_computable_without_facility",
                "profit_definition": "gross biomass sale revenue minus estimated transport cost",
            },
            "warnings": [
                "No registered biomass facility is available for transport-cost calculation; estimated net profit is therefore not computable."
            ],
            "opportunity": opportunity,
        }

    straight_line_km = max(0.0, _number(nearest.get("distance_km")))
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

    gross_revenue = recoverable * sale_price
    net_profit = gross_revenue - estimated_transport_cost
    profit_per_tonne = (
        net_profit / recoverable
        if recoverable > 0
        else 0.0
    )

    screening_status = nearest.get("screening_status")

    if recoverable <= 0:
        logistics_status = "no_recoverable_biomass"
    elif screening_status != "within_search_radius":
        logistics_status = "nearest_facility_outside_screening_radius"
    elif straight_line_km <= 10:
        logistics_status = "short_distance"
    elif straight_line_km <= 25:
        logistics_status = "local_logistics"
    else:
        logistics_status = "regional_logistics"

    warnings: List[str] = []

    if recoverable < SMALL_LOAD_THRESHOLD_TONNES:
        warnings.append(
            "Field biomass is below the small-load threshold; a real truck may have a minimum trip/load cost not captured by this tonne-kilometre estimate."
        )

    if nearest.get("coordinate_quality") != "exact plant-gate location":
        warnings.append(
            "Facility coordinates may be approximate, so the distance is a screening estimate rather than an exact plant-gate route."
        )

    return {
        "field_id": str(source_field_id).strip(),
        "recoverable_biomass_tonnes": round(recoverable, 3),
        "logistics_status": logistics_status,
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
            "estimated_transport_cost_inr": round(estimated_transport_cost, 2),
            "estimated_cost_per_tonne_inr": round(cost_per_tonne, 2),
        },
        "economics": {
            "biomass_sale_price_inr_per_tonne": round(sale_price, 2),
            "gross_revenue_inr": round(gross_revenue, 2),
            "transport_cost_inr": round(estimated_transport_cost, 2),
            "net_profit_inr": round(net_profit, 2),
            "net_profit_per_tonne_inr": round(profit_per_tonne, 2),
            "profit_margin_percent": round(
                (net_profit / gross_revenue * 100)
                if gross_revenue > 0
                else 0.0,
                2,
            ),
        },
        "warnings": warnings,
        "opportunity": opportunity,
    }


def _aggregate_logical_logistics(
    field_id: str,
    context: Dict[str, Any],
    search_radius_km: float,
    road_distance_factor: float,
    transport_rate_per_tonne_km: float,
    biomass_sale_price_inr_per_tonne: float,
) -> Dict[str, Any]:
    """Aggregate transport and economics for all source-year members."""

    source_field_ids = [
        str(item)
        for item in context.get("source_field_ids", [])
    ]

    source_results: List[Dict[str, Any]] = []
    total_recoverable = 0.0
    total_transport_cost = 0.0
    total_gross_revenue = 0.0
    weighted_road_distance = 0.0
    weighted_straight_distance = 0.0
    distance_weight = 0.0
    warnings: List[str] = []
    all_sources_have_facility = True

    for source_id in source_field_ids:
        try:
            residue = estimate_residue(source_id)
            recoverable = _number(
                residue.get("recoverable_biomass_tonnes")
            )
        except Exception:
            recoverable = 0.0

        result = _source_logistics(
            source_field_id=source_id,
            recoverable_biomass_tonnes=recoverable,
            search_radius_km=search_radius_km,
            road_distance_factor=road_distance_factor,
            transport_rate_per_tonne_km=transport_rate_per_tonne_km,
            biomass_sale_price_inr_per_tonne=biomass_sale_price_inr_per_tonne,
        )

        source_results.append(result)
        total_recoverable += recoverable

        if not result.get("nearest_facility"):
            all_sources_have_facility = False

        transport = result.get("transport") or {}
        cost = _number(transport.get("estimated_transport_cost_inr"))
        total_transport_cost += cost

        economics = result.get("economics") or {}
        total_gross_revenue += _number(economics.get("gross_revenue_inr"))

        nearest = result.get("nearest_facility")
        if nearest and recoverable > 0:
            straight = _number(nearest.get("straight_line_distance_km"))
            road = _number(transport.get("estimated_road_distance_km"))
            weighted_straight_distance += straight * recoverable
            weighted_road_distance += road * recoverable
            distance_weight += recoverable

        warnings.extend(result.get("warnings") or [])

    nearest_source_result = None
    for result in source_results:
        if not result.get("nearest_facility"):
            continue
        if nearest_source_result is None:
            nearest_source_result = result
            continue
        current_distance = _number(
            result["nearest_facility"].get("straight_line_distance_km")
        )
        selected_distance = _number(
            nearest_source_result["nearest_facility"].get(
                "straight_line_distance_km"
            )
        )
        if current_distance < selected_distance:
            nearest_source_result = result

    weighted_straight = (
        weighted_straight_distance / distance_weight
        if distance_weight > 0
        else 0.0
    )
    weighted_road = (
        weighted_road_distance / distance_weight
        if distance_weight > 0
        else 0.0
    )

    cost_per_tonne = (
        total_transport_cost / total_recoverable
        if total_recoverable > 0
        else 0.0
    )
    total_net_profit = (
        total_gross_revenue - total_transport_cost
        if all_sources_have_facility
        else None
    )
    net_profit_per_tonne = (
        total_net_profit / total_recoverable
        if total_net_profit is not None and total_recoverable > 0
        else None
    )
    profit_margin_percent = (
        total_net_profit / total_gross_revenue * 100
        if total_net_profit is not None and total_gross_revenue > 0
        else None
    )

    within_radius_count = sum(
        1
        for result in source_results
        if (result.get("nearest_facility") or {}).get("screening_status")
        == "within_search_radius"
    )

    if total_recoverable <= 0:
        logistics_status = "no_recoverable_biomass"
    elif not source_results or nearest_source_result is None:
        logistics_status = "no_registered_facility"
    elif within_radius_count == len(source_results):
        if weighted_straight <= 10:
            logistics_status = "short_distance"
        elif weighted_straight <= 25:
            logistics_status = "local_logistics"
        elif weighted_straight <= 50:
            logistics_status = "regional_logistics"
        else:
            logistics_status = "long_distance_screening"
    elif within_radius_count > 0:
        logistics_status = "mixed_facility_screening"
    else:
        logistics_status = "nearest_facility_outside_screening_radius"

    nearest = (
        nearest_source_result.get("nearest_facility")
        if nearest_source_result
        else None
    )

    # De-duplicate warnings while preserving their order.
    warnings = list(dict.fromkeys(warnings))

    return {
        "success": True,
        "field_id": str(field_id).strip(),
        "prediction_type": "assumption-based logistics screening",
        "logistics_status": logistics_status,
        "recoverable_biomass_tonnes": round(total_recoverable, 3),
        "nearest_facility": nearest,
        "transport": {
            "estimated_road_distance_km": round(weighted_road, 2),
            "road_distance_factor": road_distance_factor,
            "transport_rate_per_tonne_km": transport_rate_per_tonne_km,
            "estimated_transport_cost_inr": round(total_transport_cost, 2),
            "estimated_cost_per_tonne_inr": round(cost_per_tonne, 2),
            "distance_aggregation_method": "recoverable-biomass-weighted mean across source-year fields",
        },
        "economics": {
            "biomass_sale_price_inr_per_tonne": round(_number(biomass_sale_price_inr_per_tonne), 2),
            "gross_revenue_inr": round(total_gross_revenue, 2),
            "transport_cost_inr": round(total_transport_cost, 2),
            "net_profit_inr": (
                round(total_net_profit, 2)
                if total_net_profit is not None
                else None
            ),
            "net_profit_per_tonne_inr": (
                round(net_profit_per_tonne, 2)
                if net_profit_per_tonne is not None
                else None
            ),
            "profit_margin_percent": (
                round(profit_margin_percent, 2)
                if profit_margin_percent is not None
                else None
            ),
            "profit_status": (
                "ready"
                if all_sources_have_facility
                else "partial_facility_coverage"
            ),
            "profit_definition": "gross biomass sale revenue minus estimated transport cost",
        },
        "warnings": warnings,
        "facility_matching": {
            "search_radius_km": search_radius_km,
            "source_field_count": len(source_field_ids),
            "source_fields_within_radius": within_radius_count,
            "nearest_source_field_id": (
                nearest_source_result.get("field_id")
                if nearest_source_result
                else None
            ),
        },
        "source_field_ids": source_field_ids,
        "source_field_count": len(source_field_ids),
        "source_logistics": source_results,
        "methodology": (
            "For a logical multi-source field, each source-year geometry is evaluated separately. "
            "Transport cost is calculated per source and summed; aggregate distance is recoverable-biomass weighted."
        ),
        "assumptions": {
            "road_distance_factor": road_distance_factor,
            "transport_rate_per_tonne_km_inr": transport_rate_per_tonne_km,
            "small_load_threshold_tonnes": SMALL_LOAD_THRESHOLD_TONNES,
            "biomass_sale_price_inr_per_tonne": biomass_sale_price_inr_per_tonne,
        },
        "validation_note": (
            "This is a logistics screening estimate. Road distance is not obtained from a live routing service, "
            "and the transport rate is a configurable assumption rather than a market quote. Actual cost depends "
            "on vehicle type, loading, route, tolls, fuel, contractor pricing, and minimum trip charges."
        ),
        # Backward-compatible flat fields.
        "straight_line_distance_km": (
            round(
                _number(nearest.get("straight_line_distance_km")),
                2,
            )
            if nearest
            else None
        ),
        "estimated_road_distance_km": round(weighted_road, 2),
        "estimated_transport_cost_inr": round(total_transport_cost, 2),
        "cost_per_tonne_inr": round(cost_per_tonne, 2),
        "search_radius_km": search_radius_km,
        "methodology_note": (
            "Logistics values are screening estimates. Multi-source logical fields are calculated per source-year member and then aggregated."
        ),
    }


def estimate_logistics(
    field_id: str,
    recoverable_biomass_tonnes: float | None = None,
    search_radius_km: float = DEFAULT_SEARCH_RADIUS_KM,
    road_distance_factor: float = DEFAULT_ROAD_DISTANCE_FACTOR,
    transport_rate_per_tonne_km: float = DEFAULT_TRANSPORT_RATE_PER_TONNE_KM,
    biomass_sale_price_inr_per_tonne: float = DEFAULT_BIOMASS_SALE_PRICE_INR_PER_TONNE,
) -> Dict[str, Any]:
    """Return logistics screening for one logical or source field."""

    if road_distance_factor < 1.0:
        raise ValueError("road_distance_factor must be >= 1.0")

    if transport_rate_per_tonne_km < 0:
        raise ValueError("transport_rate_per_tonne_km must be >= 0")

    if search_radius_km <= 0:
        raise ValueError("search_radius_km must be greater than 0")

    if biomass_sale_price_inr_per_tonne < 0:
        raise ValueError("biomass_sale_price_inr_per_tonne must be >= 0")

    normalized_id = str(field_id).strip()
    if not normalized_id:
        raise ValueError("field_id cannot be empty")

    context = resolve_field_context(normalized_id)
    source_ids = [str(item) for item in context.get("source_field_ids", [])]

    # A logical field with multiple source-year records must calculate
    # distance-sensitive transport per source member before aggregation.
    if len(source_ids) > 1 and normalized_id not in source_ids:
        return _aggregate_logical_logistics(
            field_id=normalized_id,
            context=context,
            search_radius_km=search_radius_km,
            road_distance_factor=road_distance_factor,
            transport_rate_per_tonne_km=transport_rate_per_tonne_km,
            biomass_sale_price_inr_per_tonne=biomass_sale_price_inr_per_tonne,
        )

    # Preserve compatibility for a source field and for logical IDs with one
    # source. Prefer the explicitly provided residue value when supplied.
    source_id = source_ids[0] if source_ids else normalized_id

    if recoverable_biomass_tonnes is None:
        residue = estimate_residue(source_id)
        recoverable = _number(
            residue.get("recoverable_biomass_tonnes")
        )
    else:
        recoverable = max(
            0.0,
            _number(recoverable_biomass_tonnes),
        )

    result = _source_logistics(
        source_field_id=source_id,
        recoverable_biomass_tonnes=recoverable,
        search_radius_km=search_radius_km,
        road_distance_factor=road_distance_factor,
        transport_rate_per_tonne_km=transport_rate_per_tonne_km,
        biomass_sale_price_inr_per_tonne=biomass_sale_price_inr_per_tonne,
    )

    nearest = result.get("nearest_facility")
    transport = result.get("transport")
    opportunity = result.get("opportunity") or {}

    if nearest is None:
        return {
            "success": True,
            "field_id": normalized_id,
            "source_field_ids": source_ids,
            "source_field_count": len(source_ids),
            "prediction_type": "assumption-based logistics screening",
            "logistics_status": result["logistics_status"],
            "recoverable_biomass_tonnes": round(recoverable, 3),
            "nearest_facility": None,
            "transport": None,
            "economics": {
                "biomass_sale_price_inr_per_tonne": round(_number(biomass_sale_price_inr_per_tonne), 2),
                "gross_revenue_inr": round(recoverable * _number(biomass_sale_price_inr_per_tonne), 2),
                "transport_cost_inr": None,
                "net_profit_inr": None,
                "net_profit_per_tonne_inr": None,
                "profit_margin_percent": None,
                "profit_status": "not_computable_without_facility",
                "profit_definition": "gross biomass sale revenue minus estimated transport cost",
            },
            "warnings": result.get("warnings") or [],
            "facility_matching": {
                "search_radius_km": search_radius_km,
                "facility_count": opportunity.get("facility_count", 0),
                "within_radius_count": opportunity.get("within_radius_count", 0),
            },
            "source_logistics": [result],
            "assumptions": {
                "biomass_sale_price_inr_per_tonne": biomass_sale_price_inr_per_tonne,
            },
            "methodology": (
                "No registered biomass facility is available for distance calculation. "
                "Add a sourced facility to the registry."
            ),
            "validation_note": (
                "This module does not provide actual road routing or a transporter quotation."
            ),
            "straight_line_distance_km": None,
            "estimated_road_distance_km": None,
            "estimated_transport_cost_inr": None,
            "cost_per_tonne_inr": None,
            "search_radius_km": search_radius_km,
            "methodology_note": "No-facility logistics screening result.",
        }

    return {
        "success": True,
        "field_id": normalized_id,
        "source_field_ids": source_ids,
        "source_field_count": len(source_ids),
        "prediction_type": "assumption-based logistics screening",
        "logistics_status": result["logistics_status"],
        "recoverable_biomass_tonnes": round(recoverable, 3),
        "nearest_facility": nearest,
        "transport": transport,
        "economics": result.get("economics") or {},
        "warnings": result.get("warnings") or [],
        "facility_matching": {
            "search_radius_km": search_radius_km,
            "facility_count": opportunity.get("facility_count", 0),
            "within_radius_count": opportunity.get("within_radius_count", 0),
        },
        "source_logistics": [result],
        "methodology": (
            "Estimated road distance = straight-line Haversine distance × road-distance factor. "
            "Estimated transport cost = recoverable biomass × estimated road distance × transport rate per tonne-km."
        ),
        "assumptions": {
            "road_distance_factor": road_distance_factor,
            "transport_rate_per_tonne_km_inr": transport_rate_per_tonne_km,
            "small_load_threshold_tonnes": SMALL_LOAD_THRESHOLD_TONNES,
            "biomass_sale_price_inr_per_tonne": biomass_sale_price_inr_per_tonne,
        },
        "validation_note": (
            "This is a logistics screening estimate. The road distance is not obtained from a routing service, "
            "and the transport rate is a configurable assumption rather than a live market quote. Actual cost "
            "depends on vehicle type, loading, route, tolls, fuel, contractor pricing, and minimum trip charges."
        ),
        # Backward-compatible flat fields for older frontend components.
        "straight_line_distance_km": _safe_round(
            nearest.get("straight_line_distance_km")
        ),
        "estimated_road_distance_km": _safe_round(
            transport.get("estimated_road_distance_km")
        ),
        "estimated_transport_cost_inr": _safe_round(
            transport.get("estimated_transport_cost_inr")
        ),
        "cost_per_tonne_inr": _safe_round(
            transport.get("estimated_cost_per_tonne_inr")
        ),
        "search_radius_km": search_radius_km,
        "methodology_note": (
            "Logistics values are screening estimates. Road distance uses a configurable factor rather than live routing."
        ),
    }


if __name__ == "__main__":
    import json

    print(
        json.dumps(
            estimate_logistics("34"),
            indent=2,
            default=str,
        )
    )
