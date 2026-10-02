import {
  Building2,
  CalendarDays,
  ChevronDown,
  ChevronUp,
  Clock3,
  Factory,
  Radio,
  Route,
  Satellite,
  Target,
  TrendingDown,
  TrendingUp,
  Truck,
  Wheat,
  X
} from "lucide-react";
import { useEffect, useState } from "react";

const API_URL =
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:8000";

function formatValue(value, digits = 4) {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return "N/A";
  }

  const number = Number(value);

  return Number.isFinite(number)
    ? number.toFixed(digits)
    : String(value);
}

function formatTonnes(value) {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return "N/A";
  }

  const number = Number(value);

  return Number.isFinite(number)
    ? `${number.toFixed(3)} t`
    : String(value);
}

function formatCurrency(value) {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return "N/A";
  }

  const number = Number(value);

  if (!Number.isFinite(number)) {
    return String(value);
  }

  return `₹${number.toLocaleString("en-IN", {
    maximumFractionDigits: 0
  })}`;
}

function formatLabel(value) {
  if (!value) {
    return "Unknown";
  }

  return String(value)
    .replace(/_/g, " ")
    .replace(/-/g, " ")
    .replace(/\b\w/g, (letter) =>
      letter.toUpperCase()
    );
}

function fetchJson(url, signal) {
  return fetch(url, { signal }).then(async (response) => {
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(
        data?.detail ||
          data?.message ||
          `Request failed with status ${response.status}`
      );
    }

    return data;
  });
}

