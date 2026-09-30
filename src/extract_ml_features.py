import ee
import geopandas as gpd
import pandas as pd
from pathlib import Path

# --------------------------------------------------
# 1. Initialize Earth Engine
# --------------------------------------------------

PROJECT_ID = "project-18808c04-2093-4bb1-940"

ee.Initialize(project=PROJECT_ID)

print("Earth Engine initialized successfully!")


# --------------------------------------------------
# 2. Load labeled Sangrur fields
# --------------------------------------------------

input_file = Path("data/processed/sangrur_fields.geojson")

gdf = gpd.read_file(input_file)

print("Fields loaded:", len(gdf))


# --------------------------------------------------
# 3. Convert GeoDataFrame to Earth Engine
# --------------------------------------------------

geojson = gdf.__geo_interface__

fields = ee.FeatureCollection(geojson)

print("Earth Engine field collection created.")


# --------------------------------------------------
# 4. Define study area
# --------------------------------------------------

sangrur = ee.Geometry.Rectangle([
    75.40, 29.70,
    76.30, 30.35
])


# --------------------------------------------------
# 5. Load Sentinel-2
# --------------------------------------------------

collection = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(sangrur)
    .filterDate("2024-10-01", "2024-12-31")
    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
)

print("Sentinel-2 collection filtered.")


# --------------------------------------------------
# 6. Create median image
# --------------------------------------------------

image = collection.median().clip(sangrur)

print("Median Sentinel-2 image created.")


# --------------------------------------------------
# 7. Select spectral bands
# --------------------------------------------------

bands = [
    "B2",
    "B3",
    "B4",
    "B8",
    "B11",
    "B12"
]

spectral = image.select(bands).divide(10000)


# --------------------------------------------------
# 8. Calculate NDVI
# --------------------------------------------------

ndvi = image.normalizedDifference([
    "B8",
    "B4"
]).rename("NDVI")


# --------------------------------------------------
# 9. Calculate NBR
# --------------------------------------------------

nbr = image.normalizedDifference([
    "B8",
    "B12"
]).rename("NBR")


# --------------------------------------------------
# 10. Combine all ML features
# --------------------------------------------------

feature_image = (
    spectral
    .addBands(ndvi)
    .addBands(nbr)
)

print("ML feature image created.")


# --------------------------------------------------
# 11. Extract mean features for every field
# --------------------------------------------------

result = feature_image.reduceRegions(
    collection=fields,
    reducer=ee.Reducer.mean(),
    scale=20,
    tileScale=4
)

print("Features extracted for all fields.")


# --------------------------------------------------
# 12. Download results
# --------------------------------------------------

data = result.getInfo()

rows = []

for feature in data["features"]:

    properties = feature["properties"]

    rows.append(properties)


# --------------------------------------------------
# 13. Create DataFrame
# --------------------------------------------------

df = pd.DataFrame(rows)

print("\nExtracted dataset:")
print(df.head())

print("\nDataset shape:")
print(df.shape)

print("\nClass distribution:")
print(df["label"].value_counts())


# --------------------------------------------------
# 14. Save ML dataset
# --------------------------------------------------

output_file = Path(
    "data/processed/sangrur_ml_features.csv"
)

df.to_csv(output_file, index=False)

print("\nSaved to:")
print(output_file)

print("\nML FEATURE EXTRACTION COMPLETE!")