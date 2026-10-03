"""Shared Sentinel-2 acquisition service for Project Parali.

Phase 2 architecture:
- Resolve logical fields through the shared field context.
- Authenticate/configure Google Earth Engine once per API process.
- Fetch one canonical Sentinel-2 observation series for a field.
- Derive the common vegetation/burn spectral indicators in one place.
- Cache the short-lived result so Live Harvest and Live Burn can reuse the
  same Earth Engine observations instead of issuing duplicate requests.

This service intentionally does not decide whether a field is harvested or
burned. It only acquires and standardizes satellite evidence.
"""

from __future__ import annotations

import os
import threading
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

import ee
import pandas as pd

try:
    from .field_context import resolve_field_context
except ImportError:
    from field_context import resolve_field_context


BASE_DIR = Path(__file__).resolve().parent.parent
GEOJSON_PATH = BASE_DIR / "data" / "processed" / "sangrur_fields.geojson"

EE_PROJECT = os.getenv(
    "EARTH_ENGINE_PROJECT",
    "project-18808c04-2093-4bb1-940",
)

# Render runs without the developer's local Earth Engine credentials.
# When a service-account email is configured, authenticate with the private
# key stored as a Render Secret File. Without these variables, preserve the
# existing local ee.Initialize() behavior for development on the user's PC.
EE_SERVICE_ACCOUNT = os.getenv("EARTH_ENGINE_SERVICE_ACCOUNT", "").strip()
EE_PRIVATE_KEY_FILE = os.getenv(
    "EARTH_ENGINE_PRIVATE_KEY_FILE",
    "/etc/secrets/earth-engine-key.json",
).strip()

COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
DEFAULT_LOOKBACK_DAYS = 120
DEFAULT_MAX_CLOUD_PERCENT = 40
DEFAULT_REDUCE_SCALE = 10
DEFAULT_CACHE_TTL_SECONDS = 300


_initialized = False
_initialize_lock = threading.Lock()
_cache_lock = threading.Lock()
_series_cache: Dict[Tuple[str, int, float, int], Tuple[float, List[Dict[str, Any]]]] = {}


class SatelliteServiceError(RuntimeError):
    """Raised when shared Sentinel-2 acquisition cannot be completed."""


def initialize_earth_engine() -> None:
    """Initialize Earth Engine once for the current API process."""

    global _initialized

    if _initialized:
        return

    with _initialize_lock:
        if _initialized:
            return

        try:
            if EE_SERVICE_ACCOUNT:
                if not os.path.isfile(EE_PRIVATE_KEY_FILE):
                    raise FileNotFoundError(
                        f"Earth Engine private key file not found: {EE_PRIVATE_KEY_FILE}"
                    )

                credentials = ee.ServiceAccountCredentials(
                    EE_SERVICE_ACCOUNT,
                    EE_PRIVATE_KEY_FILE,
                )
                ee.Initialize(
                    credentials=credentials,
                    project=EE_PROJECT,
                )
            else:
                # Local development fallback. This uses the credentials created
                # by ee.Authenticate()/earthengine authenticate on the developer PC.
                ee.Initialize(project=EE_PROJECT)
        except Exception as exc:
            if EE_SERVICE_ACCOUNT:
                raise SatelliteServiceError(
                    "Google Earth Engine service-account authentication failed. "
                    "Verify EARTH_ENGINE_SERVICE_ACCOUNT, the Render Secret File "
                    f"at '{EE_PRIVATE_KEY_FILE}', and project '{EE_PROJECT}'. "
                    f"Original error: {exc}"
                ) from exc

            raise SatelliteServiceError(
                "Google Earth Engine is not initialized for the API process. "
                "For local development, authenticate this Windows account with "
                "Earth Engine. For Render, configure the service-account variables "
                f"and project '{EE_PROJECT}'. Original error: {exc}"
            ) from exc

        _initialized = True


def _mask_and_indices(image: ee.Image) -> ee.Image:
    """Apply the existing QA60 mask and derive the canonical indicators."""

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
    nbr2 = scaled.normalizedDifference(["B11", "B12"]).rename("NBR2")

    swir2_nir_ratio = scaled.select("B12").divide(
        scaled.select("B8").add(0.001)
    ).rename("SWIR2_NIR_RATIO")

    return scaled.addBands(
        [ndvi, nbr, nbr2, swir2_nir_ratio]
    ).copyProperties(image, image.propertyNames())


