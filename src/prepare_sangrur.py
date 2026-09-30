import geopandas as gpd
import pandas as pd
from pathlib import Path

DATA_DIR = Path("data/sangrur")
OUTPUT_DIR = Path("data/processed")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

files = list(DATA_DIR.glob("*.geojson"))

print(f"Found {len(files)} GeoJSON files")

all_gdfs = []

for file in files:
    print(f"Reading: {file.name}")

    gdf = gpd.read_file(file)

    # Keep only the columns we need
    gdf = gdf[[
        "field_id",
        "field_name",
        "field_category",
        "geometry"
    ]].copy()

    # Add source year/file
    gdf["source_file"] = file.name

    all_gdfs.append(gdf)

# Combine
combined = gpd.GeoDataFrame(
    pd.concat(all_gdfs, ignore_index=True),
    crs=all_gdfs[0].crs
)

# Create numerical labels
label_map = {
    "unburnt": 0,
    "partially_burnt": 1,
    "completely_burnt": 2
}

combined["label"] = combined["field_category"].map(label_map)

# Save
output_file = OUTPUT_DIR / "sangrur_fields.geojson"

combined.to_file(
    output_file,
    driver="GeoJSON"
)

print("\n" + "=" * 60)
print("SANGRUR DATASET READY")
print("=" * 60)

print("\nTotal fields:", len(combined))

print("\nClass distribution:")
print(combined["field_category"].value_counts())

print("\nNumeric labels:")
print(combined["label"].value_counts().sort_index())

print("\nCRS:")
print(combined.crs)

print("\nSaved to:")
print(output_file)