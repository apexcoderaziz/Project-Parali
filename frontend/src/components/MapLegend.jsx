import {
  Circle,
  Flame,
  Sprout,
  Wheat
} from "lucide-react";

function MapLegend() {
  return (
    <div className="map-intelligence-legend">
      <div className="legend-heading">
        <div className="legend-heading-icon">
          <Wheat size={14} />
        </div>
        <div>
          <span>FIELD LAYER</span>
          <strong>Classification</strong>
        </div>
      </div>

      <div className="map-legend-items">
        <div className="map-legend-item">
          <span className="map-legend-swatch map-legend-unburnt" />
          <span>Unburnt</span>
        </div>

        <div className="map-legend-item">
          <span className="map-legend-swatch map-legend-partial" />
          <span>Partially burnt</span>
        </div>

        <div className="map-legend-item">
          <span className="map-legend-swatch map-legend-complete" />
          <span>Completely burnt</span>
        </div>

        <div className="map-legend-item">
          <span className="map-legend-swatch map-legend-unknown" />
          <span>Other / unknown</span>
        </div>
      </div>

      <div className="map-legend-divider" />

      <div className="legend-heading compact">
        <div className="legend-heading-icon signal">
          <Circle size={13} />
        </div>
        <div>
          <span>SIGNAL</span>
          <strong>Transition candidate</strong>
        </div>
      </div>

      <div className="map-signal-item">
        <span className="map-transition-border" />
        <p>
          Yellow outline marks an NDVI-based crop-transition signal.
        </p>
      </div>

      <div className="map-legend-note">
        <Flame size={12} />
        <span>
          Map colors reflect dataset categories, not live fire detections.
        </span>
      </div>

      <div className="map-legend-note map-legend-note-green">
        <Sprout size={12} />
        <span>
          Candidate dates are monitoring indicators, not confirmed harvest dates.
        </span>
      </div>
    </div>
  );
}

export default MapLegend;
