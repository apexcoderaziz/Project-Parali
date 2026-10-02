"""Shared-context crop residue estimation for Project Parali.

Phase 3 architecture:

    logical field ID
          |
          v
    field_context.py
          |
          +--> source-year fields (for example 2020_34 + 2021_34)
          |
          +--> combined area / categories / indicator context
          |
          v
    residue estimation

The residue module deliberately keeps the mass calculation transparent.
Satellite imagery supplies field geometry and historical/current field context;
it does not directly measure kilograms or tonnes of residue. The current MVP
therefore converts field area into an estimated residue supply using configurable
agronomic assumptions.

The public function ``estimate_residue(field_id)`` keeps the existing API
contract used by FastAPI and the frontend.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

try:
    from .field_context import get_field_context
except ImportError:
    from field_context import get_field_context


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
# Configurable agronomic assumptions
# ---------------------------------------------------------------------------
# Defaults preserve the assumptions used by the previous residue module.
DEFAULT_CROP = "paddy"
DEFAULT_YIELD_TONNES_PER_HECTARE = 4.132
DEFAULT_RESIDUE_TO_PRODUCT_RATIO = 1.10
DEFAULT_COLLECTION_EFFICIENCY = 0.70


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    """Read a finite positive configuration value from an environment variable."""

    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default

    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default

    if value < minimum:
        return default

    return value


def _config() -> Dict[str, Any]:
    """Return the effective residue-model configuration."""

    crop = os.getenv("PARALI_RESIDUE_CROP", DEFAULT_CROP).strip() or DEFAULT_CROP

    yield_tph = _env_float(
        "PARALI_RESIDUE_YIELD_TPH",
        DEFAULT_YIELD_TONNES_PER_HECTARE,
        minimum=0.0,
    )

    residue_ratio = _env_float(
        "PARALI_RESIDUE_RATIO",
        DEFAULT_RESIDUE_TO_PRODUCT_RATIO,
        minimum=0.0,
    )

    collection_efficiency = _env_float(
        "PARALI_COLLECTION_EFFICIENCY",
        DEFAULT_COLLECTION_EFFICIENCY,
        minimum=0.0,
    )
    collection_efficiency = min(collection_efficiency, 1.0)

    return {
        "crop": crop,
        "yield_tonnes_per_hectare": yield_tph,
        "residue_to_product_ratio": residue_ratio,
        "collection_efficiency": collection_efficiency,
    }


def _round_number(value: Optional[float], digits: int = 3):
    if value is None:
        return None
    return round(float(value), digits)


def _clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip()
    return text if text else None


def _source_indicator_map(context: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Index source indicator dictionaries by source field ID."""

    result: Dict[str, Dict[str, Any]] = {}

    for item in context.get("source_indicators", []):
        source_id = _clean_text(item.get("field_id"))
        if source_id:
            result[source_id] = item

    return result


def _estimate_mass(area_hectares: float, cfg: Dict[str, Any]) -> Dict[str, float]:
    """Convert area to gross and recoverable residue using configured assumptions."""

    gross_residue = (
        area_hectares
        * cfg["yield_tonnes_per_hectare"]
        * cfg["residue_to_product_ratio"]
    )

    recoverable_residue = (
        gross_residue
        * cfg["collection_efficiency"]
    )

    return {
        "gross_residue_tonnes": gross_residue,
        "recoverable_biomass_tonnes": recoverable_residue,
    }


