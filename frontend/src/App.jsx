import {
  useState,
  useEffect
} from "react";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from "recharts";

import FieldMap from "./FieldMap";

import "./App.css";


const API_URL = "http://127.0.0.1:8000";


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
  // SATELLITE ANALYSIS STATE
  // =====================================================

  const [fieldId, setFieldId] = useState("1");

  const [fieldData, setFieldData] = useState(null);

  const [fieldLoading, setFieldLoading] = useState(false);

  const [fieldError, setFieldError] = useState("");


  // =====================================================
  // MAP STATE
  // =====================================================

  const [geojson, setGeojson] = useState(null);

  const [mapLoading, setMapLoading] = useState(true);


  // =====================================================
  // LOAD GEOJSON FIELDS
  // =====================================================

  useEffect(() => {

    const loadFields = async () => {

      try {

        const response = await fetch(
          `${API_URL}/fields`
        );


        const data =
          await response.json();


        if (!response.ok) {

          throw new Error(
            data.detail ||
            "Failed to load field map"
          );

        }


        setGeojson(data);

      } catch (err) {

        setFieldError(
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


      const data =
        await response.json();


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
  // ANALYZE FIELD BY ID
  // =====================================================

  const analyzeFieldById = async (
    selectedFieldId
  ) => {

    setFieldLoading(true);

    setFieldError("");

    setFieldData(null);


    try {

      const response = await fetch(
        `${API_URL}/field-analysis/${selectedFieldId}`
      );


      const data =
        await response.json();


      if (!response.ok) {

        throw new Error(
          data.detail ||
          "Field analysis failed"
        );

      }


      setFieldData(data);

    } catch (err) {

      setFieldError(
        err.message
      );

    } finally {

      setFieldLoading(false);

    }

  };


  // =====================================================
  // MANUAL FIELD ANALYSIS
  // =====================================================

  const analyzeField = () => {

    if (!fieldId) {

      setFieldError(
        "Please enter a field ID."
      );

      return;

    }


    analyzeFieldById(
      fieldId
    );

  };


  // =====================================================
  // MAP FIELD SELECTION
  // =====================================================

  const handleFieldSelect = (
    selectedFieldId
  ) => {

    setFieldId(
      String(selectedFieldId)
    );


    analyzeFieldById(
      selectedFieldId
    );

  };


  // =====================================================
  // UI
  // =====================================================

  return (

    <div className="app">


      {/* =================================================
          HEADER
      ================================================= */}

      <header className="header">

        <div>

          <h1>
            🌾 Project Parali
          </h1>


          <p>
            AI-powered crop residue
            monitoring platform
          </p>

        </div>


        <div className="status">

          <span></span>

          API Connected

        </div>

      </header>


      <main className="container">


        {/* =================================================
            HERO
        ================================================= */}

        <section className="hero">

          <h2>
            Crop Residue Intelligence
          </h2>


          <p>
            Detect burning and analyze
            satellite crop conditions.
          </p>

        </section>


        {/* =================================================
            SANGRUR FIELD MAP
        ================================================= */}

        <section className="map-card">

          <h2>
            🗺️ Sangrur Field Map
          </h2>


          <p className="section-description">

            Click any field to analyze its
            Sentinel-2 satellite data.

          </p>


          {mapLoading ? (

            <div className="map-loading">

              Loading field map...

            </div>

          ) : geojson ? (

            <FieldMap
              geojson={geojson}
              onFieldSelect={
                handleFieldSelect
              }
            />

          ) : (

            <div className="error">

              Unable to load field map.

            </div>

          )}

        </section>


        {/* =================================================
            SATELLITE FIELD ANALYSIS
        ================================================= */}

        <section className="upload-card">

          <h2>
            🛰️ Satellite Field Analysis
          </h2>


          <p className="section-description">

            Select a field from the GeoJSON
            dataset to analyze its Sentinel-2
            NDVI and NBR time series.

          </p>


          <div className="field-input">

            <input
              type="number"
              min="1"
              value={fieldId}
              onChange={(e) =>
                setFieldId(
                  e.target.value
                )
              }
              placeholder="Field ID"
            />


            <button
              onClick={analyzeField}
              disabled={fieldLoading}
            >

              {fieldLoading
                ? "Analyzing..."
                : "Analyze Satellite Data"}

            </button>

          </div>


          {fieldError && (

            <div className="error">

              {fieldError}

            </div>

          )}

        </section>


        {/* =================================================
            FIELD RESULTS
        ================================================= */}

        {fieldData && (

          <section className="result-card">

            <h2>
              🛰️ Field {fieldData.field_id}
            </h2>


            <div className="field-category">

              <span>
                Field Category
              </span>


              <strong>
                {fieldData.field_category ||
                  "Unknown"}
              </strong>

            </div>


            {/* =============================================
                LATEST OBSERVATION
            ============================================= */}

            <h3>
              Latest Satellite Observation
            </h3>


            <div className="metrics">

              <div className="metric">

                <span>
                  Date
                </span>


                <strong>

                  {
                    fieldData
                      .latest_observation
                      .date
                  }

                </strong>

              </div>


              <div className="metric">

                <span>
                  NDVI
                </span>


                <strong>

                  {
                    fieldData
                      .latest_observation
                      .ndvi
                  }

                </strong>

              </div>


              <div className="metric">

                <span>
                  NBR
                </span>


                <strong>

                  {
                    fieldData
                      .latest_observation
                      .nbr
                  }

                </strong>

              </div>

            </div>


            {/* =============================================
                TRANSITION ANALYSIS
            ============================================= */}

            {fieldData.transition_analysis && (

              <div className="transition-box">

                <h3>
                  🌱 Crop Transition Analysis
                </h3>


                <p>

                  Peak NDVI:

                  <strong>

                    {" "}

                    {
                      fieldData
                        .transition_analysis
                        .peak_ndvi
                    }

                  </strong>

                </p>


                <p>

                  Peak Date:

                  <strong>

                    {" "}

                    {
                      fieldData
                        .transition_analysis
                        .peak_date
                    }

                  </strong>

                </p>


                <p>

                  Candidate Transition:

                  <strong>

                    {" "}

                    {
                      fieldData
                        .transition_analysis
                        .candidate_date ||
                      "Not detected"
                    }

                  </strong>

                </p>


                <p>

                  Status:

                  <strong>

                    {" "}

                    {
                      fieldData
                        .transition_analysis
                        .status
                    }

                  </strong>

                </p>

              </div>

            )}


            {/* =============================================
                NDVI / NBR CHART
            ============================================= */}

            <h3>
              Sentinel-2 Time Series
            </h3>


            <div className="chart-container">

              <ResponsiveContainer
                width="100%"
                height={400}
              >

                <LineChart
                  data={
                    fieldData.time_series
                  }
                >

                  <CartesianGrid
                    strokeDasharray="3 3"
                  />


                  <XAxis
                    dataKey="date"
                  />


                  <YAxis
                    domain={[
                      0,
                      1
                    ]}
                  />


                  <Tooltip />


                  <Legend />


                  <Line
                    type="monotone"
                    dataKey="ndvi"
                    name="NDVI"
                    stroke="#166534"
                    strokeWidth={3}
                    dot={false}
                  />


                  <Line
                    type="monotone"
                    dataKey="nbr"
                    name="NBR"
                    stroke="#2563eb"
                    strokeWidth={3}
                    dot={false}
                  />

                </LineChart>

              </ResponsiveContainer>

            </div>

          </section>

        )}


        {/* =================================================
            BURN DETECTION
        ================================================= */}

        <section className="upload-card">

          <h2>
            🔥 Burn Detection
          </h2>


          <p className="section-description">

            Upload a matching RGB and SWIR
            image pair for the Dual CNN
            burn detector.

          </p>


          <div className="upload-grid">


            {/* RGB */}

            <div className="upload-box">

              <h3>
                RGB Image
              </h3>


              <p>
                Upload RGB satellite imagery
              </p>


              <input
                type="file"
                accept="image/*"
                onChange={(e) =>
                  setRgbFile(
                    e.target.files[0]
                  )
                }
              />


              {rgbFile && (

                <p className="filename">

                  {rgbFile.name}

                </p>

              )}

            </div>


            {/* SWIR */}

            <div className="upload-box">

              <h3>
                SWIR Image
              </h3>


              <p>
                Upload SWIR satellite imagery
              </p>


              <input
                type="file"
                accept="image/*"
                onChange={(e) =>
                  setSwirFile(
                    e.target.files[0]
                  )
                }
              />


              {swirFile && (

                <p className="filename">

                  {swirFile.name}

                </p>

              )}

            </div>

          </div>


          <button
            onClick={handlePredict}
            disabled={loading}
          >

            {loading
              ? "Analyzing..."
              : "Analyze Burn Risk"}

          </button>


          {error && (

            <div className="error">

              {error}

            </div>

          )}

        </section>


        {/* =================================================
            BURN RESULT
        ================================================= */}

        {result && (

          <section className="result-card">

            <h2>
              🔥 Burn Detection Result
            </h2>


            <div
              className={
                result.prediction === "Burn"
                  ? "prediction burn"
                  : "prediction no-burn"
              }
            >

              <div className="prediction-icon">

                {result.prediction === "Burn"
                  ? "🔥"
                  : "🌱"}

              </div>


              <div>

                <p>
                  Field Status
                </p>


                <h3>
                  {result.prediction}
                </h3>

              </div>

            </div>


            <div className="metrics">

              <div className="metric">

                <span>
                  Confidence
                </span>


                <strong>
                  {result.confidence}%
                </strong>

              </div>


              <div className="metric">

                <span>
                  No Burn
                </span>


                <strong>
                  {result.no_burn_probability}%
                </strong>

              </div>


              <div className="metric">

                <span>
                  Burn
                </span>


                <strong>
                  {result.burn_probability}%
                </strong>

              </div>

            </div>

          </section>

        )}

      </main>


      {/* =================================================
          FOOTER
      ================================================= */}

      <footer>

        Project Parali •
        Sentinel-2 + Dual RGB/SWIR CNN

      </footer>

    </div>

  );

}


export default App;