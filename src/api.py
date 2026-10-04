import json
import math
import os
from numbers import Number
import shutil
import uuid

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

try:
    from .predict import load_model, predict
except ImportError:
    from predict import load_model, predict

from .residue_estimation import estimate_residue

try:
    from .field_grouping import group_summary, resolve_field_ids
except ImportError:
    from field_grouping import group_summary, resolve_field_ids

try:
    from .logistics_estimation import estimate_logistics
except ImportError:
    from logistics_estimation import estimate_logistics

try:
    from .biomass_opportunity import match_facilities
except ImportError:
    from biomass_opportunity import match_facilities

try:
    from .biomass_clustering import get_field_cluster
except ImportError:
    from biomass_clustering import get_field_cluster


# Live Sentinel-2 monitoring engine.
try:
    from .harvest_prediction import predict_harvest
except ImportError:
    from harvest_prediction import predict_harvest

# Live Sentinel-2 burn-analysis engine.
try:
    from .live_burn_analysis import analyze_live_burn
except ImportError:
    from live_burn_analysis import analyze_live_burn


# =========================================================
# PATHS
# =========================================================

BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

TIMESERIES_PATH = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "field_ndvi_timeseries.csv",
)

HARVEST_WINDOW_PATH = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "harvest_windows.csv",
)

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


# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(
    title="Project Parali API",
    description=(
        "AI-powered satellite crop harvest and crop-residue "
        "intelligence platform"
    ),
    version="2.0.0",
)


# Keep localhost origins for development and explicitly allow the
# deployed React frontend. Environment variables are still supported
# so another deployed frontend URL can be added without changing code.
_local_frontend_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

_production_frontend_origins = [
    "https://project-parali-frontend.onrender.com",
]

_configured_frontend_origins = [
    value.strip().rstrip("/")
    for value in os.getenv(
        "FRONTEND_URLS",
        os.getenv("FRONTEND_URL", ""),
    ).split(",")
    if value.strip()
]

