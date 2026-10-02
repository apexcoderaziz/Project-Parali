"""
Live Sentinel-2 burn analysis for Project Parali.

This module uses the selected field polygon and the latest usable
Sentinel-2 SR Harmonized observations from Google Earth Engine.
It intentionally provides a transparent spectral burn-signal assessment,
not a calibrated ML probability.

The existing RGB + SWIR CNN workflow is not changed by this module.
"""

from __future__ import annotations

import json
import math
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

try:
    from .field_context import resolve_field_context
except ImportError:
    from field_context import resolve_field_context

try:
    from .satellite_service import get_sentinel2_series
except ImportError:
    from satellite_service import get_sentinel2_series

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
GEOJSON_PATH = BASE_DIR / "data" / "processed" / "sangrur_fields.geojson"
COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
LOOKBACK_DAYS = 120
MAX_CLOUD_PERCENT = 40
REDUCE_SCALE = 10

EE_PROJECT = os.getenv(
    "EARTH_ENGINE_PROJECT",
    "project-18808c04-2093-4bb1-940",
)


def _fetch_current_series(field_id: str) -> list[dict[str, Any]]:
    """Return the shared canonical Sentinel-2 series for the field."""

    return get_sentinel2_series(
        field_id=field_id,
        lookback_days=LOOKBACK_DAYS,
        max_cloud_percent=MAX_CLOUD_PERCENT,
        reduce_scale=REDUCE_SCALE,
    )


def _safe_percent_change(previous: float, current: float) -> float:
    denominator = max(abs(previous), 0.001)
    return (current - previous) / denominator


def _score_burn_signals(series: list[dict[str, Any]]) -> dict[str, Any]:
    if len(series) < 2:
        return {
            "score": 0.0,
            "label": "insufficient data",
            "status": "insufficient_data",
            "status_label": "Insufficient current satellite data",
            "reasons": [],
        }

    recent = series[-8:]
    current = recent[-1]
    previous = recent[-2]

    # Use the recent maximum as a pre-event reference when available.
    pre_event = max(recent[:-1], key=lambda item: item["nbr"])

    nbr_drop = max(0.0, pre_event["nbr"] - current["nbr"])
    ndvi_drop = max(0.0, pre_event["ndvi"] - current["ndvi"])
    swir2_increase = max(0.0, current["swir2"] - pre_event["swir2"])
    nbr2_change = current["nbr2"] - pre_event["nbr2"]
    ratio_increase = max(
        0.0,
        current["swir2_nir_ratio"] - pre_event["swir2_nir_ratio"],
    )

    immediate_nbr_drop = max(0.0, previous["nbr"] - current["nbr"])
    immediate_ndvi_drop = max(0.0, previous["ndvi"] - current["ndvi"])

    score = 0.0
    reasons: list[str] = []

    if nbr_drop >= 0.25:
        score += 35
        reasons.append("NBR shows a substantial decline from the recent reference")
    elif nbr_drop >= 0.15:
        score += 25
        reasons.append("NBR shows a meaningful decline from the recent reference")
    elif nbr_drop >= 0.08:
        score += 12
        reasons.append("NBR shows an early decline")

    if ndvi_drop >= 0.30:
        score += 25
        reasons.append("NDVI shows a substantial vegetation decline")
    elif ndvi_drop >= 0.18:
        score += 18
        reasons.append("NDVI shows a meaningful vegetation decline")
    elif ndvi_drop >= 0.10:
        score += 8
        reasons.append("NDVI shows an early vegetation decline")

    if swir2_increase >= 0.04:
        score += 15
        reasons.append("SWIR2 reflectance increased")
    elif swir2_increase >= 0.02:
        score += 8
        reasons.append("SWIR2 shows a mild increase")

    if ratio_increase >= 0.20:
        score += 15
        reasons.append("SWIR2-to-NIR ratio increased")
    elif ratio_increase >= 0.10:
        score += 8
        reasons.append("SWIR2-to-NIR ratio shows an increase")

    # A sharp one-observation change is useful evidence but is not enough by itself.
    if immediate_nbr_drop >= 0.12 and immediate_ndvi_drop >= 0.10:
        score += 10
        reasons.append("Latest observation shows a concurrent NBR and NDVI drop")

    score = min(score, 100.0)

    if score >= 70:
        label = "high"
        status = "burn_signal"
        status_label = "Strong burn-related spectral signal"
    elif score >= 45:
        label = "medium"
        status = "possible_burn_signal"
        status_label = "Possible burn-related spectral signal"
    else:
        label = "low"
        status = "no_strong_burn_signal"
        status_label = "No strong burn-related spectral signal"

    if not reasons:
        reasons.append("Current Sentinel-2 spectral signals do not show a strong burn-related change")

    return {
        "score": round(score, 1),
        "label": label,
        "status": status,
        "status_label": status_label,
        "reasons": reasons,
        "nbr_drop_from_reference": round(nbr_drop, 4),
        "ndvi_drop_from_reference": round(ndvi_drop, 4),
        "swir2_increase_from_reference": round(swir2_increase, 4),
        "nbr2_change_from_reference": round(nbr2_change, 4),
        "swir2_nir_ratio_increase": round(ratio_increase, 4),
        "latest_nbr_change": round(immediate_nbr_drop, 4),
        "latest_ndvi_change": round(immediate_ndvi_drop, 4),
        "reference_date": pre_event["date"],
    }


