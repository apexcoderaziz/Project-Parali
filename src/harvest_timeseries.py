import os
import json
import ee
import pandas as pd


# =========================================================
# CONFIG
# =========================================================

PROJECT_ID = "project-18808c04-2093-4bb1-940"


# Project root:
# Project-Parali/
BASE_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        ".."
    )
)


# Input GeoJSON
GEOJSON_PATH = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "sangrur_fields.geojson"
)


# Output CSV
OUTPUT_PATH = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "field_ndvi_timeseries.csv"
)


# Process all fields
MAX_FIELDS = None


# 2020 observation period
START_DATE = "2020-09-15"
END_DATE = "2020-12-31"


# Maximum cloud percentage
CLOUD_PERCENT = 40


# Sentinel-2 resolution
SCALE = 10


# =========================================================
# INITIALIZE EARTH ENGINE
# =========================================================

print("Initializing Google Earth Engine...")

try:

    ee.Initialize(
        project=PROJECT_ID
    )

except Exception as e:

    print("\nEarth Engine initialization failed.")
    print("\nRun:")
    print("earthengine authenticate")

    raise e


print(
    "Earth Engine initialized successfully."
)


# =========================================================
# LOAD GEOJSON
# =========================================================

print("\nLoading GeoJSON...")

with open(
    GEOJSON_PATH,
    "r",
    encoding="utf-8"
) as f:

    geojson = json.load(f)


features = geojson.get(
    "features",
    []
)


print(
    "Total GeoJSON features:",
    len(features)
)


# =========================================================
# LIMIT FIELDS
# =========================================================

if MAX_FIELDS is not None:

    features = features[:MAX_FIELDS]

    print(
        "Processing fields:",
        len(features)
    )

else:

    print(
        "Processing ALL fields:",
        len(features)
    )


# =========================================================
# CONVERT GEOJSON → EARTH ENGINE FEATURES
# =========================================================

ee_features = []


for index, feature in enumerate(features):

    geometry = feature.get(
        "geometry"
    )

    properties = feature.get(
        "properties",
        {}
    )


    if geometry is None:

        print(
            f"Skipping feature {index + 1}: "
            "missing geometry"
        )

        continue


    # -----------------------------------------------------
    # CONSISTENT STRING FIELD ID
    # -----------------------------------------------------
    #
    # New IDs look like:
    #
    #   2020_34
    #   2021_34
    #
    # They MUST remain strings.
    # -----------------------------------------------------

    raw_field_id = (
        properties.get("field_id")
        or properties.get("id")
        or properties.get("ID")
        or properties.get("Id")
        or str(index + 1)
    )


    field_id = str(
        raw_field_id
    ).strip()


    if not field_id:

        field_id = str(
            index + 1
        )


    # -----------------------------------------------------
    # FIELD CATEGORY
    # -----------------------------------------------------

    field_category = (
        properties.get("field_category")
        or properties.get("category")
        or properties.get("burn_category")
        or ""
    )


    field_category = str(
        field_category
    ).strip()


    # -----------------------------------------------------
    # CREATE EE GEOMETRY
    # -----------------------------------------------------

    try:

        ee_geometry = ee.Geometry(
            geometry
        )

    except Exception:

        print(
            f"Skipping field {field_id}: "
            "invalid geometry"
        )

        continue


    # -----------------------------------------------------
    # CREATE EE FEATURE
    # -----------------------------------------------------

    ee_feature = ee.Feature(
        ee_geometry,
        {
            "field_id": field_id,
            "field_category": field_category
        }
    )


    ee_features.append(
        ee_feature
    )


fields = ee.FeatureCollection(
    ee_features
)


print(
    "Earth Engine fields created:",
    len(ee_features)
)


if len(ee_features) == 0:

    raise RuntimeError(
        "No valid field geometries found."
    )


# =========================================================
# SENTINEL-2 CLOUD MASK
# =========================================================