def _cache_key(
    field_id: str,
    lookback_days: int,
    max_cloud_percent: float,
    reduce_scale: int,
) -> Tuple[str, int, float, int]:
    return (
        str(field_id).strip(),
        int(lookback_days),
        float(max_cloud_percent),
        int(reduce_scale),
    )


def _get_cached_series(
    key: Tuple[str, int, float, int],
    ttl_seconds: float,
) -> List[Dict[str, Any]] | None:
    now = time.monotonic()

    with _cache_lock:
        cached = _series_cache.get(key)
        if cached is None:
            return None

        created_at, series = cached
        if now - created_at > ttl_seconds:
            _series_cache.pop(key, None)
            return None

        # Return a new list and dicts so downstream scoring cannot mutate the
        # canonical cached representation.
        return [dict(item) for item in series]


def clear_satellite_cache(field_id: str | None = None) -> None:
    """Clear all cached satellite series or only one field's series."""

    with _cache_lock:
        if field_id is None:
            _series_cache.clear()
            return

        normalized = str(field_id).strip()
        keys_to_remove = [
            key for key in _series_cache
            if key[0] == normalized
        ]
        for key in keys_to_remove:
            _series_cache.pop(key, None)


def _build_collection(
    field_geometry: Dict[str, Any],
    start: date,
    end: date,
    max_cloud_percent: float,
) -> ee.ImageCollection:
    """Build the canonical filtered Sentinel-2 collection."""

    region = ee.Geometry(field_geometry)

    return (
        ee.ImageCollection(COLLECTION)
        .filterBounds(region)
        .filterDate(start.isoformat(), end.isoformat())
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud_percent))
        .filter(ee.Filter.notNull(["system:time_start"]))
        .map(_mask_and_indices)
    )


def _fetch_series_from_earth_engine(
    field_id: str,
    lookback_days: int,
    max_cloud_percent: float,
    reduce_scale: int,
) -> List[Dict[str, Any]]:
    """Fetch and normalize the canonical Sentinel-2 field time series."""

    initialize_earth_engine()

    context = resolve_field_context(
        field_id,
        str(GEOJSON_PATH),
    )
    geometry_dict = context.get("geometry")

    if not isinstance(geometry_dict, dict):
        raise ValueError(f"Field '{field_id}' has no usable geometry")

    region = ee.Geometry(geometry_dict)
    today = date.today()
    start = today - timedelta(days=int(lookback_days))
    end = today + timedelta(days=1)

    collection = _build_collection(
        geometry_dict,
        start,
        end,
        max_cloud_percent,
    )

    def summarize(image: ee.Image) -> ee.Feature:
        reduced = image.select(
            [
                "B4",
                "B8",
                "B11",
                "B12",
                "NDVI",
                "NBR",
                "NBR2",
                "SWIR2_NIR_RATIO",
            ]
        ).reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=region,
            scale=reduce_scale,
            bestEffort=True,
            maxPixels=1_000_000,
        )

        # The collection is filtered for non-null timestamps. Keep the same
        # defensive metadata handling used by the previous implementations.
        time_start = image.get("system:time_start")
        date_value = ee.Date(time_start).format("YYYY-MM-dd")

        return ee.Feature(
            None,
            {
                "date": date_value,
                "red": reduced.get("B4"),
                "nir": reduced.get("B8"),
                "swir1": reduced.get("B11"),
                "swir2": reduced.get("B12"),
                "ndvi": reduced.get("NDVI"),
                "nbr": reduced.get("NBR"),
                "nbr2": reduced.get("NBR2"),
                "swir2_nir_ratio": reduced.get("SWIR2_NIR_RATIO"),
                "cloud_pct": image.get("CLOUDY_PIXEL_PERCENTAGE"),
            },
        )

    features = ee.FeatureCollection(collection.map(summarize)).getInfo()

    observations: List[Dict[str, Any]] = []

    for feature in features.get("features", []):
        properties = feature.get("properties") or {}
        observation_date = properties.get("date")

        if observation_date is None:
            continue

        try:
            observations.append(
                {
                    "date": str(observation_date),
                    "red": float(properties["red"]),
                    "nir": float(properties["nir"]),
                    "swir1": float(properties["swir1"]),
                    "swir2": float(properties["swir2"]),
                    "ndvi": float(properties["ndvi"]),
                    "nbr": float(properties["nbr"]),
                    "nbr2": float(properties["nbr2"]),
                    "swir2_nir_ratio": float(properties["swir2_nir_ratio"]),
                    "cloud_pct": (
                        None
                        if properties.get("cloud_pct") is None
                        else float(properties["cloud_pct"])
                    ),
                }
            )
        except (KeyError, TypeError, ValueError):
            # Drop observations that do not contain complete field-level
            # spectral values. This keeps downstream scoring deterministic.
            continue

    observations.sort(key=lambda item: item["date"])

    if not observations:
        return []

    frame = pd.DataFrame(observations)
    numeric_columns = [
        "red",
        "nir",
        "swir1",
        "swir2",
        "ndvi",
        "nbr",
        "nbr2",
        "swir2_nir_ratio",
        "cloud_pct",
    ]

    grouped = (
        frame.groupby("date", as_index=False)[numeric_columns]
        .mean()
        .sort_values("date")
    )

    series: List[Dict[str, Any]] = []

    for _, row in grouped.iterrows():
        series.append(
            {
                "date": row["date"],
                "red": round(float(row["red"]), 4),
                "nir": round(float(row["nir"]), 4),
                "swir1": round(float(row["swir1"]), 4),
                "swir2": round(float(row["swir2"]), 4),
                "ndvi": round(float(row["ndvi"]), 4),
                "nbr": round(float(row["nbr"]), 4),
                "nbr2": round(float(row["nbr2"]), 4),
                "swir2_nir_ratio": round(
                    float(row["swir2_nir_ratio"]),
                    4,
                ),
                "cloud_pct": (
                    None
                    if pd.isna(row["cloud_pct"])
                    else round(float(row["cloud_pct"]), 2)
                ),
            }
        )

    return series


