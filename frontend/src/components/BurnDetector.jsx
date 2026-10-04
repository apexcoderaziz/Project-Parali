import {
  CheckCircle2,
  Flame,
  LoaderCircle,
  Satellite
} from "lucide-react";
import { useEffect, useState } from "react";

const API_URL =
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:8000";

// Render can need time to wake up, and the live Sentinel-2 route may need
// additional time for Earth Engine scene acquisition. Keep this separate
// from the shorter general App.jsx request timeout.
const LIVE_BURN_TIMEOUT_MS = 90000;
const LIVE_BURN_RETRY_DELAY_MS = 1500;
const LIVE_BURN_MAX_ATTEMPTS = 2;

function isRetryableNetworkError(error) {
  return (
    error?.name === "TypeError" ||
    error?.name === "NetworkError"
  );
}

async function fetchLiveBurnWithTimeout(url, { signal } = {}) {
  let lastError = null;

  for (
    let attempt = 0;
    attempt < LIVE_BURN_MAX_ATTEMPTS;
    attempt += 1
  ) {
    const timeoutController = new AbortController();
    let timedOut = false;

    const handleParentAbort = () => {
      timeoutController.abort();
    };

    signal?.addEventListener(
      "abort",
      handleParentAbort,
      { once: true }
    );

    const timeoutId = window.setTimeout(() => {
      timedOut = true;
      timeoutController.abort();
    }, LIVE_BURN_TIMEOUT_MS);

    try {
      const response = await fetch(url, {
        signal: timeoutController.signal,
        headers: {
          Accept: "application/json"
        }
      });

      const contentType =
        response.headers.get("content-type") || "";

      const data = contentType.includes("application/json")
        ? await response.json()
        : {
            detail: await response.text()
          };

      if (!response.ok) {
        throw new Error(
          data?.detail ||
            `Live burn analysis failed (${response.status})`
        );
      }

      return data;
    } catch (error) {
      if (signal?.aborted) {
        const abortError = new Error(
          "Live burn request cancelled."
        );
        abortError.name = "AbortError";
        throw abortError;
      }

      lastError = error;

      const retryable =
        timedOut ||
        isRetryableNetworkError(error);

      if (
        retryable &&
        attempt < LIVE_BURN_MAX_ATTEMPTS - 1
      ) {
        await new Promise((resolve, reject) => {
          const retryTimer = window.setTimeout(
            resolve,
            LIVE_BURN_RETRY_DELAY_MS
          );

          const handleRetryAbort = () => {
            window.clearTimeout(retryTimer);
            reject(
              Object.assign(
                new Error("Live burn request cancelled."),
                { name: "AbortError" }
              )
            );
          };

          signal?.addEventListener(
            "abort",
            handleRetryAbort,
            { once: true }
          );
        });

        continue;
      }

      if (timedOut) {
        throw new Error(
          "Live burn analysis timed out after 90 seconds. The Render API may be waking up, or Earth Engine may still be processing the Sentinel-2 scene."
        );
      }

      throw error;
    } finally {
      window.clearTimeout(timeoutId);
      signal?.removeEventListener(
        "abort",
        handleParentAbort
      );
    }
  }

  throw (
    lastError ||
    new Error("Live burn analysis failed")
  );
}