function MetricCard({ label, value, icon: Icon }) {
  return (
    <div className="biomass-metric-card">
      {Icon ? <Icon size={14} /> : null}
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ModuleState({ loading, error, children }) {
  if (loading) {
    return (
      <div className="biomass-module-loading">
        <div className="mini-spinner" />
        <div>
          <strong>Loading intelligence…</strong>
          <span>Reading the selected field from the API.</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="biomass-module-error">
        <strong>Module unavailable</strong>
        <span>{error}</span>
      </div>
    );
  }

  return children;
}

function FieldDrawer({
  fieldData,
  harvestPrediction = null,
  harvestLoading = false,
  harvestError = "",
  open = false,
  loading = false,
  error = "",
  onClose,
  onAnalyze
}) {
  const [showTimeline, setShowTimeline] = useState(true);
  const [showBiomass, setShowBiomass] = useState(true);
  const [showResidue, setShowResidue] = useState(true);
  const [showOpportunity, setShowOpportunity] = useState(true);
  const [showCluster, setShowCluster] = useState(true);
  const [showLogistics, setShowLogistics] = useState(true);

  const [moduleData, setModuleData] = useState({
    residue: null,
    opportunity: null,
    cluster: null,
    logistics: null,
    burn: null
  });

  const [moduleLoading, setModuleLoading] = useState({
    residue: false,
    opportunity: false,
    cluster: false,
    logistics: false,
    burn: false
  });

  const [moduleErrors, setModuleErrors] = useState({
    residue: "",
    opportunity: "",
    cluster: "",
    logistics: "",
    burn: ""
  });

  const requestedFieldId = String(
    fieldData?.field_id || ""
  ).trim();

  useEffect(() => {
    if (!open || !requestedFieldId) {
      return undefined;
    }

    const controller = new AbortController();

    setModuleData({
      residue: null,
      opportunity: null,
      cluster: null,
      logistics: null,
      burn: null
    });

    setModuleLoading({
      residue: true,
      opportunity: true,
      cluster: true,
      logistics: true,
      burn: true
    });

    setModuleErrors({
      residue: "",
      opportunity: "",
      cluster: "",
      logistics: "",
      burn: ""
    });

    const endpoints = {
      residue: `${API_URL}/residue-estimation/${encodeURIComponent(
        requestedFieldId
      )}`,
      opportunity: `${API_URL}/biomass-opportunity/${encodeURIComponent(
        requestedFieldId
      )}`,
      cluster: `${API_URL}/biomass-cluster/${encodeURIComponent(
        requestedFieldId
      )}`,
      logistics: `${API_URL}/logistics-estimation/${encodeURIComponent(
        requestedFieldId
      )}`,
      burn: `${API_URL}/live-burn-analysis/${encodeURIComponent(
        requestedFieldId
      )}`
    };

    Object.entries(endpoints).forEach(([key, url]) => {
      fetchJson(url, controller.signal)
        .then((data) => {
          setModuleData((current) => ({
            ...current,
            [key]: data
          }));
        })
        .catch((requestError) => {
          if (requestError?.name === "AbortError") {
            return;
          }

          setModuleErrors((current) => ({
            ...current,
            [key]: requestError?.message || "Request failed"
          }));
        })
        .finally(() => {
          if (!controller.signal.aborted) {
            setModuleLoading((current) => ({
              ...current,
              [key]: false
            }));
          }
        });
    });

    return () => controller.abort();
  }, [open, requestedFieldId]);

  if (!open) {
    return null;
  }

  const indicators = fieldData?.field_indicators || {};

  const category =
    fieldData?.field_category ||
    indicators?.category ||
    "Unknown";

  // Resolve API module data before deriving any live values.
  // Keeping liveBurn above the latest/time-series calculations prevents
  // a temporal-dead-zone ReferenceError that can blank the React page.
  const residue = moduleData.residue;
  const opportunity = moduleData.opportunity;
  const cluster = moduleData.cluster;
  const logistics = moduleData.logistics;
  const liveBurn = moduleData.burn;

  const latest =
    liveBurn?.latest_observation ||
    harvestPrediction?.latest_observation ||
    fieldData?.latest_observation ||
    {};

  const timeSeries =
    liveBurn?.time_series?.length
      ? liveBurn.time_series
      : harvestPrediction?.time_series?.length
      ? harvestPrediction.time_series
      : fieldData?.time_series || [];

  const sourceFieldIds =
    fieldData?.source_field_ids ||
    fieldData?.source_fields?.map(
      (item) => item.field_id
    ) ||
    [];

  const residueArea =
    residue?.area?.hectares ??
    indicators?.area_hectares ??
    null;

  const nearestFacility =
    opportunity?.nearest_facility ||
    logistics?.nearest_facility ||
    null;

  const clusterSummary =
    cluster?.collection_cluster || {};

  const clusterAggregation =
    cluster?.aggregation_effect || {};

  const opportunityStatus =
    nearestFacility?.opportunity_status ||
    nearestFacility?.screening_status ||
    opportunity?.matching_status ||
    "No facility match";

  const liveSeries = Array.isArray(liveBurn?.time_series)
    ? liveBurn.time_series.filter(
        (point) =>
          Number.isFinite(Number(point?.ndvi)) ||
          Number.isFinite(Number(point?.nbr))
      )
    : [];

  const deriveTrend = (key, fallback) => {
    const values = liveSeries
      .map((point) => Number(point?.[key]))
      .filter(Number.isFinite);

    if (values.length >= 2) {
      const recent = values.slice(-5);
      const first = recent[0];
      const last = recent[recent.length - 1];
      const delta = last - first;

      if (delta > 0.02) return "Increasing";
      if (delta < -0.02) return "Decreasing";
      return "Stable";
    }

    return fallback || "N/A";
  };

  const liveNDVI =
    latest?.ndvi ??
    harvestPrediction?.signals?.latest_ndvi ??
    indicators?.latest_ndvi ??
    null;

  const liveNBR =
    latest?.nbr ??
    harvestPrediction?.signals?.latest_nbr ??
    indicators?.latest_nbr ??
    null;

  const liveNDVITrend = deriveTrend(
    "ndvi",
    indicators?.ndvi_trend
  );

  const liveNBRTrend = deriveTrend(
    "nbr",
    indicators?.nbr_trend
  );

  const liveStatus =
    harvestPrediction?.status_label ||
    liveBurn?.status_label ||
    indicators?.field_status ||
    "Monitoring active";

  const liveObservationDate =
    liveBurn?.as_of_date ||
    latest?.date ||
    harvestPrediction?.as_of_date ||
    "N/A";

  return (
    <>
      <div
        className="field-drawer-backdrop"
        onClick={onClose}
      />

      <aside
        className="field-drawer"
        aria-label="Field analysis"
      >
        <div className="field-drawer-glow" />

        <div className="field-drawer-header">
          <div>
            <div className="drawer-kicker">
              FIELD ANALYSIS
            </div>

            <h2>
              Field {fieldData?.field_id || "—"}
            </h2>

            <div className="drawer-header-meta">
              <span className="drawer-live-pill">
                <span />
                Live satellite view
              </span>
              <span>
                {formatLabel(category)}
              </span>
              {sourceFieldIds.length > 1 ? (
                <span className="drawer-group-pill">
                  {sourceFieldIds.length} source years
                </span>
              ) : null}
            </div>
          </div>

          <button
            type="button"
            className="field-drawer-close"
            onClick={onClose}
            aria-label="Close field analysis"
          >
            <X size={19} />
          </button>
        </div>

        <div className="field-drawer-content">
          {loading && (
            <div className="field-drawer-state">
              <div className="drawer-orbit-loader">
                <Satellite size={22} />
              </div>
              <strong>Reading satellite data</strong>
              <p>
                Loading field indicators and current observations…
              </p>
            </div>
          )}

          {!loading && error && (
            <div className="field-drawer-error">
              <strong>Field analysis failed</strong>
              <p>{error}</p>

              <button
                type="button"
                onClick={onAnalyze}
              >
                Try again
              </button>
            </div>
          )}

          {!loading && !error && fieldData && (
            <>
              <section className="drawer-hero-panel">
                <div className="drawer-hero-top">
                  <div>
                    <span>CURRENT FIELD STATE</span>
                    <strong>
                      {formatLabel(liveStatus)}
                    </strong>
                  </div>

                  <div className="drawer-radar">
                    <span />
                    <span />
                    <span />
                    <Satellite size={18} />
                  </div>
                </div>

                <div className="drawer-mini-grid">
                  <div>
                    <span>Area</span>
                    <strong>
                      {residueArea != null
                        ? `${residueArea} ha`
                        : "N/A"}
                    </strong>
                  </div>

                  <div>
                    <span>NDVI</span>
                    <strong>
                      {latest?.ndvi != null
                        ? formatValue(latest.ndvi)
                        : "N/A"}
                    </strong>
                  </div>

                  <div>
                    <span>NBR</span>
                    <strong>
                      {latest?.nbr != null
                        ? formatValue(latest.nbr)
                        : "N/A"}
                    </strong>
                  </div>

                  <div>
                    <span>Latest scene</span>
                    <strong>
                      {latest?.date || "N/A"}
                    </strong>
                  </div>
                </div>
              </section>

              <section className="drawer-section">
                <div className="drawer-section-heading">
                  <div className="drawer-section-icon">
                    <Target size={16} />
                  </div>

                  <div>
                    <span>LIVE SENTINEL-2 SIGNAL</span>
                    <h3>Crop-transition assessment</h3>
                  </div>
                </div>

                {harvestLoading && (
                  <div className="drawer-loading-card">
                    <div className="mini-spinner" />
                    <div>
                      <strong>Examining the latest observations…</strong>
                      <span>
                        Calculating current NDVI/NBR change signals.
                      </span>
                    </div>
                  </div>
                )}

                {!harvestLoading && harvestError && (
                  <div className="drawer-warning-card">
                    <strong>Live signal unavailable</strong>
                    <span>{harvestError}</span>
                  </div>
                )}

                {!harvestLoading &&
                  !harvestError &&
                  harvestPrediction && (
                    <>
                      <div className="drawer-signal-hero">
                        <div>
                          <span>Signal level</span>
                          <strong>
                            {harvestPrediction.signal_level || "Unknown"}
                          </strong>
                        </div>

                        <div className="drawer-signal-status">
                          {harvestPrediction.status_label ||
                            "Assessment available"}
                        </div>
                      </div>

                      <div className="drawer-metric-grid">
                        <div>
                          <TrendingDown size={15} />
                          <span>NDVI decline</span>
                          <strong>
                            {harvestPrediction.signals
                              ?.ndvi_decline_from_peak ?? "N/A"}
                          </strong>
                        </div>

                        <div>
                          <TrendingDown size={15} />
                          <span>NBR decline</span>
                          <strong>
                            {harvestPrediction.signals
                              ?.nbr_decline_from_peak ?? "N/A"}
                          </strong>
                        </div>

                        <div>
                          <Radio size={15} />
                          <span>Observations</span>
                          <strong>
                            {harvestPrediction.signals?.observations ??
                              "N/A"}
                          </strong>
                        </div>

                        <div>
                          <TrendingUp size={15} />
                          <span>Recent NDVI slope</span>
                          <strong>
                            {harvestPrediction.signals
                              ?.recent_ndvi_slope_per_day ?? "N/A"}
                          </strong>
                        </div>
                      </div>

                      {(harvestPrediction.signals?.candidate_date ||
                        harvestPrediction.estimated_transition_window
                          ?.start) && (
                        <div className="drawer-transition-box">
                          <CalendarDays size={16} />
                          <div>
                            <span>Transition timing</span>
                            <strong>
                              {harvestPrediction
                                .estimated_transition_window?.start
                                ? `${harvestPrediction.estimated_transition_window.start} → ${harvestPrediction.estimated_transition_window.end}`
                                : harvestPrediction.signals
                                    ?.candidate_date ||
                                  "Candidate detected"}
                            </strong>
                          </div>
                        </div>
                      )}

                      <div className="drawer-reason-list">
                        {(harvestPrediction.reasons || []).map(
                          (reason) => (
                            <div key={reason}>
                              <span>+</span>
                              {reason}
                            </div>
                          )
                        )}
                      </div>

                      <p className="drawer-note">
                        {harvestPrediction.validation_note ||
                          "This is a satellite-transition signal assessment, not a calibrated harvest probability or confirmed harvest date."}
                      </p>
                    </>
                  )}
              </section>
              <section className="drawer-section live-burn-section">
                <div className="drawer-section-heading">
                  <div className="drawer-section-icon burn-section-icon">
                    <Radio size={16} />
                  </div>

                  <div>
                    <span>BURN DETECTION</span>
                    <h3>Satellite burn intelligence</h3>
                  </div>

                  <div className="live-module-badge">
                    LIVE
                  </div>
                </div>

                {moduleLoading.burn && (
                  <div className="drawer-loading-card live-burn-loading">
                    <div className="mini-spinner" />
                    <div>
                      <strong>Scanning current Sentinel-2 signals…</strong>
                      <span>
                        Reading NBR, NDVI and SWIR-sensitive burn indicators.
                      </span>
                    </div>
                  </div>
                )}

                {!moduleLoading.burn && moduleErrors.burn && (
                  <div className="drawer-warning-card live-burn-error">
                    <strong>Live burn intelligence unavailable</strong>
                    <span>{moduleErrors.burn}</span>
                  </div>
                )}

                {!moduleLoading.burn &&
                  !moduleErrors.burn &&
                  liveBurn && (
                    <>
                      <div className="live-burn-hero">
                        <div className="live-burn-score-orb">
                          <span>Signal</span>
                          <strong>
                            {liveBurn.signal_strength != null
                              ? `${liveBurn.signal_strength}`
                              : "—"}
                          </strong>
                          <small>/ 100</small>
                        </div>

                        <div className="live-burn-status-copy">
                          <span>Current spectral assessment</span>
                          <strong>
                            {liveBurn.status_label || "Assessment available"}
                          </strong>
                          <small>
                            As of {liveBurn.as_of_date || "latest available scene"}
                          </small>
                        </div>
                      </div>

                      <div className="live-burn-metric-grid">
                        <div>
                          <span>Burn signal</span>
                          <strong>
                            {formatLabel(
                              liveBurn.burn_likelihood ||
                                liveBurn.status ||
                                "N/A"
                            )}
                          </strong>
                        </div>

                        <div>
                          <span>Latest NBR</span>
                          <strong>
                            {liveBurn?.latest_observation?.nbr != null
                              ? formatValue(
                                  liveBurn.latest_observation.nbr
                                )
                              : "N/A"}
                          </strong>
                        </div>

                        <div>
                          <span>NBR drop</span>
                          <strong>
                            {liveBurn?.signals?.nbr_drop_from_reference !=
                            null
                              ? formatValue(
                                  liveBurn.signals.nbr_drop_from_reference
                                )
                              : "N/A"}
                          </strong>
                        </div>

                        <div>
                          <span>NDVI drop</span>
                          <strong>
                            {liveBurn?.signals?.ndvi_drop_from_reference !=
                            null
                              ? formatValue(
                                  liveBurn.signals.ndvi_drop_from_reference
                                )
                              : "N/A"}
                          </strong>
                        </div>
                      </div>

                      <div className="live-burn-spectrum">
                        <div>
                          <span>SWIR2</span>
                          <strong>
                            {liveBurn?.latest_observation?.swir2 != null
                              ? formatValue(
                                  liveBurn.latest_observation.swir2
                                )
                              : "N/A"}
                          </strong>
                        </div>

                        <div>
                          <span>NBR2</span>
                          <strong>
                            {liveBurn?.latest_observation?.nbr2 != null
                              ? formatValue(
                                  liveBurn.latest_observation.nbr2
                                )
                              : "N/A"}
                          </strong>
                        </div>

                        <div>
                          <span>SWIR2 / NIR</span>
                          <strong>
                            {liveBurn?.latest_observation?.swir2_nir_ratio !=
                            null
                              ? formatValue(
                                  liveBurn.latest_observation.swir2_nir_ratio
                                )
                              : "N/A"}
                          </strong>
                        </div>

                        <div>
                          <span>Observations</span>
                          <strong>
                            {liveBurn.observations ?? "N/A"}
                          </strong>
                        </div>
                      </div>

                      <div className="live-burn-reasons">
                        {(liveBurn.reasons || []).slice(0, 4).map(
                          (reason) => (
                            <div key={reason}>
                              <span>+</span>
                              {reason}
                            </div>
                          )
                        )}
                      </div>

                      <p className="biomass-note">
                        {liveBurn.validation_note ||
                          "Live Sentinel-2 spectral burn intelligence is a screening signal, not a confirmed fire or burn event."}
                      </p>
                    </>
                  )}
              </section>


              <section className="drawer-section biomass-intelligence-section">
                <button
                  type="button"
                  className="timeline-toggle biomass-main-toggle"
                  onClick={() => setShowBiomass((visible) => !visible)}
                >
                  <div className="biomass-title-wrap">
                    <div className="drawer-section-icon">
                      <Wheat size={16} />
                    </div>
                    <div>
                      <span>BIOMASS + OPERATIONAL FIELD INTELLIGENCE</span>
                      <strong>Operational field intelligence</strong>
                    </div>
                  </div>

                  {showBiomass ? (
                    <ChevronUp size={18} />
                  ) : (
                    <ChevronDown size={18} />
                  )}
                </button>

                {showBiomass && (
                  <div className="biomass-intelligence-stack">
                    <div className="biomass-live-strip">
                      <span>
                        <span className="biomass-live-dot" />
                        API intelligence sync
                      </span>
                      <code>{requestedFieldId}</code>
                    </div>

                    <section className="biomass-module">
                      <button
                        type="button"
                        className="biomass-module-toggle"
                        onClick={() =>
                          setShowResidue((visible) => !visible)
                        }
                      >
                        <span className="biomass-module-icon">
                          <Wheat size={15} />
                        </span>
                        <span className="biomass-module-heading">
                          <small>RESIDUE ESTIMATION</small>
                          <strong>Field biomass potential</strong>
                        </span>
                        {showResidue ? (
                          <ChevronUp size={16} />
                        ) : (
                          <ChevronDown size={16} />
                        )}
                      </button>

                      {showResidue && (
                        <ModuleState
                          loading={moduleLoading.residue}
                          error={moduleErrors.residue}
                        >
                          {residue ? (
                            <>
                              <div className="biomass-highlight">
                                <div>
                                  <span>Recoverable biomass</span>
                                  <strong>
                                    {formatTonnes(
                                      residue.recoverable_biomass_tonnes
                                    )}
                                  </strong>
                                </div>
                                <div className="biomass-highlight-badge">
                                  {residue.collection_potential_percent ??
                                    "N/A"}
                                  % collection
                                </div>
                              </div>

                              <div className="biomass-metric-grid">
                                <MetricCard
                                  label="Gross residue"
                                  value={formatTonnes(
                                    residue.gross_residue_tonnes
                                  )}
                                  icon={Wheat}
                                />
                                <MetricCard
                                  label="Area"
                                  value={
                                    residueArea != null
                                      ? `${formatValue(residueArea, 4)} ha`
                                      : "N/A"
                                  }
                                  icon={Satellite}
                                />
                                <MetricCard
                                  label="Crop"
                                  value={formatLabel(residue.crop)}
                                  icon={Wheat}
                                />
                                <MetricCard
                                  label="Source records"
                                  value={
                                    residue.source_field_count ??
                                    sourceFieldIds.length
                                  }
                                  icon={Building2}
                                />
                              </div>

                              <p className="biomass-note">
                                {residue.validation_note ||
                                  "Assumption-based biomass estimate using the configured crop-residue model."}
                              </p>
                            </>
                          ) : null}
                        </ModuleState>
                      )}
                    </section>

                    <section className="biomass-module">
                      <button
                        type="button"
                        className="biomass-module-toggle"
                        onClick={() =>
                          setShowOpportunity((visible) => !visible)
                        }
                      >
                        <span className="biomass-module-icon">
                          <Factory size={15} />
                        </span>
                        <span className="biomass-module-heading">
                          <small>BIOMASS OPPORTUNITY</small>
                          <strong>Facility matching</strong>
                        </span>
                        {showOpportunity ? (
                          <ChevronUp size={16} />
                        ) : (
                          <ChevronDown size={16} />
                        )}
                      </button>

                      {showOpportunity && (
                        <ModuleState
                          loading={moduleLoading.opportunity}
                          error={moduleErrors.opportunity}
                        >
                          {opportunity ? (
                            <>
                              <div className="facility-card">
                                <div className="facility-card-top">
                                  <div className="facility-card-icon">
                                    <Factory size={16} />
                                  </div>
                                  <div>
                                    <span>Nearest registered facility</span>
                                    <strong>
                                      {nearestFacility?.name ||
                                        "No facility found"}
                                    </strong>
                                  </div>
                                </div>

                                <div className="facility-distance-line">
                                  <span>Distance</span>
                                  <strong>
                                    {nearestFacility?.distance_km != null
                                      ? `${nearestFacility.distance_km} km`
                                      : "N/A"}
                                  </strong>
                                </div>

                                <div className="facility-distance-line">
                                  <span>Estimated supply</span>
                                  <strong>
                                    {nearestFacility?.estimated_supply_tonnes !=
                                    null
                                      ? formatTonnes(
                                          nearestFacility.estimated_supply_tonnes
                                        )
                                      : formatTonnes(
                                          opportunity.recoverable_biomass_tonnes
                                        )}
                                  </strong>
                                </div>

                                <div className="facility-status-chip">
                                  {formatLabel(opportunityStatus)}
                                </div>
                              </div>

                              <div className="biomass-metric-grid">
                                <MetricCard
                                  label="Facilities screened"
                                  value={
                                    opportunity.facility_count ??
                                    opportunity.facilities?.length ??
                                    0
                                  }
                                  icon={Factory}
                                />
                                <MetricCard
                                  label="Within radius"
                                  value={
                                    opportunity.within_radius_count ??
                                    opportunity.facilities_within_search_radius
                                      ?.length ??
                                    0
                                  }
                                  icon={Target}
                                />
                              </div>

                              <p className="biomass-note">
                                Facility coordinates may be approximate. This
                                is screening intelligence, not a confirmed
                                procurement contract.
                              </p>
                            </>
                          ) : null}
                        </ModuleState>
                      )}
                    </section>

                    <section className="biomass-module">
                      <button
                        type="button"
                        className="biomass-module-toggle"
                        onClick={() =>
                          setShowCluster((visible) => !visible)
                        }
                      >
                        <span className="biomass-module-icon">
                          <Truck size={15} />
                        </span>
                        <span className="biomass-module-heading">
                          <small>BIOMASS COLLECTION CLUSTER</small>
                          <strong>Nearby field aggregation</strong>
                        </span>
                        {showCluster ? (
                          <ChevronUp size={16} />
                        ) : (
                          <ChevronDown size={16} />
                        )}
                      </button>

                      {showCluster && (
                        <ModuleState
                          loading={moduleLoading.cluster}
                          error={moduleErrors.cluster}
                        >
                          {cluster ? (
                            <>
                              <div className="biomass-metric-grid">
                                <MetricCard
                                  label="Cluster biomass"
                                  value={formatTonnes(
                                    clusterAggregation.cluster_recoverable_tonnes ??
                                      clusterSummary.recoverable_biomass_tonnes
                                  )}
                                  icon={Truck}
                                />
                                <MetricCard
                                  label="Fields aggregated"
                                  value={
                                    clusterSummary.field_count ??
                                    "N/A"
                                  }
                                  icon={Building2}
                                />
                                <MetricCard
                                  label="Truckloads"
                                  value={
                                    clusterAggregation.estimated_truckloads ??
                                    clusterSummary.estimated_truckloads ??
                                    0
                                  }
                                  icon={Truck}
                                />
                                <MetricCard
                                  label="Radius"
                                  value={`${
                                    cluster.cluster_radius_km ??
                                    5
                                  } km`}
                                  icon={Target}
                                />
                              </div>

                              <div className="cluster-callout">
                                <div>
                                  <span>This field</span>
                                  <strong>
                                    {formatTonnes(
                                      clusterAggregation.individual_field_recoverable_tonnes ??
                                        cluster.field?.recoverable_biomass_tonnes ??
                                        0
                                    )}
                                  </strong>
                                </div>
                                <div>
                                  <span>Additional fields</span>
                                  <strong>
                                    {clusterAggregation.additional_fields_aggregated ??
                                      Math.max(
                                        0,
                                        Number(
                                          clusterSummary.field_count || 0
                                        ) - 1
                                      )}
                                  </strong>
                                </div>
                              </div>

                              <p className="biomass-note">
                                {cluster.validation_note ||
                                  "Nearby fields are grouped as a planning estimate; this does not confirm participation, routes, or transporter capacity."}
                              </p>
                            </>
                          ) : null}
                        </ModuleState>
                      )}
                    </section>

                    <section className="biomass-module">
                      <button
                        type="button"
                        className="biomass-module-toggle"
                        onClick={() =>
                          setShowLogistics((visible) => !visible)
                        }
                      >
                        <span className="biomass-module-icon">
                          <Route size={15} />
                        </span>
                        <span className="biomass-module-heading">
                          <small>LOGISTICS ESTIMATION</small>
                          <strong>Transport screening</strong>
                        </span>
                        {showLogistics ? (
                          <ChevronUp size={16} />
                        ) : (
                          <ChevronDown size={16} />
                        )}
                      </button>

                      {showLogistics && (
                        <ModuleState
                          loading={moduleLoading.logistics}
                          error={moduleErrors.logistics}
                        >
                          {logistics ? (
                            <>
                              <div className="logistics-route-card">
                                <div className="route-node">
                                  <span className="route-node-dot field-dot" />
                                  <div>
                                    <small>FIELD</small>
                                    <strong>
                                      {requestedFieldId}
                                    </strong>
                                  </div>
                                </div>

                                <div className="route-line">
                                  <span />
                                </div>

                                <div className="route-node">
                                  <span className="route-node-dot facility-dot" />
                                  <div>
                                    <small>FACILITY</small>
                                    <strong>
                                      {logistics.nearest_facility?.name ||
                                        "N/A"}
                                    </strong>
                                  </div>
                                </div>
                              </div>

                              <div className="biomass-metric-grid">
                                <MetricCard
                                  label="Straight line"
                                  value={
                                    logistics.straight_line_distance_km !=
                                    null
                                      ? `${logistics.straight_line_distance_km} km`
                                      : "N/A"
                                  }
                                  icon={Route}
                                />
                                <MetricCard
                                  label="Road estimate"
                                  value={
                                    logistics.estimated_road_distance_km !=
                                    null
                                      ? `${logistics.estimated_road_distance_km} km`
                                      : "N/A"
                                  }
                                  icon={Truck}
                                />
                                <MetricCard
                                  label="Transport estimate"
                                  value={formatCurrency(
                                    logistics.estimated_transport_cost_inr
                                  )}
                                  icon={Truck}
                                />
                                <MetricCard
                                  label="Cost / tonne"
                                  value={formatCurrency(
                                    logistics.cost_per_tonne_inr
                                  )}
                                  icon={Wheat}
                                />
                              </div>

                              <div className="logistics-status-line">
                                <span>Status</span>
                                <strong>
                                  {formatLabel(
                                    logistics.logistics_status
                                  )}
                                </strong>
                              </div>

                              {(logistics.warnings || []).length > 0 && (
                                <div className="logistics-warning-list">
                                  {logistics.warnings.slice(0, 2).map((warning) => (
                                    <div key={warning}>{warning}</div>
                                  ))}
                                </div>
                              )}

                              <p className="biomass-note">
                                {logistics.validation_note ||
                                  "Road distance and transport cost are screening assumptions, not live routing or a transporter quotation."}
                              </p>
                            </>
                          ) : null}
                        </ModuleState>
                      )}
                    </section>
                  </div>
                )}
              </section>

              <section className="drawer-section live-context-section">
                <div className="drawer-section-heading">
                  <div className="drawer-section-icon">
                    <TrendingDown size={16} />
                  </div>

                  <div>
                    <span>FIELD CONTEXT</span>
                    <h3>Indicator snapshot</h3>
                  </div>

                  <div className="live-module-badge">
                    LIVE
                  </div>
                </div>

                <div className="live-context-grid">
                  <div className="live-context-card">
                    <span>Current NDVI</span>
                    <strong>
                      {liveNDVI != null
                        ? formatValue(liveNDVI)
                        : "N/A"}
                    </strong>
                    <small>
                      Latest Sentinel-2 observation
                    </small>
                  </div>

                  <div className="live-context-card">
                    <span>Current NBR</span>
                    <strong>
                      {liveNBR != null
                        ? formatValue(liveNBR)
                        : "N/A"}
                    </strong>
                    <small>
                      Latest Sentinel-2 observation
                    </small>
                  </div>

                  <div className="live-context-card">
                    <span>NDVI trend</span>
                    <strong>{liveNDVITrend}</strong>
                    <small>
                      Derived from recent live observations
                    </small>
                  </div>

                  <div className="live-context-card">
                    <span>NBR trend</span>
                    <strong>{liveNBRTrend}</strong>
                    <small>
                      Derived from recent live observations
                    </small>
                  </div>
                </div>

                <div className="live-context-meta">
                  <div>
                    <span>Live status</span>
                    <strong>{formatLabel(liveStatus)}</strong>
                  </div>

                  <div>
                    <span>Last observation</span>
                    <strong>{liveObservationDate}</strong>
                  </div>

                  <div>
                    <span>Field category</span>
                    <strong>{formatLabel(category)}</strong>
                  </div>
                </div>

                {sourceFieldIds.length > 0 && (
                  <div className="drawer-source-tray">
                    <span>Source records</span>
                    <div>
                      {sourceFieldIds.map((sourceId) => (
                        <code key={sourceId}>{sourceId}</code>
                      ))}
                    </div>
                  </div>
                )}
              </section>

              <section className="drawer-section">
                <button
                  type="button"
                  className="timeline-toggle"
                  onClick={() => setShowTimeline((visible) => !visible)}
                >
                  <div>
                    <span>SATELLITE TIMELINE</span>
                    <strong>Sentinel-2 observations</strong>
                  </div>

                  {showTimeline ? (
                    <ChevronUp size={18} />
                  ) : (
                    <ChevronDown size={18} />
                  )}
                </button>

                {showTimeline && (
                  <div className="timeline-list">
                    {timeSeries.length > 0 ? (
                      timeSeries
                        .slice()
                        .reverse()
                        .map((point, index) => (
                          <div
                            className="timeline-row"
                            key={`${point.date}-${index}`}
                          >
                            <div className="timeline-date">
                              <Clock3 size={13} />
                              {point.date}
                            </div>
                            <span>
                              NDVI {formatValue(point.ndvi)}
                            </span>
                            <span>
                              NBR {formatValue(point.nbr)}
                            </span>
                          </div>
                        ))
                    ) : (
                      <div className="timeline-empty">
                        No satellite observations available.
                      </div>
                    )}
                  </div>
                )}
              </section>


              <div className="drawer-footnote">
                Satellite observations are interpreted as monitoring evidence.
                Burn, biomass, facility, clustering, and logistics values are
                screening estimates based on the current Project Parali model
                assumptions and are not confirmed operational commitments.
              </div>
            </>
          )}

          {!loading && !error && !fieldData && (
            <div className="field-drawer-state">
              <Satellite size={25} />
              <strong>Select a field</strong>
              <p>
                Choose a polygon from the monitoring map to open field analysis.
              </p>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}

export default FieldDrawer;