def analyze_live_burn(field_id: str) -> dict[str, Any]:
    """Run live Sentinel-2 burn-related spectral assessment for one field."""
    normalized_id = str(field_id).strip()
    if not normalized_id:
        raise ValueError("field_id cannot be empty")

    series = _fetch_current_series(normalized_id)
    signals = _score_burn_signals(series)
    latest = series[-1] if series else None
    field_group = resolve_field_context(normalized_id, str(GEOJSON_PATH))

    return {
        "success": True,
        "field_id": normalized_id,
        "source_field_ids": field_group["source_field_ids"],
        "source_field_count": field_group["source_field_count"],
        "geometry_mode": field_group["geometry_mode"],
        "analysis_type": "live Sentinel-2 burn spectral assessment",
        "burn_likelihood": signals["label"],
        "signal_strength": signals["score"],
        "status": signals["status"],
        "status_label": signals["status_label"],
        "as_of_date": latest["date"] if latest else None,
        "confidence": None,
        "signals": {
            key: value
            for key, value in signals.items()
            if key not in {"score", "label", "status", "status_label", "reasons"}
        },
        "reasons": signals["reasons"],
        "latest_observation": latest,
        "observations": len(series),
        "time_series": series,
        "data_source": {
            "current": COLLECTION,
            "lookback_days": LOOKBACK_DAYS,
            "max_cloud_percent": MAX_CLOUD_PERCENT,
            "scale_meters": REDUCE_SCALE,
            "bands": ["B4", "B8", "B11", "B12"],
            "indices": ["NDVI", "NBR", "NBR2", "SWIR2_NIR_RATIO"],
            "source_field_ids": field_group["source_field_ids"],
            "geometry_mode": field_group["geometry_mode"],
        },
        "validation_note": (
            "This is a live Sentinel-2 spectral burn-related signal assessment, "
            "not a calibrated statistical probability or a confirmed fire/burn event. "
            "It uses changes in vegetation and SWIR-sensitive indicators within the "
            "selected field. Cloud masking, mixed pixels, crop senescence, soil, "
            "and other land-surface changes can produce similar spectral patterns."
        ),
        "limitations": [
            "The latest Sentinel-2 scene is the latest usable observation returned by Earth Engine, not necessarily an observation from today.",
            "The signal is field-level and may contain mixed pixels near field boundaries.",
            "Drying or harvesting vegetation can produce spectral changes similar to burning.",
            "This endpoint does not use the existing RGB + SWIR CNN, because that CNN was trained on a different image-input dataset.",
        ],
    }
