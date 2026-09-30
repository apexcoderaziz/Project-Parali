import os
import pandas as pd
import matplotlib.pyplot as plt


# =========================================================
# CONFIG
# =========================================================

INPUT_PATH = (
    "data/processed/field_ndvi_timeseries.csv"
)

OUTPUT_DIR = (
    "data/processed/timeseries_plots"
)

MAX_FIELDS_TO_PLOT = 5


# =========================================================
# LOAD DATA
# =========================================================

print("Loading time-series data...")

df = pd.read_csv(
    INPUT_PATH
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

df = df.dropna(
    subset=[
        "field_id",
        "date",
        "ndvi",
        "nbr"
    ]
)

df = df.sort_values(
    [
        "field_id",
        "date"
    ]
)


# =========================================================
# CREATE OUTPUT DIRECTORY
# =========================================================

os.makedirs(
    OUTPUT_DIR,
    exist_ok=True
)


# =========================================================
# SELECT FIELDS
# =========================================================

field_ids = (
    df["field_id"]
    .drop_duplicates()
    .head(MAX_FIELDS_TO_PLOT)
    .tolist()
)

print(
    "Fields to plot:",
    field_ids
)


# =========================================================
# PLOT EACH FIELD
# =========================================================

for field_id in field_ids:

    field_df = df[
        df["field_id"] == field_id
    ].copy()

    if field_df.empty:
        continue


    # -----------------------------------------------------
    # NDVI PLOT
    # -----------------------------------------------------

    plt.figure(
        figsize=(12, 6)
    )

    plt.plot(
        field_df["date"],
        field_df["ndvi"],
        marker="o"
    )

    plt.xlabel("Date")

    plt.ylabel("NDVI")

    plt.title(
        f"Field {field_id} - NDVI Time Series"
    )

    plt.grid(
        True,
        alpha=0.3
    )

    plt.xticks(
        rotation=45
    )

    plt.tight_layout()


    output_path = os.path.join(
        OUTPUT_DIR,
        f"field_{field_id}_ndvi.png"
    )

    plt.savefig(
        output_path,
        dpi=150
    )

    plt.close()


    # -----------------------------------------------------
    # NBR PLOT
    # -----------------------------------------------------

    plt.figure(
        figsize=(12, 6)
    )

    plt.plot(
        field_df["date"],
        field_df["nbr"],
        marker="o"
    )

    plt.xlabel("Date")

    plt.ylabel("NBR")

    plt.title(
        f"Field {field_id} - NBR Time Series"
    )

    plt.grid(
        True,
        alpha=0.3
    )

    plt.xticks(
        rotation=45
    )

    plt.tight_layout()


    output_path = os.path.join(
        OUTPUT_DIR,
        f"field_{field_id}_nbr.png"
    )

    plt.savefig(
        output_path,
        dpi=150
    )

    plt.close()


# =========================================================
# COMBINED PLOT
# =========================================================

plt.figure(
    figsize=(14, 7)
)

for field_id in field_ids:

    field_df = df[
        df["field_id"] == field_id
    ]

    plt.plot(
        field_df["date"],
        field_df["ndvi"],
        marker="o",
        label=f"Field {field_id}"
    )


plt.xlabel("Date")

plt.ylabel("NDVI")

plt.title(
    "Project Parali - Field NDVI Time Series"
)

plt.legend()

plt.grid(
    True,
    alpha=0.3
)

plt.xticks(
    rotation=45
)

plt.tight_layout()


combined_path = os.path.join(
    OUTPUT_DIR,
    "combined_ndvi_timeseries.png"
)

plt.savefig(
    combined_path,
    dpi=150
)

plt.close()


# =========================================================
# SUMMARY
# =========================================================

print("\n======================================")
print("TIME-SERIES VISUALIZATION COMPLETE")
print("======================================")

print(
    "Fields plotted:",
    len(field_ids)
)

print(
    "Output directory:",
    OUTPUT_DIR
)

print(
    "Combined plot:",
    combined_path
)