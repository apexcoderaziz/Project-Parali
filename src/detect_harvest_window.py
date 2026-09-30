import os
import pandas as pd


# =========================================================
# CONFIG
# =========================================================

# Project root:
#
# Project-Parali/
#     data/
#     src/
#
BASE_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        ".."
    )
)


# Input Sentinel-2 time-series data
INPUT_PATH = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "field_ndvi_timeseries.csv"
)


# Output harvest/crop-transition analysis
OUTPUT_PATH = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "harvest_windows.csv"
)


# =========================================================
# CONFIGURATION
# =========================================================

# Rolling window used to smooth NDVI
SMOOTHING_WINDOW = 3

# Minimum NDVI decline considered significant
MIN_DECLINE = 0.20

# Number of consecutive observations required
# after the peak to confirm a sustained decline
CONSECUTIVE_POINTS = 2


# =========================================================
# CHECK INPUT
# =========================================================

print(
    "Loading Sentinel-2 time series..."
)

print(
    "Input:",
    INPUT_PATH
)


if not os.path.exists(INPUT_PATH):

    raise FileNotFoundError(
        "\nSentinel-2 time-series file not found:\n"
        f"{INPUT_PATH}\n\n"
        "Run harvest_timeseries.py first."
    )


# =========================================================
# LOAD DATA
# =========================================================

df = pd.read_csv(
    INPUT_PATH
)


print(
    "Rows loaded:",
    len(df)
)


# =========================================================
# CLEAN DATA
# =========================================================

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


# Remove rows without valid field/date

df = df.dropna(
    subset=[
        "field_id",
        "date"
    ]
)


# Make field IDs integers

df["field_id"] = (
    df["field_id"]
    .astype(int)
)


# Sort observations

df = df.sort_values(
    [
        "field_id",
        "date"
    ]
)


# =========================================================
# PROCESS EACH FIELD
# =========================================================

results = []


field_ids = (
    df["field_id"]
    .dropna()
    .unique()
)


print(
    "Fields found:",
    len(field_ids)
)


for field_id in field_ids:

    field_df = (
        df[
            df["field_id"] == field_id
        ]
        .copy()
        .sort_values("date")
    )


    # -----------------------------------------------------
    # Remove observations without NDVI
    # -----------------------------------------------------

    ndvi_df = field_df.dropna(
        subset=["ndvi"]
    ).copy()


    if ndvi_df.empty:

        results.append(
            {
                "field_id": field_id,
                "peak_date": None,
                "peak_ndvi": None,
                "candidate_date": None,
                "candidate_ndvi": None,
                "decline": None,
                "status": "No NDVI data"
            }
        )

        continue


    # -----------------------------------------------------
    # Smooth NDVI
    # -----------------------------------------------------

    ndvi_df["ndvi_smooth"] = (
        ndvi_df["ndvi"]
        .rolling(
            window=SMOOTHING_WINDOW,
            min_periods=1
        )
        .mean()
    )


    # -----------------------------------------------------
    # Find peak NDVI
    # -----------------------------------------------------

    peak_index = (
        ndvi_df["ndvi_smooth"]
        .idxmax()
    )


    peak_row = (
        ndvi_df.loc[peak_index]
    )


    peak_date = (
        peak_row["date"]
    )


    peak_ndvi = (
        float(
            peak_row["ndvi_smooth"]
        )
    )


    # -----------------------------------------------------
    # Look for sustained decline after peak
    # -----------------------------------------------------

    after_peak = (
        ndvi_df[
            ndvi_df["date"] > peak_date
        ]
        .copy()
    )


    candidate_date = None
    candidate_ndvi = None
    decline = None
    status = "No significant transition detected"


    if not after_peak.empty:

        consecutive_count = 0


        for _, row in after_peak.iterrows():

            current_ndvi = float(
                row["ndvi_smooth"]
            )


            current_decline = (
                peak_ndvi -
                current_ndvi
            )


            # Significant decline
            if current_decline >= MIN_DECLINE:

                consecutive_count += 1

            else:

                consecutive_count = 0


            # Sustained decline detected
            if (
                consecutive_count
                >= CONSECUTIVE_POINTS
            ):

                candidate_date = (
                    row["date"]
                )

                candidate_ndvi = (
                    current_ndvi
                )

                decline = (
                    peak_ndvi -
                    current_ndvi
                )

                status = (
                    "Candidate crop-transition detected"
                )

                break


    # -----------------------------------------------------
    # Save field result
    # -----------------------------------------------------

    results.append(
        {
            "field_id": field_id,

            "peak_date": (
                peak_date.strftime(
                    "%Y-%m-%d"
                )
            ),

            "peak_ndvi": round(
                peak_ndvi,
                4
            ),

            "candidate_date": (
                candidate_date.strftime(
                    "%Y-%m-%d"
                )
                if candidate_date is not None
                else None
            ),

            "candidate_ndvi": (
                round(
                    candidate_ndvi,
                    4
                )
                if candidate_ndvi is not None
                else None
            ),

            "decline": (
                round(
                    decline,
                    4
                )
                if decline is not None
                else None
            ),

            "status": status
        }
    )


# =========================================================
# CREATE OUTPUT DATAFRAME
# =========================================================

results_df = pd.DataFrame(
    results
)


# =========================================================
# SAVE RESULTS
# =========================================================

os.makedirs(
    os.path.dirname(
        OUTPUT_PATH
    ),
    exist_ok=True
)


results_df.to_csv(
    OUTPUT_PATH,
    index=False
)


# =========================================================
# SUMMARY
# =========================================================

print(
    "\n======================================"
)

print(
    "PROJECT PARALI"
)

print(
    "CROP TRANSITION ANALYSIS"
)

print(
    "======================================"
)


print(
    "Fields processed:",
    len(results_df)
)


detected_count = (
    results_df["candidate_date"]
    .notna()
    .sum()
)


print(
    "Candidate transitions detected:",
    detected_count
)


print(
    "Output:"
)

print(
    OUTPUT_PATH
)


print(
    "\nFirst 10 results:"
)

print(
    results_df
    .head(10)
    .to_string(
        index=False
    )
)


print(
    "\nHarvest-window analysis complete!"
)