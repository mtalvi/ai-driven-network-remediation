import { useState } from "react";

const SCENARIOS = [
  { id: "low_signal", label: "Trigger Low Signal Demo" },
  { id: "cell_outage", label: "Trigger Cell Outage Demo" },
];

export function DemoTrigger({ baseUrl, onTriggered }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  async function trigger(scenario) {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const url = baseUrl ? `${baseUrl}/api/demo/trigger` : "/api/demo/trigger";
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(body.error || body.detail || body.message || `Demo trigger failed (${res.status})`);
      }
      setResult(body);
      onTriggered?.();
    } catch (err) {
      setError(err.message || "Demo trigger failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel">
      <h2>Demo Mode</h2>
      <p className="meta">
        Inject a synthetic RAN KPI reading straight into the real
        detection -&gt; root-cause pipeline and watch it get diagnosed live.
      </p>
      <div className="demo-actions">
        {SCENARIOS.map((s) => (
          <button key={s.id} type="button" disabled={loading} onClick={() => trigger(s.id)}>
            {s.label}
          </button>
        ))}
      </div>
      {error && <p className="demo-error">{error}</p>}
      {result && (
        <div className="demo-result">
          <p>
            <strong>Cell:</strong> <code>{result.cell_id}</code> · Band:{" "}
            <code>{result.band}</code>
          </p>
          <p>
            <strong>Scenario:</strong> <code>{result.scenario}</code> · Topic:{" "}
            <code>{result.topic}</code> · Offset: <code>{result.kafka_offset}</code>
          </p>
          <p>
            Ask the chat about cell {result.cell_id} in about 15-20 seconds — it'll show up in the
            anomaly table once root cause analysis finishes.
          </p>
        </div>
      )}
    </section>
  );
}
