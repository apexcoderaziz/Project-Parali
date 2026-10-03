"""Live Sentinel-2 + ML burn analysis for Project Parali.

The endpoint keeps the existing transparent Sentinel-2 spectral assessment and
adds the existing trained Dual RGB + SWIR ResNet18 as a second, independent
piece of evidence. The CNN is given images rendered from the latest Sentinel-2
scene over the selected field geometry:

    RGB   = B4 / B3 / B2
    SWIR  = B12 / B11 / B8 (false-colour representation)

Important:
- The existing CNN was trained on a different image dataset, so its live
  Sentinel-2 output is cross-domain model evidence, not a newly calibrated
  Sentinel-2 probability.
- The spectral assessment remains separate. This module intentionally avoids
  inventing an arbitrary weighted fusion of the CNN and spectral score.
- Logical fields such as 34 use the shared field context geometry, so all
  matching source-year polygons are analysed together.
"""

from __future__ import annotations

import io
import os
import threading
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import ee
import numpy as np
import pandas as pd
try:
    import requests
except ImportError:
    requests = None

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import rasterio
    from rasterio.io import MemoryFile
except ImportError:
    rasterio = None
    MemoryFile = None

try:
    from .field_context import resolve_field_context
except ImportError:
    from field_context import resolve_field_context

try:
    from .satellite_service import (
        get_sentinel2_series,
        initialize_earth_engine,
    )
except ImportError:
    from satellite_service import (
        get_sentinel2_series,
        initialize_earth_engine,
    )

try:
    from .predict import load_model, predict
except ImportError:
    from predict import load_model, predict


BASE_DIR = Path(__file__).resolve().parent.parent
GEOJSON_PATH = BASE_DIR / "data" / "processed" / "sangrur_fields.geojson"
COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
LOOKBACK_DAYS = 120
MAX_CLOUD_PERCENT = 40
REDUCE_SCALE = 10
ML_REQUEST_TIMEOUT_SECONDS = 60
# Keep the live CNN Earth Engine request bounded. A full-resolution polygon
# download can exceed Earth Engine's 48 MB download-request limit.
ML_CHIP_DIMENSIONS = "512x512"

_MODEL_LOCK = threading.Lock()
_LIVE_MODEL = None


def _fetch_current_series(field_id: str) -> list[dict[str, Any]]:
    """Return the shared canonical Sentinel-2 series for the field."""

    return get_sentinel2_series(
        field_id=field_id,
        lookback_days=LOOKBACK_DAYS,
        max_cloud_percent=MAX_CLOUD_PERCENT,
        reduce_scale=REDUCE_SCALE,
    )


def _get_live_model():
    """Load and cache the existing Dual RGB + SWIR model on first use."""

    global _LIVE_MODEL

    if _LIVE_MODEL is not None:
        return _LIVE_MODEL

    with _MODEL_LOCK:
        if _LIVE_MODEL is None:
            _LIVE_MODEL = load_model()

    return _LIVE_MODEL


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


def _percentile_stretch(channel: np.ndarray) -> np.ndarray:
    """Convert a Sentinel reflectance channel into an 8-bit display image."""

    array = np.asarray(channel, dtype=np.float32)
    finite = array[np.isfinite(array)]

    if finite.size == 0:
        return np.zeros(array.shape, dtype=np.uint8)

    low, high = np.percentile(finite, [2, 98])
    if not np.isfinite(low) or not np.isfinite(high) or high <= low:
        low = float(np.nanmin(finite))
        high = float(np.nanmax(finite))

    if high <= low:
        return np.zeros(array.shape, dtype=np.uint8)

    stretched = (array - low) / (high - low)
    stretched = np.clip(stretched, 0.0, 1.0)
    return np.rint(stretched * 255.0).astype(np.uint8)


