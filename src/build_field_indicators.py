import os
import pandas as pd


# ============================================================
# Project paths
# ============================================================

BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

AREA_PATH = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "field_area.csv"
)

TIMESERIES_PATH = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "field_ndvi_timeseries.csv"
)

HARVEST_PATH = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "harvest_windows.csv"
)

OUTPUT_PATH = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "field_indicators.csv"
)


# ============================================================
# Configuration
# ============================================================

TREND_THRESHOLD = 0.02


# ============================================================
# Helpers
# ============================================================

def normalize_field_id(value):
    """
    Normalize field IDs while preserving globally unique IDs.

    New field IDs look like:

        2020_34
        2021_34

    They must remain strings.
    """

    if pd.isna(value):
        return None

    value = str(value).strip()

    if not value:
        return None

    return value


def calculate_trend(values):
    """
    Determine whether a field's indicator is increasing,
    decreasing, or stable.

    Uses the first and last valid values.
    """

    values = pd.to_numeric(
        values,
        errors="coerce"
    ).dropna()

    if len(values) < 2:
        return "insufficient_data"

    difference = (
        values.iloc[-1]
        - values.iloc[0]
    )

    if difference > TREND_THRESHOLD:
        return "increasing"

    if difference < -TREND_THRESHOLD:
        return "decreasing"

    return "stable"


