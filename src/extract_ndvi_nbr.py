import ee

# --------------------------------------------------
# 1. Initialize Earth Engine
# --------------------------------------------------

PROJECT_ID = "project-18808c04-2093-4bb1-940"

ee.Initialize(project=PROJECT_ID)

print("Earth Engine initialized successfully!")


# --------------------------------------------------
# 2. Define Sangrur approximate study area
# --------------------------------------------------

sangrur = ee.Geometry.Rectangle([
    75.40, 29.70,   # min longitude, min latitude
    76.30, 30.35    # max longitude, max latitude
])

print("Sangrur study area created.")


# --------------------------------------------------
# 3. Load Sentinel-2
# --------------------------------------------------

collection = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(sangrur)
    .filterDate("2024-10-01", "2024-12-31")
    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
)

print("Sentinel-2 collection filtered for Sangrur.")


# --------------------------------------------------
# 4. Check number of useful images
# --------------------------------------------------

count = collection.size().getInfo()

print("Useful Sentinel-2 images:", count)


# --------------------------------------------------
# 5. Get median image
# --------------------------------------------------

image = collection.median().clip(sangrur)

print("Median Sentinel-2 image created.")


# --------------------------------------------------
# 6. Calculate NDVI
# --------------------------------------------------

ndvi = image.normalizedDifference([
    "B8",
    "B4"
]).rename("NDVI")


# --------------------------------------------------
# 7. Calculate NBR
# --------------------------------------------------

nbr = image.normalizedDifference([
    "B8",
    "B12"
]).rename("NBR")


# --------------------------------------------------
# 8. Combine NDVI + NBR
# --------------------------------------------------

features = ndvi.addBands(nbr)

print("NDVI + NBR calculated successfully.")


# --------------------------------------------------
# 9. Get mean values over Sangrur
# --------------------------------------------------

stats = features.reduceRegion(
    reducer=ee.Reducer.mean(),
    geometry=sangrur,
    scale=20,
    maxPixels=1e9
)

print("Sangrur NDVI/NBR statistics:")
print(stats.getInfo())

print("\nNDVI + NBR extraction COMPLETE!")