def _render_rgb_and_swir(dataset: "rasterio.DatasetReader") -> tuple["Image.Image", "Image.Image"]:
    """Render RGB and SWIR three-channel images from a six-band Sentinel scene."""

    if rasterio is None or MemoryFile is None or Image is None:
        raise RuntimeError(
            "Live CNN rendering requires rasterio and Pillow. "
            "Install them with: pip install rasterio pillow"
        )

    data = dataset.read().astype(np.float32)

    if data.shape[0] < 6:
        raise RuntimeError(
            f"Expected at least 6 Sentinel-2 bands, received {data.shape[0]}"
        )

    # Requested band order: B2, B3, B4, B8, B11, B12.
    blue = _percentile_stretch(data[0])
    green = _percentile_stretch(data[1])
    red = _percentile_stretch(data[2])
    nir = _percentile_stretch(data[3])
    swir1 = _percentile_stretch(data[4])
    swir2 = _percentile_stretch(data[5])

    rgb = np.stack([red, green, blue], axis=-1)
    swir = np.stack([swir2, swir1, nir], axis=-1)

    return Image.fromarray(rgb, mode="RGB"), Image.fromarray(swir, mode="RGB")


def _download_latest_sentinel_scene(field_id: str, destination: str) -> dict[str, Any]:
    """Download the latest usable Sentinel-2 six-band scene for live CNN input."""

    if requests is None or rasterio is None or MemoryFile is None or Image is None:
        raise RuntimeError(
            "Live CNN scene rendering dependencies are missing. "
            "Install them with: pip install requests rasterio pillow"
        )

    initialize_earth_engine()

    context = resolve_field_context(field_id, str(GEOJSON_PATH))
    geometry = context.get("geometry")
    if not isinstance(geometry, dict):
        raise ValueError(f"Field '{field_id}' has no usable geometry")

    region = ee.Geometry(geometry)
    today = date.today()
    start = today - timedelta(days=LOOKBACK_DAYS)
    end = today + timedelta(days=1)

    collection = (
        ee.ImageCollection(COLLECTION)
        .filterBounds(region)
        .filterDate(start.isoformat(), end.isoformat())
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", MAX_CLOUD_PERCENT))
        .filter(ee.Filter.notNull(["system:time_start"]))
        .sort("system:time_start", False)
    )

    count = int(collection.size().getInfo())
    if count <= 0:
        raise RuntimeError("No usable Sentinel-2 scenes were found for this field")

    image = ee.Image(collection.first())
    time_start = image.get("system:time_start")
    scene_date = ee.Date(time_start).format("YYYY-MM-dd").getInfo()
    scene_id = image.get("PRODUCT_ID").getInfo()
    cloud_pct = image.get("CLOUDY_PIXEL_PERCENTAGE").getInfo()

    # IMPORTANT: Do not request the entire field at native 10 m resolution.
    # Large logical/combined field geometries can produce hundreds of MB and
    # exceed Earth Engine's 48 MB getDownloadURL request limit. The CNN later
    # resizes both inputs to 224x224, so a bounded 512x512 scene chip is
    # sufficient for the existing model interface.
    download_url = image.getDownloadURL(
        {
            "bands": ["B2", "B3", "B4", "B8", "B11", "B12"],
            "region": geometry,
            "dimensions": ML_CHIP_DIMENSIONS,
            "filePerBand": False,
            "format": "GEO_TIFF",
        }
    )

    response = requests.get(
        download_url,
        timeout=ML_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    with MemoryFile(response.content) as memory_file:
        with memory_file.open() as dataset:
            rgb_image, swir_image = _render_rgb_and_swir(dataset)
            rgb_path = os.path.join(destination, "live_rgb.png")
            swir_path = os.path.join(destination, "live_swir.png")
            rgb_image.save(rgb_path, format="PNG")
            swir_image.save(swir_path, format="PNG")

    return {
        "scene_date": scene_date,
        "scene_id": scene_id,
        "cloud_pct": None if cloud_pct is None else float(cloud_pct),
        "bands_downloaded": ["B2", "B3", "B4", "B8", "B11", "B12"],
        "rgb_representation": ["B4", "B3", "B2"],
        "swir_representation": ["B12", "B11", "B8"],
        "source_field_ids": context["source_field_ids"],
        "geometry_mode": context["geometry_mode"],
    }, rgb_path, swir_path


def _run_live_cnn(field_id: str) -> dict[str, Any]:
    """Run the existing Dual RGB + SWIR CNN on live Sentinel-2 rendered inputs."""

    model = _get_live_model()

    with TemporaryDirectory(prefix="parali_live_burn_") as temp_dir:
        scene, rgb_path, swir_path = _download_latest_sentinel_scene(
            field_id,
            temp_dir,
        )

        result = predict(
            model,
            rgb_path,
            swir_path,
        )

    return {
        "available": True,
        "model": "Dual RGB + SWIR ResNet18",
        "task": "Crop residue burning detection",
        "prediction": result["prediction"],
        "confidence_percent": round(float(result["confidence"]), 2),
        "softmax_burn_score_percent": round(
            float(result["burn_probability"]),
            2,
        ),
        "softmax_no_burn_score_percent": round(
            float(result["no_burn_probability"]),
            2,
        ),
        "score_interpretation": "Model softmax score; not a calibrated Sentinel-2 probability.",
        "input_source": "Live Sentinel-2 SR Harmonized",
        **scene,
        "training_domain_warning": (
            "The CNN was trained on a separate RGB + SWIR image dataset. "
            "Live Sentinel-2 imagery is a different input domain, so this result "
            "should be treated as independent model evidence until retrained and "
            "validated directly on Sentinel-2 samples."
        ),
    }


def analyze_live_burn(field_id: str) -> dict[str, Any]:
    """Run live Sentinel-2 spectral + independent ML burn assessment."""

    normalized_id = str(field_id).strip()
    if not normalized_id:
        raise ValueError("field_id cannot be empty")

    series = _fetch_current_series(normalized_id)
    signals = _score_burn_signals(series)
    latest = series[-1] if series else None
    field_group = resolve_field_context(normalized_id, str(GEOJSON_PATH))

    ml_result: dict[str, Any]
    try:
        ml_result = _run_live_cnn(normalized_id)
    except Exception as exc:
        # Keep spectral intelligence available even when the optional CNN
        # bridge cannot download/render a live scene.
        ml_result = {
            "available": False,
            "model": "Dual RGB + SWIR ResNet18",
            "error": str(exc),
            "score_interpretation": "Live ML evidence unavailable for this request.",
        }

    return {
        "success": True,
        "field_id": normalized_id,
        "source_field_ids": field_group["source_field_ids"],
        "source_field_count": field_group["source_field_count"],
        "geometry_mode": field_group["geometry_mode"],
        "analysis_type": "live Sentinel-2 spectral + Dual CNN burn assessment",
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
        "ml_model": ml_result,
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
            "The spectral score is a transparent field-level burn-related signal assessment. "
            "The CNN result is an independent model output from the existing RGB + SWIR model, "
            "rendered from the latest Sentinel-2 scene; it is not a calibrated Sentinel-2 probability. "
            "The two signals are intentionally reported separately rather than fused with an arbitrary weight."
        ),
        "limitations": [
            "The latest Sentinel-2 scene is the latest usable observation returned by Earth Engine, not necessarily an observation from today.",
            "The signal is field-level and may contain mixed pixels near field boundaries.",
            "Drying or harvesting vegetation can produce spectral changes similar to burning.",
            "The existing CNN was trained on a separate RGB + SWIR image dataset and has not been calibrated on live Sentinel-2 inputs in this module.",
            "Live CNN rendering uses B4/B3/B2 as RGB and B12/B11/B8 as a SWIR false-colour representation for compatibility with the trained model input interface.",
        ],
    }
