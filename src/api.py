import os
import json
import shutil
import uuid

import pandas as pd

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException
)

from fastapi.middleware.cors import CORSMiddleware

from predict import load_model, predict


# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(
    title="Project Parali API",
    description="AI-powered crop residue monitoring platform",
    version="1.0.0"
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)


# =========================================================
# LOAD ML MODEL
# =========================================================

print(
    "Loading Project Parali model..."
)

model = load_model()

print(
    "Project Parali model ready!"
)


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():

    return {
        "project": "Project Parali",
        "status": "running",
        "model": "Dual RGB + SWIR ResNet18"
    }


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health():

    return {
        "status": "healthy",
        "model_loaded": True
    }


# =========================================================
# BURN PREDICTION
# =========================================================

@app.post("/predict")
async def predict_burn(
    rgb_image: UploadFile = File(...),
    swir_image: UploadFile = File(...)
):

    allowed_types = [
        "image/jpeg",
        "image/jpg",
        "image/png"
    ]


    # -----------------------------------------------------
    # Validate RGB image
    # -----------------------------------------------------

    if rgb_image.content_type not in allowed_types:

        raise HTTPException(
            status_code=400,
            detail="RGB image must be JPG or PNG"
        )


    # -----------------------------------------------------
    # Validate SWIR image
    # -----------------------------------------------------

    if swir_image.content_type not in allowed_types:

        raise HTTPException(
            status_code=400,
            detail="SWIR image must be JPG or PNG"
        )


    # -----------------------------------------------------
    # Temporary upload directory
    # -----------------------------------------------------

    temp_dir = os.path.join(
        os.path.dirname(__file__),
        "temp_uploads"
    )


    os.makedirs(
        temp_dir,
        exist_ok=True
    )


    file_id = str(
        uuid.uuid4()
    )


    rgb_path = os.path.join(
        temp_dir,
        f"{file_id}_rgb.jpg"
    )


    swir_path = os.path.join(
        temp_dir,
        f"{file_id}_swir.jpg"
    )


    try:

        # -------------------------------------------------
        # Save RGB
        # -------------------------------------------------

        with open(
            rgb_path,
            "wb"
        ) as buffer:

            shutil.copyfileobj(
                rgb_image.file,
                buffer
            )


        # -------------------------------------------------
        # Save SWIR
        # -------------------------------------------------

        with open(
            swir_path,
            "wb"
        ) as buffer:

            shutil.copyfileobj(
                swir_image.file,
                buffer
            )


        # -------------------------------------------------
        # Run prediction
        # -------------------------------------------------

        result = predict(
            model,
            rgb_path,
            swir_path
        )


        return {
            "success": True,

            "prediction":
                result["prediction"],

            "confidence":
                round(
                    result["confidence"],
                    2
                ),

            "no_burn_probability":
                round(
                    result["no_burn_probability"],
                    2
                ),

            "burn_probability":
                round(
                    result["burn_probability"],
                    2
                )
        }


    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


    finally:

        # -------------------------------------------------
        # Delete temporary files
        # -------------------------------------------------

        if os.path.exists(
            rgb_path
        ):

            os.remove(
                rgb_path
            )


        if os.path.exists(
            swir_path
        ):

            os.remove(
                swir_path
            )


# =========================================================
# MODEL INFORMATION
# =========================================================

@app.get("/model-info")
def model_info():

    return {

        "model":
            "Dual RGB + SWIR ResNet18",

        "task":
            "Crop residue burning detection",

        "classes":
            [
                "No Burn",
                "Burn"
            ],

        "input":
            [
                "RGB image",
                "SWIR image"
            ]
    }


# =========================================================
# FILE PATHS
# =========================================================

TIMESERIES_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "data",
        "processed",
        "field_ndvi_timeseries.csv"
    )
)


HARVEST_WINDOW_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "data",
        "processed",
        "harvest_windows.csv"
    )
)


GEOJSON_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "data",
        "processed",
        "sangrur_fields.geojson"
    )
)


