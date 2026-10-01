import {
  Activity,
  Flame,
  MapPinned,
  Sprout
} from "lucide-react";

function DashboardCards({
  totalFields = 0,
  completelyBurnt = 0,
  partiallyBurnt = 0,
  transitionCandidates = 0
}) {
  const cards = [
    {
      label: "Fields Monitored",
      value: totalFields,
      description: "Satellite fields in dataset",
      icon: MapPinned,
      className: "dashboard-card-green"
    },
    {
      label: "Completely Burnt",
      value: completelyBurnt,
      description: "Labeled completely burnt",
      icon: Flame,
      className: "dashboard-card-red"
    },
    {
      label: "Partially Burnt",
      value: partiallyBurnt,
      description: "Labeled partially burnt",
      icon: Activity,
      className: "dashboard-card-orange"
    },
    {
      label: "Transition Signals",
      value: transitionCandidates,
      description: "NDVI-based candidates",
      icon: Sprout,
      className: "dashboard-card-yellow"
    }
  ];

  return (
    <div className="dashboard-cards">
      {cards.map((card) => {
        const Icon = card.icon;

        return (
          <article
            key={card.label}
            className={`dashboard-card ${card.className}`}
          >
            <div className="dashboard-card-top">
              <div className="dashboard-card-icon">
                <Icon size={20} strokeWidth={2} />
              </div>

              <span className="dashboard-card-label">
                {card.label}
              </span>
            </div>

            <div className="dashboard-card-value">
              {Number(card.value).toLocaleString()}
            </div>

            <p className="dashboard-card-description">
              {card.description}
            </p>
          </article>
        );
      })}
    </div>
  );
}

export default DashboardCards;
