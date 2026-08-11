const ANOMALY_TYPE_LABELS = {
  LowRsrp: "Low RSRP",
  SinrDegradation: "SINR Degradation",
  ThroughputDrop: "Throughput Drop",
  UesSpikeOrDrop: "UEs Spike/Drop",
  HighPrbUtilization: "High PRB Utilization",
  CellOutage: "Cell Outage",
};

function typeLabel(anomalyType) {
  return ANOMALY_TYPE_LABELS[anomalyType] || anomalyType;
}

export function AnomalyTable({ anomalies }) {
  return (
    <section className="panel">
      <h2>Recent Anomalies</h2>
      {(!anomalies || anomalies.length === 0) ? (
        <p className="empty-state">
          No RAN anomalies detected yet. This panel updates automatically as new
          readings are processed.
        </p>
      ) : (
        <div className="anomaly-list">
          {anomalies.map((a, idx) => (
            <article key={`${a.cell_id}-${a.band}-${a.anomaly_type}-${idx}`} className="anomaly-card">
              <header>
                <span className="anomaly-type-pill">{typeLabel(a.anomaly_type)}</span>
                <span className="anomaly-cell">
                  Cell {a.cell_id} · {a.band}
                </span>
              </header>
              <p className="anomaly-detail">{a.anomaly}</p>
              <div className="anomaly-grid">
                <div>
                  <span className="anomaly-label">Root Cause</span>
                  <p>{a.root_cause || "n/a"}</p>
                </div>
                <div>
                  <span className="anomaly-label">Recommended Fix</span>
                  <p>{a.recommended_fix || "n/a"}</p>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
