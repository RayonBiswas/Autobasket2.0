// The signature element: a container drawn as a container. Fill height = how much is left; fill colour
// follows the level itself (not the "runs out" forecast, which the status pill carries separately).

function levelBand(pct) {
  if (pct == null) return "none";
  if (pct >= 45) return "high";
  if (pct >= 20) return "mid";
  return "low";
}

function Gauge({ fraction, slim = false, label }) {
  const pct = fraction == null ? null : Math.max(0, Math.min(100, Math.round(fraction * 100)));
  const band = levelBand(pct);
  const text = pct == null ? "Not measured yet" : `${pct}% left`;
  return (
    <div className={`gauge level-${band}${slim ? " gauge-slim" : ""}`} role="img" aria-label={label || text}>
      <div className="gauge-fill" style={{ height: `${pct ?? 0}%` }} />
      <div className="gauge-ticks" aria-hidden="true" />
      <div className="gauge-pct" aria-hidden="true">{pct == null ? "?" : `${pct}%`}</div>
    </div>
  );
}

export default Gauge;
