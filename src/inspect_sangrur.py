import geopandas as gpd
from pathlib import Path


DATA_DIR = Path("data/sangrur")


files = list(DATA_DIR.glob("*.geojson"))

print("=" * 60)
print("PROJECT PARALI - SANGRUR DATASET INSPECTION")
print("=" * 60)

print(f"\nFound {len(files)} GeoJSON files:\n")

for file in files:

    print("=" * 60)
    print(f"FILE: {file.name}")
    print("=" * 60)

    gdf = gpd.read_file(file)

    print("\nNumber of fields:", len(gdf))

    print("\nColumns:")
    print(list(gdf.columns))

    print("\nCoordinate Reference System:")
    print(gdf.crs)

    print("\nGeometry types:")
    print(gdf.geometry.geom_type.value_counts())

    print("\nFirst 5 rows:")
    print(gdf.head())

    # Print likely class columns
    for column in gdf.columns:

        if column != "geometry":

            unique = gdf[column].dropna().unique()

            if len(unique) <= 20:

                print(f"\n{column}:")
                print(unique)


print("\n" + "=" * 60)
print("INSPECTION COMPLETE")
print("=" * 60)