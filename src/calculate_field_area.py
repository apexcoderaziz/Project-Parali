import os
import json
import csv

from shapely.geometry import shape
from pyproj import Geod


# ============================================================
# Project paths
# ============================================================

BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

GEOJSON_PATH = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "sangrur_fields.geojson"
)

OUTPUT_PATH = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "field_area.csv"
)


# ============================================================
# Geodesic calculator
# WGS84 ellipsoid gives area in square meters
# ============================================================

GEOD = Geod(ellps="WGS84")


# ============================================================
# Helpers
# ============================================================

def get_field_id(properties, index):
    """
    Extract the globally unique field ID from GeoJSON.

    The prepared Sangrur GeoJSON now uses IDs such as:

        2020_34
        2021_34

    These are intentionally kept as strings because they contain
    the source year and original field ID.
    """

    raw_field_id = (
        properties.get("field_id")
        or properties.get("id")
        or properties.get("ID")
        or properties.get("Id")
    )

    if raw_field_id is None:
        return str(index + 1)

    return str(raw_field_id).strip()


def get_category(properties):
    """
    Extract the field category from GeoJSON properties.

    The prepared Sangrur GeoJSON stores the category in:

        field_category

    Example:

        partially_burnt
        completely_burnt
        unburnt
        golden_yellow_unburnt
        green_unburnt
    """

    possible_keys = [
        "field_category",
        "category",
        "Category",
        "class",
        "Class",
        "burn_category",
        "burn_class"
    ]

    for key in possible_keys:

        value = properties.get(key)

        if value is not None and str(value).strip():

            return str(value).strip()

    return "unknown"


def calculate_area_hectares(geometry):
    """
    Calculate geodesic polygon area using WGS84.

    Returns area in hectares.
    """

    polygon = shape(geometry)

    # Fix invalid geometries when possible.
    if not polygon.is_valid:
        polygon = polygon.buffer(0)

    area_square_meters, _ = GEOD.geometry_area_perimeter(
        polygon
    )

    # Geometry area can theoretically be negative depending
    # on polygon orientation.
    area_square_meters = abs(area_square_meters)

    area_hectares = area_square_meters / 10_000

    return area_hectares


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 60)
    print("Project Parali - Field Area Calculation")
    print("=" * 60)

    print("\nInput:")
    print(GEOJSON_PATH)

    print("\nOutput:")
    print(OUTPUT_PATH)

    if not os.path.exists(GEOJSON_PATH):

        raise FileNotFoundError(
            f"GeoJSON file not found:\n{GEOJSON_PATH}"
        )

    # --------------------------------------------------------
    # Load GeoJSON
    # --------------------------------------------------------

    with open(
        GEOJSON_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        geojson = json.load(file)

    features = geojson.get("features", [])

    if not features:
        raise ValueError(
            "No features found in GeoJSON."
        )

    print(
        f"\nTotal fields found: {len(features)}"
    )

    results = []

    # --------------------------------------------------------
    # Process fields
    # --------------------------------------------------------

    for index, feature in enumerate(features):

        properties = feature.get(
            "properties",
            {}
        )

        geometry = feature.get(
            "geometry"
        )

        field_id = get_field_id(
            properties,
            index
        )

        category = get_category(
            properties
        )

        if geometry is None:

            print(
                f"Warning: Field {field_id} "
                f"has no geometry. Skipping."
            )

            continue

        try:

            area_hectares = calculate_area_hectares(
                geometry
            )

            area_acres = (
                area_hectares * 2.47105
            )

            results.append({

                "field_id": field_id,

                "category": category,

                "area_hectares": round(
                    area_hectares,
                    4
                ),

                "area_acres": round(
                    area_acres,
                    4
                )
            })

        except Exception as error:

            print(
                f"Warning: Could not calculate area "
                f"for field {field_id}: {error}"
            )

    # --------------------------------------------------------
    # Validate unique IDs
    # --------------------------------------------------------

    field_ids = [
        row["field_id"]
        for row in results
    ]

    duplicate_ids = {
        field_id
        for field_id in field_ids
        if field_ids.count(field_id) > 1
    }

    if duplicate_ids:

        raise ValueError(
            "Duplicate field IDs detected: "
            f"{sorted(duplicate_ids)}"
        )

    # --------------------------------------------------------
    # Save CSV
    # --------------------------------------------------------

    os.makedirs(
        os.path.dirname(OUTPUT_PATH),
        exist_ok=True
    )

    with open(
        OUTPUT_PATH,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=[
                "field_id",
                "category",
                "area_hectares",
                "area_acres"
            ]
        )

        writer.writeheader()

        writer.writerows(results)

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print("\n" + "=" * 60)
    print("Field area calculation complete!")
    print("=" * 60)

    print(
        f"\nFields processed: {len(results)}"
    )

    print(
        f"Unique field IDs: "
        f"{len(set(field_ids))}"
    )

    if results:

        total_area = sum(
            row["area_hectares"]
            for row in results
        )

        print(
            f"\nTotal mapped area: "
            f"{total_area:.2f} hectares"
        )

        print("\nFirst 5 fields:")

        for row in results[:5]:

            print(
                f"Field {row['field_id']} | "
                f"{row['category']} | "
                f"{row['area_hectares']:.4f} ha | "
                f"{row['area_acres']:.4f} acres"
            )

    print("\nChecking Field 34 records:")

    field_34_records = [
        row
        for row in results
        if row["field_id"] in {
            "2020_34",
            "2021_34"
        }
    ]

    for row in field_34_records:

        print(
            f"Field {row['field_id']} | "
            f"{row['category']} | "
            f"{row['area_hectares']:.4f} ha | "
            f"{row['area_acres']:.4f} acres"
        )

    print("\nSaved to:")
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()