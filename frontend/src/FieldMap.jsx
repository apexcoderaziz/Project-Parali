import {
  MapContainer,
  TileLayer,
  GeoJSON,
  Marker,
  useMap,
  LayersControl
} from "react-leaflet";

import {
  useEffect,
  useMemo
} from "react";

import L from "leaflet";


const getCategoryStyle = (category) => {
  const normalized =
    String(category || "")
      .toLowerCase()
      .trim()
      .replace(/-/g, "_")
      .replace(/\s+/g, "_");

  if (
    normalized === "unburnt" ||
    normalized === "unburned"
  ) {
    return {
      color: "#83b86b",
      fillColor: "#b8ef75",
      fillOpacity: 0.24
    };
  }

  if (
    normalized === "partially_burnt" ||
    normalized === "partial_burnt"
  ) {
    return {
      color: "#f3a94d",
      fillColor: "#ffb74d",
      fillOpacity: 0.26
    };
  }

  if (
    normalized === "completely_burnt" ||
    normalized === "burnt" ||
    normalized === "burned"
  ) {
    return {
      color: "#ef6d5a",
      fillColor: "#ff7465",
      fillOpacity: 0.26
    };
  }

  return {
    color: "#c2d0c8",
    fillColor: "#d7e2dc",
    fillOpacity: 0.2
  };
};


const getIndicators = (feature) =>
  feature?.properties?.field_indicators ||
  feature?.properties?.indicators ||
  {};


const getFieldId = (
  feature,
  index
) => {
  const raw =
    feature?.properties?.field_id ??
    feature?.properties?.id;

  if (
    raw !== null &&
    raw !== undefined &&
    String(raw).trim()
  ) {
    return String(raw).trim();
  }

  return `field-${index + 1}`;
};


const getDisplayFieldNumber = (
  feature,
  index
) => {
  const fieldId =
    getFieldId(feature, index);

  return (
    String(fieldId).match(
      /^\d{4}_(.+)$/
    )?.[1] || fieldId
  );
};


const getSourceYear = (feature) => {
  const sourceYear =
    feature?.properties?.source_year;

  if (
    sourceYear !== null &&
    sourceYear !== undefined &&
    String(sourceYear).trim()
  ) {
    return String(sourceYear).trim();
  }

  return (
    String(
      feature?.properties?.field_id ||
        ""
    ).match(/^\d{4}_/)?.[0] ||
    ""
  ).replace("_", "");
};


const getCategory = (feature) => {
  const indicators =
    getIndicators(feature);

  return (
    feature?.properties?.category ||
    feature?.properties?.field_category ||
    indicators.category ||
    "Unknown"
  );
};


const getFieldStatus = (feature) => {
  const indicators =
    getIndicators(feature);

  return (
    feature?.properties?.field_status ||
    indicators.field_status ||
    "Unknown"
  );
};


const getCandidateDate = (feature) => {
  const indicators =
    getIndicators(feature);

  return (
    feature?.properties?.candidate_date ||
    indicators.candidate_date ||
    null
  );
};


const isTransitionCandidate = (
  feature
) => {
  const status =
    String(getFieldStatus(feature))
      .toLowerCase()
      .trim();

  return Boolean(
    getCandidateDate(feature)
  ) ||
    status ===
      "crop_transition_candidate" ||
    status.includes("crop-transition") ||
    status.includes("transition candidate");
};


const getTransitionStyle = (
  baseStyle,
  feature
) => {
  if (!isTransitionCandidate(feature)) {
    return baseStyle;
  }

  return {
    ...baseStyle,
    color: "#e8e873",
    weight: 3,
    dashArray: "7 5",
    fillOpacity:
      Math.min(
        0.42,
        (baseStyle.fillOpacity || 0.2) + 0.08
      )
  };
};


function FitBounds({
  geojson
}) {
  const map = useMap();

  useEffect(() => {
    if (
      !geojson?.features?.length
    ) {
      return;
    }

    try {
      const bounds =
        L.geoJSON(
          geojson
        ).getBounds();

      if (bounds.isValid()) {
        map.fitBounds(
          bounds,
          {
            padding: [24, 24]
          }
        );
      }
    } catch (error) {
      console.error(
        "Failed to fit map bounds:",
        error
      );
    }
  }, [geojson, map]);

  return null;
}


function ResizeMap() {
  const map = useMap();

  useEffect(() => {
    const invalidate = () =>
      map.invalidateSize();

    const timer =
      window.setTimeout(
        invalidate,
        120
      );

    window.addEventListener(
      "resize",
      invalidate
    );

    return () => {
      window.clearTimeout(timer);
      window.removeEventListener(
        "resize",
        invalidate
      );
    };
  }, [map]);

  return null;
}


