import {
  MapContainer,
  TileLayer,
  GeoJSON,
  Marker,
  useMap
} from "react-leaflet";

import {
  useEffect,
  useMemo
} from "react";

import L from "leaflet";


// =====================================================
// CATEGORY COLORS
// =====================================================

const getCategoryStyle = (category) => {
  const normalizedCategory =
    String(category || "")
      .toLowerCase()
      .trim();

  // Unburnt
  if (
    normalizedCategory === "unburnt" ||
    normalizedCategory === "unburned"
  ) {
    return {
      color: "#15803d",
      weight: 2,
      fillColor: "#22c55e",
      fillOpacity: 0.25
    };
  }

  // Partially burnt
  if (
    normalizedCategory === "partially_burnt" ||
    normalizedCategory === "partially burnt" ||
    normalizedCategory === "partial_burnt" ||
    normalizedCategory === "partial burnt"
  ) {
    return {
      color: "#c2410c",
      weight: 2,
      fillColor: "#f97316",
      fillOpacity: 0.30
    };
  }

  // Completely burnt
  if (
    normalizedCategory === "completely_burnt" ||
    normalizedCategory === "completely burnt" ||
    normalizedCategory === "burnt" ||
    normalizedCategory === "burned"
  ) {
    return {
      color: "#b91c1c",
      weight: 2,
      fillColor: "#ef4444",
      fillOpacity: 0.30
    };
  }

  // Unknown
  return {
    color: "#6b7280",
    weight: 2,
    fillColor: "#9ca3af",
    fillOpacity: 0.20
  };
};


// =====================================================
// FIELD INTELLIGENCE HELPERS
// =====================================================

const getIndicators = (feature) => {
  return (
    feature?.properties?.field_indicators ||
    feature?.properties?.indicators ||
    {}
  );
};


const getFieldId = (feature, index) => {
  const rawFieldId =
    feature?.properties?.field_id;

  // IMPORTANT:
  // IDs such as 2020_34 and 2021_34
  // must remain strings.

  if (
    rawFieldId !== null &&
    rawFieldId !== undefined &&
    String(rawFieldId).trim() !== ""
  ) {
    return String(rawFieldId).trim();
  }

  return `field-${index + 1}`;
};


const getCategory = (feature) => {
  const indicators =
    getIndicators(feature);

  return (
    feature?.properties?.category ||
    feature?.properties?.field_category ||
    indicators?.category ||
    "Unknown"
  );
};


const getFieldStatus = (feature) => {
  const indicators =
    getIndicators(feature);

  return (
    feature?.properties?.field_status ||
    indicators?.field_status ||
    "Unknown"
  );
};


const getCandidateDate = (feature) => {
  const indicators =
    getIndicators(feature);

  return (
    feature?.properties?.candidate_date ||
    indicators?.candidate_date ||
    null
  );
};


const getNdviTrend = (feature) => {
  const indicators =
    getIndicators(feature);

  return (
    feature?.properties?.ndvi_trend ||
    indicators?.ndvi_trend ||
    null
  );
};


const getNbrTrend = (feature) => {
  const indicators =
    getIndicators(feature);

  return (
    feature?.properties?.nbr_trend ||
    indicators?.nbr_trend ||
    null
  );
};


const isTransitionCandidate = (feature) => {
  const status =
    String(getFieldStatus(feature))
      .toLowerCase()
      .trim();

  const candidateDate =
    getCandidateDate(feature);

  return (
    Boolean(candidateDate) ||
    status === "crop_transition_candidate" ||
    status.includes("crop-transition") ||
    status.includes("transition candidate")
  );
};


// =====================================================
// TRANSITION MAP STYLE
// =====================================================

const getTransitionStyle = (
  baseStyle,
  feature
) => {
  if (!isTransitionCandidate(feature)) {
    return baseStyle;
  }

  return {
    ...baseStyle,

    // Yellow dashed border represents
    // crop-transition candidate signal.
    color: "#eab308",

    weight: 3,

    dashArray: "7 5",

    fillOpacity:
      Math.min(
        0.42,
        (baseStyle.fillOpacity || 0.25) + 0.08
      )
  };
};