def mask_sentinel2(image):

    qa = image.select(
        "QA60"
    )

    cloud_bit = 1 << 10
    cirrus_bit = 1 << 11


    mask = (
        qa.bitwiseAnd(
            cloud_bit
        ).eq(0)
        .And(
            qa.bitwiseAnd(
                cirrus_bit
            ).eq(0)
        )
    )


    return (
        image
        .updateMask(mask)
        .divide(10000)
        .copyProperties(
            image,
            [
                "system:time_start",
                "CLOUDY_PIXEL_PERCENTAGE"
            ]
        )
    )


# =========================================================
# ADD NDVI + NBR
# =========================================================

def add_indices(image):

    ndvi = (
        image
        .normalizedDifference(
            [
                "B8",
                "B4"
            ]
        )
        .rename("NDVI")
    )


    nbr = (
        image
        .normalizedDifference(
            [
                "B8",
                "B12"
            ]
        )
        .rename("NBR")
    )


    return (
        image
        .addBands(ndvi)
        .addBands(nbr)
    )


# =========================================================
# SENTINEL-2 COLLECTION
# =========================================================

print(
    "\nSearching Sentinel-2..."
)


collection = (
    ee.ImageCollection(
        "COPERNICUS/S2_SR_HARMONIZED"
    )

    .filterDate(
        START_DATE,
        END_DATE
    )

    .filterBounds(
        fields.geometry()
    )

    .filter(
        ee.Filter.lt(
            "CLOUDY_PIXEL_PERCENTAGE",
            CLOUD_PERCENT
        )
    )

    .map(
        mask_sentinel2
    )

    .map(
        add_indices
    )

    .sort(
        "system:time_start"
    )
)


image_count = (
    collection
    .size()
    .getInfo()
)


print(
    "Sentinel-2 images found:",
    image_count
)


if image_count == 0:

    raise RuntimeError(
        "No Sentinel-2 images found."
    )


# =========================================================
# IMPORTANT:
# PROCESS ONE IMAGE AT A TIME
#
# This avoids:
#
# Collection query aborted after accumulating
# over 5000 elements.
# =========================================================

print(
    "\nStarting field-level extraction..."
)


print(
    "Processing one satellite image at a time."
)


image_list = collection.toList(
    image_count
)


all_rows = []


for image_index in range(
    image_count
):

    print(
        f"\nProcessing image "
        f"{image_index + 1}/{image_count}..."
    )


    # -----------------------------------------------------
    # Get image
    # -----------------------------------------------------

    image = ee.Image(
        image_list.get(
            image_index
        )
    )


    # -----------------------------------------------------
    # Get image date
    # -----------------------------------------------------

    date = (
        ee.Date(
            image.get(
                "system:time_start"
            )
        )
        .format(
            "YYYY-MM-dd"
        )
        .getInfo()
    )


    image_id = image.id().getInfo()


    print(
        "Date:",
        date
    )


    # -----------------------------------------------------
    # Select NDVI + NBR
    # -----------------------------------------------------

    selected_bands = image.select(
        [
            "NDVI",
            "NBR"
        ]
    )


    # -----------------------------------------------------
    # Reduce image over fields
    # -----------------------------------------------------

    reduced = (
        selected_bands
        .reduceRegions(
            collection=fields,
            reducer=ee.Reducer.mean(),
            scale=SCALE
        )
    )


    # -----------------------------------------------------
    # Download ONLY this image's results
    #
    # This is the important fix.
    # -----------------------------------------------------

    try:

        image_results = reduced.getInfo()

    except Exception as e:

        print(
            f"WARNING: Could not process "
            f"{date}: {e}"
        )

        continue


    image_features = image_results.get(
        "features",
        []
    )


    print(
        "Fields returned:",
        len(image_features)
    )


    # -----------------------------------------------------
    # Convert to local rows
    # -----------------------------------------------------

    for feature in image_features:

        properties = feature.get(
            "properties",
            {}
        )


        field_id = properties.get(
            "field_id"
        )


        if field_id is None:

            continue


        # IMPORTANT:
        # Always preserve field IDs as strings.

        field_id = str(
            field_id
        ).strip()


        field_category = properties.get(
            "field_category",
            ""
        )


        field_category = str(
            field_category
        ).strip()


        ndvi = properties.get(
            "NDVI"
        )


        nbr = properties.get(
            "NBR"
        )


        all_rows.append(
            {
                "field_id": field_id,

                "field_category":
                    field_category,

                "date":
                    date,

                "image_id":
                    image_id,

                "ndvi":
                    ndvi,

                "nbr":
                    nbr
            }
        )


