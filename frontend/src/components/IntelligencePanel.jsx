import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  ShieldCheck
} from "lucide-react";

function IntelligencePanel({
  high = 0,
  medium = 0,
  low = 0,
  priorityFields = [],
  onFieldSelect
}) {
  const priorityCards = [
    {
      label: "High attention",
      value: high,
      description: "Multiple monitoring signals",
      icon: CircleAlert,
      className: "intelligence-high"
    },
    {
      label: "Medium attention",
      value: medium,
      description: "Signals worth monitoring",
      icon: AlertTriangle,
      className: "intelligence-medium"
    },
    {
      label: "Low attention",
      value: low,
      description: "Limited current signals",
      icon: ShieldCheck,
      className: "intelligence-low"
    }
  ];

  const formatCategory = (value) => {
    if (!value) return "Unknown";

    return String(value)
      .replace(/_/g, " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase());
  };

  const formatTrend = (value) => {
    if (!value) return "N/A";

    return String(value)
      .replace(/_/g, " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase());
  };

  return (
    <div className="intelligence-panel">
      <div className="intelligence-summary">
        {priorityCards.map((card) => {
          const Icon = card.icon;

          return (
            <div
              key={card.label}
              className={`intelligence-summary-card ${card.className}`}
            >
              <div className="intelligence-summary-icon">
                <Icon size={19} />
              </div>

              <div>
                <span className="intelligence-summary-label">
                  {card.label}
                </span>

                <strong className="intelligence-summary-value">
                  {Number(card.value).toLocaleString()}
                </strong>

                <span className="intelligence-summary-description">
                  {card.description}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="intelligence-header">
        <div>
          <div className="intelligence-eyebrow">
            FIELD PRIORITIZATION
          </div>

          <h3>Highest-signal fields</h3>

          <p>
            A transparent monitoring heuristic based on the existing
            field indicators. It is not a validated burn or harvest
            prediction.
          </p>
        </div>

        <div className="intelligence-status">
          <CheckCircle2 size={16} />
          Monitoring active
        </div>
      </div>

      <div className="priority-list">
        {priorityFields.length > 0 ? (
          priorityFields.map((field) => {
            const isHigh =
              field.priority === "High attention";

            const isMedium =
              field.priority === "Medium attention";

            const priorityClass = isHigh
              ? "priority-high"
              : isMedium
                ? "priority-medium"
                : "priority-low";

            return (
              <button
                type="button"
                key={field.fieldId}
                className={`priority-field ${priorityClass}`}
                onClick={() =>
                  onFieldSelect?.(field.fieldId)
                }
              >
                <div className="priority-field-main">
                  <div className="priority-field-id">
                    <span className="priority-dot"></span>
                    Field {field.fieldId}
                  </div>

                  <span className="priority-score">
                    Score {field.score ?? 0}
                  </span>
                </div>

                <div className="priority-field-details">
                  <span>
                    {formatCategory(field.category)}
                  </span>

                  <span>
                    NDVI {formatTrend(field.ndviTrend)}
                  </span>

                  <span>
                    NBR {formatTrend(field.nbrTrend)}
                  </span>

                  {field.candidateDate && (
                    <span>
                      Candidate {field.candidateDate}
                    </span>
                  )}
                </div>

                <ChevronRight
                  className="priority-arrow"
                  size={18}
                />
              </button>
            );
          })
        ) : (
          <div className="intelligence-empty">
            <ShieldCheck size={24} />

            <div>
              <strong>No priority fields available</strong>
              <p>
                Field intelligence will appear when indicator data
                is available.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default IntelligencePanel;
