import {
  useEffect,
  useMemo,
  useState
} from "react";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  ZAxis
} from "recharts";

import "./styles.css";

import FieldMap from "./FieldMap.jsx";

import DashboardCards from "./components/DashboardCards.jsx";
import IntelligencePanel from "./components/IntelligencePanel.jsx";
import FieldDrawer from "./components/FieldDrawer.jsx";
import MapLegend from "./components/MapLegend.jsx";
import BurnDetector from "./components/BurnDetector.jsx";

const API_URL = "http://127.0.0.1:8000";


function FieldAreaDeclineChart({ data }) {
  const points = Array.isArray(data) ? data.filter(
    (point) =>
      Number.isFinite(Number(point?.area)) &&
      Number.isFinite(Number(point?.decline))
  ) : [];

  if (points.length === 0) {
    return (
      <div className="chart-empty-state">
        <strong>No valid field trend data available.</strong>
        <span>Area and NDVI-decline values are required for this chart.</span>
      </div>
    );
  }

  const width = 900;
  const height = 360;
  const margin = { top: 24, right: 28, bottom: 58, left: 68 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;

  const areas = points.map((p) => Number(p.area));
  const declines = points.map((p) => Number(p.decline));

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
    margin.left + ((value - minX) / Math.max(maxX - minX, 0.0001)) * innerWidth;

  const yScale = (value) =>
    margin.top + innerHeight - ((value - minY) / Math.max(maxY - minY, 0.0001)) * innerHeight;

  const tickCount = 5;
  const xTicks = Array.from({ length: tickCount }, (_, index) =>
    minX + ((maxX - minX) * index) / (tickCount - 1)
  );
  const yTicks = Array.from({ length: tickCount }, (_, index) =>
    minY + ((maxY - minY) * index) / (tickCount - 1)
  );

  return (
    <div className="scatter-chart-frame" style={{ width: "100%", height: "360px" }}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        height="100%"
        role="img"
        aria-label="Field area versus NDVI decline scatter plot"
      >
        <rect x="0" y="0" width={width} height={height} fill="#ffffff" />

        {yTicks.map((tick, index) => {
          const y = yScale(tick);
          return (
            <g key={`y-${index}`}>
              <line
                x1={margin.left}
                x2={width - margin.right}
                y1={y}
                y2={y}
                stroke="#e5e7eb"
                strokeDasharray="3 3"
              />
              <text
                x={margin.left - 10}
                y={y + 4}
                textAnchor="end"
                fontSize="11"
                fill="#64748b"
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
                stroke="#f1f5f9"
              />
              <text
                x={x}
                y={height - margin.bottom + 22}
                textAnchor="middle"
                fontSize="11"
                fill="#64748b"
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
          stroke="#94a3b8"
        />
        <line
          x1={margin.left}
          x2={margin.left}
          y1={margin.top}
          y2={height - margin.bottom}
          stroke="#94a3b8"
        />

        {points.map((point, index) => {
          const area = Number(point.area);
          const decline = Number(point.decline);
          const x = xScale(area);
          const y = yScale(decline);

          return (
            <circle
              key={`${point.fieldId}-${index}`}
              cx={x}
              cy={y}
              r="4.5"
              fill="#166534"
              fillOpacity="0.72"
              stroke="#14532d"
              strokeWidth="1"
            >
              <title>
                {`Field ${point.fieldId} | Area: ${area.toFixed(4)} ha | NDVI decline: ${decline.toFixed(4)}`}
              </title>
            </circle>
          );
        })}

        <text
          x={margin.left + innerWidth / 2}
          y={height - 10}
          textAnchor="middle"
          fontSize="12"
          fontWeight="600"
          fill="#334155"
        >
          Field area (ha)
        </text>

        <text
          x="16"
          y={margin.top + innerHeight / 2}
          textAnchor="middle"
          fontSize="12"
          fontWeight="600"
          fill="#334155"
          transform={`rotate(-90 16 ${margin.top + innerHeight / 2})`}
        >
          NDVI decline
        </text>
      </svg>
    </div>
  );
}


function App() {

  // =====================================================
  // BURN DETECTION STATE
  // =====================================================

  const [rgbFile, setRgbFile] = useState(null);

  const [swirFile, setSwirFile] = useState(null);

  const [result, setResult] = useState(null);

  const [loading, setLoading] = useState(false);

  const [error, setError] = useState("");


  // =====================================================
  // SATELLITE FIELD ANALYSIS STATE
  // =====================================================

  // IMPORTANT:
  // Field IDs are globally unique strings.
  //
  // Examples:
  // 2020_34
  // 2021_34
  //
  // Do NOT convert these IDs to numbers.

  const [fieldId, setFieldId] = useState("2020_1");

  const [fieldData, setFieldData] = useState(null);
  const [residueEstimate, setResidueEstimate] = useState(null);
  const [residueLoading, setResidueLoading] = useState(false);
  const [residueError, setResidueError] = useState("");

  const [biomassOpportunity, setBiomassOpportunity] = useState(null);
  const [biomassOpportunityLoading, setBiomassOpportunityLoading] = useState(false);
  const [biomassOpportunityError, setBiomassOpportunityError] = useState("");

  const [clusterEstimate, setClusterEstimate] = useState(null);
  const [clusterLoading, setClusterLoading] = useState(false);
  const [clusterError, setClusterError] = useState("");

  const [logisticsEstimate, setLogisticsEstimate] = useState(null);
  const [logisticsLoading, setLogisticsLoading] = useState(false);
  const [logisticsError, setLogisticsError] = useState("");

  const [fieldLoading, setFieldLoading] = useState(false);

  const [fieldError, setFieldError] = useState("");

  // =====================================================
  // HARVEST PREDICTION STATE
  // =====================================================

  const [harvestPrediction, setHarvestPrediction] = useState(null);

  const [harvestLoading, setHarvestLoading] = useState(false);

  const [harvestError, setHarvestError] = useState("");


  // =====================================================
  // FIELD MAP STATE
  // =====================================================

  const [geojson, setGeojson] = useState(null);

  const [mapLoading, setMapLoading] = useState(true);

  const [mapError, setMapError] = useState("");

  // =====================================================
  // DASHBOARD FILTER STATE
  // =====================================================

  const [fieldSearch, setFieldSearch] = useState("");

  const [categoryFilter, setCategoryFilter] = useState("all");


  // =====================================================
  // LOAD FIELD MAP
  // =====================================================

  useEffect(() => {

    const loadFields = async () => {

      setMapLoading(true);

      setMapError("");

      try {

        const response = await fetch(
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

      } catch (err) {

        console.error(
          "Field map error:",
          err
        );

        setMapError(
          err.message
        );

      } finally {

        setMapLoading(false);

      }

    };

    loadFields();

  }, []);


  // =====================================================
  // BURN PREDICTION
  // =====================================================

  const handlePredict = async () => {

    if (!rgbFile || !swirFile) {

      setError(
        "Please select both RGB and SWIR images."
      );

      return;
    }


    setLoading(true);

    setError("");

    setResult(null);


    const formData = new FormData();

    formData.append(
      "rgb_image",
      rgbFile
    );

    formData.append(
      "swir_image",
      swirFile
    );


    try {

      const response = await fetch(
        `${API_URL}/predict`,
        {
          method: "POST",
          body: formData
        }
      );


      const data = await response.json();


      if (!response.ok) {

        throw new Error(
          data.detail ||
          "Prediction failed"
        );

      }


      setResult(data);

    } catch (err) {

      setError(
        err.message
      );

    } finally {

      setLoading(false);

    }

  };


  // =====================================================
  // FIELD SATELLITE ANALYSIS
  // =====================================================

  const analyzeField = async (
    selectedFieldId = fieldId
  ) => {

    // ---------------------------------------------------
    // Normalize the field ID as a STRING.
    //
    // This is important because IDs such as:
    //
    // 2020_34
    // 2021_34
    //
    // contain an underscore.
    // ---------------------------------------------------

    const normalizedFieldId = String(
      selectedFieldId || ""
    ).trim();


    if (!normalizedFieldId) {

      setFieldError(
        "Please select a field."
      );

      return;
    }


    setFieldLoading(true);

    setFieldError("");

    setFieldData(null);


    // Keep input synchronized
    // with selected map field.

    setFieldId(
      normalizedFieldId
    );


    try {

      const encodedFieldId =
        encodeURIComponent(
          normalizedFieldId
        );


      const response = await fetch(
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

      setHarvestPrediction(
        data?.harvest_prediction ||
        null
      );

      setHarvestError("");

      // Load residue, biomass cluster, and logistics estimates independently.
      // A failure in one planning layer should not hide the satellite field analysis.
      setResidueLoading(true);
      setResidueError("");
      setBiomassOpportunityLoading(true);
      setBiomassOpportunityError("");
      setClusterLoading(true);
      setClusterError("");
      setLogisticsLoading(true);
      setLogisticsError("");
      setResidueEstimate(null);
      setBiomassOpportunity(null);
      setClusterEstimate(null);
      setLogisticsEstimate(null);

      const loadPlanningEstimate = async (path, setter, setErrorState, label) => {
        try {
          const estimateResponse = await fetch(`${API_URL}${path}`);
          const estimateData = await estimateResponse.json();

          if (!estimateResponse.ok) {
            throw new Error(
              estimateData.detail ||
              `${label} failed`
            );
          }

          setter(estimateData);
        } catch (estimateErr) {
          console.error(`${label} error:`, estimateErr);
          setter(null);
          setErrorState(estimateErr.message);
        }
      };

      await Promise.all([
        loadPlanningEstimate(
          `/residue-estimation/${encodedFieldId}`,
          setResidueEstimate,
          setResidueError,
          "Residue estimation"
        ),
        loadPlanningEstimate(
          `/biomass-opportunity/${encodedFieldId}`,
          setBiomassOpportunity,
          setBiomassOpportunityError,
          "Biomass opportunity"
        ),
        loadPlanningEstimate(
          `/biomass-cluster/${encodedFieldId}?radius_km=5&truck_capacity_tonnes=10`,
          setClusterEstimate,
          setClusterError,
          "Biomass cluster estimation"
        ),
        loadPlanningEstimate(
          `/logistics-estimation/${encodedFieldId}`,
          setLogisticsEstimate,
          setLogisticsError,
          "Logistics estimation"
        )
      ]);

      setResidueLoading(false);
      setBiomassOpportunityLoading(false);
      setClusterLoading(false);
      setLogisticsLoading(false);

    } catch (err) {

      console.error(
        "Field analysis error:",
        err
      );


      setFieldError(
        err.message
      );

    } finally {

      setFieldLoading(false);

    }

  };


  // =====================================================
  // HARVEST PREDICTION
  // =====================================================

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

    try {

      const response = await fetch(
        `${API_URL}/harvest-prediction/${encodeURIComponent(
          normalizedFieldId
        )}`
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
          "Harvest prediction failed"
        );
      }

      setHarvestPrediction(
        data.prediction || null
      );

    } catch (err) {

      console.error(
        "Harvest prediction error:",
        err
      );

      setHarvestPrediction(null);
      setHarvestError(err.message);

    } finally {
      setHarvestLoading(false);
    }

  };


  // =====================================================
  // FIELD MAP SELECTION
  // =====================================================

  const handleFieldSelect = (
    selectedFieldId
  ) => {

    const normalizedFieldId = String(
      selectedFieldId || ""
    ).trim();


    if (!normalizedFieldId) {

      return;

    }


    setFieldId(
      normalizedFieldId
    );


    analyzeField(
      normalizedFieldId
    );

    // Scroll to field analysis.

    setTimeout(() => {

      const element =
        document.getElementById(
          "field-analysis"
        );


      if (element) {

        element.scrollIntoView({
          behavior: "smooth",
          block: "start"
        });

      }

    }, 100);

  };


  // =====================================================
  // FIELD INDICATORS
  // =====================================================

  const indicators =
    fieldData?.field_indicators ||
    null;


  // =====================================================
  // DASHBOARD STATISTICS + FILTERING
  // =====================================================

  const dashboardStats = useMemo(() => {

    const features =
      geojson?.features || [];

    const normalizeCategory = (value) =>
      String(value || "")
        .toLowerCase()
        .trim()
        .replace(/-/g, "_")
        .replace(/\s+/g, "_");

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

    const totalFields =
      features.length;

    const completelyBurnt =
      features.filter(
        (feature) =>
          categoryOf(feature) ===
          "completely_burnt"
      ).length;

    const partiallyBurnt =
      features.filter(
        (feature) =>
          categoryOf(feature) ===
          "partially_burnt"
      ).length;

    const transitionCandidates =
      features.filter(
        (feature) =>
          normalizeCategory(
            feature?.properties?.field_status ??
            feature?.properties?.indicators?.field_status ??
            feature?.properties?.field_indicators?.field_status
          ) ===
          "crop_transition_candidate"
      ).length;

    return {
      totalFields,
      completelyBurnt,
      partiallyBurnt,
      transitionCandidates
    };

  }, [geojson]);


  const filteredGeojson = useMemo(() => {

    if (!geojson) {
      return null;
    }

    const normalizedSearch =
      fieldSearch
        .toLowerCase()
        .trim();

    const normalizeCategory = (value) =>
      String(value || "")
        .toLowerCase()
        .trim()
        .replace(/-/g, "_")
        .replace(/\s+/g, "_");

    const features =
      (geojson.features || [])
        .filter((feature) => {

          const properties =
            feature?.properties || {};

          const id = String(
            properties.field_id ??
            properties.id ??
            ""
          ).toLowerCase();

          const category =
            normalizeCategory(
              properties.category ??
              properties.field_category ??
              properties.indicators?.category ??
              properties.field_indicators?.category
            );

          const matchesSearch =
            !normalizedSearch ||
            id.includes(
              normalizedSearch
            );

          const matchesCategory =
            categoryFilter === "all" ||
            category ===
              categoryFilter;

          return (
            matchesSearch &&
            matchesCategory
          );

        });

    return {
      ...geojson,
      features
    };

  }, [
    geojson,
    fieldSearch,
    categoryFilter
  ]);


  const filteredFieldCount =
    filteredGeojson?.features?.length || 0;


  // =====================================================
  // FIELD MONITORING TABLE
  // =====================================================

  const monitoringFields = useMemo(() => {

    const features = geojson?.features || [];

    const normalizeCategory = (value) =>
      String(value || "")
        .toLowerCase()
        .trim()
        .replace(/-/g, "_")
        .replace(/\s+/g, "_");

    const numeric = (value) => {
      const number = Number(value);
      return Number.isFinite(number) ? number : null;
    };

    return features
      .map((feature) => {

        const properties =
          feature?.properties || {};

        const indicators =
          properties.field_indicators ||
          properties.indicators ||
          {};

        const category =
          normalizeCategory(
            properties.category ??
            properties.field_category ??
            indicators.category
          );

        const fieldId = String(
          properties.field_id ??
          properties.id ??
          ""
        );

        const area = numeric(
          indicators.area_hectares ??
          properties.area_hectares
        );

        const decline = numeric(
          indicators.decline ??
          properties.decline
        );

        const candidateDate =
          indicators.candidate_date ??
          properties.candidate_date ??
          null;

        const status =
          indicators.field_status ??
          properties.field_status ??
          "";

        const ndviTrend =
          indicators.ndvi_trend ??
          properties.ndvi_trend ??
          "";

        const nbrTrend =
          indicators.nbr_trend ??
          properties.nbr_trend ??
          "";

        return {
          fieldId,
          category,
          area,
          decline,
          candidateDate,
          status,
          ndviTrend,
          nbrTrend
        };

      })
      .filter((field) => field.fieldId)
      .filter((field) => {
        const normalizedSearch =
          fieldSearch.toLowerCase().trim();

        const matchesSearch =
          !normalizedSearch ||
          field.fieldId
            .toLowerCase()
            .includes(normalizedSearch);

        const matchesCategory =
          categoryFilter === "all" ||
          field.category === categoryFilter;

        return matchesSearch && matchesCategory;
      })
      .sort((a, b) => {
        const declineA = a.decline ?? -Infinity;
        const declineB = b.decline ?? -Infinity;

        return declineB - declineA;
      })
      .slice(0, 10);

  }, [
    geojson,
    fieldSearch,
    categoryFilter
  ]);


  // =====================================================
  // TREND OVERVIEW
  // =====================================================

  const trendStats = useMemo(() => {

    const features = geojson?.features || [];

    const normalize = (value) =>
      String(value || "")
        .toLowerCase()
        .trim();

    let ndviDecreasing = 0;
    let nbrDecreasing = 0;
    let bothDecreasing = 0;

    const scatterData = [];

    features.forEach((feature) => {

      const properties = feature?.properties || {};

      const indicators =
        properties.field_indicators ||
        properties.indicators ||
        {};

      const ndviTrend = normalize(
        indicators.ndvi_trend ??
        properties.ndvi_trend
      );

      const nbrTrend = normalize(
        indicators.nbr_trend ??
        properties.nbr_trend
      );

      if (ndviTrend === "decreasing") {
        ndviDecreasing += 1;
      }

      if (nbrTrend === "decreasing") {
        nbrDecreasing += 1;
      }

      if (
        ndviTrend === "decreasing" &&
        nbrTrend === "decreasing"
      ) {
        bothDecreasing += 1;
      }

      const area = Number(
        indicators.area_hectares ??
        properties.area_hectares
      );

      const decline = Number(
        indicators.decline ??
        properties.decline
      );

      const fieldId = String(
        properties.field_id ??
        properties.id ??
        ""
      );

      if (
        fieldId &&
        Number.isFinite(area) &&
        Number.isFinite(decline)
      ) {
        scatterData.push({
          fieldId,
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


  // =====================================================
  // FIELD INTELLIGENCE PRIORITIZATION
  // =====================================================

  // This is a transparent dashboard heuristic, not an ML
  // prediction or validated burn/harvest forecast.
  const fieldIntelligence = useMemo(() => {

    const features = geojson?.features || [];

    const normalize = (value) =>
      String(value || "")
        .toLowerCase()
        .trim()
        .replace(/-/g, "_")
        .replace(/\s+/g, "_");

    const numeric = (value) => {
      const number = Number(value);
      return Number.isFinite(number) ? number : null;
    };

    const getField = (feature) => {

      const properties = feature?.properties || {};

      const indicators =
        properties.field_indicators ||
        properties.indicators ||
        {};

      const category = normalize(
        properties.category ??
        properties.field_category ??
        indicators.category
      );

      const fieldId = String(
        properties.field_id ??
        properties.id ??
        ""
      );

      const fieldStatus = normalize(
        indicators.field_status ??
        properties.field_status
      );

      const ndviTrend = normalize(
        indicators.ndvi_trend ??
        properties.ndvi_trend
      );

      const nbrTrend = normalize(
        indicators.nbr_trend ??
        properties.nbr_trend
      );

      const candidateDate =
        indicators.candidate_date ??
        properties.candidate_date ??
        null;

      const decline = numeric(
        indicators.decline ??
        properties.decline
      );

      let score = 0;

      if (
        fieldStatus ===
        "crop_transition_candidate"
      ) {
        score += 2;
      }

      if (ndviTrend === "decreasing") {
        score += 1;
      }

      if (nbrTrend === "decreasing") {
        score += 1;
      }

      if (category === "completely_burnt") {
        score += 2;
      } else if (category === "partially_burnt") {
        score += 1;
      }

      let priority = "Low attention";

      if (score >= 4) {
        priority = "High attention";
      } else if (score >= 2) {
        priority = "Medium attention";
      }

      return {
        fieldId,
        category,
        fieldStatus,
        ndviTrend,
        nbrTrend,
        candidateDate,
        decline,
        score,
        priority
      };

    };

    const fields = features
      .map(getField)
      .filter((field) => field.fieldId);

    const high = fields.filter(
      (field) =>
        field.priority === "High attention"
    ).length;

    const medium = fields.filter(
      (field) =>
        field.priority === "Medium attention"
    ).length;

    const low = fields.filter(
      (field) =>
        field.priority === "Low attention"
    ).length;

    const priorityFields = [...fields]
      .sort((a, b) => {

        if (b.score !== a.score) {
          return b.score - a.score;
        }

        return (
          (b.decline ?? -Infinity) -
          (a.decline ?? -Infinity)
        );

      })
      .slice(0, 10);

    return {
      fields,
      high,
      medium,
      low,
      priorityFields
    };

  }, [geojson]);


  // =====================================================
  // RENDER
  // =====================================================

  return (
    <div className="app">

      <header className="header">
        <div>
          <h1>🌾 Project Parali</h1>
          <p>AI-powered crop residue monitoring platform</p>
        </div>

        <div className="status">
          <span></span>
          API Connected
        </div>
      </header>

      <main className="container">

        <section className="hero">
          <span className="eyebrow">AGRI INTELLIGENCE COMMAND CENTER</span>

          <h2>AI Harvest Prediction Command Center</h2>

          <p>
            Predict near-term harvest likelihood from Sentinel-2
            NDVI/NBR time-series signals, then use burn detection
            and field intelligence as supporting evidence.
          </p>
        </section>

        {/* =================================================
            DASHBOARD OVERVIEW
        ================================================= */}

        <section className="dashboard-section">

          <div className="section-heading">
            <div>
              <span className="eyebrow">OVERVIEW</span>

              <h2>Field Intelligence Dashboard</h2>

              <p>
                Overview of the Sangrur field dataset and current
                satellite-derived monitoring indicators.
              </p>
            </div>

            <div className="map-count">
              {filteredFieldCount} / {dashboardStats.totalFields} fields
            </div>
          </div>

          <DashboardCards
            totalFields={dashboardStats.totalFields}
            completelyBurnt={dashboardStats.completelyBurnt}
            partiallyBurnt={dashboardStats.partiallyBurnt}
            transitionCandidates={
              dashboardStats.transitionCandidates
            }
          />

          <div className="dashboard-filters">

            <div className="filter-field">
              <label htmlFor="field-search">
                Search field
              </label>

              <input
                id="field-search"
                type="text"
                value={fieldSearch}
                onChange={(e) =>
                  setFieldSearch(e.target.value)
                }
                placeholder="Search field ID e.g. 2021_34"
              />
            </div>

            <div className="filter-field">
              <label htmlFor="category-filter">
                Category
              </label>

              <select
                id="category-filter"
                value={categoryFilter}
                onChange={(e) =>
                  setCategoryFilter(e.target.value)
                }
              >
                <option value="all">
                  All Categories
                </option>

                <option value="unburnt">
                  Unburnt
                </option>

                <option value="partially_burnt">
                  Partially Burnt
                </option>

                <option value="completely_burnt">
                  Completely Burnt
                </option>

                <option value="golden_yellow_unburnt">
                  Golden Yellow Unburnt
                </option>

                <option value="green_unburnt">
                  Green Unburnt
                </option>
              </select>
            </div>

          </div>

        </section>

        {/* =================================================
            FIELD INTELLIGENCE
        ================================================= */}

        <IntelligencePanel
          high={fieldIntelligence.high}
          medium={fieldIntelligence.medium}
          low={fieldIntelligence.low}
          priorityFields={
            fieldIntelligence.priorityFields
          }
          onFieldSelect={handleFieldSelect}
        />

        {/* =================================================
            HARVEST SIGNAL
        ================================================= */}

        <section className="harvest-command-section">

          <div className="section-heading">
            <div>
              <span className="eyebrow">FIELD ANALYSIS</span>

              <h2>Harvest Signal Assessment</h2>

              <p>
                Analyze the selected field using its Sentinel-2 NDVI/NBR
                time series. The result is a crop-transition signal, not
                a calibrated probability or confirmed harvest date.
              </p>
            </div>

            {harvestPrediction?.field_id && (
              <div className="harvest-field-badge">
                Field {harvestPrediction.field_id}
              </div>
            )}
          </div>

          {harvestLoading && (
            <div className="harvest-state-card">
              <strong>Analyzing satellite signals...</strong>
              <span>Examining NDVI/NBR trends for the selected field.</span>
            </div>
          )}

          {!harvestLoading && harvestError && (
            <div className="error">
              {harvestError}
            </div>
          )}

          {!harvestLoading && !harvestError && harvestPrediction && (
            <>
              <div className="harvest-probability-grid">

                <div className="harvest-main-card">
                  <span className="harvest-card-label">
                    Current satellite assessment
                  </span>

                  <strong>
                    {harvestPrediction.status_label || "Assessment available"}
                  </strong>

                  <div className={`harvest-level harvest-level-${String(
                    harvestPrediction.signal_level || "unknown"
                  ).toLowerCase()}`}>
                    {harvestPrediction.signal_level || "Unknown"} signal
                  </div>

                  <span className="harvest-asof">
                    Based on observations through {harvestPrediction.as_of_date || "N/A"}
                  </span>
                </div>

                <div className="harvest-horizon-card">
                  <span>NDVI observations</span>
                  <strong>
                    {harvestPrediction.signals?.observations ?? "N/A"}
                  </strong>
                </div>

                <div className="harvest-horizon-card">
                  <span>Candidate transition</span>
                  <strong>
                    {harvestPrediction.signals?.candidate_date || "None"}
                  </strong>
                </div>

              </div>

              <div className="harvest-detail-grid">

                <div className="harvest-window-card">
                  <span>What the satellite evidence says</span>

                  <strong>
                    {harvestPrediction.status === "harvest_transition_signal"
                      ? "Harvest/crop-transition signal detected"
                      : harvestPrediction.status === "possible_transition"
                        ? "Possible crop-transition signal"
                        : harvestPrediction.status === "insufficient_data"
                          ? "More observations required"
                          : "No strong harvest signal"}
                  </strong>

                  <small>
                    This describes observed vegetation change. It is not a
                    confirmed harvest date.
                  </small>
                </div>

                <div className="harvest-signals-card">
                  <span>Evidence</span>

                  <ul>
                    {(harvestPrediction.reasons || []).map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                </div>

              </div>

              <div className="harvest-signal-strip">
                <div>
                  <span>NDVI decline</span>
                  <strong>
                    {harvestPrediction.signals?.ndvi_decline_from_peak ?? "N/A"}
                  </strong>
                </div>

                <div>
                  <span>Recent NDVI slope</span>
                  <strong>
                    {harvestPrediction.signals?.recent_ndvi_slope_per_day ?? "N/A"}
                  </strong>
                </div>

                <div>
                  <span>NBR decline</span>
                  <strong>
                    {harvestPrediction.signals?.nbr_decline_from_peak ?? "N/A"}
                  </strong>
                </div>

                <div>
                  <span>Latest NDVI</span>
                  <strong>
                    {harvestPrediction.signals?.latest_ndvi ?? "N/A"}
                  </strong>
                </div>
              </div>

              <div className="harvest-validation-note">
                <strong>Important:</strong>{" "}
                {harvestPrediction.validation_note}
              </div>
            </>
          )}

          {!harvestLoading && !harvestError && !harvestPrediction && (
            <div className="harvest-state-card">
              <strong>Click a field on the map to analyze it.</strong>
              <span>The selected field's satellite time series will appear here.</span>
            </div>
          )}

        </section>

        {/* =================================================
            TREND OVERVIEW
        ================================================= */}

        <section className="analytics-section">

          <div className="section-heading">
            <div>
              <span className="eyebrow">SATELLITE SIGNALS</span>

              <h2>Transition Signal Overview</h2>

              <p>
                Observed NDVI and NBR trends across the loaded
                field dataset. These are monitoring indicators,
                not confirmed burn or harvest predictions.
              </p>
            </div>
          </div>

          <div className="signal-summary">

            <div className="signal-card">
              <span>NDVI Decreasing</span>
              <strong>{trendStats.ndviDecreasing}</strong>
            </div>

            <div className="signal-card">
              <span>NBR Decreasing</span>
              <strong>{trendStats.nbrDecreasing}</strong>
            </div>

            <div className="signal-card">
              <span>Both Decreasing</span>
              <strong>{trendStats.bothDecreasing}</strong>
            </div>

          </div>

          <div className="chart-card">

            <div className="chart-header">
              <div>
                <h3>Field Area vs NDVI Decline</h3>

                <p>
                  Each point represents a field with available
                  area and NDVI-decline indicators.
                </p>
              </div>
            </div>

            <div className="chart-container">

              <FieldAreaDeclineChart data={trendStats.scatterData} />

            </div>
          </div>

        </section>

        {/* =================================================
            FIELD MAP
        ================================================= */}

        <section className="map-section">

          <div className="section-heading">

            <div>
              <span className="eyebrow">
                SATELLITE MONITORING
              </span>

              <h2>Sangrur Field Intelligence Map</h2>

              <p>
                Click a field to inspect its satellite
                indicators and crop-transition signals.
              </p>
            </div>

            <div className="map-count">
              {filteredFieldCount} fields
            </div>

          </div>

          {mapError && (
            <div className="error">
              {mapError}
            </div>
          )}

          <div className="map-shell">

            {mapLoading ? (
              <div className="map-loading">
                Loading satellite field map...
              </div>
            ) : filteredFieldCount > 0 ? (
              <FieldMap
                geojson={filteredGeojson}
                onFieldSelect={handleFieldSelect}
              />
            ) : (
              <div className="map-loading">
                {geojson
                  ? "No fields match the current filters."
                  : "Field map unavailable."}
              </div>
            )}

            <MapLegend />

          </div>

        </section>

        {/* =================================================
            FIELD DRAWER
        ================================================= */}

        <FieldDrawer
          fieldData={fieldData}
          residueEstimate={residueEstimate}
          residueLoading={residueLoading}
          residueError={residueError}
          biomassOpportunity={biomassOpportunity}
          biomassOpportunityLoading={biomassOpportunityLoading}
          biomassOpportunityError={biomassOpportunityError}
          clusterEstimate={clusterEstimate}
          clusterLoading={clusterLoading}
          clusterError={clusterError}
          logisticsEstimate={logisticsEstimate}
          logisticsLoading={logisticsLoading}
          logisticsError={logisticsError}
          open={Boolean(fieldData)}
          loading={fieldLoading}
          error={fieldError}
          onClose={() => {
            setFieldData(null);
            setFieldError("");
            setResidueEstimate(null);
            setResidueError("");
            setBiomassOpportunity(null);
            setBiomassOpportunityError("");
            setClusterEstimate(null);
            setClusterError("");
            setLogisticsEstimate(null);
            setLogisticsError("");
          }}
          onAnalyze={() => analyzeField(fieldId)}
        />

        {/* =================================================
            BURN DETECTION
        ================================================= */}

        <BurnDetector
          rgbFile={rgbFile}
          swirFile={swirFile}
          setRgbFile={setRgbFile}
          setSwirFile={setSwirFile}
          result={result}
          loading={loading}
          error={error}
          onPredict={handlePredict}
        />

        {/* =================================================
            FALLBACK FIELD ANALYSIS
        ================================================= */}

        {!fieldData && (
          <section
            id="field-analysis"
            className="analysis-placeholder"
          >
            <div>
              <span className="eyebrow">
                FIELD ANALYSIS
              </span>

              <h2>Select a field to inspect</h2>

              <p>
                Click any field on the map or select a field
                from the intelligence panel to open its
                Sentinel-2 analysis drawer.
              </p>
            </div>

            <div className="field-analysis-input">

              <input
                type="text"
                value={fieldId}
                onChange={(e) =>
                  setFieldId(e.target.value.trim())
                }
                placeholder="Field ID e.g. 2020_34"
              />

              <button
                onClick={() => analyzeField()}
                disabled={fieldLoading}
              >
                {fieldLoading
                  ? "Analyzing..."
                  : "Analyze Field"}
              </button>

            </div>

            {fieldError && (
              <div className="error">
                {fieldError}
              </div>
            )}
          </section>
        )}

      </main>

      <footer>
        Project Parali • Sentinel-2 Harvest Prediction + Dual RGB/SWIR Burn Detection
      </footer>

    </div>
  );
}

export default App;