function FieldMarkers({
  geojson,
  onFieldSelect
}) {
  const markers = useMemo(() => {
    const features =
      geojson?.features || [];

    return features.flatMap(
      (feature, index) => {
        try {
          const bounds =
            L.geoJSON(
              feature
            ).getBounds();

          if (!bounds.isValid()) {
            return [];
          }

          return [
            {
              fieldId:
                getFieldId(
                  feature,
                  index
                ),
              displayFieldNumber:
                getDisplayFieldNumber(
                  feature,
                  index
                ),
              center:
                bounds.getCenter(),
              category:
                getCategory(
                  feature
                ),
              transition:
                isTransitionCandidate(
                  feature
                )
            }
          ];
        } catch (error) {
          console.error(
            "Failed to create field marker:",
            error
          );
          return [];
        }
      }
    );
  }, [geojson]);

  return (
    <>
      {markers.map((marker) => {
        const categoryStyle =
          getCategoryStyle(
            marker.category
          );

        const icon =
          L.divIcon({
            className:
              "parali-map-marker-shell",
            html: `
              <div
                class="parali-map-marker ${
                  marker.transition
                    ? "is-transition"
                    : ""
                }"
                style="
                  --marker-fill:${categoryStyle.fillColor};
                "
              >
                <span>
                  ${marker.displayFieldNumber}
                </span>
              </div>
            `,
            iconSize: [34, 34],
            iconAnchor: [17, 17]
          });

        return (
          <Marker
            key={`marker-${marker.fieldId}`}
            position={marker.center}
            icon={icon}
            eventHandlers={{
              click: (event) => {
                const map =
                  event.target._map;

                map.setView(
                  marker.center,
                  17,
                  {
                    animate: true
                  }
                );

                onFieldSelect(
                  marker.displayFieldNumber
                );
              }
            }}
          />
        );
      })}
    </>
  );
}


function FieldMap({
  geojson,
  onFieldSelect
}) {
  if (
    !geojson?.features
  ) {
    return (
      <div className="map-loading">
        Loading field map...
      </div>
    );
  }

  const onEachField = (
    feature,
    layer
  ) => {
    const index =
      geojson.features.indexOf(
        feature
      );

    const fieldId =
      getFieldId(
        feature,
        index
      );

    const displayFieldNumber =
      getDisplayFieldNumber(
        feature,
        index
      );

    const category =
      getCategory(feature);

    const fieldStatus =
      getFieldStatus(feature);

    const candidateDate =
      getCandidateDate(feature);

    const indicators =
      getIndicators(feature);

    const baseStyle =
      getCategoryStyle(
        category
      );

    const mapStyle =
      getTransitionStyle(
        baseStyle,
        feature
      );

    layer.setStyle(
      mapStyle
    );

    layer.bindPopup(
      `
        <div class="parali-map-popup">
          <div class="map-popup-kicker">
            FIELD ANALYSIS
          </div>

          <strong>
            Field ${displayFieldNumber}
          </strong>

          <div class="map-popup-meta">
            <span>Source</span>
            <b>${fieldId}</b>
          </div>

          <div class="map-popup-meta">
            <span>Year</span>
            <b>${getSourceYear(feature) || "N/A"}</b>
          </div>

          <div class="map-popup-meta">
            <span>Category</span>
            <b>${category}</b>
          </div>

          <div class="map-popup-meta">
            <span>NDVI trend</span>
            <b>${indicators.ndvi_trend || "N/A"}</b>
          </div>

          <div class="map-popup-meta">
            <span>NBR trend</span>
            <b>${indicators.nbr_trend || "N/A"}</b>
          </div>

          <div class="map-popup-status ${
            isTransitionCandidate(
              feature
            )
              ? "is-transition"
              : ""
          }">
            ${
              candidateDate
                ? `Transition candidate · ${candidateDate}`
                : fieldStatus || "Monitoring active"
            }
          </div>

          <div class="map-popup-hint">
            Click to open full field analysis.
          </div>
        </div>
      `
    );

    layer.on({
      mouseover: (event) => {
        event.target.setStyle({
          color: "#f4ffdd",
          weight: 4,
          fillColor:
            baseStyle.fillColor,
          fillOpacity: 0.48
        });

        if (
          !L.Browser.ie &&
          !L.Browser.opera &&
          !L.Browser.edge
        ) {
          event.target.bringToFront();
        }
      },

      mouseout: (event) => {
        event.target.setStyle(
          mapStyle
        );
      },

      click: (event) => {
        const map =
          event.target._map;

        const bounds =
          event.target.getBounds();

        if (bounds.isValid()) {
          map.fitBounds(
            bounds,
            {
              padding: [48, 48],
              maxZoom: 17,
              animate: true
            }
          );
        }

        event.target.openPopup();

        onFieldSelect(
          displayFieldNumber
        );
      }
    });
  };

  return (
    <MapContainer
      center={[
        30.0,
        75.0
      ]}
      zoom={10}
      scrollWheelZoom={true}
      className="field-map"
    >
      <ResizeMap />

      <LayersControl
        position="topright"
      >
        <LayersControl.BaseLayer
          checked={true}
          name="Satellite"
        >
          <TileLayer
            attribution="Imagery &copy; Esri, Maxar, Earthstar Geographics, and the GIS User Community"
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            maxZoom={19}
          />
        </LayersControl.BaseLayer>

        <LayersControl.BaseLayer
          name="Street Map"
        >
          <TileLayer
            attribution="&copy; OpenStreetMap contributors"
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            maxZoom={19}
          />
        </LayersControl.BaseLayer>
      </LayersControl>

      <GeoJSON
        data={geojson}
        onEachFeature={
          onEachField
        }
      />

      <FieldMarkers
        geojson={geojson}
        onFieldSelect={
          onFieldSelect
        }
      />

      <FitBounds
        geojson={geojson}
      />
    </MapContainer>
  );
}

export default FieldMap;
