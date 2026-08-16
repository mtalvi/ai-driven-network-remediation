import { useState } from "react";

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

export function AnomalyTable({ anomalies, baseUrl, onCleared }) {
  const [clearing, setClearing] = useState(false);
  const [error, setError] = useState("");
  const hasAnomalies = Boolean(anomalies && anomalies.length > 0);

  async function clearAnomalies() {
    setClearing(true);
    setError("");
    try {
      const url = baseUrl ? `${baseUrl}/api/anomalies` : "/api/anomalies";
      const res = await fetch(url, { method: "DELETE" });
      if (!res.ok) {
        throw new Error(`Clear failed (${res.status})`);
      }
      await onCleared?.();
    } catch (err) {
      setError(err.message || "Failed to clear anomalies");
    } finally {
      setClearing(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-title-row">
        <h2>Recent Anomalies</h2>
        <button
          type="button"
          className="toggle-btn"
          onClick={clearAnomalies}
          disabled={clearing || !hasAnomalies}
        >
          {clearing ? "Clearing..." : "Clear"}
        </button>
      </div>
      {error && <p className="demo-error">{error}</p>}
      {!hasAnomalies ? (
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
