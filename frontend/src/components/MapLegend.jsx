import {
  Circle,
  Flame,
  Sprout,
  Wheat
} from "lucide-react";

function MapLegend() {
  return (
    <div className="map-intelligence-legend">
      <div className="map-legend-title">
        <Wheat size={15} />
        <span>Field Status</span>
      </div>

      <div className="map-legend-items">
        <div className="map-legend-item">
          <span className="map-legend-swatch map-legend-unburnt" />
          <span>Unburnt</span>
        </div>

        <div className="map-legend-item">
          <span className="map-legend-swatch map-legend-partial" />
          <span>Partially Burnt</span>
        </div>

        <div className="map-legend-item">
          <span className="map-legend-swatch map-legend-complete" />
          <span>Completely Burnt</span>
        </div>

        <div className="map-legend-item">
          <span className="map-legend-swatch map-legend-unknown" />
          <span>Unknown</span>
        </div>
      </div>

      <div className="map-legend-divider" />

      <div className="map-signal-title">
        <Circle size={14} />
        <span>Intelligence Signal</span>
      </div>

      <div className="map-signal-item">
        <span className="map-transition-border" />
        <div>
          <strong>Transition candidate</strong>
          <span>
            Yellow border indicates an NDVI-based
            crop-transition signal.
          </span>
        </div>
      </div>

      <div className="map-legend-note">
        <Flame size={13} />
        <span>
          Colors represent dataset field categories.
          They are not real-time fire detections.
        </span>
      </div>

      <div className="map-legend-note map-legend-note-green">
        <Sprout size={13} />
        <span>
          Candidate transition dates are not validated
          harvest dates.
        </span>
      </div>
    </div>
  );
}

export default MapLegend;
