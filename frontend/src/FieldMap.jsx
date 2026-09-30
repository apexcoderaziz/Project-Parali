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


// =========================================================
// FIT MAP TO ALL FIELDS
// =========================================================

function FitBounds({ geojson }) {
  const map = useMap();

  useEffect(() => {
    if (!geojson?.features?.length) {
      return;
    }

    const layer = new L.GeoJSON(geojson);
    const bounds = layer.getBounds();

    if (bounds.isValid()) {
      map.fitBounds(bounds, {
        padding: [30, 30]
      });
    }
  }, [geojson, map]);

  return null;
}


// =========================================================
// FIELD MARKERS
// =========================================================

function FieldMarkers({
  geojson,
  onFieldSelect
}) {

  const markers = useMemo(() => {

    if (!geojson?.features?.length) {
      return [];
    }

    const result = [];

    geojson.features.forEach(
      (feature, index) => {

        const properties =
          feature?.properties || {};

        const fieldId =
          properties.field_id ??
          properties.id ??
          properties.ID ??
          properties.Id ??
          index + 1;

        try {

          const layer =
            new L.GeoJSON(feature);

          const bounds =
            layer.getBounds();

          if (!bounds.isValid()) {
            return;
          }

          const center =
            bounds.getCenter();

          result.push({
            fieldId,
            position: [
              center.lat,
              center.lng
            ]
          });

        } catch (error) {

          console.error(
            `Unable to calculate center for field ${fieldId}:`,
            error
          );

        }
      }
    );

    return result;

  }, [geojson]);


  return (
    <>
      {markers.map((marker) => (

        <Marker
          key={`field-marker-${marker.fieldId}`}
          position={marker.position}

          icon={L.divIcon({
            className: "",
            html: `
              <div
                style="
                  background:#166534;
                  color:white;
                  border:2px solid white;
                  border-radius:50%;
                  width:28px;
                  height:28px;
                  display:flex;
                  align-items:center;
                  justify-content:center;
                  font-size:11px;
                  font-weight:bold;
                  box-shadow:0 2px 5px rgba(0,0,0,0.4);
                  cursor:pointer;
                "
              >
                ${marker.fieldId}
              </div>
            `,
            iconSize: [28, 28],
            iconAnchor: [14, 14]
          })}

          eventHandlers={{
            click: (event) => {

              const map =
                event.target._map;

              map.setView(
                marker.position,
                17
              );

              onFieldSelect(
                marker.fieldId
              );

            }
          }}
        />

      ))}
    </>
  );
}


// =========================================================
// MAIN FIELD MAP
// =========================================================

function FieldMap({
  geojson,
  onFieldSelect
}) {


  // =======================================================
  // FIELD STYLE
  // =======================================================

  const fieldStyle = () => ({
    color: "#166534",
    weight: 3,
    opacity: 1,
    fillColor: "#22c55e",
    fillOpacity: 0.08
  });


  // =======================================================
  // GET FIELD ID
  // =======================================================

  const getFieldId = (
    feature,
    index = 0
  ) => {

    const properties =
      feature?.properties || {};

    return (
      properties.field_id ??
      properties.id ??
      properties.ID ??
      properties.Id ??
      index + 1
    );
  };


  // =======================================================
  // GET FIELD CATEGORY
  // =======================================================

  const getCategory = (feature) => {

    const properties =
      feature?.properties || {};

    return (
      properties.field_category ??
      properties.category ??
      properties.burn_category ??
      "Unknown"
    );
  };


  // =======================================================
  // FIELD EVENTS
  // =======================================================

  const onEachField = (
    feature,
    layer
  ) => {

    const fieldId =
      getFieldId(feature);

    const category =
      getCategory(feature);


    // -----------------------------------------------------
    // Popup
    // -----------------------------------------------------

    layer.bindPopup(`
      <div
        style="
          min-width:190px;
          font-family:Arial,sans-serif;
        "
      >

        <h3
          style="
            margin:0 0 8px;
            color:#166534;
          "
        >
          🌾 Field ${fieldId}
        </h3>

        <p
          style="
            margin:5px 0;
          "
        >
          <strong>Category:</strong>
          ${category}
        </p>

        <p
          style="
            margin:10px 0 0;
            color:#555;
          "
        >
          Satellite analysis selected.
        </p>

      </div>
    `);


    // -----------------------------------------------------
    // Mouse Over
    // -----------------------------------------------------

    layer.on(
      "mouseover",
      (event) => {

        event.target.setStyle({
          weight: 5,
          color: "#f59e0b",
          fillColor: "#fbbf24",
          fillOpacity: 0.35
        });

        event.target.bringToFront();
      }
    );


    // -----------------------------------------------------
    // Mouse Out
    // -----------------------------------------------------

    layer.on(
      "mouseout",
      (event) => {

        event.target.setStyle(
          fieldStyle()
        );
      }
    );


    // -----------------------------------------------------
    // Field Click
    // -----------------------------------------------------

    layer.on(
      "click",
      (event) => {

        const map =
          event.target._map;

        const bounds =
          event.target.getBounds();


        // Zoom to field
        if (bounds.isValid()) {

          map.fitBounds(
            bounds,
            {
              padding: [60, 60],
              maxZoom: 17
            }
          );

        }


        // Open popup
        event.target.openPopup();


        // Send field ID to App.jsx
        console.log(
          "Field clicked:",
          fieldId
        );

        onFieldSelect(
          fieldId
        );

      }
    );
  };


  // =======================================================
  // RENDER
  // =======================================================

  return (
    <div
      style={{
        width: "100%",
        height: "500px",
        borderRadius: "12px",
        overflow: "hidden"
      }}
    >

      <MapContainer
        center={[
          30.2,
          75.8
        ]}
        zoom={11}
        scrollWheelZoom={true}
        style={{
          width: "100%",
          height: "100%"
        }}
      >

        {/* OpenStreetMap */}

        <TileLayer
          attribution="&copy; OpenStreetMap contributors"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />


        {/* Fit map to all fields */}

        <FitBounds
          geojson={geojson}
        />


        {/* Field polygons */}

        {geojson && (
          <GeoJSON
            data={geojson}
            style={fieldStyle}
            onEachFeature={onEachField}
          />
        )}


        {/* Field ID markers */}

        {geojson && (
          <FieldMarkers
            geojson={geojson}
            onFieldSelect={onFieldSelect}
          />
        )}

      </MapContainer>

    </div>
  );
}


export default FieldMap;