def _build_source_estimates(
    context: Dict[str, Any],
    cfg: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Estimate residue for every source-year feature in the shared field context."""

    indicator_map = _source_indicator_map(context)
    estimates: List[Dict[str, Any]] = []

    for source_field in context.get("source_fields", []):
        source_id = _clean_text(source_field.get("field_id"))
        area_hectares = source_field.get("area_hectares")

        if not source_id:
            continue

        try:
            area_hectares = float(area_hectares)
        except (TypeError, ValueError):
            area_hectares = 0.0

        if area_hectares <= 0:
            continue

        mass = _estimate_mass(area_hectares, cfg)
        indicators = indicator_map.get(source_id, {})

        estimates.append(
            {
                "field_id": source_id,
                "source_year": source_field.get("source_year"),
                "source_file": source_field.get("source_file"),
                "area_hectares": round(area_hectares, 6),
                "area_acres": round(
                    float(source_field.get("area_acres") or area_hectares * 2.47105),
                    6,
                ),
                "area_source": source_field.get("area_source"),
                "category": (
                    _clean_text(source_field.get("category"))
                    or _clean_text(indicators.get("category"))
                ),
                "candidate_date": _clean_text(indicators.get("candidate_date")),
                "gross_residue_tonnes": round(
                    mass["gross_residue_tonnes"],
                    6,
                ),
                "recoverable_biomass_tonnes": round(
                    mass["recoverable_biomass_tonnes"],
                    6,
                ),
            }
        )

    return estimates


def estimate_residue(field_id: str) -> Dict[str, Any]:
    """Estimate crop residue for a logical field or exact source field ID.

    Examples:
        ``34`` resolves to all matching source-year features, such as
        ``2020_34`` + ``2021_34``.

        ``2021_343`` resolves to that single source feature.

    The calculation is:

        gross residue = area × crop yield × residue-to-product ratio
        recoverable biomass = gross residue × collection efficiency
    """

    target = str(field_id).strip()
    if not target:
        raise ValueError("field_id cannot be empty")

    context = get_field_context(target, GEOJSON_PATH)
    cfg = _config()

    source_estimates = _build_source_estimates(context, cfg)

    if not source_estimates:
        raise ValueError(
            f"Field '{target}' has no source-year records with usable area"
        )

    total_area_hectares = sum(
        float(item["area_hectares"])
        for item in source_estimates
    )
    total_area_acres = sum(
        float(item["area_acres"])
        for item in source_estimates
    )
    total_gross_residue = sum(
        float(item["gross_residue_tonnes"])
        for item in source_estimates
    )
    total_recoverable = sum(
        float(item["recoverable_biomass_tonnes"])
        for item in source_estimates
    )

    categories = sorted({
        item["category"]
        for item in source_estimates
        if item.get("category")
    })

    candidate_dates = sorted({
        item["candidate_date"]
        for item in source_estimates
        if item.get("candidate_date")
    })

    field_category = context.get("categories", [])
    if not categories and field_category:
        categories = [str(value) for value in field_category]

    category_context: Any
    if len(categories) == 1:
        category_context = categories[0]
    elif categories:
        category_context = categories
    else:
        category_context = None

    candidate_date_context: Any
    if len(candidate_dates) == 1:
        candidate_date_context = candidate_dates[0]
    elif candidate_dates:
        candidate_date_context = candidate_dates
    else:
        candidate_date_context = None

    source_count = len(source_estimates)
    is_combined = source_count > 1

    return {
        "success": True,
        "field_id": target,
        "logical_field_id": context["logical_field_id"],
        "prediction_type": "assumption-based crop-residue estimate",
        "crop": cfg["crop"],
        "gross_residue_tonnes": _round_number(total_gross_residue, 3),
        "recoverable_biomass_tonnes": _round_number(total_recoverable, 3),
        "collection_potential_percent": round(
            cfg["collection_efficiency"] * 100,
            1,
        ),
        "area": {
            "hectares": _round_number(total_area_hectares, 4),
            "acres": _round_number(total_area_acres, 4),
            "source": context["area"].get("source"),
        },
        "source_field_ids": context["source_field_ids"],
        "source_field_count": context["source_field_count"],
        "geometry_mode": context["geometry_mode"],
        "source_fields": source_estimates,
        "aggregation": {
            "method": (
                "sum of source-year field records"
                if is_combined
                else "single source-field record"
            ),
            "source_field_ids": context["source_field_ids"],
            "combined_area_hectares": _round_number(total_area_hectares, 6),
            "combined_gross_residue_tonnes": _round_number(total_gross_residue, 6),
            "combined_recoverable_biomass_tonnes": _round_number(total_recoverable, 6),
            "note": (
                "A logical field number aggregates all matching source-year "
                "records through field_context.py. An exact source ID such as "
                "2021_343 uses only that source field."
            ),
        },
        "assumptions": {
            "crop": cfg["crop"],
            "yield_tonnes_per_hectare": cfg["yield_tonnes_per_hectare"],
            "residue_to_product_ratio": cfg["residue_to_product_ratio"],
            "collection_efficiency": cfg["collection_efficiency"],
        },
        "field_context": {
            "historical_category": category_context,
            "candidate_date": candidate_date_context,
            "categories": context.get("categories", []),
            "centroid": context.get("centroid"),
            "source_field_ids": context.get("source_field_ids", []),
        },
        "methodology": (
            "Gross residue = crop yield × field area × residue-to-product ratio. "
            "Recoverable biomass = gross residue × collection efficiency. "
            "Field area and source-year membership are resolved by the shared "
            "field_context.py layer."
        ),
        "validation_note": (
            "This remains an agronomic assumption-based estimate, not a direct "
            "satellite measurement of residue mass. Sentinel-2 contributes field "
            "geometry and crop-transition context, while yield, residue ratio, "
            "and collection efficiency remain configurable model assumptions. "
            "These assumptions should be calibrated against field measurements "
            "before the estimate is treated as a production-grade biomass forecast."
        ),
    }
