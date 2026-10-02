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


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# LOAD BURN MODEL
# =========================================================

print("Loading Project Parali burn model...")
model = load_model()
print("Project Parali burn model ready!")


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
    Analyze a selected field's Sentinel-2 NDVI/NBR time series.

    This version deliberately does NOT manufacture a percentage or a
    7/14/21-day probability. The available Sangrur data has historical
    crop-transition observations but no independently validated future
    harvest-date labels.

    The result is therefore a transparent satellite signal assessment:
    - harvest_transition_signal
    - possible_transition
    - no_strong_signal
    - insufficient_data

    It is evidence for a harvest/crop-transition signal, not a calibrated
    prediction of an exact harvest date.
    """

    field_id = clean_field_id(field_id)
    df = load_timeseries()

    field_df = df[df["field_id"] == field_id].copy()

    if field_df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Field {field_id} not found",
        )

    # Multiple Sentinel-2 tiles can create duplicate field/date rows.
    # Aggregate them before calculating trends.
    series = (
        field_df.groupby("date", as_index=False)[["ndvi", "nbr"]]
        .mean()
        .sort_values("date")
    )

    valid = series[series["ndvi"].notna()].copy()

    if len(valid) < 3:
        return {
            "field_id": field_id,
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
                "The available Sangrur dataset does not contain independently "
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
        x = (
            recent["date"] - recent["date"].min()
        ).dt.total_seconds() / 86400.0
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
    candidate_date = None
    candidate_ndvi = None
    candidate_decline = None
    transition_status = None

    if not windows.empty:
        field_window = windows[
            windows["field_id"] == field_id
        ]

        if not field_window.empty:
            row = field_window.iloc[0]
            candidate_date = row.get("candidate_date")
            candidate_ndvi = row.get("candidate_ndvi")
            candidate_decline = row.get("decline")
            transition_status = row.get("status")

    if pd.isna(candidate_date):
        candidate_date = None
    if pd.isna(candidate_ndvi):
        candidate_ndvi = None
    if pd.isna(candidate_decline):
        candidate_decline = None
    if pd.isna(transition_status):
        transition_status = None

    # ---------------------------------------------------------
    # TRANSPARENT SIGNAL RULES
    # ---------------------------------------------------------
    # These are monitoring rules, not a trained/calibrated model.
    ndvi_declining = recent_slope < -0.005
    strong_ndvi_decline = relative_decline >= 0.25
    nbr_declining = nbr_decline >= 0.15
    candidate_available = candidate_date is not None

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
        reasons.append("An NDVI-based crop-transition candidate is available")

    if not reasons:
        reasons.append("Current satellite signals do not show a strong crop-transition approach")

    return {
        "field_id": field_id,
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
                candidate_date.strftime("%Y-%m-%d")
                if candidate_date is not None
                else None
            ),
            "candidate_ndvi": json_number(candidate_ndvi),
            "candidate_decline": json_number(candidate_decline),
            "observations": int(len(valid)),
        },
        "reasons": reasons,
        "transition_status": transition_status,
        "model_status": "transparent satellite-signal assessment",
        "validation_note": (
            "This assessment uses Sentinel-2 NDVI/NBR time-series evidence. "
            "The available Sangrur dataset does not contain independently "
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
            model,
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
            "model": "Sentinel-2 spectral burn-signal MVP",
            "task": "Field-level live burn / post-burn spectral assessment",
            "status": "transparent Sentinel-2 spectral-signal assessment; not a calibrated probability",
            "inputs": ["B4 Red", "B8 NIR", "B11 SWIR1", "B12 SWIR2", "NDVI", "NBR"],
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
    remains the manual RGB + SWIR CNN workflow. This route uses live
    Sentinel-2 spectral observations and transparent burn-signal rules.
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
    Return the current Sentinel-2 monitoring assessment for a field.

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
    field_id = clean_field_id(field_id)

    df = load_timeseries()

    field_df = df[df["field_id"] == field_id].copy()

    if field_df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Field {field_id} not found",
        )

    field_df = field_df.sort_values("date")

    field_category = None

    if "field_category" in field_df.columns:
        categories = (
            field_df["field_category"]
            .dropna()
            .astype(str)
        )
        if not categories.empty:
            field_category = categories.iloc[0]

    indicators_df = load_field_indicators()
    field_indicators = None

    if not indicators_df.empty:
        indicator_rows = indicators_df[
            indicators_df["field_id"] == field_id
        ]

        if not indicator_rows.empty:
            field_indicators = row_to_indicator_dict(
                indicator_rows.iloc[0]
            )

            if field_category is None:
                field_category = field_indicators.get("category")

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

    windows = load_harvest_windows()
    transition = None

    if not windows.empty:
        field_window = windows[
            windows["field_id"] == field_id
        ]

        if not field_window.empty:
            row = field_window.iloc[0]

            transition = {
                "peak_date": (
                    row["peak_date"].strftime("%Y-%m-%d")
                    if "peak_date" in row.index
                    and pd.notna(row["peak_date"])
                    else None
                ),
                "peak_ndvi": json_number(
                    row.get("peak_ndvi")
                ),
                "candidate_date": (
                    row["candidate_date"].strftime("%Y-%m-%d")
                    if "candidate_date" in row.index
                    and pd.notna(row["candidate_date"])
                    else None
                ),
                "candidate_ndvi": json_number(
                    row.get("candidate_ndvi")
                ),
                "decline": json_number(
                    row.get("decline")
                ),
                "status": (
                    None
                    if pd.isna(row.get("status"))
                    else row.get("status")
                ),
            }

    harvest = calculate_harvest_prediction(field_id)

    return {
        "success": True,
        "field_id": field_id,
        "field_category": field_category,
        "latest_observation": latest_observation,
        "transition_analysis": transition,
        "field_indicators": field_indicators,
        "harvest_prediction": harvest,
        "time_series": time_series,
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