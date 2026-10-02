"""
Project Parali - live harvest likelihood engine.

This module combines:
1. Historical Sangrur crop-transition dates from harvest_windows.csv.
2. Current/latest Sentinel-2 observations for the clicked field from
   Google Earth Engine.
3. NDVI/NBR trend signals and persistence.

Important:
- The result is a satellite-derived likelihood, not a confirmed harvest date.
- Sentinel-2 observations are only as current as the latest available scene.
- Historical labels currently describe crop-transition/burn observations;
  they are not farmer-confirmed harvest timestamps.
"""

from __future__ import annotations

import json
import math
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Any

from .field_grouping import combined_geometry, group_summary, load_field_features, resolve_field_ids

import ee
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
GEOJSON_PATH = BASE_DIR / "data" / "processed" / "sangrur_fields.geojson"
HARVEST_WINDOW_PATH = BASE_DIR / "data" / "processed" / "harvest_windows.csv"

EE_PROJECT = os.getenv(
    "EARTH_ENGINE_PROJECT",
    "project-18808c04-2093-4bb1-940",
)

COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
LOOKBACK_DAYS = 120
MAX_CLOUD_PERCENT = 40
REDUCE_SCALE = 10


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

    return scaled.addBands([ndvi, nbr]).copyProperties(
        image, image.propertyNames()
    )


def _fetch_current_series(field_id: str) -> list[dict[str, Any]]:
    _initialize_earth_engine()

    geometry_dict = _load_field_geometry(field_id)
    region = ee.Geometry(geometry_dict)

    today = date.today()
    start = today - timedelta(days=LOOKBACK_DAYS)
    end = today + timedelta(days=1)

    # Keep only images that have a valid acquisition timestamp before any
    # server-side mapping. Some Sentinel-2 records can otherwise reach the
    # mapped function with a null system:time_start, which makes ee.Date()
    # fail with: "Date: Parameter 'value' is required and may not be null."
    collection = (
        ee.ImageCollection(COLLECTION)
        .filterBounds(region)
        .filterDate(start.isoformat(), end.isoformat())
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", MAX_CLOUD_PERCENT))
        .filter(ee.Filter.notNull(["system:time_start"]))
        .map(_mask_and_indices)
    )

    def summarize(image: ee.Image) -> ee.Feature:
        # The collection was filtered for non-null timestamps above. Keep the
        # original acquisition timestamp on the transformed image as well.
        reduced = image.select(["NDVI", "NBR"]).reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=region,
            scale=REDUCE_SCALE,
            bestEffort=True,
            maxPixels=1_000_000,
        )

        # Some Earth Engine image transformations can leave a mapped image
        # without the expected acquisition-time metadata. Guard the date
        # before constructing ee.Date so one malformed image cannot fail the
        # entire server-side collection evaluation.
        time_start = image.get("system:time_start")
        date_value = ee.Date(time_start).format("YYYY-MM-dd")

        return ee.Feature(
            None,
            {
                "date": date_value,
                "ndvi": reduced.get("NDVI"),
                "nbr": reduced.get("NBR"),
                "cloud_pct": image.get("CLOUDY_PIXEL_PERCENTAGE"),
            },
        )

    features = ee.FeatureCollection(collection.map(summarize)).getInfo()

    observations: list[dict[str, Any]] = []
    for feature in features.get("features", []):
        props = feature.get("properties") or {}
        ndvi = props.get("ndvi")
        nbr = props.get("nbr")
        obs_date = props.get("date")

        if obs_date is None or ndvi is None or nbr is None:
            continue

        try:
            observations.append(
                {
                    "date": str(obs_date),
                    "ndvi": float(ndvi),
                    "nbr": float(nbr),
                    "cloud_pct": (
                        None
                        if props.get("cloud_pct") is None
                        else float(props["cloud_pct"])
                    ),
                }
            )
        except (TypeError, ValueError):
            continue

    observations.sort(key=lambda item: item["date"])

    # Multiple Sentinel-2 granules can produce duplicate dates. Average them
    # so the trend is driven by the field-level daily observation, not tile count.
    if not observations:
        return []

    frame = pd.DataFrame(observations)
    grouped = (
        frame.groupby("date", as_index=False)
        .agg(
            ndvi=("ndvi", "mean"),
            nbr=("nbr", "mean"),
            cloud_pct=("cloud_pct", "mean"),
        )
        .sort_values("date")
    )

    return [
        {
            "date": row["date"],
            "ndvi": round(float(row["ndvi"]), 4),
            "nbr": round(float(row["nbr"]), 4),
            "cloud_pct": (
                None
                if pd.isna(row["cloud_pct"])
                else round(float(row["cloud_pct"]), 2)
            ),
        }
        for _, row in grouped.iterrows()
    ]


