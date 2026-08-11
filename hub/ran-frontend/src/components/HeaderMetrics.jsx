export function HeaderMetrics({ anomalies, count, deps, lastUpdated }) {
  const updated = lastUpdated ? lastUpdated.toLocaleString() : "n/a";
  const uniqueCells = new Set((anomalies || []).map((a) => a.cell_id)).size;
  const kafkaUp = !deps || !(deps.unavailable || []).includes("kafka");

  return (
    <section className="hero">
      <p className="badge">TELCO / O-RAN · ANOMALY DASHBOARD</p>
      <h1>RAN Anomaly Command Center</h1>
      <p className="sub">
        Live view of rule-detected RAN cell anomalies, enriched with LLM root
        cause analysis and recommended fixes — ask the assistant below for
        details on any of them.
      </p>
      <div className="hero-metrics">
        <div>
          <span>Anomalies Tracked</span>
          <strong>{count || 0}</strong>
        </div>
        <div>
          <span>Cells Affected</span>
          <strong>{uniqueCells}</strong>
        </div>
        <div>
          <span>Kafka Feed</span>
          <strong className={kafkaUp ? "status-up" : "status-down"}>
            {kafkaUp ? "Connected" : "Unavailable"}
          </strong>
        </div>
        <div>
          <span>Last Updated</span>
          <strong>{updated}</strong>
        </div>
      </div>
    </section>
  );
}
