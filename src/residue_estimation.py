import csv
import math
import os

try:
    from .field_grouping import load_field_features, resolve_field_ids, group_summary
except ImportError:
    from field_grouping import load_field_features, resolve_field_ids, group_summary


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIELD_INDICATORS_PATH = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "field_indicators.csv",
)
GEOJSON_PATH = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "sangrur_fields.geojson",
)

# These are transparent defaults, not learned field-specific parameters.
DEFAULT_CROP = "paddy"
DEFAULT_YIELD_TONNES_PER_HECTARE = 4.132
DEFAULT_RESIDUE_TO_PRODUCT_RATIO = 1.10
DEFAULT_COLLECTION_EFFICIENCY = 0.70


def _number(value):
    try:
        number = float(value)
        if math.isfinite(number):
            return number
    except (TypeError, ValueError):
        pass
    return None


def _load_all_indicator_rows():
    if not os.path.exists(FIELD_INDICATORS_PATH):
        raise ValueError("field_indicators.csv not found")

    with open(
        FIELD_INDICATORS_PATH,
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        return list(csv.DictReader(file))


def _load_field(field_id):
    target = str(field_id).strip()

    for row in _load_all_indicator_rows():
        if str(row.get("field_id", "")).strip() == target:
            return row

    raise ValueError(f"Field '{target}' not found")


def _estimate_single(field_id, row):
    area_hectares = _number(row.get("area_hectares"))
    if area_hectares is None or area_hectares <= 0:
        raise ValueError(f"Field '{field_id}' does not have a valid area")

    gross_residue = (
        area_hectares
        * DEFAULT_YIELD_TONNES_PER_HECTARE
        * DEFAULT_RESIDUE_TO_PRODUCT_RATIO
    )

    recoverable_residue = gross_residue * DEFAULT_COLLECTION_EFFICIENCY

    return {
        "field_id": str(field_id),
        "gross_residue_tonnes": gross_residue,
        "recoverable_biomass_tonnes": recoverable_residue,
        "area_hectares": area_hectares,
        "area_acres": _number(row.get("area_acres"))
        or area_hectares * 2.47105,
        "category": row.get("category"),
        "candidate_date": row.get("candidate_date"),
    }


def estimate_residue(field_id):
    target = str(field_id).strip()
    source_ids = resolve_field_ids(target, GEOJSON_PATH)

    rows_by_id = {
        str(row.get("field_id", "")).strip(): row
        for row in _load_all_indicator_rows()
        if str(row.get("field_id", "")).strip()
    }

    source_estimates = []
    for source_id in source_ids:
        row = rows_by_id.get(source_id)
        if row is None:
            raise ValueError(
                f"Field indicators for source field '{source_id}' not found"
            )
        source_estimates.append(
            _estimate_single(source_id, row)
        )

    if not source_estimates:
        raise ValueError(f"Field '{target}' has no source-year records")

    gross_residue = sum(
        item["gross_residue_tonnes"]
        for item in source_estimates
    )
    recoverable_residue = sum(
        item["recoverable_biomass_tonnes"]
        for item in source_estimates
    )
    area_hectares = sum(
        item["area_hectares"]
        for item in source_estimates
    )
    area_acres = sum(
        item["area_acres"]
        for item in source_estimates
    )

    summary = group_summary(target, GEOJSON_PATH)

    categories = sorted({
        str(item["category"]).strip()
        for item in source_estimates
        if item.get("category") not in (None, "")
    })

    candidate_dates = sorted({
        str(item["candidate_date"]).strip()
        for item in source_estimates
        if item.get("candidate_date") not in (None, "")
    })

    return {
        "success": True,
        "field_id": target,
        "prediction_type": "assumption-based crop-residue estimate",
        "crop": DEFAULT_CROP,
        "gross_residue_tonnes": round(gross_residue, 3),
        "recoverable_biomass_tonnes": round(recoverable_residue, 3),
        "collection_potential_percent": round(
            DEFAULT_COLLECTION_EFFICIENCY * 100, 1
        ),
        "area": {
            "hectares": round(area_hectares, 4),
            "acres": round(area_acres, 4),
        },
        "source_field_ids": summary["source_field_ids"],
        "source_field_count": summary["source_field_count"],
        "source_fields": source_estimates,
        "aggregation": {
            "method": "sum of source-year field records",
            "note": (
                "A logical field number such as 34 aggregates every matching "
                "Sangrur source-year record, while a full ID such as 2021_34 "
                "continues to use only that source field."
            ),
        },
        "assumptions": {
            "yield_tonnes_per_hectare": DEFAULT_YIELD_TONNES_PER_HECTARE,
            "residue_to_product_ratio": DEFAULT_RESIDUE_TO_PRODUCT_RATIO,
            "collection_efficiency": DEFAULT_COLLECTION_EFFICIENCY,
        },
        "field_context": {
            "historical_category": (
                categories[0] if len(categories) == 1 else categories
            ),
            "candidate_date": (
                candidate_dates[0]
                if len(candidate_dates) == 1
                else candidate_dates
                if candidate_dates
                else None
            ),
        },
        "methodology": (
            "Gross residue = crop yield × field area × residue-to-product ratio. "
            "Recoverable biomass = gross residue × collection efficiency. "
            "For a logical multi-year field number, source-year estimates are "
            "combined across all matching GeoJSON field records."
        ),
        "validation_note": (
            "This is an agronomic assumption-based estimate. Satellite data "
            "provides field geometry and crop-transition context, but the current "
            "system does not directly measure residue mass from imagery. "
            "The crop, yield, residue ratio, and collection efficiency are "
            "configurable assumptions."
        ),
    }