_allowed_frontend_origins = list(
    dict.fromkeys(
        _local_frontend_origins
        + _production_frontend_origins
        + _configured_frontend_origins
    )
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# BURN MODEL
# =========================================================

# Keep the API startup lightweight. The trained CNN is loaded lazily so
# /fields, /field-analysis and the other data endpoints can respond even
# when model initialization or local TorchVision weights take longer.
model = None
_model_lock = None


def get_burn_model():
    """Load the trained burn model only when a CNN request needs it."""
    global model, _model_lock

    if model is not None:
        return model

    if _model_lock is None:
        import threading
        _model_lock = threading.Lock()

    with _model_lock:
        if model is None:
            model = load_model()

    return model


# =========================================================
# SMALL HELPERS
# =========================================================

def clean_field_id(value):
    if value is None:
        return ""
    return str(value).strip()


def json_number(value, digits=4):
    if value is None or pd.isna(value):
        return None
    try:
        number = float(value)
        if not math.isfinite(number):
            return None
        return round(number, digits)
    except (TypeError, ValueError):
        return None


def load_timeseries():
    if not os.path.exists(TIMESERIES_PATH):
        raise HTTPException(
            status_code=404,
            detail="Satellite time-series data not found",
        )

    df = pd.read_csv(TIMESERIES_PATH)

    required = {"field_id", "date", "ndvi", "nbr"}
    missing = required - set(df.columns)

    if missing:
        raise HTTPException(
            status_code=500,
            detail=(
                "field_ndvi_timeseries.csv is missing columns: "
                + ", ".join(sorted(missing))
            ),
        )

    df["field_id"] = df["field_id"].map(clean_field_id)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["ndvi"] = pd.to_numeric(df["ndvi"], errors="coerce")
    df["nbr"] = pd.to_numeric(df["nbr"], errors="coerce")

    df = df.dropna(subset=["date"])
    df = df[df["field_id"] != ""].copy()

    return df.sort_values(["field_id", "date"])


def load_harvest_windows():
    if not os.path.exists(HARVEST_WINDOW_PATH):
        return pd.DataFrame()

    df = pd.read_csv(HARVEST_WINDOW_PATH)

    if "field_id" not in df.columns:
        return pd.DataFrame()

    df["field_id"] = df["field_id"].map(clean_field_id)

    for column in [
        "candidate_date",
        "peak_date",
    ]:
        if column in df.columns:
            df[column] = pd.to_datetime(
                df[column],
                errors="coerce",
            )

    for column in [
        "peak_ndvi",
        "candidate_ndvi",
        "decline",
    ]:
        if column in df.columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

    return df


def load_field_indicators():
    if not os.path.exists(FIELD_INDICATORS_PATH):
        return pd.DataFrame()

    df = pd.read_csv(FIELD_INDICATORS_PATH)

    if "field_id" not in df.columns:
        return pd.DataFrame()

    df["field_id"] = df["field_id"].map(clean_field_id)
    return df


def load_geojson():
    if not os.path.exists(GEOJSON_PATH):
        raise HTTPException(
            status_code=404,
            detail="Sangrur GeoJSON not found",
        )

    try:
        with open(GEOJSON_PATH, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not read Sangrur GeoJSON: {exc}",
        )


def row_to_indicator_dict(row):
    result = {}

    for key, value in row.items():
        if pd.isna(value):
            result[key] = None
        elif isinstance(value, (pd.Timestamp,)):
            result[key] = value.strftime("%Y-%m-%d")
        elif isinstance(value, Number):
            result[key] = round(float(value), 4)
        else:
            result[key] = value

    return result


# =========================================================
# HARVEST PREDICTION ENGINE
# =========================================================


def calculate_harvest_prediction(field_id):
    """
    Analyze the selected field's Sentinel-2 NDVI/NBR time series.

    A logical field number such as ``34`` combines the matching source-year
    records (for example, ``2020_34`` and ``2021_34``). Full source IDs keep
    their original single-field behavior.

    The result is a transparent satellite signal assessment, not a
    calibrated probability or an exact future harvest-date forecast.
    """

    requested_field_id = clean_field_id(field_id)
    summary = group_summary(requested_field_id, GEOJSON_PATH)
    source_field_ids = summary["source_field_ids"]

    df = load_timeseries()
    field_df = df[df["field_id"].isin(source_field_ids)].copy()

    if field_df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Field {requested_field_id} not found",
        )

    field_df = field_df.sort_values("date")

    # Multiple Sentinel-2 tiles and multiple source-year members can create
    # duplicate dates. Aggregate them into one logical Field-N time point.
    series = (
        field_df.groupby("date", as_index=False)[["ndvi", "nbr"]]
        .mean()
        .sort_values("date")
    )

    valid = series[series["ndvi"].notna()].copy()

    group_payload = {
        "source_field_ids": source_field_ids,
        "source_field_count": len(source_field_ids),
        "geometry_mode": summary["geometry_mode"],
        "aggregation": "mean Sentinel-2 values across source-year members by date",
    }

    if len(valid) < 3:
        return {
            "field_id": requested_field_id,
            **group_payload,
            "as_of_date": (
                valid.iloc[-1]["date"].strftime("%Y-%m-%d")
                if not valid.empty
                else None
            ),
            "status": "insufficient_data",
            "status_label": "Insufficient satellite data",
            "signal_level": "Unknown",
            "confidence": None,
            "signals": {},
            "reasons": [
                "At least 3 valid NDVI observations are required for a field-level trend assessment."
            ],
            "model_status": "satellite-signal assessment",
            "validation_note": (
                "This is a satellite crop-transition signal assessment. "
                "The available Sangrur data does not contain independently "
                "validated future harvest-date labels."
            ),
        }

    latest = valid.iloc[-1]
    latest_date = latest["date"]
    latest_ndvi = float(latest["ndvi"])

    nbr_valid = series[series["nbr"].notna()].copy()
    latest_nbr = (
        float(nbr_valid.iloc[-1]["nbr"])
        if not nbr_valid.empty
        else None
    )

    peak_index = valid["ndvi"].idxmax()
    peak_row = valid.loc[peak_index]
    peak_date = peak_row["date"]
    peak_ndvi = float(peak_row["ndvi"])

    ndvi_decline = max(0.0, peak_ndvi - latest_ndvi)
    relative_decline = ndvi_decline / max(abs(peak_ndvi), 0.001)

    recent = valid.tail(min(5, len(valid))).copy()
    recent_slope = 0.0

    if len(recent) >= 2:
        x = (recent["date"] - recent["date"].min()).dt.total_seconds() / 86400.0
        y = recent["ndvi"]

        try:
            denominator = ((x - x.mean()) ** 2).sum()
            if denominator > 0:
                recent_slope = float(
                    ((x - x.mean()) * (y - y.mean())).sum()
                    / denominator
                )
        except Exception:
            recent_slope = 0.0

    nbr_decline = 0.0
    if not nbr_valid.empty:
        peak_nbr = float(nbr_valid["nbr"].max())
        if latest_nbr is not None:
            nbr_decline = max(0.0, peak_nbr - latest_nbr)

    windows = load_harvest_windows()
    candidate_rows = pd.DataFrame()

    if not windows.empty:
        candidate_rows = windows[
            windows["field_id"].isin(source_field_ids)
        ].copy()

    candidate_dates = []
    candidate_ndvis = []
    candidate_declines = []
    transition_statuses = []

    if not candidate_rows.empty:
        for _, row in candidate_rows.iterrows():
            candidate_date = row.get("candidate_date")
            candidate_ndvi = row.get("candidate_ndvi")
            candidate_decline = row.get("decline")
            status = row.get("status")

            if pd.notna(candidate_date):
                candidate_dates.append(candidate_date)
            if pd.notna(candidate_ndvi):
                candidate_ndvis.append(float(candidate_ndvi))
            if pd.notna(candidate_decline):
                candidate_declines.append(float(candidate_decline))
            if pd.notna(status):
                transition_statuses.append(str(status))

    representative_candidate_date = None
    if candidate_dates:
        representative_candidate_date = sorted(candidate_dates)[len(candidate_dates) // 2]

    representative_candidate_ndvi = (
        sum(candidate_ndvis) / len(candidate_ndvis)
        if candidate_ndvis
        else None
    )
    representative_candidate_decline = (
        sum(candidate_declines) / len(candidate_declines)
        if candidate_declines
        else None
    )
    transition_status = (
        transition_statuses[0]
        if len(set(transition_statuses)) == 1 and transition_statuses
        else (
            "multiple source-year transition observations"
            if transition_statuses
            else None
        )
    )

    # ---------------------------------------------------------
    # TRANSPARENT SIGNAL RULES
    # ---------------------------------------------------------
    ndvi_declining = recent_slope < -0.005
    strong_ndvi_decline = relative_decline >= 0.25
    nbr_declining = nbr_decline >= 0.15
    candidate_available = bool(candidate_dates)

    evidence_count = sum([
        ndvi_declining,
        strong_ndvi_decline,
        nbr_declining,
        candidate_available,
    ])

    if evidence_count >= 3:
        status = "harvest_transition_signal"
        status_label = "Harvest transition signal detected"
        signal_level = "Strong"
    elif evidence_count == 2:
        status = "possible_transition"
        status_label = "Possible harvest transition"
        signal_level = "Moderate"
    else:
        status = "no_strong_signal"
        status_label = "No strong harvest signal"
        signal_level = "Low"

    reasons = []

    if strong_ndvi_decline:
        reasons.append("NDVI has declined substantially from its observed peak")

    if ndvi_declining:
        reasons.append("Recent NDVI trajectory is decreasing")

    if nbr_declining:
        reasons.append("NBR has declined from its observed peak")

    if candidate_available:
        reasons.append("Historical candidate-transition observations are available for the source-year group")

    if not reasons:
        reasons.append("Current satellite signals do not show a strong crop-transition approach")

    return {
        "field_id": requested_field_id,
        **group_payload,
        "as_of_date": latest_date.strftime("%Y-%m-%d"),
        "status": status,
        "status_label": status_label,
        "signal_level": signal_level,
        "confidence": None,
        "signals": {
            "ndvi_decline_from_peak": json_number(ndvi_decline),
            "relative_ndvi_decline": json_number(relative_decline),
            "recent_ndvi_slope_per_day": json_number(recent_slope, 5),
            "nbr_decline_from_peak": json_number(nbr_decline),
            "latest_ndvi": json_number(latest_ndvi),
            "latest_nbr": json_number(latest_nbr),
            "peak_ndvi": json_number(peak_ndvi),
            "peak_date": peak_date.strftime("%Y-%m-%d"),
            "candidate_date": (
                representative_candidate_date.strftime("%Y-%m-%d")
                if representative_candidate_date is not None
                else None
            ),
            "candidate_ndvi": json_number(representative_candidate_ndvi),
            "candidate_decline": json_number(representative_candidate_decline),
            "candidate_source_dates": [
                value.strftime("%Y-%m-%d") for value in sorted(candidate_dates)
            ],
            "observations": int(len(valid)),
        },
        "reasons": reasons,
        "transition_status": transition_status,
        "model_status": "transparent satellite-signal assessment",
        "validation_note": (
            "This assessment uses Sentinel-2 NDVI/NBR time-series evidence. "
            "The available Sangrur data does not contain independently "
            "validated future harvest-date labels, so it does not provide "
            "a calibrated probability or a confirmed harvest date."
        ),
    }


# =========================================================
# ROOT / HEALTH
# =========================================================

@app.get("/")
def root():
    return {
        "project": "Project Parali",
        "status": "running",
        "models": {
            "burn_detection": "Dual RGB + SWIR ResNet18",
            "harvest_prediction": "Sentinel-2 NDVI/NBR signal MVP",
        },
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "burn_model_loaded": model is not None,
        "burn_model_load_mode": "lazy",
        "harvest_prediction_available": os.path.exists(
            TIMESERIES_PATH
        ),
    }


# =========================================================
# BURN PREDICTION
# =========================================================

@app.post("/predict")
async def predict_burn(
    rgb_image: UploadFile = File(...),
    swir_image: UploadFile = File(...),
):
    allowed_types = [
        "image/jpeg",
        "image/jpg",
        "image/png",
    ]

    if rgb_image.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="RGB image must be JPG or PNG",
        )

    if swir_image.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="SWIR image must be JPG or PNG",
        )

    temp_dir = os.path.join(
        os.path.dirname(__file__),
        "temp_uploads",
    )
    os.makedirs(temp_dir, exist_ok=True)

    file_id = str(uuid.uuid4())

    rgb_path = os.path.join(
        temp_dir,
        f"{file_id}_rgb.jpg",
    )
    swir_path = os.path.join(
        temp_dir,
        f"{file_id}_swir.jpg",
    )

    try:
        with open(rgb_path, "wb") as buffer:
            shutil.copyfileobj(rgb_image.file, buffer)

        with open(swir_path, "wb") as buffer:
            shutil.copyfileobj(swir_image.file, buffer)

        result = predict(
            get_burn_model(),
            rgb_path,
            swir_path,
        )

        return {
            "success": True,
            "prediction": result["prediction"],
            "confidence": round(result["confidence"], 2),
            "no_burn_probability": round(
                result["no_burn_probability"],
                2,
            ),
            "burn_probability": round(
                result["burn_probability"],
                2,
            ),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    finally:
        for path in [rgb_path, swir_path]:
            if os.path.exists(path):
                os.remove(path)


# =========================================================
# CROP-RESIDUE ESTIMATION
# =========================================================

@app.get("/residue-estimation/{field_id}")
def residue_estimation(field_id: str):
    """Return an assumption-based crop-residue estimate for a field."""

    try:
        return estimate_residue(field_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))