function SignalResult({ result }) {
  if (!result) {
    return null;
  }

  const status = String(
    result.status || ""
  ).toLowerCase();

  const isStrong =
    status === "burn_signal";

  const isPossible =
    status === "possible_burn_signal";

  const isInsufficient =
    status === "insufficient_data";

  const isUnavailable =
    status === "data_unavailable";

  const resultClass =
    isStrong || isPossible
      ? "burn-result burn-result-danger"
      : "burn-result burn-result-safe";

  const icon =
    isStrong || isPossible
      ? <Flame size={23} />
      : <CheckCircle2 size={23} />;

  const primaryNote = isUnavailable
    ? "Live Sentinel-2 acquisition is temporarily unavailable. No burn score was fabricated."
    : isInsufficient
      ? "More usable Sentinel-2 observations are required for a live spectral assessment."
      : "The spectral layer is a satellite-derived burn-related signal, not a calibrated probability or confirmed burn event.";

  const ml = result.ml_model || null;
  const mlAvailable =
    ml?.available === true;

  return (
    <div className={resultClass}>
      <div className="burn-result-header">
        <div className="burn-result-icon">
          {icon}
        </div>

        <div>
          <span>Live Sentinel-2 assessment</span>
          <h3>
            {result.status_label ||
              "Assessment available"}
          </h3>
        </div>
      </div>

      <div className="burn-result-metrics">
        <div>
          <span>Spectral signal</span>
          <strong>
            {result.signal_strength ??
              "N/A"}
            {result.signal_strength != null
              ? "/100"
              : ""}
          </strong>
        </div>

        <div>
          <span>Latest observation</span>
          <strong>
            {result.as_of_date ||
              "N/A"}
          </strong>
        </div>

        <div>
          <span>Observations</span>
          <strong>
            {result.observations ??
              "N/A"}
          </strong>
        </div>
      </div>

      <div className="burn-result-note">
        {primaryNote}
      </div>

      {(result.reasons || []).length > 0 && (
        <div className="burn-live-reasons">
          <strong>
            Satellite evidence
          </strong>

          <ul>
            {result.reasons.map(
              (reason, index) => (
                <li
                  key={`${reason}-${index}`}
                >
                  {reason}
                </li>
              )
            )}
          </ul>
        </div>
      )}

      {result.signals && (
        <div className="burn-result-metrics">
          <div>
            <span>
              NBR decline
            </span>
            <strong>
              {result.signals
                .nbr_drop_from_reference ??
                "N/A"}
            </strong>
          </div>

          <div>
            <span>
              NDVI decline
            </span>
            <strong>
              {result.signals
                .ndvi_drop_from_reference ??
                "N/A"}
            </strong>
          </div>

          <div>
            <span>
              SWIR2/NIR increase
            </span>
            <strong>
              {result.signals
                .swir2_nir_ratio_increase ??
                "N/A"}
            </strong>
          </div>
        </div>
      )}

      <div className="burn-ml-card">
        <div className="burn-ml-card-header">
          <div>
            <span>
              INDEPENDENT ML EVIDENCE
            </span>
            <strong>
              Dual RGB + SWIR ResNet18
            </strong>
          </div>

          <span
            className={
              mlAvailable
                ? "burn-ml-status is-ready"
                : "burn-ml-status"
            }
          >
            {mlAvailable
              ? "LIVE ML READY"
              : "ML UNAVAILABLE"}
          </span>
        </div>

        {mlAvailable ? (
          <>
            <div className="burn-result-metrics">
              <div>
                <span>
                  Prediction
                </span>
                <strong>
                  {ml.prediction ||
                    "N/A"}
                </strong>
              </div>

              <div>
                <span>
                  Confidence
                </span>
                <strong>
                  {ml.confidence_percent !=
                  null
                    ? `${ml.confidence_percent}%`
                    : "N/A"}
                </strong>
              </div>

              <div>
                <span>
                  Burn score
                </span>
                <strong>
                  {ml.softmax_burn_score_percent !=
                  null
                    ? `${ml.softmax_burn_score_percent}%`
                    : "N/A"}
                </strong>
              </div>
            </div>

            <div className="burn-result-note">
              {ml.score_interpretation ||
                "CNN output is model evidence, not a calibrated live Sentinel-2 probability."}
            </div>
          </>
        ) : (
          <div className="burn-result-note">
            {ml?.error ||
              "The Sentinel-2 spectral analysis completed, but the live CNN bridge was unavailable for this request."}
          </div>
        )}
      </div>

      <div className="burn-result-note">
        {result.validation_note ||
          "Live Sentinel-2 burn assessment with known limitations."}
      </div>
    </div>
  );
}

function BurnDetector({
  fieldId,
  fieldData
}) {
  const [result, setResult] =
    useState(null);

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState("");

  const selectedFieldId = String(
    fieldData?.field_id ||
      fieldId ||
      ""
  ).trim();

  useEffect(() => {
    if (
      !selectedFieldId ||
      !fieldData
    ) {
      setResult(null);
      setError("");
      return undefined;
    }

    const controller =
      new AbortController();

    const loadLiveBurnAnalysis =
      async () => {
        setLoading(true);
        setError("");
        setResult(null);

        try {
          const data =
            await fetchLiveBurnWithTimeout(
              `${API_URL}/live-burn-analysis/${encodeURIComponent(
                selectedFieldId
              )}`,
              {
                signal:
                  controller.signal
              }
            );

          setResult(data);
        } catch (err) {
          if (
            err.name ===
            "AbortError"
          ) {
            return;
          }

          console.error(
            "Live burn analysis error:",
            err
          );

          setResult(null);
          setError(
            err.message ||
              "Live burn analysis failed"
          );
        } finally {
          if (
            !controller.signal
              .aborted
          ) {
            setLoading(false);
          }
        }
      };

    loadLiveBurnAnalysis();

    return () =>
      controller.abort();
  }, [selectedFieldId, fieldData]);

  return (
    <section className="burn-detector">
      <div className="burn-detector-header">
        <div className="burn-detector-icon">
          <Flame size={22} />
        </div>

        <div>
          <div className="burn-detector-eyebrow">
            LIVE SENTINEL-2 MONITORING
          </div>

          <h3>
            Live Burn Analysis
          </h3>

          <p>
            Automatically assess burn-related spectral signals
            from Sentinel-2 for the selected field. No RGB or
            SWIR image upload is required.
          </p>
        </div>
      </div>

      <div className="burn-pair-notice">
        <Satellite size={16} />

        <div>
          <strong>
            Automatic satellite analysis
          </strong>

          <span>
            {selectedFieldId
              ? `Analyzing field ${selectedFieldId} using the latest usable Sentinel-2 observations.`
              : "Select a field on the map to start live burn analysis."}
          </span>
        </div>
      </div>

      {loading && (
        <div className="burn-action-row">
          <span className="burn-action-ready">
            <LoaderCircle
              size={15}
              className="burn-spinner"
            />
            Fetching live Sentinel-2 observations...
          </span>
        </div>
      )}

      {!loading && error && (
        <div className="burn-error">
          {error}
        </div>
      )}

      {!loading &&
        !error &&
        !selectedFieldId && (
          <div className="burn-action-row">
            <span className="burn-action-hint">
              Select a field to continue.
            </span>
          </div>
        )}

      {!loading &&
        !error &&
        result && (
          <SignalResult
            result={result}
          />
        )}
    </section>
  );
}

export default BurnDetector;