def calculate_latest_values(group):
    """
    Return the latest valid NDVI and NBR observations.
    """

    group = group.sort_values("date")

    latest_ndvi = None
    latest_nbr = None

    valid_ndvi = group.dropna(
        subset=["ndvi"]
    )

    if not valid_ndvi.empty:

        latest_ndvi = float(
            valid_ndvi.iloc[-1]["ndvi"]
        )

    valid_nbr = group.dropna(
        subset=["nbr"]
    )

    if not valid_nbr.empty:

        latest_nbr = float(
            valid_nbr.iloc[-1]["nbr"]
        )

    return latest_ndvi, latest_nbr


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 70)
    print("Project Parali - Building Unified Field Indicators")
    print("=" * 70)

    # --------------------------------------------------------
    # Check files
    # --------------------------------------------------------

    required_files = [
        AREA_PATH,
        TIMESERIES_PATH,
        HARVEST_PATH
    ]

    for path in required_files:

        if not os.path.exists(path):

            raise FileNotFoundError(
                f"\nRequired file not found:\n{path}"
            )

    # --------------------------------------------------------
    # Load datasets
    # --------------------------------------------------------

    print("\nLoading field area data...")

    area_df = pd.read_csv(
        AREA_PATH,
        dtype={"field_id": str}
    )

    print(
        f"Area records: {len(area_df)}"
    )

    print("\nLoading satellite time-series data...")

    timeseries_df = pd.read_csv(
        TIMESERIES_PATH,
        dtype={"field_id": str}
    )

    print(
        f"Time-series records: {len(timeseries_df)}"
    )

    print("\nLoading crop-transition analysis...")

    harvest_df = pd.read_csv(
        HARVEST_PATH,
        dtype={"field_id": str}
    )

    print(
        f"Transition records: {len(harvest_df)}"
    )

    # --------------------------------------------------------
    # Normalize field IDs
    # --------------------------------------------------------

    for df in [
        area_df,
        timeseries_df,
        harvest_df
    ]:

        df["field_id"] = df[
            "field_id"
        ].apply(normalize_field_id)

        df.dropna(
            subset=["field_id"],
            inplace=True
        )

    # --------------------------------------------------------
    # Validate area IDs
    # --------------------------------------------------------

    duplicate_area_ids = area_df[
        area_df["field_id"].duplicated(
            keep=False
        )
    ]

    if not duplicate_area_ids.empty:

        print(
            "\nWARNING: Duplicate field IDs "
            "found in field_area.csv:"
        )

        print(
            duplicate_area_ids[
                ["field_id", "category"]
            ].to_string(index=False)
        )

        raise ValueError(
            "field_area.csv contains duplicate "
            "field IDs."
        )

    # --------------------------------------------------------
    # Normalize dates
    # --------------------------------------------------------

    timeseries_df["date"] = pd.to_datetime(
        timeseries_df["date"],
        errors="coerce"
    )

    timeseries_df.dropna(
        subset=["date"],
        inplace=True
    )

    # --------------------------------------------------------
    # Build field-level satellite indicators
    # --------------------------------------------------------

    records = []

    grouped = timeseries_df.groupby(
        "field_id"
    )

    print(
        "\nCalculating field indicators..."
    )

    for field_id, group in grouped:

        group = group.sort_values(
            "date"
        )

        latest_ndvi, latest_nbr = (
            calculate_latest_values(group)
        )

        ndvi_trend = calculate_trend(
            group["ndvi"]
        )

        nbr_trend = calculate_trend(
            group["nbr"]
        )

        records.append({

            "field_id": str(field_id),

            "latest_ndvi": (
                round(latest_ndvi, 4)
                if latest_ndvi is not None
                else None
            ),

            "latest_nbr": (
                round(latest_nbr, 4)
                if latest_nbr is not None
                else None
            ),

            "ndvi_trend": ndvi_trend,

            "nbr_trend": nbr_trend
        })

    indicator_df = pd.DataFrame(
        records
    )

    # --------------------------------------------------------
    # Merge area information
    # --------------------------------------------------------

    final_df = area_df.merge(
        indicator_df,
        on="field_id",
        how="left"
    )

    # --------------------------------------------------------
    # Merge transition information
    # --------------------------------------------------------

    transition_columns = [
        "field_id"
    ]

    for column in [
        "candidate_date",
        "candidate_ndvi",
        "decline",
        "status"
    ]:

        if column in harvest_df.columns:

            transition_columns.append(
                column
            )

    transition_df = harvest_df[
        transition_columns
    ].copy()

    # --------------------------------------------------------
    # Check duplicate transition IDs
    # --------------------------------------------------------

    duplicate_transition_ids = (
        transition_df[
            transition_df["field_id"].duplicated(
                keep=False
            )
        ]
    )

    if not duplicate_transition_ids.empty:

        print(
            "\nWARNING: Multiple transition "
            "records found for the same field."
        )

        print(
            duplicate_transition_ids.to_string(
                index=False
            )
        )

        # Keep the first record for each unique
        # field ID to maintain one row per field.
        transition_df = (
            transition_df
            .drop_duplicates(
                subset=["field_id"],
                keep="first"
            )
        )

    final_df = final_df.merge(
        transition_df,
        on="field_id",
        how="left"
    )

    # --------------------------------------------------------
    # Clean numeric values
    # --------------------------------------------------------

    numeric_columns = [
        "area_hectares",
        "area_acres",
        "latest_ndvi",
        "latest_nbr",
        "candidate_ndvi",
        "decline"
    ]

    for column in numeric_columns:

        if column in final_df.columns:

            final_df[column] = pd.to_numeric(
                final_df[column],
                errors="coerce"
            )

    # --------------------------------------------------------
    # Create unified field status
    # --------------------------------------------------------

    def determine_status(row):

        transition_status = str(
            row.get("status", "")
        ).lower()

        ndvi_trend = str(
            row.get("ndvi_trend", "")
        ).lower()

        category = str(
            row.get("category", "")
        ).lower()

        if "candidate" in transition_status:

            return "crop_transition_candidate"

        if (
            "burnt" in category
            and category != "unburnt"
        ):

            return "burn_labeled"

        if ndvi_trend == "decreasing":

            return "vegetation_declining"

        if ndvi_trend == "increasing":

            return "vegetation_growing"

        return "stable"

    final_df["field_status"] = final_df.apply(
        determine_status,
        axis=1
    )

    # --------------------------------------------------------
    # Sort by field ID
    # --------------------------------------------------------

    final_df = final_df.sort_values(
        "field_id"
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    os.makedirs(
        os.path.dirname(OUTPUT_PATH),
        exist_ok=True
    )

    final_df.to_csv(
        OUTPUT_PATH,
        index=False
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print(
        "Unified field indicators created successfully!"
    )
    print("=" * 70)

    print(
        f"\nTotal fields: {len(final_df)}"
    )

    print(
        f"Total columns: {len(final_df.columns)}"
    )

    print(
        f"Unique field IDs: "
        f"{final_df['field_id'].nunique()}"
    )

    print("\nColumns:")

    for column in final_df.columns:

        print(
            f"  - {column}"
        )

    print("\nField status distribution:")

    print(
        final_df["field_status"]
        .value_counts(
            dropna=False
        )
        .to_string()
    )

    # --------------------------------------------------------
    # Specifically inspect the old Field 34 collision
    # --------------------------------------------------------

    print(
        "\nChecking regenerated Field 34 records:"
    )

    field_34_records = final_df[
        final_df["field_id"].isin(
            [
                "2020_34",
                "2021_34"
            ]
        )
    ]

    if field_34_records.empty:

        print(
            "No 2020_34 / 2021_34 records found."
        )

    else:

        display_columns = [
            column
            for column in [
                "field_id",
                "category",
                "area_hectares",
                "area_acres",
                "latest_ndvi",
                "latest_nbr",
                "ndvi_trend",
                "nbr_trend",
                "candidate_date",
                "decline",
                "status",
                "field_status"
            ]
            if column in final_df.columns
        ]

        print(
            field_34_records[
                display_columns
            ].to_string(index=False)
        )

    print("\nSaved to:")

    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()