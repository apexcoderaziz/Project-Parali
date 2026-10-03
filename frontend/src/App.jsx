import {
  useEffect,
  useMemo,
  useState
} from "react";

import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  CalendarDays,
  ChevronRight,
  Crosshair,
  Leaf,
  LocateFixed,
  MapPinned,
  Radio,
  ScanSearch,
  Satellite,
  ShieldCheck,
  Sparkles,
  Moon,
  Sun,
  Target,
  TrendingDown,
  TrendingUp,
  Waves,
  Wheat,
  X
} from "lucide-react";

import "./styles.css";

import FieldMap from "./FieldMap.jsx";
import FieldDrawer from "./components/FieldDrawer.jsx";
import MapLegend from "./components/MapLegend.jsx";
import BurnDetector from "./components/BurnDetector.jsx";

const API_URL =
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:8000";

const API_TIMEOUT_MS = 15000;

async function fetchWithTimeout(url, options = {}) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(
    () => controller.abort(),
    API_TIMEOUT_MS
  );

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal
    });

    return response;
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error(
        `Request timed out after ${API_TIMEOUT_MS / 1000}s. Check that the Project Parali API is running at ${API_URL}.`
      );
    }

    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}


function FieldAreaDeclineChart({ data }) {
  const points = Array.isArray(data)
    ? data.filter(
        (point) =>
          Number.isFinite(Number(point?.area)) &&
          Number.isFinite(Number(point?.decline))
      )
    : [];

  if (points.length === 0) {
    return (
      <div className="signal-chart-empty">
        <Waves size={20} />
        <strong>Signal landscape is waiting for data.</strong>
        <span>
          Area and NDVI-decline indicators will appear here when the field
          dataset is available.
        </span>
      </div>
    );
  }

  const width = 900;
  const height = 330;
  const margin = { top: 28, right: 24, bottom: 54, left: 60 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;

  const areas = points.map((point) => Number(point.area));
  const declines = points.map((point) => Number(point.decline));

  const rawMinX = Math.min(...areas);
  const rawMaxX = Math.max(...areas);
  const rawMinY = Math.min(...declines);
  const rawMaxY = Math.max(...declines);

  const xPadding = Math.max((rawMaxX - rawMinX) * 0.08, 0.01);
  const yPadding = Math.max((rawMaxY - rawMinY) * 0.08, 0.01);

  const minX = Math.max(0, rawMinX - xPadding);
  const maxX = rawMaxX + xPadding;
  const minY = Math.max(0, rawMinY - yPadding);
  const maxY = rawMaxY + yPadding;

  const xScale = (value) =>
    margin.left +
    ((value - minX) / Math.max(maxX - minX, 0.0001)) *
      innerWidth;

  const yScale = (value) =>
    margin.top +
    innerHeight -
    ((value - minY) / Math.max(maxY - minY, 0.0001)) *
      innerHeight;

  const tickCount = 5;

  const xTicks = Array.from(
    { length: tickCount },
    (_, index) =>
      minX +
      ((maxX - minX) * index) /
        (tickCount - 1)
  );

  const yTicks = Array.from(
    { length: tickCount },
    (_, index) =>
      minY +
      ((maxY - minY) * index) /
        (tickCount - 1)
  );

  return (
    <div className="signal-scatter-shell">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        height="100%"
        role="img"
        aria-label="Field area versus NDVI decline"
      >
        <defs>
          <linearGradient
            id="signalGlow"
            x1="0"
            y1="0"
            x2="1"
            y2="1"
          >
            <stop offset="0%" stopColor="#d8ff65" stopOpacity="0.9" />
            <stop offset="100%" stopColor="#55e3a4" stopOpacity="0.35" />
          </linearGradient>
        </defs>

        <rect
          x="0"
          y="0"
          width={width}
          height={height}
          fill="transparent"
        />

        {yTicks.map((tick, index) => {
          const y = yScale(tick);

          return (
            <g key={`y-${index}`}>
              <line
                x1={margin.left}
                x2={width - margin.right}
                y1={y}
                y2={y}
                stroke="rgba(148,163,184,0.18)"
                strokeDasharray="4 6"
              />
              <text
                x={margin.left - 10}
                y={y + 4}
                textAnchor="end"
                fontSize="11"
                fill="#90a39a"
              >
                {tick.toFixed(2)}
              </text>
            </g>
          );
        })}

        {xTicks.map((tick, index) => {
          const x = xScale(tick);

          return (
            <g key={`x-${index}`}>
              <line
                x1={x}
                x2={x}
                y1={margin.top}
                y2={height - margin.bottom}
                stroke="rgba(148,163,184,0.10)"
              />
              <text
                x={x}
                y={height - margin.bottom + 20}
                textAnchor="middle"
                fontSize="11"
                fill="#90a39a"
              >
                {tick.toFixed(2)}
              </text>
            </g>
          );
        })}

        <line
          x1={margin.left}
          x2={width - margin.right}
          y1={height - margin.bottom}
          y2={height - margin.bottom}
          stroke="rgba(180,197,188,0.42)"
        />

        <line
          x1={margin.left}
          x2={margin.left}
          y1={margin.top}
          y2={height - margin.bottom}
          stroke="rgba(180,197,188,0.42)"
        />

        {points.map((point, index) => {
          const area = Number(point.area);
          const decline = Number(point.decline);

          return (
            <g
              key={`${point.fieldId}-${index}`}
              className="signal-point"
            >
              <circle
                cx={xScale(area)}
                cy={yScale(decline)}
                r="9"
                fill="#d8ff65"
                fillOpacity="0.06"
              />
              <circle
                cx={xScale(area)}
                cy={yScale(decline)}
                r="4.2"
                fill="url(#signalGlow)"
                stroke="#e9ffb4"
                strokeWidth="1"
              >
                <title>
                  {`Field ${point.fieldId} · Area ${area.toFixed(
                    4
                  )} ha · NDVI decline ${decline.toFixed(4)}`}
                </title>
              </circle>
            </g>
          );
        })}

        <text
          x={margin.left + innerWidth / 2}
          y={height - 8}
          textAnchor="middle"
          fontSize="12"
          fontWeight="600"
          fill="#b8c9c0"
        >
          Field area (ha)
        </text>

        <text
          x="16"
          y={margin.top + innerHeight / 2}
          textAnchor="middle"
          fontSize="12"
          fontWeight="600"
          fill="#b8c9c0"
          transform={`rotate(-90 16 ${
            margin.top + innerHeight / 2
          })`}
        >
          NDVI decline
        </text>
      </svg>
    </div>
  );
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


function normalizeCategory(value) {
  return String(value || "")
    .toLowerCase()
    .trim()
    .replace(/-/g, "_")
    .replace(/\s+/g, "_");
}


function App() {
  const [fieldId, setFieldId] = useState("");
  const [fieldData, setFieldData] = useState(null);

  const [harvestPrediction, setHarvestPrediction] =
    useState(null);
  const [harvestLoading, setHarvestLoading] =
    useState(false);
  const [harvestError, setHarvestError] =
    useState("");

  const [fieldLoading, setFieldLoading] =
    useState(false);
  const [fieldError, setFieldError] =
    useState("");

  const [geojson, setGeojson] = useState(null);
  const [mapLoading, setMapLoading] =
    useState(true);
  const [mapError, setMapError] =
    useState("");

  const [fieldSearch, setFieldSearch] =
    useState("");
  const [categoryFilter, setCategoryFilter] =
    useState("all");

  const [darkMode, setDarkMode] = useState(() => {
    try {
      return localStorage.getItem("parali-theme") === "dark";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    const theme = darkMode ? "dark" : "light";

    try {
      localStorage.setItem("parali-theme", theme);
    } catch {
      // Theme persistence is optional; the UI still works without storage.
    }

    document.documentElement.setAttribute("data-theme", theme);
    document.body.setAttribute("data-theme", theme);
  }, [darkMode]);

  useEffect(() => {
    const loadFields = async () => {
      setMapLoading(true);
      setMapError("");

      try {
        const response = await fetchWithTimeout(
          `${API_URL}/fields`
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            data.detail ||
              "Failed to load field map"
          );
        }

        setGeojson(data);
      } catch (error) {
        console.error(
          "Field map error:",
          error
        );

        setMapError(
          error.message ||
            "Field map unavailable"
        );
      } finally {
        setMapLoading(false);
      }
    };

    loadFields();
  }, []);


  const loadHarvestPrediction = async (
    selectedFieldId
  ) => {
    const normalizedFieldId = String(
      selectedFieldId || ""
    ).trim();

    if (!normalizedFieldId) {
      return;
    }

    setHarvestLoading(true);
    setHarvestError("");
    setHarvestPrediction(null);

    try {
      const response = await fetchWithTimeout(
        `${API_URL}/live-harvest-prediction/${encodeURIComponent(
          normalizedFieldId
        )}`
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
            "Live harvest assessment failed"
        );
      }

      setHarvestPrediction(data);
    } catch (error) {
      console.error(
        "Live harvest assessment error:",
        error
      );

      setHarvestPrediction(null);
      setHarvestError(
        error.message ||
          "Live harvest assessment failed"
      );
    } finally {
      setHarvestLoading(false);
    }
  };


  const analyzeField = async (
    selectedFieldId = fieldId
  ) => {
    const normalizedFieldId = String(
      selectedFieldId || ""
    ).trim();

    if (!normalizedFieldId) {
      setFieldError(
        "Enter a logical field number such as 34."
      );
      return;
    }

    setFieldId(normalizedFieldId);
    setFieldLoading(true);
    setFieldError("");
    setFieldData(null);

    try {
      const encodedFieldId =
        encodeURIComponent(
          normalizedFieldId
        );

      const response = await fetchWithTimeout(
        `${API_URL}/field-analysis/${encodedFieldId}`
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
            "Field analysis failed"
        );
      }

      setFieldData(data);

      // Do not block the field analysis UI on the live Sentinel-2
      // harvest request. The field data can render independently while
      // the live harvest layer loads in the background.
      void loadHarvestPrediction(
        normalizedFieldId
      );
    } catch (error) {
      console.error(
        "Field analysis error:",
        error
      );

      setFieldError(
        error.message ||
          "Field analysis failed"
      );
    } finally {
      setFieldLoading(false);
    }
  };


  const handleFieldSelect = (
    selectedFieldId
  ) => {
    const sourceFieldId = String(
      selectedFieldId || ""
    ).trim();

    if (!sourceFieldId) {
      return;
    }

    const logicalMatch =
      sourceFieldId.match(
        /^\d{4}_(.+)$/
      );

    const logicalFieldId = logicalMatch
      ? logicalMatch[1].trim()
      : sourceFieldId;

    setFieldId(logicalFieldId);

    analyzeField(logicalFieldId);

    window.setTimeout(() => {
      document
        .getElementById("field-analysis")
        ?.scrollIntoView({
          behavior: "smooth",
          block: "start"
        });
    }, 120);
  };


  const indicators =
    fieldData?.field_indicators || null;

  const latestObservation =
    harvestPrediction?.latest_observation ||
    fieldData?.latest_observation ||
    null;


  const dashboardStats = useMemo(() => {
    const features =
      geojson?.features || [];

    const categoryOf = (feature) => {
      const properties =
        feature?.properties || {};

      return normalizeCategory(
        properties.category ??
          properties.field_category ??
          properties.indicators?.category ??
          properties.field_indicators?.category
      );
    };

    return {
      totalFields: features.length,

      completelyBurnt:
        features.filter(
          (feature) =>
            categoryOf(feature) ===
            "completely_burnt"
        ).length,

      partiallyBurnt:
        features.filter(
          (feature) =>
            categoryOf(feature) ===
            "partially_burnt"
        ).length,

      transitionCandidates:
        features.filter((feature) => {
          const status =
            normalizeCategory(
              feature?.properties?.field_status ??
                feature?.properties?.indicators
                  ?.field_status ??
                feature?.properties
                  ?.field_indicators
                  ?.field_status
            );

          return (
            status ===
            "crop_transition_candidate"
          );
        }).length
    };
  }, [geojson]);


  const trendStats = useMemo(() => {
    const features =
      geojson?.features || [];

    let ndviDecreasing = 0;
    let nbrDecreasing = 0;
    let bothDecreasing = 0;

    const scatterData = [];

    features.forEach((feature) => {
      const properties =
        feature?.properties || {};

      const indicators =
        properties.field_indicators ||
        properties.indicators ||
        {};

      const ndviTrend =
        normalizeCategory(
          indicators.ndvi_trend ??
            properties.ndvi_trend
        );

      const nbrTrend =
        normalizeCategory(
          indicators.nbr_trend ??
            properties.nbr_trend
        );

      const area = Number(
        indicators.area_hectares ??
          properties.area_hectares
      );

      const decline = Number(
        indicators.decline ??
          properties.decline
      );

      if (
        ndviTrend ===
        "decreasing"
      ) {
        ndviDecreasing += 1;
      }

      if (
        nbrTrend ===
        "decreasing"
      ) {
        nbrDecreasing += 1;
      }

      if (
        ndviTrend === "decreasing" &&
        nbrTrend === "decreasing"
      ) {
        bothDecreasing += 1;
      }

      if (
        Number.isFinite(area) &&
        Number.isFinite(decline)
      ) {
        scatterData.push({
          fieldId:
            properties.field_id ||
            properties.id ||
            "Unknown",
          area,
          decline
        });
      }
    });

    return {
      ndviDecreasing,
      nbrDecreasing,
      bothDecreasing,
      scatterData
    };
  }, [geojson]);


  const filteredGeojson =
    useMemo(() => {
      if (!geojson) {
        return null;
      }

      const normalizedSearch =
        fieldSearch
          .toLowerCase()
          .trim();

      return {
        ...geojson,
        features: (
          geojson.features || []
        ).filter((feature) => {
          const properties =
            feature?.properties || {};

          const sourceId =
            String(
              properties.field_id ??
                properties.id ??
                ""
            ).toLowerCase();

          const logicalId =
            sourceId.match(
              /^\d{4}_(.+)$/
            )?.[1] || sourceId;

          const category =
            normalizeCategory(
              properties.category ??
                properties.field_category ??
                properties.indicators
                  ?.category ??
                properties
                  .field_indicators
                  ?.category
            );

          const matchesSearch =
            !normalizedSearch ||
            sourceId.includes(
              normalizedSearch
            ) ||
            logicalId.includes(
              normalizedSearch
            );

          const matchesCategory =
            categoryFilter === "all" ||
            category === categoryFilter;

          return (
            matchesSearch &&
            matchesCategory
          );
        })
      };
    }, [
      geojson,
      fieldSearch,
      categoryFilter
    ]);


  const selectedCategory =
    normalizeCategory(
      indicators?.category ||
        fieldData?.field_category
    );


  const scrollTo = (id) => {
    document
      .getElementById(id)
      ?.scrollIntoView({
        behavior: "smooth",
        block: "start"
      });
  };


  const clearField = () => {
    setFieldData(null);
    setFieldError("");
    setHarvestPrediction(null);
    setHarvestError("");
    setHarvestLoading(false);
  };


  return (
    <div className={`parali-app${darkMode ? " dark-mode" : ""}`}>
      <header className="parali-header">
        <div className="parali-brand">
          <div className="parali-logo">
            <Leaf size={20} strokeWidth={2.3} />
          </div>

          <div>
            <div className="parali-brand-name">
              PROJECT <span>PARALI</span>
            </div>
            <div className="parali-brand-sub">
              Satellite Intelligence for Crop Transition
            </div>
          </div>
        </div>

        <nav className="parali-nav">
          <button
            type="button"
            onClick={() =>
              scrollTo("project-explanation")
            }
          >
            Project
          </button>
          <button
            type="button"
            onClick={() =>
              scrollTo("satellite-signals")
            }
          >
            Signals
          </button>
          <button
            type="button"
            onClick={() =>
              scrollTo("satellite-monitoring")
            }
          >
            Monitoring
          </button>
          <button
            type="button"
            onClick={() =>
              scrollTo("field-analysis")
            }
          >
            Analysis
          </button>
          <button
            type="button"
            onClick={() =>
              scrollTo("burn-detection")
            }
          >
            Burn
          </button>
        </nav>

        <div className="parali-header-actions">
          <button
            type="button"
            className="theme-toggle"
            aria-label={
              darkMode
                ? "Switch to light mode"
                : "Switch to dark mode"
            }
            title={
              darkMode
                ? "Switch to light mode"
                : "Switch to dark mode"
            }
            onClick={() => setDarkMode((current) => !current)}
          >
            {darkMode ? (
              <Sun size={15} strokeWidth={2.2} />
            ) : (
              <Moon size={15} strokeWidth={2.2} />
            )}
            <span>{darkMode ? "LIGHT" : "DARK"}</span>
          </button>

          <div className="parali-live-status">
            <span className="live-dot" />
            API LINKED
          </div>
        </div>
      </header>


      <main>
        <section className="parali-hero">
          <div className="hero-grid-overlay" />

          <div className="hero-content">
            <div className="hero-kicker">
              <span className="kicker-line" />
              AGRI-TECH / SANGRUR / LIVE
            </div>

            <div className="hero-title-wrap">
              <div className="hero-index">
                01
              </div>

              <h1>
                See the
                <span> harvest </span>
                before the smoke.
              </h1>
            </div>

            <p className="hero-copy">
              Project Parali turns Sentinel-2 observations into
              field-level crop-transition signals and live burn
              intelligence — giving each selected field a clear
              satellite evidence trail.
            </p>

            <div className="hero-actions">
              <button
                type="button"
                className="hero-primary-action"
                onClick={() =>
                  scrollTo(
                    "satellite-monitoring"
                  )
                }
              >
                <LocateFixed size={17} />
                Explore field map
                <ChevronRight size={17} />
              </button>

              <button
                type="button"
                className="hero-secondary-action"
                onClick={() =>
                  scrollTo(
                    "project-explanation"
                  )
                }
              >
                How it works
                <ArrowDownRight size={16} />
              </button>
            </div>

            <div className="hero-metrics">
              <div>
                <span>Fields in view</span>
                <strong>
                  {dashboardStats.totalFields.toLocaleString()}
                </strong>
              </div>

              <div>
                <span>Transition candidates</span>
                <strong>
                  {dashboardStats.transitionCandidates.toLocaleString()}
                </strong>
              </div>

              <div>
                <span>Signal engine</span>
                <strong>
                  NDVI / NBR
                </strong>
              </div>
            </div>
          </div>

          <div className="hero-art">
            <div className="hero-orbit hero-orbit-one" />
            <div className="hero-orbit hero-orbit-two" />
            <div className="hero-orbit hero-orbit-three" />

            <div className="hero-satellite-card">
              <div className="satellite-card-top">
                <span>FIELD TELEMETRY</span>
                <Radio size={15} />
              </div>

              <div className="satellite-card-number">
                {fieldId || "—"}
              </div>

              <div className="satellite-card-caption">
                {fieldId
                  ? "Logical field selected"
                  : "Select a field to begin"}
              </div>

              <div className="satellite-card-wave">
                <span />
                <span />
                <span />
                <span />
                <span />
                <span />
                <span />
                <span />
              </div>
            </div>

            <div className="hero-coordinate-chip">
              <Crosshair size={13} />
              <span>Sentinel-2 / 10m context</span>
            </div>
          </div>
        </section>


        <section
          id="project-explanation"
          className="parali-section project-section"
        >
          <div className="section-rail">
            <span>PROJECT EXPLANATION</span>
            <span>02</span>
          </div>

          <div className="section-main">
            <div className="section-heading-wide">
              <div>
                <div className="section-overline">
                  THE SYSTEM IN ONE GLANCE
                </div>

                <h2>
                  From satellite pixels
                  <span> to field intelligence.</span>
                </h2>
              </div>

              <p>
                The interface is built around one simple interaction:
                pick a field, then follow the evidence. Historical
                field context remains visible while live Sentinel-2
                observations provide the current monitoring layer.
              </p>
            </div>

            <div className="project-flow">
              <article className="flow-card flow-card-dark">
                <div className="flow-number">01</div>
                <Satellite size={22} />
                <h3>Observe</h3>
                <p>
                  Sentinel-2 imagery is translated into NDVI and NBR
                  time-series signals for the selected field.
                </p>
              </article>

              <div className="flow-arrow">
                <ChevronRight size={19} />
              </div>

              <article className="flow-card">
                <div className="flow-number">02</div>
                <Activity size={22} />
                <h3>Interpret</h3>
                <p>
                  Changes in vegetation and spectral response are
                  surfaced as transparent crop-transition signals.
                </p>
              </article>

              <div className="flow-arrow">
                <ChevronRight size={19} />
              </div>

              <article className="flow-card">
                <div className="flow-number">03</div>
                <ShieldCheck size={22} />
                <h3>Inspect</h3>
                <p>
                  Burn detection and field analysis give the selected
                  location a second, independent monitoring view.
                </p>
              </article>
            </div>

            <div className="project-note">
              <Sparkles size={17} />
              <div>
                <strong>Designed around evidence, not a single score.</strong>
                <span>
                  The current system presents satellite-derived
                  indicators as monitoring evidence rather than a
                  confirmed harvest date or calibrated probability.
                </span>
              </div>
            </div>
          </div>
        </section>


        <section
          id="satellite-signals"
          className="parali-section signals-section"
        >
          <div className="section-rail">
            <span>SATELLITE SIGNALS</span>
            <span>03</span>
          </div>

          <div className="section-main">
            <div className="section-heading-wide">
              <div>
                <div className="section-overline">
                  FIELD SIGNAL LANDSCAPE
                </div>
                <h2>
                  What the
                  <span> satellites are seeing.</span>
                </h2>
              </div>

              <p>
                These counts summarize the loaded field indicators.
                They describe observed trends and candidate
                transitions, not validated outcomes.
              </p>
            </div>

            <div className="signal-stat-grid">
              <article className="signal-stat-card">
                <div className="signal-stat-icon">
                  <TrendingDown size={19} />
                </div>
                <span>NDVI decreasing</span>
                <strong>
                  {trendStats.ndviDecreasing}
                </strong>
                <small>
                  Fields with a decreasing vegetation trend
                </small>
              </article>

              <article className="signal-stat-card signal-stat-card-accent">
                <div className="signal-stat-icon">
                  <Waves size={19} />
                </div>
                <span>NBR decreasing</span>
                <strong>
                  {trendStats.nbrDecreasing}
                </strong>
                <small>
                  Fields with a decreasing NBR trend
                </small>
              </article>

              <article className="signal-stat-card">
                <div className="signal-stat-icon">
                  <Target size={19} />
                </div>
                <span>Both decreasing</span>
                <strong>
                  {trendStats.bothDecreasing}
                </strong>
                <small>
                  Fields where both indicators are decreasing
                </small>
              </article>

              <article className="signal-stat-card">
                <div className="signal-stat-icon">
                  <Sparkles size={19} />
                </div>
                <span>Transition candidates</span>
                <strong>
                  {dashboardStats.transitionCandidates}
                </strong>
                <small>
                  Existing candidate-transition indicator
                </small>
              </article>
            </div>

            <div className="signal-chart-card">
              <div className="signal-chart-header">
                <div>
                  <span>FIELD RELATIONSHIP</span>
                  <h3>Area vs NDVI decline</h3>
                </div>

                <div className="signal-chart-legend">
                  <span className="signal-legend-dot" />
                  Field observations
                </div>
              </div>

              <FieldAreaDeclineChart
                data={trendStats.scatterData}
              />
            </div>
          </div>
        </section>


        <section
          id="satellite-monitoring"
          className="parali-section monitoring-section"
        >
          <div className="section-rail">
            <span>SATELLITE MONITORING</span>
            <span>04</span>
          </div>

          <div className="section-main">
            <div className="section-heading-wide monitoring-heading">
              <div>
                <div className="section-overline">
                  LIVE FIELD ATLAS
                </div>
                <h2>
                  Explore every
                  <span> monitored polygon.</span>
                </h2>
              </div>

              <div className="monitoring-counter">
                <span>Visible</span>
                <strong>
                  {filteredGeojson?.features?.length || 0}
                </strong>
                <small>
                  / {dashboardStats.totalFields}
                </small>
              </div>
            </div>

            <div className="monitoring-toolbar">
              <label className="monitoring-search">
                <ScanSearch size={17} />
                <input
                  type="text"
                  value={fieldSearch}
                  onChange={(event) =>
                    setFieldSearch(
                      event.target.value
                    )
                  }
                  placeholder="Search field 34, 343, 2021_343..."
                />
                {fieldSearch && (
                  <button
                    type="button"
                    onClick={() =>
                      setFieldSearch("")
                    }
                    aria-label="Clear field search"
                  >
                    <X size={15} />
                  </button>
                )}
              </label>

              <div className="monitoring-filters">
                {[
                  ["all", "All"],
                  ["unburnt", "Unburnt"],
                  ["partially_burnt", "Partial"],
                  ["completely_burnt", "Burnt"],
                  [
                    "golden_yellow_unburnt",
                    "Golden"
                  ],
                  ["green_unburnt", "Green"]
                ].map(
                  ([value, label]) => (
                    <button
                      type="button"
                      key={value}
                      className={
                        categoryFilter ===
                        value
                          ? "filter-chip active"
                          : "filter-chip"
                      }
                      onClick={() =>
                        setCategoryFilter(
                          value
                        )
                      }
                    >
                      {label}
                    </button>
                  )
                )}
              </div>
            </div>

            {mapError && (
              <div className="parali-inline-error">
                {mapError}
              </div>
            )}

            <div className="map-frame">
              <div className="map-frame-topline">
                <div className="map-frame-label">
                  <span className="map-live-dot" />
                  SATELLITE LAYER
                </div>

                <span>
                  Click a polygon or field number
                </span>
              </div>

              <div className="map-frame-body">
                {mapLoading ? (
                  <div className="map-loading">
                    <div className="map-loader-ring" />
                    <strong>
                      Loading field atlas...
                    </strong>
                    <span>
                      Connecting to Project Parali field geometry.
                    </span>
                  </div>
                ) : filteredGeojson?.features?.length ? (
                  <FieldMap
                    geojson={filteredGeojson}
                    onFieldSelect={
                      handleFieldSelect
                    }
                  />
                ) : (
                  <div className="map-loading">
                    <MapPinned size={25} />
                    <strong>
                      No fields match the current filter.
                    </strong>
                    <span>
                      Reset the search or category filter to continue.
                    </span>
                  </div>
                )}

                <MapLegend />
              </div>
            </div>
          </div>
        </section>


        <section
          id="field-analysis"
          className="parali-section field-analysis-section"
        >
          <div className="section-rail">
            <span>FIELD ANALYSIS</span>
            <span>05</span>
          </div>

          <div className="section-main">
            <div className="section-heading-wide">
              <div>
                <div className="section-overline">
                  SELECTED FIELD
                </div>
                <h2>
                  Turn one polygon into a
                  <span> complete evidence trail.</span>
                </h2>
              </div>

              <p>
                Select a logical field number to pull the current
                satellite analysis. Source-year records remain
                resolved by the backend while the interface keeps
                the field view simple.
              </p>
            </div>

            <div className="field-command-card">
              <div className="field-command-top">
                <div className="field-command-badge">
                  <Crosshair size={17} />
                </div>

                <div>
                  <span>FIELD ID</span>
                  <strong>
                    {fieldId || "Awaiting selection"}
                  </strong>
                </div>

                {fieldId && (
                  <button
                    type="button"
                    className="field-clear-button"
                    onClick={clearField}
                  >
                    <X size={16} />
                  </button>
                )}
              </div>

              <div className="field-command-form">
                <label>
                  <span>
                    Analyze a logical field directly
                  </span>
                  <input
                    type="text"
                    value={fieldId}
                    onChange={(event) =>
                      setFieldId(
                        event.target.value
                          .trim()
                      )
                    }
                    placeholder="e.g. 34 or 343"
                    onKeyDown={(event) => {
                      if (
                        event.key ===
                        "Enter"
                      ) {
                        analyzeField();
                      }
                    }}
                  />
                </label>

                <button
                  type="button"
                  onClick={() =>
                    analyzeField()
                  }
                  disabled={fieldLoading}
                >
                  {fieldLoading ? (
                    <>
                      <span className="button-spinner" />
                      Reading field...
                    </>
                  ) : (
                    <>
                      <Satellite size={17} />
                      Open analysis
                    </>
                  )}
                </button>
              </div>

              {fieldError && (
                <div className="parali-inline-error">
                  {fieldError}
                </div>
              )}

              {!fieldData && !fieldLoading && !fieldError && (
                <div className="analysis-waiting">
                  <Radio size={18} />
                  <span>
                    Choose a field on the map or enter a field number
                    to begin.
                  </span>
                </div>
              )}

              {fieldData && !fieldLoading && (
                <div className="analysis-snapshot">
                  <div className="analysis-snapshot-main">
                    <div className="analysis-status-line">
                      <span className="status-pulse" />
                      SATELLITE ANALYSIS READY
                    </div>

                    <h3>
                      Field {fieldData.field_id}
                    </h3>

                    <p>
                      {formatLabel(
                        selectedCategory ||
                          "field analysis"
                      )}
                    </p>
                  </div>

                  <div className="analysis-snapshot-grid">
                    <div>
                      <span>Area</span>
                      <strong>
                        {indicators?.area_hectares != null
                          ? `${indicators.area_hectares} ha`
                          : "N/A"}
                      </strong>
                    </div>

                    <div>
                      <span>NDVI trend</span>
                      <strong>
                        {formatLabel(
                          indicators?.ndvi_trend
                        )}
                      </strong>
                    </div>

                    <div>
                      <span>NBR trend</span>
                      <strong>
                        {formatLabel(
                          indicators?.nbr_trend
                        )}
                      </strong>
                    </div>

                    <div>
                      <span>Latest scene</span>
                      <strong>
                        {latestObservation?.date ||
                          "N/A"}
                      </strong>
                    </div>
                  </div>

                  <div className="analysis-signal-banner">
                    <div>
                      <span>Current signal</span>
                      <strong>
                        {harvestPrediction?.status_label ||
                          "Satellite assessment available"}
                      </strong>
                    </div>

                    <div className="analysis-signal-level">
                      {harvestPrediction?.signal_level ||
                        "Unknown"}
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="analysis-guidance">
              <div className="guidance-icon">
                <TrendingUp size={19} />
              </div>

              <div>
                <strong>
                  One field. Multiple signals. One view.
                </strong>
                <span>
                  The analysis drawer combines the selected field's
                  historical context, current NDVI/NBR evidence and
                  Sentinel-2 timeline without mixing the evidence
                  layers together.
                </span>
              </div>
            </div>
          </div>
        </section>


        <section
          id="burn-detection"
          className="parali-section burn-section"
        >
          <div className="section-rail">
            <span>BURN DETECTION</span>
            <span>06</span>
          </div>

          <div className="section-main">
            <div className="section-heading-wide">
              <div>
                <div className="section-overline">
                  LIVE SATELLITE MONITORING
                </div>
                <h2>
                  Detect spectral
                  <span> burn-related signals.</span>
                </h2>
              </div>

              <p>
                Run a live Sentinel-2 burn assessment against the
                selected field. The result remains an evidence signal,
                not a confirmed fire event.
              </p>
            </div>

            <BurnDetector
              fieldId={fieldId}
              fieldData={fieldData}
            />
          </div>
        </section>
      </main>


      <FieldDrawer
        fieldData={fieldData}
        harvestPrediction={
          harvestPrediction
        }
        harvestLoading={
          harvestLoading
        }
        harvestError={
          harvestError
        }
        open={Boolean(fieldData)}
        loading={fieldLoading}
        error={fieldError}
        onClose={clearField}
        onAnalyze={() =>
          analyzeField(fieldId)
        }
      />


      <footer className="parali-footer">
        <div className="footer-brand">
          <div className="parali-logo small">
            <Leaf size={16} />
          </div>
          <span>
            PROJECT PARALI
          </span>
        </div>

        <div className="footer-copy">
          Satellite evidence layer · Sangrur
        </div>

        <div className="footer-right">
          <span>NDVI</span>
          <span>NBR</span>
          <span>LIVE MONITORING</span>
        </div>
      </footer>
    </div>
  );
}

export default App;