# =========================================================
# CHECK RESULTS
# =========================================================

print(
    "\n======================================"
)


print(
    "Earth Engine extraction finished."
)


print(
    "Total downloaded observations:",
    len(all_rows)
)


if len(all_rows) == 0:

    raise RuntimeError(
        "No field observations were returned."
    )


# =========================================================
# CREATE DATAFRAME
# =========================================================

df = pd.DataFrame(
    all_rows
)


# =========================================================
# CLEAN DATA
# =========================================================

# ---------------------------------------------------------
# KEEP FIELD IDs AS STRINGS
# ---------------------------------------------------------

df["field_id"] = (
    df["field_id"]
    .astype(str)
    .str.strip()
)


# ---------------------------------------------------------
# Normalize date
# ---------------------------------------------------------

df["date"] = pd.to_datetime(
    df["date"],
    errors="coerce"
)


# ---------------------------------------------------------
# Normalize NDVI
# ---------------------------------------------------------

df["ndvi"] = pd.to_numeric(
    df["ndvi"],
    errors="coerce"
)


# ---------------------------------------------------------
# Normalize NBR
# ---------------------------------------------------------

df["nbr"] = pd.to_numeric(
    df["nbr"],
    errors="coerce"
)


# ---------------------------------------------------------
# Remove invalid field/date rows
# ---------------------------------------------------------

df = df.dropna(
    subset=[
        "field_id",
        "date"
    ]
)


# ---------------------------------------------------------
# Sort
# ---------------------------------------------------------

df = df.sort_values(
    [
        "field_id",
        "date"
    ]
)


# =========================================================
# VALIDATE FIELD IDs
# =========================================================

unique_field_ids = (
    df["field_id"]
    .dropna()
    .unique()
)


print(
    "\nUnique field IDs in time series:",
    len(unique_field_ids)
)


print(
    "\nSample Field IDs:"
)


for field_id in sorted(
    unique_field_ids
)[:30]:

    print(
        " ",
        field_id
    )


# =========================================================
# SPECIFIC FIELD 34 CHECK
# =========================================================

print(
    "\nChecking Field 34 records:"
)


field_34_ids = [
    "2020_34",
    "2021_34"
]


field_34_df = df[
    df["field_id"].isin(
        field_34_ids
    )
]


if field_34_df.empty:

    print(
        "No 2020_34 / 2021_34 observations found."
    )

else:

    print(
        field_34_df[
            [
                "field_id",
                "field_category",
                "date",
                "ndvi",
                "nbr"
            ]
        ]
        .head(10)
        .to_string(index=False)
    )


# =========================================================
# SAVE
# =========================================================

os.makedirs(
    os.path.dirname(
        OUTPUT_PATH
    ),
    exist_ok=True
)


df.to_csv(
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
    "SENTINEL-2 FIELD TIME SERIES"
)


print(
    "======================================"
)


print(
    "Fields:",
    df["field_id"].nunique()
)


print(
    "Observations:",
    len(df)
)


print(
    "Date range:",
    df["date"].min(),
    "to",
    df["date"].max()
)


print(
    "Output:"
)


print(
    OUTPUT_PATH
)


print(
    "\nFirst 10 rows:"
)


print(
    df.head(10).to_string(
        index=False
    )
)


print(
    "\nTime-series extraction complete!"
)