import {
  CalendarDays,
  ChevronDown,
  ChevronUp,
  Map,
  Package,
  Ruler,
  TrendingUp,
  Target,
  Satellite,
  Sprout,
  TrendingDown,
  Truck,
  X
} from "lucide-react";
import { useState } from "react";

function FieldDrawer({
  fieldData,
  residueEstimate = null,
  residueLoading = false,
  residueError = "",
  biomassOpportunity = null,
  biomassOpportunityLoading = false,
  biomassOpportunityError = "",
  logisticsEstimate = null,
  logisticsLoading = false,
  logisticsError = "",
  clusterEstimate = null,
  clusterLoading = false,
  clusterError = "",
  open = false,
  loading = false,
  error = "",
  onClose,
  onAnalyze
}) {
  const [showTimeline, setShowTimeline] = useState(true);

  if (!open) {
    return null;
  }

  const indicators = fieldData?.field_indicators || null;
  const transition = fieldData?.transition_analysis || null;
  const harvestPrediction = fieldData?.harvest_prediction || null;
  const timeSeries = fieldData?.time_series || [];
  const category = fieldData?.field_category || "Unknown";

  const formatValue = (value, digits = 4) => {
    if (value === null || value === undefined || value === "") {
      return "N/A";
    }

    const number = Number(value);

    return Number.isFinite(number)
      ? number.toFixed(digits)
      : String(value);
  };

  const formatLabel = (value) => {
    if (!value) return "Unknown";

    return String(value)
      .replace(/_/g, " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase());
  };

  const latest = fieldData?.latest_observation || {};
  const cluster = clusterEstimate?.collection_cluster || null;
  const aggregation = clusterEstimate?.aggregation_effect || null;

  return (
    <>
      <div
        className="field-drawer-backdrop"
        onClick={onClose}
      />

      <aside
        className="field-drawer"
        aria-label="Field intelligence"
      >
        <div className="field-drawer-header">
          <div>
            <div className="field-drawer-eyebrow">
              FIELD INTELLIGENCE
            </div>

            <h2>
              {fieldData?.field_id
                ? `Field ${fieldData.field_id}`
                : "Field Analysis"}
            </h2>
          </div>

          <button
            type="button"
            className="field-drawer-close"
            onClick={onClose}
            aria-label="Close field analysis"
          >
            <X size={20} />
          </button>
        </div>

        <div className="field-drawer-content">

          {loading && (
            <div className="field-drawer-state">
              <div className="field-drawer-spinner"></div>

              <strong>
                Analyzing satellite data
              </strong>

              <p>
                Loading field indicators and Sentinel-2
                observations...
              </p>
            </div>
          )}

          {!loading && error && (
            <div className="field-drawer-error">
              <strong>
                Field analysis failed
              </strong>

              <p>{error}</p>

              {onAnalyze && (
                <button
                  type="button"
                  onClick={onAnalyze}
                >
                  Try again
                </button>
              )}
            </div>
          )}

          {!loading && !error && fieldData && (
            <>
              <div className="field-status-card">
                <div className="field-status-icon">
                  <Satellite size={20} />
                </div>

                <div>
                  <span>Field category</span>

                  <strong>
                    {formatLabel(category)}
                  </strong>
                </div>
              </div>

              {harvestPrediction && (
                <section className="field-drawer-section harvest-drawer-section">

                  <div className="field-drawer-section-title">
                    <Target size={17} />

                    <h3>
                      Harvest Signal Assessment
                    </h3>
                  </div>

                  <div className="harvest-drawer-hero">
                    <div>
                      <span>Current satellite signal</span>

                      <strong>
                        {harvestPrediction.status_label ||
                          "Assessment available"}
                      </strong>
                    </div>

                    <div className={`harvest-level harvest-level-${String(
                      harvestPrediction.signal_level || "unknown"
                    ).toLowerCase()}`}>
                      {harvestPrediction.signal_level || "Unknown"}
                    </div>
                  </div>

                  <div className="harvest-drawer-horizons">
                    <div>
                      <span>NDVI decline</span>
                      <strong>
                        {harvestPrediction.signals
                          ?.ndvi_decline_from_peak ?? "N/A"}
                      </strong>
                    </div>

                    <div>
                      <span>NBR decline</span>
                      <strong>
                        {harvestPrediction.signals
                          ?.nbr_decline_from_peak ?? "N/A"}
                      </strong>
                    </div>
                  </div>

                  {harvestPrediction.signals?.candidate_date && (
                    <div className="harvest-drawer-window">
                      <TrendingUp size={16} />

                      <div>
                        <span>Historical transition candidate</span>
                        <strong>
                          {harvestPrediction.signals.candidate_date}
                        </strong>
                      </div>
                    </div>
                  )}

                  <div className="harvest-drawer-reasons">
                    {(harvestPrediction.reasons || []).map(
                      (reason) => (
                        <div key={reason}>
                          <span>✓</span>
                          {reason}
                        </div>
                      )
                    )}
                  </div>

                  <p className="harvest-drawer-note">
                    This is a Sentinel-2 crop-transition signal assessment,
                    not a calibrated harvest probability or confirmed
                    harvest date.
                  </p>

                </section>
              )}

              <section className="field-drawer-section residue-drawer-section">

                <div className="field-drawer-section-title">
                  <Package size={17} />

                  <h3>
                    Crop Residue Intelligence
                  </h3>
                </div>

                {residueLoading && (
                  <div className="transition-drawer-card">
                    <strong>Estimating residue...</strong>
                    <p>
                      Calculating biomass from field area and the
                      configured agronomic assumptions.
                    </p>
                  </div>
                )}

                {!residueLoading && residueError && (
                  <div className="transition-drawer-card">
                    <strong>Residue estimate unavailable</strong>
                    <p>{residueError}</p>
                  </div>
                )}

                {!residueLoading && !residueError && residueEstimate && (
                  <>
                    <div className="field-drawer-grid">
                      <div className="field-drawer-stat">
                        <Package size={16} />
                        <span>Gross residue</span>
                        <strong>
                          {residueEstimate.gross_residue_tonnes != null
                            ? `${residueEstimate.gross_residue_tonnes} t`
                            : "N/A"}
                        </strong>
                      </div>

                      <div className="field-drawer-stat">
                        <Package size={16} />
                        <span>Recoverable biomass</span>
                        <strong>
                          {residueEstimate.recoverable_biomass_tonnes != null
                            ? `${residueEstimate.recoverable_biomass_tonnes} t`
                            : "N/A"}
                        </strong>
                      </div>

                      <div className="field-drawer-stat">
                        <Ruler size={16} />
                        <span>Collection potential</span>
                        <strong>
                          {residueEstimate.collection_potential_percent != null
                            ? `${residueEstimate.collection_potential_percent}%`
                            : "N/A"}
                        </strong>
                      </div>

                      <div className="field-drawer-stat">
                        <Sprout size={16} />
                        <span>Crop assumption</span>
                        <strong>
                          {formatLabel(residueEstimate.crop)}
                        </strong>
                      </div>
                    </div>

                    <div className="transition-drawer-card">
                      <div className="transition-drawer-row">
                        <span>Yield assumption</span>
                        <strong>
                          {residueEstimate.assumptions
                            ?.yield_tonnes_per_hectare ?? "N/A"} t/ha
                        </strong>
                      </div>

                      <div className="transition-drawer-row">
                        <span>Residue-to-product ratio</span>
                        <strong>
                          {residueEstimate.assumptions
                            ?.residue_to_product_ratio ?? "N/A"}
                        </strong>
                      </div>

                      <div className="transition-drawer-row">
                        <span>Collection efficiency</span>
                        <strong>
                          {residueEstimate.assumptions
                            ?.collection_efficiency != null
                            ? `${Math.round(
                                residueEstimate.assumptions
                                  .collection_efficiency * 100
                              )}%`
                            : "N/A"}
                        </strong>
                      </div>

                      <p>
                        These tonnes are assumption-based estimates.
                        Satellite imagery provides field area and
                        crop-transition context; it does not directly
                        measure residue mass.
                      </p>
                    </div>
                  </>
                )}

              </section>

              {/* =====================================================
                  BIOMASS OPPORTUNITY
              ===================================================== */}

              <section className="field-drawer-section">

                <div className="field-drawer-section-title">
                  <Map size={17} />
                  <h3>Biomass Opportunity</h3>
                </div>

                {biomassOpportunityLoading && (
                  <div className="transition-drawer-card">
                    <strong>Finding nearby biomass facilities...</strong>
                    <p>
                      Screening recoverable biomass against the current
                      facility registry.
                    </p>
                  </div>
                )}

                {!biomassOpportunityLoading && biomassOpportunityError && (
                  <div className="transition-drawer-card">
                    <strong>Opportunity analysis unavailable</strong>
                    <p>{biomassOpportunityError}</p>
                  </div>
                )}

                {!biomassOpportunityLoading &&
                  !biomassOpportunityError &&
                  biomassOpportunity && (
                    <>
                      <div className="field-drawer-grid">

                        <div className="field-drawer-stat">
                          <Package size={16} />
                          <span>Recoverable biomass</span>
                          <strong>
                            {biomassOpportunity.recoverable_biomass_tonnes != null
                              ? `${biomassOpportunity.recoverable_biomass_tonnes} t`
                              : "N/A"}
                          </strong>
                        </div>

                        <div className="field-drawer-stat">
                          <Map size={16} />
                          <span>Facilities found</span>
                          <strong>
                            {biomassOpportunity.facilities?.length ?? 0}
                          </strong>
                        </div>

                      </div>

                      {biomassOpportunity.nearest_facility ? (
                        <div className="transition-drawer-card">

                          <div className="transition-drawer-row">
                            <span>Nearest facility</span>
                            <strong>
                              {biomassOpportunity.nearest_facility.name || "N/A"}
                            </strong>
                          </div>

                          <div className="transition-drawer-row">
                            <span>Type</span>
                            <strong>
                              {biomassOpportunity.nearest_facility.type || "N/A"}
                            </strong>
                          </div>

                          <div className="transition-drawer-row">
                            <span>Distance</span>
                            <strong>
                              {biomassOpportunity.nearest_facility.distance_km != null
                                ? `${biomassOpportunity.nearest_facility.distance_km} km`
                                : "N/A"}
                            </strong>
                          </div>

                          <div className="transition-drawer-status">
                            {formatLabel(
                              biomassOpportunity.nearest_facility.opportunity_status
                            )}
                          </div>

                          <p>
                            Distance is a straight-line Haversine screening
                            estimate from the field centroid.
                          </p>

                        </div>
                      ) : (
                        <div className="transition-drawer-card">
                          <strong>No registered facility found.</strong>
                          <p>
                            The current facility registry may need to be
                            expanded for this field.
                          </p>
                        </div>
                      )}
                    </>
                  )}

              </section>

              {/* =====================================================
                  COLLECTION CLUSTER
              ===================================================== */}

              <section className="field-drawer-section">

                <div className="field-drawer-section-title">
                  <Truck size={17} />

                  <h3>
                    Biomass Collection Cluster
                  </h3>
                </div>

                {clusterLoading && (
                  <div className="transition-drawer-card">
                    <strong>Finding nearby fields...</strong>
                    <p>
                      Aggregating nearby fields into a collection cluster.
                    </p>
                  </div>
                )}

                {!clusterLoading && clusterError && (
                  <div className="transition-drawer-card">
                    <strong>Cluster estimate unavailable</strong>
                    <p>{clusterError}</p>
                  </div>
                )}

                {!clusterLoading && !clusterError && cluster && (
                  <>
                    <div className="field-drawer-grid">

                      <div className="field-drawer-stat">
                        <Truck size={16} />
                        <span>Cluster biomass</span>
                        <strong>
                          {cluster.recoverable_biomass_tonnes != null
                            ? `${Number(
                                cluster.recoverable_biomass_tonnes
                              ).toFixed(2)} t`
                            : "N/A"}
                        </strong>
                      </div>

                      <div className="field-drawer-stat">
                        <Map size={16} />
                        <span>Fields aggregated</span>
                        <strong>
                          {cluster.field_count ?? "N/A"}
                        </strong>
                      </div>

                      <div className="field-drawer-stat">
                        <Truck size={16} />
                        <span>Estimated truckloads</span>
                        <strong>
                          {cluster.estimated_truckloads ?? "N/A"}
                        </strong>
                      </div>

                      <div className="field-drawer-stat">
                        <Ruler size={16} />
                        <span>Cluster radius</span>
                        <strong>
                          {cluster.radius_km != null
                            ? `${cluster.radius_km} km`
                            : "N/A"}
                        </strong>
                      </div>

                    </div>

                    {aggregation && (
                      <div className="transition-drawer-card">

                        <div className="transition-drawer-row">
                          <span>This field</span>
                          <strong>
                            {aggregation
                              .individual_field_recoverable_tonnes != null
                              ? `${Number(
                                  aggregation
                                    .individual_field_recoverable_tonnes
                                ).toFixed(2)} t`
                              : "N/A"}
                          </strong>
                        </div>

                        <div className="transition-drawer-row">
                          <span>Aggregated supply</span>
                          <strong>
                            {aggregation
                              .cluster_recoverable_tonnes != null
                              ? `${Number(
                                  aggregation.cluster_recoverable_tonnes
                                ).toFixed(2)} t`
                              : "N/A"}
                          </strong>
                        </div>

                        <div className="transition-drawer-row">
                          <span>Additional fields</span>
                          <strong>
                            {aggregation.additional_fields_aggregated ?? "N/A"}
                          </strong>
                        </div>

                        <p>
                          Nearby fields are grouped so a small individual
                          field load can be considered as part of an
                          aggregated collection opportunity.
                        </p>

                      </div>
                    )}

                    <div className="transition-drawer-card">
                      <div className="transition-drawer-row">
                        <span>Truck capacity assumption</span>
                        <strong>
                          {cluster.truck_capacity_tonnes ?? "N/A"} t
                        </strong>
                      </div>

                      <p>
                        Truckload count is a simplified planning estimate.
                        It does not confirm farmer participation, actual
                        truck availability, loading constraints, or routes.
                      </p>
                    </div>
                  </>
                )}

              </section>

              {/* =====================================================
                  LOGISTICS
              ===================================================== */}

              {logisticsEstimate && (
                <section className="field-drawer-section">

                  <div className="field-drawer-section-title">
                    <Truck size={17} />

                    <h3>
                      Biomass Logistics
                    </h3>
                  </div>

                  <div className="field-drawer-grid">

                    <div className="field-drawer-stat">
                      <Map size={16} />
                      <span>Nearest facility</span>
                      <strong>
                        {logisticsEstimate.nearest_facility?.name ||
                          "N/A"}
                      </strong>
                    </div>

                    <div className="field-drawer-stat">
                      <Ruler size={16} />
                      <span>Straight-line distance</span>
                      <strong>
                        {logisticsEstimate.straight_line_distance_km != null
                          ? `${logisticsEstimate.straight_line_distance_km} km`
                          : "N/A"}
                      </strong>
                    </div>

                    <div className="field-drawer-stat">
                      <Ruler size={16} />
                      <span>Estimated road distance</span>
                      <strong>
                        {logisticsEstimate.estimated_road_distance_km != null
                          ? `${logisticsEstimate.estimated_road_distance_km} km`
                          : "N/A"}
                      </strong>
                    </div>

                    <div className="field-drawer-stat">
                      <Package size={16} />
                      <span>Transport cost</span>
                      <strong>
                        {logisticsEstimate.estimated_transport_cost_inr != null
                          ? `₹${Number(
                              logisticsEstimate
                                .estimated_transport_cost_inr
                            ).toFixed(0)}`
                          : "N/A"}
                      </strong>
                    </div>

                  </div>

                  <div className="transition-drawer-card">

                    <div className="transition-drawer-row">
                      <span>Logistics status</span>
                      <strong>
                        {formatLabel(
                          logisticsEstimate.logistics_status
                        )}
                      </strong>
                    </div>

                    <div className="transition-drawer-row">
                      <span>Cost per tonne</span>
                      <strong>
                        {logisticsEstimate.cost_per_tonne_inr != null
                          ? `₹${Number(
                              logisticsEstimate.cost_per_tonne_inr
                            ).toFixed(0)}/t`
                          : "N/A"}
                      </strong>
                    </div>

                    <div className="transition-drawer-row">
                      <span>Search radius</span>
                      <strong>
                        {logisticsEstimate.search_radius_km != null
                          ? `${logisticsEstimate.search_radius_km} km`
                          : "N/A"}
                      </strong>
                    </div>

                    <p>
                      {logisticsEstimate.methodology_note ||
                        "Logistics values are screening estimates."}
                    </p>

                    {(logisticsEstimate.warnings || []).map(
                      (warning) => (
                        <p
                          key={warning}
                          style={{ marginTop: "8px" }}
                        >
                          ⚠️ {warning}
                        </p>
                      )
                    )}

                  </div>

                </section>
              )}

              <div className="field-drawer-grid">

                <div className="field-drawer-stat">
                  <Ruler size={16} />
                  <span>Area</span>
                  <strong>
                    {indicators?.area_hectares != null
                      ? `${indicators.area_hectares} ha`
                      : "N/A"}
                  </strong>
                </div>

                <div className="field-drawer-stat">
                  <Map size={16} />
                  <span>Acres</span>
                  <strong>
                    {indicators?.area_acres != null
                      ? `${indicators.area_acres} ac`
                      : "N/A"}
                  </strong>
                </div>

                <div className="field-drawer-stat">
                  <TrendingDown size={16} />
                  <span>NDVI trend</span>
                  <strong>
                    {formatLabel(indicators?.ndvi_trend)}
                  </strong>
                </div>

                <div className="field-drawer-stat">
                  <TrendingDown size={16} />
                  <span>NBR trend</span>
                  <strong>
                    {formatLabel(indicators?.nbr_trend)}
                  </strong>
                </div>

              </div>

              <section className="field-drawer-section">
                <div className="field-drawer-section-title">
                  <Sprout size={17} />
                  <h3>Crop Transition</h3>
                </div>

                <div className="transition-drawer-card">

                  <div className="transition-drawer-row">
                    <span>Peak date</span>
                    <strong>
                      {transition?.peak_date || "N/A"}
                    </strong>
                  </div>

                  <div className="transition-drawer-row">
                    <span>Peak NDVI</span>
                    <strong>
                      {formatValue(transition?.peak_ndvi)}
                    </strong>
                  </div>

                  <div className="transition-drawer-row">
                    <span>Candidate date</span>
                    <strong>
                      {transition?.candidate_date || "Not detected"}
                    </strong>
                  </div>

                  <div className="transition-drawer-row">
                    <span>NDVI decline</span>
                    <strong>
                      {formatValue(transition?.decline)}
                    </strong>
                  </div>

                  <div className="transition-drawer-status">
                    {transition?.status || "No transition detected"}
                  </div>

                  <p>
                    Candidate transition dates are NDVI-based
                    signals and are not validated harvest dates.
                  </p>

                </div>
              </section>

              <section className="field-drawer-section">

                <div className="field-drawer-section-title">
                  <CalendarDays size={17} />
                  <h3>Latest Observation</h3>
                </div>

                <div className="latest-observation">

                  <div>
                    <span>Date</span>
                    <strong>{latest.date || "N/A"}</strong>
                  </div>

                  <div>
                    <span>NDVI</span>
                    <strong>{formatValue(latest.ndvi)}</strong>
                  </div>

                  <div>
                    <span>NBR</span>
                    <strong>{formatValue(latest.nbr)}</strong>
                  </div>

                </div>

              </section>

              <section className="field-drawer-section">

                <button
                  type="button"
                  className="timeline-toggle"
                  onClick={() =>
                    setShowTimeline((visible) => !visible)
                  }
                >
                  <span>Sentinel-2 Timeline</span>

                  {showTimeline ? (
                    <ChevronUp size={18} />
                  ) : (
                    <ChevronDown size={18} />
                  )}
                </button>

                {showTimeline && (
                  <div className="timeline-list">

                    {timeSeries.length > 0 ? (
                      timeSeries.map((point, index) => (
                        <div
                          className="timeline-row"
                          key={`${point.date}-${index}`}
                        >
                          <span>{point.date}</span>

                          <span>
                            NDVI {formatValue(point.ndvi)}
                          </span>

                          <span>
                            NBR {formatValue(point.nbr)}
                          </span>
                        </div>
                      ))
                    ) : (
                      <p className="timeline-empty">
                        No time-series observations available.
                      </p>
                    )}

                  </div>
                )}

              </section>
            </>
          )}

          {!loading && !error && !fieldData && (
            <div className="field-drawer-state">
              <Satellite size={26} />

              <strong>Select a field</strong>

              <p>
                Choose a field from the map or monitoring
                table to view its satellite intelligence.
              </p>
            </div>
          )}

        </div>
      </aside>
    </>
  );
}

export default FieldDrawer;
