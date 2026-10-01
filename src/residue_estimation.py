import csv
import math
import os


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIELD_INDICATORS_PATH = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "field_indicators.csv",
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


def _load_field(field_id):
    if not os.path.exists(FIELD_INDICATORS_PATH):
        raise ValueError("field_indicators.csv not found")

    target = str(field_id).strip()

    with open(FIELD_INDICATORS_PATH, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            if str(row.get("field_id", "")).strip() == target:
                return row

    raise ValueError(f"Field '{target}' not found")


def estimate_residue(field_id):
    row = _load_field(field_id)

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
        "success": True,
        "field_id": str(field_id),
        "prediction_type": "assumption-based crop-residue estimate",
        "crop": DEFAULT_CROP,
        "gross_residue_tonnes": round(gross_residue, 3),
        "recoverable_biomass_tonnes": round(recoverable_residue, 3),
        "collection_potential_percent": round(
            DEFAULT_COLLECTION_EFFICIENCY * 100, 1
        ),
        "area": {
            "hectares": round(area_hectares, 4),
            "acres": _number(row.get("area_acres")),
        },
        "assumptions": {
            "yield_tonnes_per_hectare": DEFAULT_YIELD_TONNES_PER_HECTARE,
            "residue_to_product_ratio": DEFAULT_RESIDUE_TO_PRODUCT_RATIO,
            "collection_efficiency": DEFAULT_COLLECTION_EFFICIENCY,
        },
        "field_context": {
            "historical_category": row.get("category"),
            "candidate_date": row.get("candidate_date"),
        },
        "methodology": (
            "Gross residue = crop yield × field area × residue-to-product ratio. "
            "Recoverable biomass = gross residue × collection efficiency."
        ),
        "validation_note": (
            "This is an agronomic assumption-based estimate. Satellite data "
            "provides field area and crop-transition context, but the current "
            "system does not directly measure residue mass from imagery. "
            "The crop, yield, residue ratio, and collection efficiency are "
            "configurable assumptions."
        ),
    }