# =========================================================
# BIOMASS OPPORTUNITY + LOGISTICS
# =========================================================

@app.get("/biomass-opportunity/{field_id}")
def biomass_opportunity(field_id: str):
    """
    Screen the selected field's recoverable biomass against nearby
    biomass facilities.

    This is a screening model based on the facility registry and
    distance calculations; it is not a confirmed procurement contract.
    """
    try:
        residue = estimate_residue(field_id)
        recoverable = residue["recoverable_biomass_tonnes"]

        opportunity = match_facilities(
            field_id=field_id,
            recoverable_biomass_tonnes=recoverable,
        )

        return {
            "success": True,
            "prediction_type": "biomass facility opportunity screening",
            "residue_estimate": residue,
            **opportunity,
        }

    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/logistics-estimation/{field_id}")
def logistics_estimation(field_id: str):
    """
    Estimate screening-level biomass transport logistics for a field.

    The logistics module uses straight-line distance plus an assumed
    road-distance factor and transport rate. It is not live road routing
    or a transporter quotation.
    """
    try:
        residue = estimate_residue(field_id)

        return estimate_logistics(
            field_id=field_id,
            recoverable_biomass_tonnes=residue["recoverable_biomass_tonnes"],
        )

    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# =========================================================
# BIOMASS COLLECTION CLUSTERING
# =========================================================

