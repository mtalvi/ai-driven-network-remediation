export function DegradedBanner({ deps }) {
  if (!deps || deps.status === "ok") return null;

  return (
    <div className="degraded-banner" role="alert">
      <span className="degraded-icon">⚠</span>
      <span>
        Partial data &mdash; unavailable:{" "}
        <strong>{(deps.unavailable || []).join(", ")}</strong>
      </span>
    </div>
  );
}
