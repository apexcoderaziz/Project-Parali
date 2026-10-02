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

from .field_grouping import combined_geometry, group_summary

import ee
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

_initialized = False


def _initialize_earth_engine() -> None:
    global _initialized

    if _initialized:
        return

    try:
        ee.Initialize(project=EE_PROJECT)
    except Exception as exc:
        raise RuntimeError(
            "Google Earth Engine is not initialized for the API process. "
            "Run Earth Engine authentication for this Windows account and "
            f"make sure project '{EE_PROJECT}' is available. Original error: {exc}"
        ) from exc

    _initialized = True


def _load_field_geometry(field_id: str) -> dict[str, Any]:
    """Load the selected field geometry, combining all matching source years."""

    return combined_geometry(field_id, str(GEOJSON_PATH))


def _mask_and_indices(image: ee.Image) -> ee.Image:
    qa = image.select("QA60")
    cloud_bit = 1 << 10
    cirrus_bit = 1 << 11

    mask = (
        qa.bitwiseAnd(cloud_bit).eq(0)
        .And(qa.bitwiseAnd(cirrus_bit).eq(0))
    )

    scaled = image.updateMask(mask).divide(10000)

    ndvi = scaled.normalizedDifference(["B8", "B4"]).rename("NDVI")
    nbr = scaled.normalizedDifference(["B8", "B12"]).rename("NBR")

    # NBR2 is useful for distinguishing dry/burned SWIR responses.
    nbr2 = scaled.normalizedDifference(["B11", "B12"]).rename("NBR2")

    # Burn-sensitive band ratio: SWIR2 relative to NIR.
    swir2_nir_ratio = scaled.select("B12").divide(
        scaled.select("B8").add(0.001)
    ).rename("SWIR2_NIR_RATIO")

    return scaled.addBands([ndvi, nbr, nbr2, swir2_nir_ratio]).copyProperties(
        image, image.propertyNames()
    )


def _fetch_current_series(field_id: str) -> list[dict[str, Any]]:
    _initialize_earth_engine()

    geometry_dict = _load_field_geometry(field_id)
    region = ee.Geometry(geometry_dict)

    today = date.today()
    start = today - timedelta(days=LOOKBACK_DAYS)
    end = today + timedelta(days=1)

    collection = (
        ee.ImageCollection(COLLECTION)
        .filterBounds(region)
        .filterDate(start.isoformat(), end.isoformat())
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", MAX_CLOUD_PERCENT))
        .filter(ee.Filter.notNull(["system:time_start"]))
        .map(_mask_and_indices)
    )

    def summarize(image: ee.Image) -> ee.Feature:
        reduced = image.select(
            ["B4", "B8", "B11", "B12", "NDVI", "NBR", "NBR2", "SWIR2_NIR_RATIO"]
        ).reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=region,
            scale=REDUCE_SCALE,
            bestEffort=True,
            maxPixels=1_000_000,
        )

        time_start = image.get("system:time_start")
        date_value = ee.Date(time_start).format("YYYY-MM-dd")

        return ee.Feature(
            None,
            {
                "date": date_value,
                "B4": reduced.get("B4"),
                "B8": reduced.get("B8"),
                "B11": reduced.get("B11"),
                "B12": reduced.get("B12"),
                "NDVI": reduced.get("NDVI"),
                "NBR": reduced.get("NBR"),
                "NBR2": reduced.get("NBR2"),
                "SWIR2_NIR_RATIO": reduced.get("SWIR2_NIR_RATIO"),
                "cloud_pct": image.get("CLOUDY_PIXEL_PERCENTAGE"),
            },
        )

    features = ee.FeatureCollection(collection.map(summarize)).getInfo()

    observations: list[dict[str, Any]] = []
    for feature in features.get("features", []):
        props = feature.get("properties") or {}
        if props.get("date") is None:
            continue

        try:
            values = {
                "date": str(props["date"]),
                "red": float(props["B4"]),
                "nir": float(props["B8"]),
                "swir1": float(props["B11"]),
                "swir2": float(props["B12"]),
                "ndvi": float(props["NDVI"]),
                "nbr": float(props["NBR"]),
                "nbr2": float(props["NBR2"]),
                "swir2_nir_ratio": float(props["SWIR2_NIR_RATIO"]),
                "cloud_pct": (
                    None
                    if props.get("cloud_pct") is None
                    else float(props["cloud_pct"])
                ),
            }
        except (TypeError, ValueError):
            continue

        observations.append(values)

    observations.sort(key=lambda item: item["date"])

    if not observations:
        return []

    frame = pd.DataFrame(observations)
    numeric_columns = [
        "red", "nir", "swir1", "swir2", "ndvi", "nbr", "nbr2", "swir2_nir_ratio", "cloud_pct"
    ]
    grouped = (
        frame.groupby("date", as_index=False)[numeric_columns]
        .mean()
        .sort_values("date")
    )

    result = []
    for _, row in grouped.iterrows():
        result.append(
            {
                "date": row["date"],
                "red": round(float(row["red"]), 4),
                "nir": round(float(row["nir"]), 4),
                "swir1": round(float(row["swir1"]), 4),
                "swir2": round(float(row["swir2"]), 4),
                "ndvi": round(float(row["ndvi"]), 4),
                "nbr": round(float(row["nbr"]), 4),
                "nbr2": round(float(row["nbr2"]), 4),
                "swir2_nir_ratio": round(float(row["swir2_nir_ratio"]), 4),
                "cloud_pct": (
                    None if pd.isna(row["cloud_pct"]) else round(float(row["cloud_pct"]), 2)
                ),
            }
        )

    return result


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
    field_group = group_summary(normalized_id, str(GEOJSON_PATH))

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
