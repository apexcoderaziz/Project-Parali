import ee

PROJECT_ID = "project-18808c04-2093-4bb1-940"

ee.Initialize(project=PROJECT_ID)

print("Earth Engine initialized successfully!")

collection = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")

print("Sentinel-2 collection loaded!")
print("Earth Engine connection is working.")