def get_sentinel2_series(
    field_id: str,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    max_cloud_percent: float = DEFAULT_MAX_CLOUD_PERCENT,
    reduce_scale: int = DEFAULT_REDUCE_SCALE,
    cache_ttl_seconds: float = DEFAULT_CACHE_TTL_SECONDS,
) -> List[Dict[str, Any]]:
    """Return one canonical Sentinel-2 evidence series for a field.

    The first request performs the Earth Engine query. Repeated requests with
    the same parameters within the short cache TTL reuse the exact same series,
    allowing Live Harvest and Live Burn to share one acquisition result.
    """

    normalized_id = str(field_id).strip()
    if not normalized_id:
        raise ValueError("field_id cannot be empty")

    if lookback_days <= 0:
        raise ValueError("lookback_days must be greater than 0")

    if max_cloud_percent < 0 or max_cloud_percent > 100:
        raise ValueError("max_cloud_percent must be between 0 and 100")

    if reduce_scale <= 0:
        raise ValueError("reduce_scale must be greater than 0")

    key = _cache_key(
        normalized_id,
        lookback_days,
        max_cloud_percent,
        reduce_scale,
    )

    cached = _get_cached_series(key, cache_ttl_seconds)
    if cached is not None:
        return cached

    series = _fetch_series_from_earth_engine(
        normalized_id,
        lookback_days,
        max_cloud_percent,
        reduce_scale,
    )

    with _cache_lock:
        _series_cache[key] = (
            time.monotonic(),
            [dict(item) for item in series],
        )

    return [dict(item) for item in series]


def latest_observation(
    series: List[Dict[str, Any]],
) -> Dict[str, Any] | None:
    """Return the latest canonical observation without mutating the series."""

    if not series:
        return None
    return dict(series[-1])


def satellite_data_source_metadata(
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    max_cloud_percent: float = DEFAULT_MAX_CLOUD_PERCENT,
    reduce_scale: int = DEFAULT_REDUCE_SCALE,
) -> Dict[str, Any]:
    """Return shared metadata for module responses and diagnostics."""

    return {
        "collection": COLLECTION,
        "lookback_days": int(lookback_days),
        "max_cloud_percent": float(max_cloud_percent),
        "scale_meters": int(reduce_scale),
        "bands": ["B4", "B8", "B11", "B12"],
        "indices": [
            "NDVI",
            "NBR",
            "NBR2",
            "SWIR2_NIR_RATIO",
        ],
    }