@app.get("/biomass-cluster/{field_id}")
def biomass_cluster(
    field_id: str,
    radius_km: float = 5.0,
    truck_capacity_tonnes: float = 10.0,
):
    """
    Aggregate nearby fields into a collection cluster.

    The radius and truck capacity are configurable MVP planning
    assumptions. This endpoint does not perform road routing and
    does not confirm farmer participation or transporter capacity.
    """

    if radius_km <= 0:
        raise HTTPException(
            status_code=400,
            detail="radius_km must be greater than 0",
        )

    if truck_capacity_tonnes <= 0:
        raise HTTPException(
            status_code=400,
            detail="truck_capacity_tonnes must be greater than 0",
        )

    try:
        result = get_field_cluster(
            field_id=field_id,
            radius_km=radius_km,
            truck_capacity_tonnes=truck_capacity_tonnes,
        )

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.get("/biomass-clusters")
def biomass_clusters(
    radius_km: float = 5.0,
    truck_capacity_tonnes: float = 10.0,
):
    """Return all field collection clusters."""

    if radius_km <= 0:
        raise HTTPException(
            status_code=400,
            detail="radius_km must be greater than 0",
        )

    if truck_capacity_tonnes <= 0:
        raise HTTPException(
            status_code=400,
            detail="truck_capacity_tonnes must be greater than 0",
        )

    try:
        from .biomass_clustering import get_all_clusters
    except ImportError:
        from biomass_clustering import get_all_clusters

    try:
        return get_all_clusters(
            radius_km=radius_km,
            truck_capacity_tonnes=truck_capacity_tonnes,
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# =========================================================
# MODEL INFORMATION
# =========================================================

@app.get("/model-info")
def model_info():
    return {
        "burn_model": {
            "model": "Dual RGB + SWIR ResNet18",
            "task": "Crop residue burning detection",
            "classes": ["No Burn", "Burn"],
            "input": ["RGB image", "SWIR image"],
        },
        "harvest_model": {
            "model": "Sentinel-2 NDVI/NBR signal MVP",
            "task": "Field-level crop-transition / harvest signal assessment",
            "status": "transparent Sentinel-2 NDVI/NBR signal assessment; not a calibrated probability",
        },
        "live_burn_analysis": {
            "models": [
                "Sentinel-2 spectral burn-signal assessment",
                "Dual RGB + SWIR ResNet18 live model evidence",
            ],
            "task": "Field-level live burn / post-burn assessment",
            "status": (
                "Spectral signals and the existing CNN are reported as separate "
                "pieces of evidence; neither is presented as a calibrated Sentinel-2 probability."
            ),
            "spectral_inputs": [
                "B4 Red",
                "B8 NIR",
                "B11 SWIR1",
                "B12 SWIR2",
                "NDVI",
                "NBR",
                "NBR2",
                "SWIR2/NIR",
            ],
            "ml_input_rendering": {
                "rgb": ["B4", "B3", "B2"],
                "swir": ["B12", "B11", "B8"],
            },
        },
    }


# =========================================================
# LIVE BURN ANALYSIS ENDPOINT
# =========================================================

@app.get("/live-burn-analysis/{field_id}")
def live_burn_analysis(field_id: str):
    """
    Analyze the selected field using the latest usable Sentinel-2 imagery.

    This route is separate from /predict. The existing /predict endpoint
    remains the manual RGB + SWIR CNN workflow. This route adds live
    Sentinel-2 spectral observations and runs the existing CNN on a
    Sentinel-2-rendered RGB/SWIR representation when available.
    """
    try:
        return analyze_live_burn(field_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# =========================================================
# HARVEST PREDICTION ENDPOINT
# =========================================================

@app.get("/harvest-prediction/{field_id}")
def harvest_prediction(field_id: str):
    return {
        "success": True,
        "prediction": calculate_harvest_prediction(field_id),
    }


@app.get("/live-harvest-prediction/{field_id}")
def live_harvest_prediction(field_id: str):
    """
    Return the current Sentinel-2 monitoring assessment for a field or
    logical field number. For a logical number such as 34, the live engine
    combines the matching source-year geometries and source IDs.

    This is deliberately separate from /harvest-prediction/{field_id}.
    The latter uses the historical 2020 field time series, while this route
    calls the existing live Earth Engine Sentinel-2 engine.
    """
    try:
        return predict_harvest(field_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# =========================================================
# FIELD SATELLITE ANALYSIS
# =========================================================

@app.get("/field-analysis/{field_id}")
def field_analysis(field_id: str):
    requested_field_id = clean_field_id(field_id)

    try:
        summary = group_summary(requested_field_id, GEOJSON_PATH)
        source_field_ids = summary["source_field_ids"]
    except (ValueError, KeyError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    df = load_timeseries()
    field_df = df[df["field_id"].isin(source_field_ids)].copy()

    if field_df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Field {requested_field_id} not found",
        )

    field_df = field_df.sort_values("date")

    # ---------------------------------------------------------
    # Source-year field information
    # ---------------------------------------------------------
    source_features = []
    geojson = load_geojson()

    for feature in geojson.get("features", []):
        properties = feature.get("properties") or {}
        source_id = clean_field_id(
            properties.get("field_id")
            or properties.get("id")
            or properties.get("ID")
            or properties.get("Id")
        )
        if source_id in source_field_ids:
            source_features.append(feature)

    categories = []
    source_fields = []

    for feature in source_features:
        properties = feature.get("properties") or {}
        category = (
            properties.get("field_category")
            or properties.get("category")
        )
        if category is not None:
            categories.append(str(category))

        source_fields.append({
            "field_id": clean_field_id(properties.get("field_id")),
            "source_year": properties.get("source_year"),
            "field_name": properties.get("field_name"),
            "category": category,
            "original_field_id": properties.get("original_field_id"),
        })

    if len(source_field_ids) == 1:
        field_category = categories[0] if categories else None
    else:
        field_category = "combined_source_year_group"

    # ---------------------------------------------------------
    # Aggregate field indicators from both source-year members.
    # ---------------------------------------------------------
    indicators_df = load_field_indicators()
    field_indicators = None

    if not indicators_df.empty:
        indicator_rows = indicators_df[
            indicators_df["field_id"].isin(source_field_ids)
        ].copy()

        if not indicator_rows.empty:
            if len(source_field_ids) == 1:
                field_indicators = row_to_indicator_dict(
                    indicator_rows.iloc[0]
                )
            else:
                indicator_records = [
                    row_to_indicator_dict(row)
                    for _, row in indicator_rows.iterrows()
                ]

                def numeric_mean(column):
                    values = []
                    for row in indicator_records:
                        value = row.get(column)
                        if value is not None:
                            try:
                                number = float(value)
                                if math.isfinite(number):
                                    values.append(number)
                            except (TypeError, ValueError):
                                pass
                    return round(sum(values) / len(values), 4) if values else None

                def numeric_sum(column):
                    values = []
                    for row in indicator_records:
                        value = row.get(column)
                        if value is not None:
                            try:
                                number = float(value)
                                if math.isfinite(number):
                                    values.append(number)
                            except (TypeError, ValueError):
                                pass
                    return round(sum(values), 4) if values else None

                candidate_dates = [
                    str(row["candidate_date"])
                    for row in indicator_records
                    if row.get("candidate_date")
                ]

                categories_from_indicators = [
                    str(row["category"])
                    for row in indicator_records
                    if row.get("category")
                ]

                ndvi_trends = [
                    str(row["ndvi_trend"])
                    for row in indicator_records
                    if row.get("ndvi_trend")
                ]
                nbr_trends = [
                    str(row["nbr_trend"])
                    for row in indicator_records
                    if row.get("nbr_trend")
                ]

                field_indicators = {
                    "field_id": requested_field_id,
                    "category": "combined_source_year_group",
                    "source_field_ids": source_field_ids,
                    "source_field_count": len(source_field_ids),
                    "area_hectares": numeric_sum("area_hectares"),
                    "area_acres": numeric_sum("area_acres"),
                    "latest_ndvi": numeric_mean("latest_ndvi"),
                    "latest_nbr": numeric_mean("latest_nbr"),
                    "ndvi_trend": (
                        ndvi_trends[0]
                        if len(set(ndvi_trends)) == 1 and ndvi_trends
                        else "mixed" if ndvi_trends else None
                    ),
                    "nbr_trend": (
                        nbr_trends[0]
                        if len(set(nbr_trends)) == 1 and nbr_trends
                        else "mixed" if nbr_trends else None
                    ),
                    "candidate_date": candidate_dates,
                    "field_status": "combined historical source-year context",
                    "source_fields": indicator_records,
                }

    if field_indicators is None:
        field_indicators = {
            "field_id": requested_field_id,
            "category": field_category,
            "source_field_ids": source_field_ids,
            "source_field_count": len(source_field_ids),
            "source_fields": source_fields,
        }

    valid_latest = field_df[
        field_df["ndvi"].notna()
        & field_df["nbr"].notna()
    ].copy()

    if valid_latest.empty:
        valid_latest = field_df[
            field_df["ndvi"].notna()
            | field_df["nbr"].notna()
        ].copy()

    if valid_latest.empty:
        latest_observation = {
            "date": None,
            "ndvi": None,
            "nbr": None,
        }
    else:
        latest = valid_latest.iloc[-1]
        latest_observation = {
            "date": latest["date"].strftime("%Y-%m-%d"),
            "ndvi": json_number(latest["ndvi"]),
            "nbr": json_number(latest["nbr"]),
        }

    chart_df = field_df[
        field_df["ndvi"].notna()
        & field_df["nbr"].notna()
    ].copy()

    chart_df = (
        chart_df.groupby("date", as_index=False)[["ndvi", "nbr"]]
        .mean()
        .sort_values("date")
    )

    time_series = [
        {
            "date": row["date"].strftime("%Y-%m-%d"),
            "ndvi": json_number(row["ndvi"]),
            "nbr": json_number(row["nbr"]),
        }
        for _, row in chart_df.iterrows()
    ]

    # Historical transition information is combined by source field.
    windows = load_harvest_windows()
    transition_rows = []

    if not windows.empty:
        transition_rows_df = windows[
            windows["field_id"].isin(source_field_ids)
        ].copy()
        for _, row in transition_rows_df.iterrows():
            transition_rows.append({
                "field_id": clean_field_id(row.get("field_id")),
                "peak_date": (
                    row["peak_date"].strftime("%Y-%m-%d")
                    if "peak_date" in row.index and pd.notna(row["peak_date"])
                    else None
                ),
                "peak_ndvi": json_number(row.get("peak_ndvi")),
                "candidate_date": (
                    row["candidate_date"].strftime("%Y-%m-%d")
                    if "candidate_date" in row.index and pd.notna(row["candidate_date"])
                    else None
                ),
                "candidate_ndvi": json_number(row.get("candidate_ndvi")),
                "decline": json_number(row.get("decline")),
                "status": (
                    None if pd.isna(row.get("status")) else row.get("status")
                ),
            })

    if len(source_field_ids) == 1:
        transition = transition_rows[0] if transition_rows else None
    else:
        transition = {
            "mode": "combined_source_year_context",
            "source_field_ids": source_field_ids,
            "source_fields": transition_rows,
        }

    harvest = calculate_harvest_prediction(requested_field_id)

    return {
        "success": True,
        "field_id": requested_field_id,
        "source_field_ids": source_field_ids,
        "source_field_count": len(source_field_ids),
        "geometry_mode": summary["geometry_mode"],
        "field_category": field_category,
        "latest_observation": latest_observation,
        "transition_analysis": transition,
        "field_indicators": field_indicators,
        "harvest_prediction": harvest,
        "time_series": time_series,
        "source_fields": source_fields,
    }


# =========================================================
# GEOJSON FIELD MAP
# =========================================================

@app.get("/fields")
def get_fields():
    geojson = load_geojson()
    indicators_df = load_field_indicators()

    indicator_map = {}

    if not indicators_df.empty:
        for _, row in indicators_df.iterrows():
            field_id = clean_field_id(row.get("field_id"))
            if field_id:
                indicator_map[field_id] = row_to_indicator_dict(row)

    for index, feature in enumerate(
        geojson.get("features", [])
    ):
        properties = feature.setdefault("properties", {})

        field_id = clean_field_id(
            properties.get("field_id")
            or properties.get("id")
            or properties.get("ID")
            or properties.get("Id")
            or f"field-{index + 1}"
        )

        properties["field_id"] = field_id

        indicator = indicator_map.get(field_id)

        if indicator:
            properties["field_indicators"] = indicator

            properties.setdefault(
                "category",
                indicator.get("category"),
            )

            properties.setdefault(
                "field_status",
                indicator.get("field_status"),
            )

            properties.setdefault(
                "candidate_date",
                indicator.get("candidate_date"),
            )

    return geojson