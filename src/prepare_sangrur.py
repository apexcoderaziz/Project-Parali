import geopandas as gpd
import pandas as pd
from pathlib import Path


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data" / "sangrur"
OUTPUT_DIR = BASE_DIR / "data" / "processed"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# FIND SOURCE FILES
# ============================================================

files = sorted(DATA_DIR.glob("*.geojson"))

print(f"Found {len(files)} GeoJSON files")

if not files:
    raise FileNotFoundError(
        f"No GeoJSON files found in: {DATA_DIR}"
    )


# ============================================================
# READ AND PREPARE EACH FILE
# ============================================================

all_gdfs = []

for file in files:

    print(f"\nReading: {file.name}")

    gdf = gpd.read_file(file)

    print(f"  Fields found: {len(gdf)}")

    # --------------------------------------------------------
    # Check required columns
    # --------------------------------------------------------

    required_columns = [
        "field_id",
        "field_name",
        "field_category",
        "geometry"
    ]

    missing_columns = [
        column for column in required_columns
        if column not in gdf.columns
    ]

    if missing_columns:
        raise ValueError(
            f"{file.name} is missing columns: {missing_columns}"
        )

    # --------------------------------------------------------
    # Keep only required columns
    # --------------------------------------------------------

    gdf = gdf[required_columns].copy()

    # --------------------------------------------------------
    # Preserve original field ID
    # --------------------------------------------------------

    gdf["original_field_id"] = gdf["field_id"]

    # --------------------------------------------------------
    # Add source file
    # --------------------------------------------------------

    gdf["source_file"] = file.name

    # --------------------------------------------------------
    # Extract source year from filename
    #
    # Example:
    # partially_completely_burnt_2020_11_10.geojson
    # -> 2020
    # --------------------------------------------------------

    year_matches = file.stem.split("_")

    source_year = None

    for part in year_matches:
        if part.isdigit() and len(part) == 4:
            source_year = int(part)
            break

    if source_year is None:
        raise ValueError(
            f"Could not determine source year from filename: {file.name}"
        )

    gdf["source_year"] = source_year

    # --------------------------------------------------------
    # Create globally unique field ID
    #
    # Example:
    # original field_id = 34
    # source_year = 2020
    #
    # new field_id = 2020_34
    # --------------------------------------------------------

    gdf["field_id"] = (
        gdf["source_year"].astype(str)
        + "_"
        + gdf["original_field_id"].astype(str)
    )

    # --------------------------------------------------------
    # Create numerical labels
    # --------------------------------------------------------

    label_map = {
        "unburnt": 0,
        "partially_burnt": 1,
        "completely_burnt": 2
    }

    gdf["label"] = gdf["field_category"].map(label_map)

    # --------------------------------------------------------
    # Validate categories
    # --------------------------------------------------------

    unknown_categories = gdf.loc[
        gdf["label"].isna(),
        "field_category"
    ].dropna().unique()

    if len(unknown_categories) > 0:
        print(
            f"WARNING: Unknown categories in {file.name}: "
            f"{list(unknown_categories)}"
        )

    all_gdfs.append(gdf)


# ============================================================
# COMBINE DATASETS
# ============================================================

combined = gpd.GeoDataFrame(
    pd.concat(
        all_gdfs,
        ignore_index=True
    ),
    crs=all_gdfs[0].crs
)


# ============================================================
# VALIDATE UNIQUE FIELD IDS
# ============================================================

duplicate_ids = combined[
    combined["field_id"].duplicated(keep=False)
]

if not duplicate_ids.empty:

    print("\nWARNING: Duplicate field IDs detected:")

    print(
        duplicate_ids[
            [
                "field_id",
                "original_field_id",
                "field_name",
                "source_year",
                "field_category"
            ]
        ].to_string(index=False)
    )

    raise ValueError(
        "Field IDs are still duplicated. "
        "Dataset preparation stopped."
    )


# ============================================================
# SAVE DATASET
# ============================================================

output_file = OUTPUT_DIR / "sangrur_fields.geojson"

combined.to_file(
    output_file,
    driver="GeoJSON"
)


# ============================================================
# REPORT
# ============================================================

print("\n" + "=" * 60)
print("SANGRUR DATASET READY")
print("=" * 60)

print("\nTotal fields:", len(combined))

print("\nUnique field IDs:", combined["field_id"].nunique())

print("\nClass distribution:")

print(
    combined["field_category"]
    .value_counts()
)


print("\nNumeric labels:")

print(
    combined["label"]
    .value_counts()
    .sort_index()
)


print("\nSource-year distribution:")

print(
    combined["source_year"]
    .value_counts()
    .sort_index()
)


print("\nExample of generated field IDs:")

print(
    combined[
        [
            "field_id",
            "original_field_id",
            "field_name",
            "source_year",
            "field_category"
        ]
    ]
    .head(10)
    .to_string(index=False)
)


print("\nCRS:")

print(combined.crs)


print("\nSaved to:")

print(output_file)

print("\n" + "=" * 60)