// =====================================================
// MAP SIZE FIX
// =====================================================

function MapSizeFix() {
  const map = useMap();

  useEffect(() => {
    const invalidateMap = () => {
      map.invalidateSize({
        animate: false,
        pan: false
      });
    };

    // Initial fix
    invalidateMap();

    // Fix after layout settles
    const timers = [
      setTimeout(invalidateMap, 100),
      setTimeout(invalidateMap, 500),
      setTimeout(invalidateMap, 1000)
    ];

    window.addEventListener(
      "resize",
      invalidateMap
    );

    return () => {
      timers.forEach(clearTimeout);

      window.removeEventListener(
        "resize",
        invalidateMap
      );
    };
  }, [map]);

  return null;
}


// =====================================================
// FIT MAP TO ALL FIELDS
// =====================================================

function FitBounds({
  geojson
}) {
  const map = useMap();

  useEffect(() => {
    if (
      !geojson ||
      !geojson.features ||
      geojson.features.length === 0
    ) {
      return;
    }

    try {
      const layer =
        L.geoJSON(geojson);

      const bounds =
        layer.getBounds();

      if (bounds.isValid()) {
        map.fitBounds(
          bounds,
          {
            padding: [30, 30],
            maxZoom: 13,
            animate: true
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


// =====================================================
// CUSTOM MAP CONTROLS
// =====================================================

function MapControls({
  geojson
}) {
  const map = useMap();

  useEffect(() => {
    const control =
      L.control({
        position: "topright"
      });

    control.onAdd = () => {
      const container =
        L.DomUtil.create(
          "div",
          "parali-map-controls"
        );

      container.style.display =
        "flex";

      container.style.flexDirection =
        "column";

      container.style.gap =
        "6px";


      // -------------------------------------------------
      // BUTTON CREATOR
      // -------------------------------------------------

      const createButton = (
        label,
        title,
        callback
      ) => {
        const button =
          L.DomUtil.create(
            "button",
            "parali-map-control-button",
            container
          );

        button.type = "button";

        button.innerHTML =
          label;

        button.title =
          title;

        button.setAttribute(
          "aria-label",
          title
        );

        button.style.width =
          "38px";

        button.style.height =
          "38px";

        button.style.border =
          "1px solid #d1d5db";

        button.style.borderRadius =
          "8px";

        button.style.background =
          "#ffffff";

        button.style.color =
          "#111827";

        button.style.fontSize =
          "20px";

        button.style.fontWeight =
          "700";

        button.style.lineHeight =
          "1";

        button.style.cursor =
          "pointer";

        button.style.display =
          "flex";

        button.style.alignItems =
          "center";

        button.style.justifyContent =
          "center";

        button.style.boxShadow =
          "0 2px 8px rgba(0,0,0,0.18)";


        // Prevent map dragging/zooming
        // when interacting with controls.
        L.DomEvent.disableClickPropagation(
          button
        );

        L.DomEvent.on(
          button,
          "mousedown",
          L.DomEvent.stopPropagation
        );

        L.DomEvent.on(
          button,
          "click",
          (event) => {
            L.DomEvent.stop(event);
            callback();
          }
        );

        return button;
      };


      // -------------------------------------------------
      // ZOOM IN
      // -------------------------------------------------

      createButton(
        "+",
        "Zoom in",
        () => {
          map.zoomIn();
        }
      );


      // -------------------------------------------------
      // ZOOM OUT
      // -------------------------------------------------

      createButton(
        "−",
        "Zoom out",
        () => {
          map.zoomOut();
        }
      );


      // -------------------------------------------------
      // HOME / RESET
      // -------------------------------------------------

      createButton(
        "⌂",
        "Reset map to all fields",
        () => {
          if (
            geojson &&
            geojson.features &&
            geojson.features.length > 0
          ) {
            const bounds =
              L.geoJSON(
                geojson
              ).getBounds();

            if (bounds.isValid()) {
              map.fitBounds(
                bounds,
                {
                  padding: [30, 30],
                  maxZoom: 13,
                  animate: true
                }
              );

              return;
            }
          }

          map.setView(
            [30.0, 75.0],
            10,
            {
              animate: true
            }
          );
        }
      );


      // -------------------------------------------------
      // FULLSCREEN
      // -------------------------------------------------

      const fullscreenButton =
        createButton(
          "⛶",
          "Enter fullscreen",
          () => {
            const mapContainer =
              map.getContainer();

            if (
              document.fullscreenElement
            ) {
              if (
                document.exitFullscreen
              ) {
                document.exitFullscreen();
              }

              return;
            }

            if (
              mapContainer.requestFullscreen
            ) {
              mapContainer.requestFullscreen();
            }
          }
        );


      // -------------------------------------------------
      // FULLSCREEN STATE
      // -------------------------------------------------

      const handleFullscreenChange =
        () => {
          if (
            document.fullscreenElement
          ) {
            fullscreenButton.title =
              "Exit fullscreen";

            fullscreenButton.setAttribute(
              "aria-label",
              "Exit fullscreen"
            );
          } else {
            fullscreenButton.title =
              "Enter fullscreen";

            fullscreenButton.setAttribute(
              "aria-label",
              "Enter fullscreen"
            );
          }

          setTimeout(() => {
            map.invalidateSize();
          }, 200);
        };


      document.addEventListener(
        "fullscreenchange",
        handleFullscreenChange
      );


      container._fullscreenHandler =
        handleFullscreenChange;

      return container;
    };


    control.addTo(map);


    return () => {
      const container =
        control.getContainer();

      if (
        container?._fullscreenHandler
      ) {
        document.removeEventListener(
          "fullscreenchange",
          container._fullscreenHandler
        );
      }

      map.removeControl(
        control
      );
    };
  }, [map, geojson]);

  return null;
}


// =====================================================
// ZOOM SLIDER
// =====================================================

function ZoomSlider() {
  const map = useMap();

  useEffect(() => {
    const MIN_ZOOM = 8;
    const MAX_ZOOM = 18;

    const ZoomSliderControl =
      L.Control.extend({
        options: {
          position: "bottomright"
        },

        onAdd() {
          const container =
            L.DomUtil.create(
              "div",
              "parali-zoom-slider"
            );

          container.style.background =
            "#ffffff";

          container.style.padding =
            "8px 7px";

          container.style.border =
            "1px solid #d1d5db";

          container.style.borderRadius =
            "8px";

          container.style.boxShadow =
            "0 2px 8px rgba(0,0,0,0.18)";


          // Slider
          const slider =
            L.DomUtil.create(
              "input",
              "",
              container
            );

          slider.type =
            "range";

          slider.min =
            String(MIN_ZOOM);

          slider.max =
            String(MAX_ZOOM);

          slider.step =
            "0.5";

          slider.value =
            String(map.getZoom());

          slider.title =
            "Map zoom level";

          slider.setAttribute(
            "aria-label",
            "Map zoom level"
          );

          slider.style.width =
            "105px";

          slider.style.cursor =
            "pointer";


          // Zoom label
          const zoomLabel =
            L.DomUtil.create(
              "div",
              "",
              container
            );

          zoomLabel.style.textAlign =
            "center";

          zoomLabel.style.fontSize =
            "11px";

          zoomLabel.style.fontWeight =
            "600";

          zoomLabel.style.color =
            "#4b5563";

          zoomLabel.style.marginTop =
            "3px";


          const updateLabel =
            () => {
              const zoom =
                map.getZoom();

              slider.value =
                String(zoom);

              zoomLabel.textContent =
                `Zoom ${zoom.toFixed(1)}`;
            };


          updateLabel();


          L.DomEvent.disableClickPropagation(
            container
          );


          L.DomEvent.on(
            slider,
            "input",
            (event) => {
              const zoom =
                Number(
                  event.target.value
                );

              map.setZoom(
                zoom,
                {
                  animate: false
                }
              );
            }
          );


          map.on(
            "zoomend",
            updateLabel
          );


          container._cleanup =
            () => {
              map.off(
                "zoomend",
                updateLabel
              );
            };


          return container;
        },


        onRemove() {
          const container =
            this.getContainer();

          if (
            container?._cleanup
          ) {
            container._cleanup();
          }
        }
      });


    const control =
      new ZoomSliderControl();

    map.addControl(control);


    return () => {
      map.removeControl(
        control
      );
    };
  }, [map]);

  return null;
}


// =====================================================
// MAP SCALE
// =====================================================

function MapScale() {
  const map = useMap();

  useEffect(() => {
    const scale =
      L.control.scale({
        position: "bottomleft",
        imperial: false,
        metric: true,
        maxWidth: 120
      });

    scale.addTo(map);

    return () => {
      map.removeControl(
        scale
      );
    };
  }, [map]);

  return null;
}


// =====================================================
// FIELD MARKERS
// =====================================================

function FieldMarkers({
  geojson,
  onFieldSelect
}) {
  const markers =
    useMemo(() => {
      if (
        !geojson ||
        !geojson.features
      ) {
        return [];
      }

      const result = [];

      geojson.features.forEach(
        (feature, index) => {
          try {
            const layer =
              L.geoJSON(feature);

            const bounds =
              layer.getBounds();

            if (
              !bounds.isValid()
            ) {
              return;
            }

            const center =
              bounds.getCenter();

            const fieldId =
              getFieldId(
                feature,
                index
              );

            const category =
              getCategory(
                feature
              );

            const transition =
              isTransitionCandidate(
                feature
              );

            result.push({
              fieldId,
              center,
              category,
              transition
            });
          } catch (error) {
            console.error(
              "Failed to create field marker:",
              error
            );
          }
        }
      );

      return result;
    }, [geojson]);


  return (
    <>
      {markers.map(
        (marker) => {
          const categoryStyle =
            getCategoryStyle(
              marker.category
            );

          const markerBorder =
            marker.transition
              ? "#eab308"
              : "white";


          const icon =
            L.divIcon({
              className:
                "field-number-marker",

              html: `
                <div
                  style="
                    width: 28px;
                    height: 28px;
                    border-radius: 50%;
                    background: ${categoryStyle.fillColor};
                    color: white;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 10px;
                    font-weight: 700;
                    border: 3px solid ${markerBorder};
                    box-shadow: 0 2px 6px rgba(0,0,0,0.35);
                    white-space: nowrap;
                  "
                >
                  ${marker.fieldId}
                </div>
              `,

              iconSize: [
                28,
                28
              ],

              iconAnchor: [
                14,
                14
              ]
            });


          return (
            <Marker
              key={`marker-${marker.fieldId}`}
              position={
                marker.center
              }
              icon={icon}
              eventHandlers={{
                click: (
                  event
                ) => {
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
                    marker.fieldId
                  );
                }
              }}
            />
          );
        }
      )}
    </>
  );
}


// =====================================================
// FIELD MAP
// =====================================================

function FieldMap({
  geojson,
  onFieldSelect
}) {
  if (
    !geojson ||
    !geojson.features
  ) {
    return (
      <div className="map-loading">
        Loading field map...
      </div>
    );
  }


  // ===================================================
  // FIELD INTERACTION
  // ===================================================

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

    const category =
      getCategory(
        feature
      );

    const fieldStatus =
      getFieldStatus(
        feature
      );

    const candidateDate =
      getCandidateDate(
        feature
      );

    const ndviTrend =
      getNdviTrend(
        feature
      );

    const nbrTrend =
      getNbrTrend(
        feature
      );

    const transition =
      isTransitionCandidate(
        feature
      );

    const baseStyle =
      getCategoryStyle(
        category
      );

    const mapStyle =
      getTransitionStyle(
        baseStyle,
        feature
      );


    // Initial polygon style
    layer.setStyle(
      mapStyle
    );


    // =================================================
    // POPUP
    // =================================================

    layer.bindPopup(`
      <div style="
        min-width: 220px;
        line-height: 1.55;
      ">

        <div style="
          font-size: 16px;
          font-weight: 700;
          margin-bottom: 6px;
        ">
          Field ${fieldId}
        </div>

        <div>
          Category:
          <strong>
            ${category}
          </strong>
        </div>

        <div>
          Field status:
          <strong>
            ${fieldStatus}
          </strong>
        </div>

        <div>
          NDVI trend:
          <strong>
            ${ndviTrend || "N/A"}
          </strong>
        </div>

        <div>
          NBR trend:
          <strong>
            ${nbrTrend || "N/A"}
          </strong>
        </div>

        <div>
          Candidate transition:
          <strong>
            ${candidateDate || "Not detected"}
          </strong>
        </div>

        ${
          transition
            ? `
              <div style="
                margin-top: 8px;
                padding: 6px 8px;
                border-radius: 6px;
                background: #fef3c7;
                color: #92400e;
                font-weight: 600;
              ">
                🟡 Crop-transition candidate
              </div>
            `
            : ""
        }

        <div style="
          margin-top: 8px;
          color: #6b7280;
          font-size: 12px;
        ">
          Click field to open satellite analysis.
        </div>

      </div>
    `);


    // =================================================
    // MOUSE EVENTS
    // =================================================

    layer.on({

      mouseover: (event) => {
        event.target.setStyle({
          color: "#111827",
          weight: 4,
          fillColor:
            baseStyle.fillColor,
          fillOpacity: 0.55
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

        if (
          bounds.isValid()
        ) {
          map.fitBounds(
            bounds,
            {
              padding: [
                50,
                50
              ],

              maxZoom: 17,

              animate: true
            }
          );
        }

        event.target.openPopup();

        onFieldSelect(
          fieldId
        );
      }

    });
  };


  // ===================================================
  // MAP
  // ===================================================

  return (
    <MapContainer
      center={[
        30.0,
        75.0
      ]}

      zoom={10}

      minZoom={8}

      maxZoom={18}

      // We use our own controls
      zoomControl={false}

      // Mouse wheel
      scrollWheelZoom={true}

      // Double click
      doubleClickZoom={true}

      // Mouse dragging
      dragging={true}

      // Touch pinch
      touchZoom={true}

      // Shift + drag
      boxZoom={true}

      // Keyboard arrows / +/- keys
      keyboard={true}

      // Smoother zoom
      zoomSnap={0.5}

      zoomDelta={1}

      wheelPxPerZoomLevel={100}

      zoomAnimation={true}

      markerZoomAnimation={true}

      className="field-map"
    >

      {/* ==============================================
          BASE MAP
      ============================================== */}

      <TileLayer
        attribution="&copy; OpenStreetMap contributors"
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />


      {/* ==============================================
          FIELD POLYGONS
      ============================================== */}

      <GeoJSON
        data={geojson}
        onEachFeature={
          onEachField
        }
      />


      {/* ==============================================
          FIELD NUMBER MARKERS
      ============================================== */}

      <FieldMarkers
        geojson={geojson}
        onFieldSelect={
          onFieldSelect
        }
      />


      {/* ==============================================
          MAP UTILITIES
      ============================================== */}

      <MapSizeFix />

      <FitBounds
        geojson={geojson}
      />

      <MapControls
        geojson={geojson}
      />

      <ZoomSlider />

      <MapScale />

    </MapContainer>
  );
}


export default FieldMap;