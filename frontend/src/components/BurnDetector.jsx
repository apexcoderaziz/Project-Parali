import React, {
  useEffect,
  useState
} from "react";

import {
  CheckCircle2,
  Flame,
  LoaderCircle,
  Sparkles
} from "lucide-react";

const API_URL = "http://127.0.0.1:8000";

function BurnResult({ result }) {
  if (!result) {
    return null;
  }

  const likelihood =
    String(
      result.burn_likelihood ??
      result.status ??
      ""
    ).toLowerCase();

  const isBurnSignal =
    likelihood.includes("high") ||
    likelihood.includes("strong") ||
    likelihood.includes("burn");

  const latest =
    result.latest_observation || {};

  const signals =
    result.signals || {};

  return (
    <div
      className={
        isBurnSignal
          ? "burn-result burn-result-danger"
          : "burn-result burn-result-safe"
      }
    >
      <div className="burn-result-header">
        <div className="burn-result-icon">
          {isBurnSignal ? (
            <Flame size={23} />
          ) : (
            <CheckCircle2 size={23} />
          )}
        </div>

        <div>
          <span>Live Sentinel-2 assessment</span>

          <h3>
            {result.status_label ||
              result.burn_likelihood ||
              result.status ||
              "Assessment available"}
          </h3>
        </div>
      </div>

      <div className="burn-result-metrics">
        <div>
          <span>Signal strength</span>
          <strong>
            {result.signal_strength != null
              ? `${result.signal_strength}`
              : "N/A"}
          </strong>
        </div>

        <div>
          <span>Latest NDVI</span>
          <strong>
            {latest.ndvi ?? "N/A"}
          </strong>
        </div>

        <div>
          <span>Latest NBR</span>
          <strong>
            {latest.nbr ?? "N/A"}
          </strong>
        </div>
      </div>

      <div className="burn-result-note">
        {result.validation_note ||
          "This is a live Sentinel-2 spectral/temporal burn indicator, not a calibrated probability or confirmed burn event."}
      </div>
    </div>
  );
}

function BurnDetector({
  fieldId,
  fieldData
}) {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [fieldRefreshKey, setFieldRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const normalizedFieldId =
      String(fieldId || "").trim();

    if (!normalizedFieldId) {
      setResult(null);
      setError("");
      return undefined;
    }

    const loadBurnAnalysis = async () => {
      setLoading(true);
      setError("");
      setResult(null);

      try {
        const response = await fetch(
          `${API_URL}/live-burn-analysis/${encodeURIComponent(
            normalizedFieldId
          )}`
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            data.detail ||
            "Live burn analysis failed"
          );
        }

        if (!cancelled) {
          setResult(data);
        }
      } catch (err) {
        console.error(
          "Live burn analysis error:",
          err
        );

        if (!cancelled) {
          setResult(null);
          setError(
            err.message ||
            "Live burn analysis failed"
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadBurnAnalysis();

    return () => {
      cancelled = true;
    };
  }, [fieldId, fieldRefreshKey]);

  const normalizedFieldId =
    String(fieldId || "").trim();

  return (
    <div className="burn-detector">

      <div className="burn-detector-header">
        <div className="burn-detector-icon">
          <Flame size={22} />
        </div>

        <div>
          <div className="burn-detector-eyebrow">
            LIVE SATELLITE ANALYSIS
          </div>

          <h3>
            Burn Detection
          </h3>

          <p>
            Analyze the selected field using current
            Sentinel-2 spectral and temporal signals.
            No RGB or SWIR image upload is required.
          </p>
        </div>
      </div>

      <div className="burn-pair-notice">
        <Sparkles size={16} />

        <div>
          <strong>
            Live Sentinel-2 monitoring
          </strong>

          <span>
            {normalizedFieldId
              ? `Field ${normalizedFieldId} is being assessed directly from satellite observations.`
              : "Select a field to start live satellite burn analysis."}
          </span>
        </div>
      </div>

      <div className="burn-action-row">

        <button
          type="button"
          className="burn-analyze-button"
          disabled={!normalizedFieldId || loading}
          onClick={() => {
            setFieldRefreshKey((value) => value + 1);
          }}
        >
          {loading ? (
            <>
              <LoaderCircle
                size={17}
                className="burn-spinner"
              />
              Analyzing satellite...
            </>
          ) : (
            <>
              <Flame size={17} />
              Refresh burn analysis
            </>
          )}
        </button>

        {!normalizedFieldId ? (
          <span className="burn-action-hint">
            Select a field to continue
          </span>
        ) : loading ? (
          <span className="burn-action-hint">
            Examining Sentinel-2 observations
          </span>
        ) : (
          <span className="burn-action-ready">
            <CheckCircle2 size={14} />
            Live satellite assessment ready
          </span>
        )}

      </div>

      {error && (
        <div className="burn-error">
          {error}
        </div>
      )}

      <BurnResult result={result} />

    </div>
  );
}

export default BurnDetector;