def _historical_candidate_days(field_id: str | None = None) -> list[int]:
    """Load historical candidate timing for the selected source field group."""

    if not HARVEST_WINDOW_PATH.exists():
        return []

    df = pd.read_csv(HARVEST_WINDOW_PATH)
    if "candidate_date" not in df.columns:
        return []

    if field_id is not None and "field_id" in df.columns:
        source_ids = set(resolve_field_ids(field_id, str(GEOJSON_PATH)))
        if source_ids:
            df["field_id"] = df["field_id"].astype(str).str.strip()
            df = df[df["field_id"].isin(source_ids)]

    dates = pd.to_datetime(df["candidate_date"], errors="coerce").dropna()
    return [int(value.dayofyear) for value in dates]


def _circular_day_distance(a: int, b: int) -> int:
    difference = abs(a - b)
    return min(difference, 365 - difference)


def _safe_slope(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0

    x_mean = (len(values) - 1) / 2
    y_mean = sum(values) / len(values)
    denominator = sum((index - x_mean) ** 2 for index in range(len(values)))
    if denominator == 0:
        return 0.0

    numerator = sum(
        (index - x_mean) * (value - y_mean)
        for index, value in enumerate(values)
    )
    return numerator / denominator


def _trend_label(values: list[float]) -> str:
    slope = _safe_slope(values)
    if slope <= -0.012:
        return "strongly decreasing"
    if slope <= -0.004:
        return "decreasing"
    if slope >= 0.012:
        return "strongly increasing"
    if slope >= 0.004:
        return "increasing"
    return "stable"


def _score_current_signals(series: list[dict[str, Any]]) -> dict[str, Any]:
    if not series:
        return {
            "score": 0.0,
            "label": "insufficient data",
            "ndvi_trend": "unknown",
            "nbr_trend": "unknown",
            "ndvi_drop": None,
            "nbr_drop": None,
            "negative_steps": 0,
            "signal_reasons": [],
        }

    recent = series[-8:]
    ndvi_values = [item["ndvi"] for item in recent]
    nbr_values = [item["nbr"] for item in recent]

    ndvi_trend = _trend_label(ndvi_values)
    nbr_trend = _trend_label(nbr_values)

    peak_ndvi = max(ndvi_values)
    peak_nbr = max(nbr_values)
    current_ndvi = ndvi_values[-1]
    current_nbr = nbr_values[-1]

    ndvi_drop = max(0.0, peak_ndvi - current_ndvi)
    nbr_drop = max(0.0, peak_nbr - current_nbr)

    negative_steps = sum(
        1
        for previous, current in zip(ndvi_values, ndvi_values[1:])
        if current < previous
    )

    # Conservative, interpretable signal score. This is not a trained
    # probability model, so the returned percentage is explicitly a
    # "signal strength", not statistical confidence.
    score = 0.0
    reasons: list[str] = []

    if ndvi_drop >= 0.30:
        score += 35
        reasons.append("NDVI has fallen substantially from the recent peak")
    elif ndvi_drop >= 0.18:
        score += 25
        reasons.append("NDVI shows a meaningful decline")
    elif ndvi_drop >= 0.10:
        score += 12
        reasons.append("NDVI shows an early decline")

    if nbr_drop >= 0.25:
        score += 25
        reasons.append("NBR has also declined strongly")
    elif nbr_drop >= 0.12:
        score += 16
        reasons.append("NBR is declining")
    elif nbr_drop >= 0.06:
        score += 8
        reasons.append("NBR shows a mild decline")

    if negative_steps >= 5:
        score += 20
        reasons.append("NDVI decline persists across recent observations")
    elif negative_steps >= 3:
        score += 12
        reasons.append("NDVI has declined across several recent observations")

    if ndvi_trend == "strongly decreasing":
        score += 10
    elif ndvi_trend == "decreasing":
        score += 6

    if nbr_trend == "strongly decreasing":
        score += 10
    elif nbr_trend == "decreasing":
        score += 6

    score = min(score, 100.0)

    if score >= 70:
        label = "high"
    elif score >= 45:
        label = "medium"
    else:
        label = "low"

    return {
        "score": round(score, 1),
        "label": label,
        "ndvi_trend": ndvi_trend,
        "nbr_trend": nbr_trend,
        "ndvi_drop": round(ndvi_drop, 4),
        "nbr_drop": round(nbr_drop, 4),
        "negative_steps": negative_steps,
        "signal_reasons": reasons,
    }


def _historical_transition_window(candidate_days: list[int], year: int) -> dict[str, Any] | None:
    """Convert historical candidate timing into a transparent calendar window.

    This is a historical-context window, not a validated future harvest forecast.
    The median candidate day is expanded by +/- 7 days to avoid presenting a
    single historical date as an exact prediction.
    """
    if not candidate_days:
        return None

    median_day = int(round(median(candidate_days)))
    start_day = max(1, median_day - 7)
    end_day = min(365, median_day + 7)

    start_date = date(year, 1, 1) + timedelta(days=start_day - 1)
    end_date = date(year, 1, 1) + timedelta(days=end_day - 1)

    return {
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "basis": "historical candidate-transition timing +/- 7 days",
        "median_candidate_date": (
            date(year, 1, 1) + timedelta(days=median_day - 1)
        ).isoformat(),
    }


def predict_harvest(field_id: str) -> dict[str, Any]:
    """Run current satellite analysis for one Sangrur field."""

    normalized_id = str(field_id).strip()
    if not normalized_id:
        raise ValueError("field_id cannot be empty")

    series = _fetch_current_series(normalized_id)
    signals = _score_current_signals(series)

    historical_days = _historical_candidate_days(normalized_id)
    field_group = group_summary(normalized_id, str(GEOJSON_PATH))
    today = date.today()
    current_day = today.timetuple().tm_yday

    historical_context: dict[str, Any] = {
        "sample_count": len(historical_days),
        "median_candidate_day_of_year": None,
        "median_candidate_date": None,
        "current_day_distance": None,
        "season_alignment": "unavailable",
        "estimated_transition_window": None,
    }

    if historical_days:
        historical_median = int(round(median(historical_days)))
        distance = _circular_day_distance(current_day, historical_median)

        if distance <= 14:
            alignment = "strong"
        elif distance <= 30:
            alignment = "moderate"
        else:
            alignment = "weak"

        transition_window = _historical_transition_window(
            historical_days,
            today.year,
        )

        historical_context.update(
            {
                "median_candidate_day_of_year": historical_median,
                "median_candidate_date": (
                    transition_window["median_candidate_date"]
                    if transition_window
                    else None
                ),
                "current_day_distance": distance,
                "season_alignment": alignment,
                "estimated_transition_window": transition_window,
            }
        )

        if alignment == "strong":
            signals["score"] = min(100.0, signals["score"] + 8)
            signals["signal_reasons"].append(
                "Current date is close to the historical Sangrur transition period"
            )
        elif alignment == "moderate":
            signals["score"] = min(100.0, signals["score"] + 4)
            signals["signal_reasons"].append(
                "Current date is moderately close to the historical transition period"
            )

    if signals["score"] >= 70:
        signals["label"] = "high"
    elif signals["score"] >= 45:
        signals["label"] = "medium"
    else:
        signals["label"] = "low"

    latest = series[-1] if series else None

    if signals["label"] == "high":
        status = "harvest_transition_signal"
        status_label = "Strong harvest-transition signal"
        signal_level = "Strong"
    elif signals["label"] == "medium":
        status = "possible_transition"
        status_label = "Possible harvest transition"
        signal_level = "Moderate"
    elif series:
        status = "no_strong_signal"
        status_label = "No strong harvest signal"
        signal_level = "Low"
    else:
        status = "insufficient_data"
        status_label = "Insufficient current satellite data"
        signal_level = "Unknown"

    validation_note = (
        "This is a live Sentinel-2 signal assessment, not a calibrated "
        "statistical probability or confirmed harvest date. Historical "
        "Sangrur data provides crop-transition context but does not contain "
        "independently validated future harvest timestamps."
    )

    return {
        "success": True,
        "field_id": normalized_id,
        "source_field_ids": field_group["source_field_ids"],
        "source_field_count": field_group["source_field_count"],
        "geometry_mode": field_group["geometry_mode"],
        "prediction_type": "live satellite harvest likelihood",
        "harvest_likelihood": signals["label"],
        "signal_strength": signals["score"],
        "status": status,
        "status_label": status_label,
        "signal_level": signal_level,
        "as_of_date": latest["date"] if latest else None,
        "confidence": None,
        "signals": {
            "ndvi_decline_from_peak": signals["ndvi_drop"],
            "nbr_decline_from_peak": signals["nbr_drop"],
            "ndvi_trend": signals["ndvi_trend"],
            "nbr_trend": signals["nbr_trend"],
            "negative_steps": signals["negative_steps"],
            "observations": len(series),
        },
        "reasons": signals["signal_reasons"],
        "validation_note": validation_note,
        "interpretation": (
            "Strong current crop-transition signals"
            if signals["label"] == "high"
            else "Some current crop-transition signals"
            if signals["label"] == "medium"
            else "No strong current crop-transition signal"
            if signals["label"] == "low"
            else "Insufficient current satellite observations"
        ),
        "latest_observation": latest,
        "current_signals": signals,
        "historical_context": historical_context,
        "estimated_transition_window": historical_context.get(
            "estimated_transition_window"
        ),
        "time_series": series,
        "data_source": {
            "current": COLLECTION,
            "historical": str(HARVEST_WINDOW_PATH.relative_to(BASE_DIR)),
            "source_field_ids": field_group["source_field_ids"],
            "geometry_mode": field_group["geometry_mode"],
            "lookback_days": LOOKBACK_DAYS,
            "max_cloud_percent": MAX_CLOUD_PERCENT,
        },
        "limitations": [
            "This is a satellite-derived likelihood, not a confirmed harvest event.",
            "The historical dataset contains candidate crop-transition dates rather than farmer-confirmed harvest timestamps.",
            "The current Sentinel-2 observation is the latest usable scene returned by Earth Engine, not necessarily an observation from today.",
            "A field polygon may contain a different crop in the current season than in the historical labeled season.",
        ],
    }
