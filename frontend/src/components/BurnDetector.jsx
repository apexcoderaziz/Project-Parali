import {
  CheckCircle2,
  FileImage,
  Flame,
  ImagePlus,
  LoaderCircle,
  Sparkles,
  Upload,
  X
} from "lucide-react";

function ImageDropZone({
  title,
  description,
  file,
  onChange,
  onClear
}) {
  return (
    <div className="burn-upload-zone">
      <div className="burn-upload-icon">
        <FileImage size={21} />
      </div>

      <div className="burn-upload-content">
        <div className="burn-upload-title">
          {title}
        </div>

        <div className="burn-upload-description">
          {description}
        </div>

        {file ? (
          <div className="burn-selected-file">
            <span title={file.name}>
              {file.name}
            </span>

            <button
              type="button"
              onClick={onClear}
              aria-label={`Remove ${title}`}
            >
              <X size={14} />
            </button>
          </div>
        ) : (
          <label className="burn-upload-button">
            <Upload size={14} />
            Choose image

            <input
              type="file"
              accept="image/*"
              onChange={(event) =>
                onChange(
                  event.target.files?.[0] || null
                )
              }
            />
          </label>
        )}
      </div>
    </div>
  );
}

function PredictionResult({ result }) {
  if (!result) {
    return null;
  }

  const isBurn =
    String(result.prediction || "").toLowerCase() ===
    "burn";

  return (
    <div
      className={
        isBurn
          ? "burn-result burn-result-danger"
          : "burn-result burn-result-safe"
      }
    >
      <div className="burn-result-header">
        <div className="burn-result-icon">
          {isBurn ? (
            <Flame size={23} />
          ) : (
            <CheckCircle2 size={23} />
          )}
        </div>

        <div>
          <span>AI classification</span>

          <h3>
            {result.prediction || "Unknown"}
          </h3>
        </div>
      </div>

      <div className="burn-result-metrics">
        <div>
          <span>Confidence</span>
          <strong>
            {result.confidence ?? "N/A"}%
          </strong>
        </div>

        <div>
          <span>No Burn</span>
          <strong>
            {result.no_burn_probability ?? "N/A"}%
          </strong>
        </div>

        <div>
          <span>Burn</span>
          <strong>
            {result.burn_probability ?? "N/A"}%
          </strong>
        </div>
      </div>

      <div className="burn-result-note">
        This result applies to the uploaded RGB/SWIR
        image pair. It should not be interpreted as a
        field-wide conclusion unless the pair represents
        that field and scene.
      </div>
    </div>
  );
}

function BurnDetector({
  rgbFile,
  swirFile,
  setRgbFile,
  setSwirFile,
  result,
  loading = false,
  error = "",
  onPredict
}) {
  const canAnalyze =
    Boolean(rgbFile && swirFile && !loading);

  return (
    <div className="burn-detector">

      <div className="burn-detector-header">
        <div className="burn-detector-icon">
          <Flame size={22} />
        </div>

        <div>
          <div className="burn-detector-eyebrow">
            DUAL-MODAL AI ANALYSIS
          </div>

          <h3>
            Burn Detection
          </h3>

          <p>
            Analyze a matching RGB and SWIR satellite
            image pair using the trained Dual CNN.
          </p>
        </div>
      </div>

      <div className="burn-pair-notice">
        <Sparkles size={16} />

        <div>
          <strong>
            Use a matching image pair
          </strong>

          <span>
            RGB and SWIR images should represent the
            same scene, field, and date.
          </span>
        </div>
      </div>

      <div className="burn-upload-grid">

        <ImageDropZone
          title="RGB image"
          description="Visible-spectrum satellite image"
          file={rgbFile}
          onChange={setRgbFile}
          onClear={() => setRgbFile(null)}
        />

        <ImageDropZone
          title="SWIR image"
          description="SWIR representation used by the model"
          file={swirFile}
          onChange={setSwirFile}
          onClear={() => setSwirFile(null)}
        />

      </div>

      <div className="burn-action-row">

        <button
          type="button"
          className="burn-analyze-button"
          disabled={!canAnalyze}
          onClick={onPredict}
        >
          {loading ? (
            <>
              <LoaderCircle
                size={17}
                className="burn-spinner"
              />
              Analyzing pair...
            </>
          ) : (
            <>
              <ImagePlus size={17} />
              Analyze burn risk
            </>
          )}
        </button>

        {!rgbFile || !swirFile ? (
          <span className="burn-action-hint">
            Select both images to continue
          </span>
        ) : (
          <span className="burn-action-ready">
            <CheckCircle2 size={14} />
            Image pair ready
          </span>
        )}

      </div>

      {error && (
        <div className="burn-error">
          {error}
        </div>
      )}

      <PredictionResult result={result} />

    </div>
  );
}

export default BurnDetector;