# =========================================================
# FIELD SATELLITE ANALYSIS
# =========================================================

@app.get(
    "/field-analysis/{field_id}"
)
def field_analysis(
    field_id: int
):

    # -----------------------------------------------------
    # Check time-series file
    # -----------------------------------------------------

    if not os.path.exists(
        TIMESERIES_PATH
    ):

        raise HTTPException(
            status_code=404,
            detail=(
                "Satellite time-series "
                "data not found"
            )
        )


    # -----------------------------------------------------
    # Load time series
    # -----------------------------------------------------

    df = pd.read_csv(
        TIMESERIES_PATH
    )


    # -----------------------------------------------------
    # Clean columns
    # -----------------------------------------------------

    df["field_id"] = pd.to_numeric(
        df["field_id"],
        errors="coerce"
    )


    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )


    df["ndvi"] = pd.to_numeric(
        df["ndvi"],
        errors="coerce"
    )


    df["nbr"] = pd.to_numeric(
        df["nbr"],
        errors="coerce"
    )


    # -----------------------------------------------------
    # Select field
    # -----------------------------------------------------

    field_df = df[
        df["field_id"] == field_id
    ].copy()


    if field_df.empty:

        raise HTTPException(
            status_code=404,
            detail=(
                f"Field {field_id} not found"
            )
        )


    # -----------------------------------------------------
    # Sort by date
    # -----------------------------------------------------

    field_df = field_df.sort_values(
        "date"
    )


    # =====================================================
    # FIELD CATEGORY
    # =====================================================

    field_category = None


    if "field_category" in field_df.columns:

        categories = (
            field_df["field_category"]
            .dropna()
            .astype(str)
        )


        if not categories.empty:

            field_category = (
                categories.iloc[0]
            )


    # =====================================================
    # LATEST VALID OBSERVATION
    # =====================================================

    # Prefer an observation where BOTH NDVI
    # and NBR are available.

    valid_latest = field_df[
        field_df["ndvi"].notna()
        &
        field_df["nbr"].notna()
    ].copy()


    if valid_latest.empty:

        # Fallback:
        # use the latest observation with
        # at least one valid index.

        valid_latest = field_df[
            field_df["ndvi"].notna()
            |
            field_df["nbr"].notna()
        ].copy()


    if valid_latest.empty:

        latest_observation = {

            "date": None,

            "ndvi": None,

            "nbr": None
        }

    else:

        latest = (
            valid_latest
            .sort_values("date")
            .iloc[-1]
        )


        latest_observation = {

            "date":
                latest["date"].strftime(
                    "%Y-%m-%d"
                ),

            "ndvi":
                (
                    None
                    if pd.isna(
                        latest["ndvi"]
                    )
                    else round(
                        float(
                            latest["ndvi"]
                        ),
                        4
                    )
                ),

            "nbr":
                (
                    None
                    if pd.isna(
                        latest["nbr"]
                    )
                    else round(
                        float(
                            latest["nbr"]
                        ),
                        4
                    )
                )
        }


    # =====================================================
    # CLEAN TIME SERIES
    # =====================================================

    # For the dashboard chart we only include
    # observations where BOTH NDVI and NBR exist.
    #
    # This removes broken/missing points caused by
    # cloud masking.

    chart_df = field_df[
        field_df["ndvi"].notna()
        &
        field_df["nbr"].notna()
    ].copy()


    chart_df = chart_df.sort_values(
        "date"
    )


    time_series = []


    for _, row in chart_df.iterrows():

        time_series.append(

            {

                "date":
                    row["date"].strftime(
                        "%Y-%m-%d"
                    ),

                "ndvi":
                    round(
                        float(
                            row["ndvi"]
                        ),
                        4
                    ),

                "nbr":
                    round(
                        float(
                            row["nbr"]
                        ),
                        4
                    )
            }

        )


    # =====================================================
    # CROP TRANSITION ANALYSIS
    # =====================================================

    transition = None


    if os.path.exists(
        HARVEST_WINDOW_PATH
    ):

        windows = pd.read_csv(
            HARVEST_WINDOW_PATH
        )


        windows["field_id"] = (
            pd.to_numeric(
                windows["field_id"],
                errors="coerce"
            )
        )


        field_window = windows[
            windows["field_id"] == field_id
        ]


        if not field_window.empty:

            row = (
                field_window
                .iloc[0]
            )


            # ---------------------------------------------
            # Candidate date
            # ---------------------------------------------

            candidate_date = (
                row.get(
                    "candidate_date"
                )
            )


            if pd.isna(
                candidate_date
            ):

                candidate_date = None


            # ---------------------------------------------
            # Peak date
            # ---------------------------------------------

            peak_date = (
                row.get(
                    "peak_date"
                )
            )


            if pd.isna(
                peak_date
            ):

                peak_date = None


            # ---------------------------------------------
            # Candidate NDVI
            # ---------------------------------------------

            candidate_ndvi = (
                row.get(
                    "candidate_ndvi"
                )
            )


            if pd.isna(
                candidate_ndvi
            ):

                candidate_ndvi = None


            # ---------------------------------------------
            # Peak NDVI
            # ---------------------------------------------

            peak_ndvi = (
                row.get(
                    "peak_ndvi"
                )
            )


            if pd.isna(
                peak_ndvi
            ):

                peak_ndvi = None


            # ---------------------------------------------
            # Decline
            # ---------------------------------------------

            decline = (
                row.get(
                    "decline"
                )
            )


            if pd.isna(
                decline
            ):

                decline = None


            # ---------------------------------------------
            # Status
            # ---------------------------------------------

            status = (
                row.get(
                    "status"
                )
            )


            if pd.isna(
                status
            ):

                status = None


            transition = {

                "peak_date":
                    peak_date,

                "peak_ndvi":
                    (
                        None
                        if peak_ndvi is None
                        else round(
                            float(
                                peak_ndvi
                            ),
                            4
                        )
                    ),

                "candidate_date":
                    candidate_date,

                "candidate_ndvi":
                    (
                        None
                        if candidate_ndvi is None
                        else round(
                            float(
                                candidate_ndvi
                            ),
                            4
                        )
                    ),

                "decline":
                    (
                        None
                        if decline is None
                        else round(
                            float(
                                decline
                            ),
                            4
                        )
                    ),

                "status":
                    status
            }


    # =====================================================
    # RESPONSE
    # =====================================================

    return {

        "success":
            True,

        "field_id":
            field_id,

        "field_category":
            field_category,

        "latest_observation":
            latest_observation,

        "transition_analysis":
            transition,

        "time_series":
            time_series
    }


# =========================================================
# GEOJSON FIELD MAP
# =========================================================

@app.get(
    "/fields"
)
def get_fields():

    if not os.path.exists(
        GEOJSON_PATH
    ):

        raise HTTPException(
            status_code=404,
            detail=(
                "Sangrur GeoJSON not found"
            )
        )


    try:

        with open(
            GEOJSON_PATH,
            "r",
            encoding="utf-8"
        ) as file:

            geojson = json.load(
                file
            )


        # -------------------------------------------------
        # Make sure every feature has a numeric field ID
        # -------------------------------------------------

        for index, feature in enumerate(
            geojson.get(
                "features",
                []
            )
        ):

            properties = (
                feature.setdefault(
                    "properties",
                    {}
                )
            )


            raw_field_id = (

                properties.get(
                    "field_id"
                )

                or

                properties.get(
                    "id"
                )

                or

                properties.get(
                    "ID"
                )

                or

                properties.get(
                    "Id"
                )

                or

                index + 1
            )


            try:

                properties["field_id"] = int(
                    raw_field_id
                )

            except (
                TypeError,
                ValueError
            ):

                properties["field_id"] = (
                    index + 1
                )


        return geojson


    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )