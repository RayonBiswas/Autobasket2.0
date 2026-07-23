import { useState, useEffect, useRef } from "react";

const VENDORS = [
  {
    id: 1,
    name: "FreshMart Express",
    distance: "0.4 km",
    eta: "8 min",
    rating: 4.9,
    badge: "Fastest",
    items: { rice: "₹58", milk: "₹28", water: "₹20" },
    score: 97,
    lat: 0.18,
    lng: -0.22,
    color: "#00e5ff",
  },
  {
    id: 2,
    name: "GreenLeaf Grocers",
    distance: "0.9 km",
    eta: "14 min",
    rating: 4.7,
    badge: "Best Value",
    items: { rice: "₹52", milk: "₹30", water: "₹18" },
    score: 91,
    lat: -0.28,
    lng: 0.14,
    color: "#00c896",
  },
  {
    id: 3,
    name: "QuickBasket Co.",
    distance: "1.2 km",
    eta: "19 min",
    rating: 4.5,
    badge: "Top Rated",
    items: { rice: "₹60", milk: "₹26", water: "₹22" },
    score: 85,
    lat: 0.1,
    lng: 0.32,
    color: "#7b61ff",
  },
];

const MAP_PINS = [
  { x: 62, y: 28, isUser: false, vendorIdx: 0 },
  { x: 28, y: 68, isUser: false, vendorIdx: 1 },
  { x: 78, y: 70, isUser: false, vendorIdx: 2 },
];

const ROAD_PATHS = [
  "M50,50 Q56,39 62,28",
  "M50,50 Q39,59 28,68",
  "M50,50 Q64,60 78,70",
];

// Decorative map road lines
const STREET_LINES = [
  "M10,30 Q40,28 70,35 Q85,38 95,42",
  "M5,55 Q25,52 50,50 Q70,48 90,55",
  "M8,75 Q30,70 55,68 Q75,72 92,78",
  "M20,10 Q22,30 25,50 Q28,68 30,90",
  "M48,5 Q50,25 50,50 Q50,72 52,92",
  "M72,8 Q70,28 68,50 Q65,70 63,90",
];

export default function VendorRadar({ onAddToCart }) {
  const [phase, setPhase] = useState("idle"); // idle | scanning | done
  const [revealedCount, setRevealedCount] = useState(0);
  const [selectedVendor, setSelectedVendor] = useState(null);
  const [pulseAngle, setPulseAngle] = useState(0);
  const [activeMap, setActiveMap] = useState(false);
  const animRef = useRef(null);
  const revealTimers = useRef([]);

  const startScan = () => {
    setPhase("scanning");
    setRevealedCount(0);
    setSelectedVendor(null);
    setActiveMap(false);
    setPulseAngle(0);

    // Reveal vendors one by one
    revealTimers.current.forEach(clearTimeout);
    revealTimers.current = [
      setTimeout(() => setRevealedCount(1), 1200),
      setTimeout(() => setRevealedCount(2), 2400),
      setTimeout(() => {
        setRevealedCount(3);
        setPhase("done");
        setActiveMap(true);
      }, 3600),
    ];
  };

  // Animate radar sweep
  useEffect(() => {
    if (phase !== "scanning") return;
    let start = null;
    const sweep = (ts) => {
      if (!start) start = ts;
      const elapsed = ts - start;
      setPulseAngle((elapsed / 12) % 360);
      animRef.current = requestAnimationFrame(sweep);
    };
    animRef.current = requestAnimationFrame(sweep);
    return () => cancelAnimationFrame(animRef.current);
  }, [phase]);

  useEffect(() => () => revealTimers.current.forEach(clearTimeout), []);

  const cx = 50, cy = 50, r = 42;

  return (
    <div style={styles.root}>
      <style>{css}</style>

      {/* ── Title ── */}
      <div style={styles.heading}>
        <div style={styles.headingLine} />
        <span style={styles.headingText}>Nearby Vendor Radar</span>
        <div style={styles.headingLine} />
      </div>
      <p style={styles.subtext}>Scan your surroundings to find the best grocery vendors near you</p>

      {/* ── Radar + Map row ── */}
      <div style={styles.vizRow}>

        {/* Radar */}
        <div style={styles.radarWrap}>
          <svg viewBox="0 0 100 100" style={styles.radarSvg} className="radar-svg">
            <defs>
              <radialGradient id="rg" cx="50%" cy="50%">
                <stop offset="0%" stopColor="#7b61ff" stopOpacity="0.08" />
                <stop offset="100%" stopColor="#00e5ff" stopOpacity="0.02" />
              </radialGradient>
              <filter id="glow">
                <feGaussianBlur stdDeviation="1.5" result="blur" />
                <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
              </filter>
              {phase !== "idle" && (
                <clipPath id="sweepClip">
                  <path d={getSweepPath(cx, cy, r + 4, pulseAngle)} />
                </clipPath>
              )}
            </defs>

            {/* Background fill */}
            <circle cx={cx} cy={cy} r={r + 5} fill="url(#rg)" />

            {/* Rings */}
            {[10, 20, 31, 42].map((radius, i) => (
              <circle key={i} cx={cx} cy={cy} r={radius}
                fill="none" stroke="rgba(0,229,255,0.12)" strokeWidth="0.4" />
            ))}

            {/* Cross-hairs */}
            <line x1={cx} y1={cy - r - 4} x2={cx} y2={cy + r + 4}
              stroke="rgba(0,229,255,0.1)" strokeWidth="0.3" />
            <line x1={cx - r - 4} y1={cy} x2={cx + r + 4} y2={cy}
              stroke="rgba(0,229,255,0.1)" strokeWidth="0.3" />

            {/* Sweep arc */}
            {phase === "scanning" && (
              <g filter="url(#glow)">
                <path d={getSweepArc(cx, cy, r, pulseAngle, 60)}
                  fill="rgba(0,229,255,0.06)" />
                <line
                  x1={cx} y1={cy}
                  x2={cx + r * Math.cos((pulseAngle - 90) * Math.PI / 180)}
                  y2={cy + r * Math.sin((pulseAngle - 90) * Math.PI / 180)}
                  stroke="#00e5ff" strokeWidth="0.8"
                  strokeLinecap="round"
                />
              </g>
            )}

            {/* Vendor blips */}
            {VENDORS.map((v, i) => {
              const bx = cx + v.lat * r * 2.1;
              const by = cy + v.lng * r * 2.1;
              const visible = revealedCount > i;
              return visible ? (
                <g key={v.id} className="blip-in">
                  <circle cx={bx} cy={by} r={3.5} fill={v.color}
                    style={{ filter: `drop-shadow(0 0 4px ${v.color})` }} />
                  <circle cx={bx} cy={by} r={6}
                    fill="none" stroke={v.color} strokeWidth="0.5"
                    opacity="0.5" className="blip-ring" />
                  <text x={bx + 5} y={by - 3} fill={v.color}
                    fontSize="3.5" fontFamily="'DM Mono', monospace" fontWeight="600">
                    {v.name.split(" ")[0]}
                  </text>
                </g>
              ) : null;
            })}

            {/* User dot */}
            <circle cx={cx} cy={cy} r={2.5} fill="#fff"
              style={{ filter: "drop-shadow(0 0 5px rgba(255,255,255,0.9))" }} />
            <circle cx={cx} cy={cy} r={5}
              fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth="0.4"
              className="user-pulse" />

            {/* Distance labels */}
            {["0.5km","1.0km","1.5km"].map((label, i) => (
              <text key={i} x={cx + [10,20,31][i] + 1} y={cy - 1}
                fill="rgba(0,229,255,0.3)" fontSize="2.5"
                fontFamily="'DM Mono', monospace">{label}</text>
            ))}
          </svg>

          {/* Scan button */}
          {phase === "idle" && (
            <button style={styles.scanBtn} className="scan-btn" onClick={startScan}>
              ◉ &nbsp;Scan Area
            </button>
          )}
          {phase === "scanning" && (
            <div style={styles.scanningLabel}>
              <span className="blink-dot" />
              Scanning...
            </div>
          )}
          {phase === "done" && (
            <div style={{ ...styles.scanningLabel, color: "#00c896" }}>
              ✓ &nbsp;3 vendors found
              <button style={styles.rescanBtn} onClick={startScan}>Re-scan</button>
            </div>
          )}
        </div>

        {/* Map */}
        <div style={{ ...styles.mapWrap, opacity: activeMap ? 1 : 0.25,
          transition: "opacity 0.8s ease", pointerEvents: activeMap ? "auto" : "none" }}>
          <div style={styles.mapInner}>
            <svg viewBox="0 0 100 100" style={styles.mapSvg}>
              <defs>
                <radialGradient id="mapbg" cx="50%" cy="50%">
                  <stop offset="0%" stopColor="#1a1a28" />
                  <stop offset="100%" stopColor="#0d0d18" />
                </radialGradient>
              </defs>
              <rect width="100" height="100" fill="url(#mapbg)" />

              {/* Streets */}
              {STREET_LINES.map((d, i) => (
                <path key={i} d={d} fill="none"
                  stroke="rgba(255,255,255,0.06)" strokeWidth={i % 2 === 0 ? "2.5" : "1.5"}
                  strokeLinecap="round" />
              ))}

              {/* Block fills */}
              {[
                "M10,10 L44,10 L44,44 L10,44Z",
                "M56,10 L90,10 L90,44 L56,44Z",
                "M10,56 L44,56 L44,88 L10,88Z",
                "M56,56 L90,56 L90,88 L56,88Z",
              ].map((d, i) => (
                <path key={i} d={d} fill="rgba(255,255,255,0.02)"
                  stroke="rgba(255,255,255,0.04)" strokeWidth="0.5" />
              ))}

              {/* Route lines (when a vendor is selected) */}
              {activeMap && ROAD_PATHS.map((d, i) => (
                <path key={i} d={d} fill="none"
                  stroke={VENDORS[i].color}
                  strokeWidth={selectedVendor === i ? 1.2 : 0.4}
                  strokeDasharray={selectedVendor === i ? "none" : "2,2"}
                  opacity={selectedVendor === null || selectedVendor === i ? 0.7 : 0.2}
                  strokeLinecap="round"
                  style={{ transition: "all 0.3s ease" }}
                />
              ))}

              {/* Vendor pins */}
              {activeMap && MAP_PINS.map((pin, i) => {
                const v = VENDORS[pin.vendorIdx];
                const isSelected = selectedVendor === i;
                return (
                  <g key={i} style={{ cursor: "pointer" }}
                    onClick={() => setSelectedVendor(isSelected ? null : i)}
                    className="map-pin">
                    <circle cx={pin.x} cy={pin.y} r={isSelected ? 5 : 3.5}
                      fill={v.color}
                      style={{ filter: `drop-shadow(0 0 ${isSelected ? 6 : 3}px ${v.color})`,
                        transition: "all 0.25s ease" }} />
                    {isSelected && (
                      <circle cx={pin.x} cy={pin.y} r={8}
                        fill="none" stroke={v.color} strokeWidth="0.5" opacity="0.5"
                        className="blip-ring" />
                    )}
                    <text x={pin.x + (i === 2 ? -2 : 4)} y={pin.y - 5}
                      fill={v.color} fontSize="3" fontFamily="'DM Mono', monospace"
                      fontWeight="600" opacity={isSelected ? 1 : 0.7}>
                      {v.name.split(" ")[0]}
                    </text>
                  </g>
                );
              })}

              {/* User location */}
              <circle cx="50" cy="50" r="3" fill="#fff"
                style={{ filter: "drop-shadow(0 0 6px rgba(255,255,255,0.9))" }} />
              <circle cx="50" cy="50" r="6" fill="rgba(255,255,255,0.08)"
                stroke="rgba(255,255,255,0.2)" strokeWidth="0.5"
                className="user-pulse" />
              <text x="53" y="48" fill="rgba(255,255,255,0.5)"
                fontSize="3" fontFamily="'DM Mono', monospace">You</text>
            </svg>
            <div style={styles.mapLabel}>📍 Live Map View</div>
          </div>
        </div>
      </div>

      {/* ── Vendor cards ── */}
      {revealedCount > 0 && (
        <div style={styles.vendorList}>
          <div style={styles.listHeader}>
            <span style={styles.listTitle}>Nearby Vendors</span>
            <span style={styles.listSub}>{revealedCount} of 3 found</span>
          </div>
          {VENDORS.slice(0, revealedCount).map((v, i) => (
            <div key={v.id}
              className={`vendor-card${selectedVendor === i ? " vendor-selected" : ""}`}
              style={{ ...styles.vendorCard, borderColor: selectedVendor === i ? v.color + "60" : "rgba(255,255,255,0.08)" }}
              onClick={() => setSelectedVendor(selectedVendor === i ? null : i)}>

              {/* rank + name */}
              <div style={styles.vcLeft}>
                <div style={{ ...styles.vcRank, color: v.color, borderColor: v.color + "40",
                  background: v.color + "12", boxShadow: `0 0 12px ${v.color}22` }}>
                  {i === 0 ? "★" : `#${i + 1}`}
                </div>
                <div>
                  <div style={styles.vcName}>
                    {v.name}
                    <span style={{ ...styles.vcBadge, color: v.color, borderColor: v.color + "50",
                      background: v.color + "12" }}>{v.badge}</span>
                  </div>
                  <div style={styles.vcMeta}>
                    <span>📍 {v.distance}</span>
                    <span>🕐 {v.eta}</span>
                    <span>⭐ {v.rating}</span>
                  </div>
                </div>
              </div>

              {/* score */}
              <div style={{ ...styles.vcScore, color: v.color }}>
                {v.score}
                <span style={styles.vcScoreLabel}>SCORE</span>
              </div>

              {/* prices */}
              <div style={styles.vcPrices}>
                {Object.entries(v.items).map(([item, price]) => (
                  <div key={item} style={styles.vcPriceItem}>
                    <span style={styles.vcPriceLabel}>{item}</span>
                    <span style={{ ...styles.vcPriceVal, color: v.color }}>{price}</span>
                  </div>
                ))}
              </div>

              {/* add button */}
              <button
                className="vc-btn"
                style={{ borderColor: v.color + "60", color: v.color }}
                onClick={(e) => {
                  e.stopPropagation();
                  onAddToCart && onAddToCart(v);
                }}>
                Add →
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Radar math helpers ──
function getSweepArc(cx, cy, r, angle, span) {
  const start = ((angle - span - 90) * Math.PI) / 180;
  const end = ((angle - 90) * Math.PI) / 180;
  const x1 = cx + r * Math.cos(start), y1 = cy + r * Math.sin(start);
  const x2 = cx + r * Math.cos(end), y2 = cy + r * Math.sin(end);
  return `M${cx},${cy} L${x1},${y1} A${r},${r} 0 0,1 ${x2},${y2} Z`;
}

function getSweepPath(cx, cy, r, angle) {
  const a = ((angle - 90) * Math.PI) / 180;
  const x2 = cx + r * Math.cos(a), y2 = cy + r * Math.sin(a);
  return `M${cx},${cy} L${cx},${cy - r} A${r},${r} 0 1,1 ${x2},${y2} Z`;
}

// ── Styles ──
const styles = {
  root: {
    background: "#0a0a0f",
    borderRadius: 20,
    border: "1px solid rgba(255,255,255,0.08)",
    padding: "28px 24px",
    display: "flex",
    flexDirection: "column",
    gap: 20,
  },
  heading: {
    display: "flex", alignItems: "center", gap: 12,
  },
  headingLine: { flex: 1, height: 1, background: "rgba(255,255,255,0.08)" },
  headingText: {
    fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 22,
    letterSpacing: -0.5, color: "#f0f0f8", whiteSpace: "nowrap",
  },
  subtext: {
    fontFamily: "'DM Mono', monospace", fontSize: 12,
    color: "#6b6b80", margin: 0,
  },
  vizRow: {
    display: "flex", gap: 16, flexWrap: "wrap",
  },
  radarWrap: {
    flex: "1 1 220px", display: "flex", flexDirection: "column",
    alignItems: "center", gap: 12,
    background: "#0d0d18",
    border: "1px solid rgba(0,229,255,0.1)",
    borderRadius: 18, padding: 16,
    position: "relative",
  },
  radarSvg: { width: "100%", maxWidth: 260, height: "auto" },
  scanBtn: {
    padding: "10px 22px",
    background: "linear-gradient(135deg, #7b61ff, #00e5ff)",
    border: "none", borderRadius: 10, color: "#fff",
    fontFamily: "'Syne', sans-serif", fontWeight: 700, fontSize: 14,
    cursor: "pointer", letterSpacing: 0.3,
  },
  scanningLabel: {
    display: "flex", alignItems: "center", gap: 8,
    fontFamily: "'DM Mono', monospace", fontSize: 12, color: "#00e5ff",
  },
  rescanBtn: {
    marginLeft: 12, padding: "4px 10px",
    background: "transparent", border: "1px solid rgba(0,200,150,0.4)",
    borderRadius: 7, color: "#00c896",
    fontFamily: "'DM Mono', monospace", fontSize: 11, cursor: "pointer",
  },
  mapWrap: {
    flex: "1 1 220px",
    borderRadius: 18, overflow: "hidden",
    border: "1px solid rgba(255,255,255,0.08)",
  },
  mapInner: { position: "relative", width: "100%", height: "100%", minHeight: 240 },
  mapSvg: { width: "100%", height: "100%", minHeight: 220, display: "block" },
  mapLabel: {
    position: "absolute", bottom: 10, left: 12,
    fontFamily: "'DM Mono', monospace", fontSize: 10,
    color: "rgba(255,255,255,0.3)",
  },
  vendorList: { display: "flex", flexDirection: "column", gap: 10 },
  listHeader: {
    display: "flex", justifyContent: "space-between", alignItems: "center",
  },
  listTitle: {
    fontFamily: "'Syne', sans-serif", fontWeight: 700, fontSize: 15, color: "#f0f0f8",
  },
  listSub: { fontFamily: "'DM Mono', monospace", fontSize: 11, color: "#6b6b80" },
  vendorCard: {
    background: "#111118",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 14, padding: "14px 18px",
    display: "flex", alignItems: "center", gap: 14,
    cursor: "pointer", flexWrap: "wrap",
    transition: "border-color 0.25s ease, transform 0.2s ease",
  },
  vcLeft: { display: "flex", alignItems: "center", gap: 12, flex: 1, minWidth: 160 },
  vcRank: {
    width: 34, height: 34, borderRadius: 9,
    border: "1px solid", display: "flex", alignItems: "center", justifyContent: "center",
    fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 14, flexShrink: 0,
  },
  vcName: {
    fontFamily: "'Syne', sans-serif", fontWeight: 700, fontSize: 14,
    color: "#f0f0f8", display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap",
  },
  vcBadge: {
    fontSize: 9, padding: "2px 7px", borderRadius: 20,
    border: "1px solid", letterSpacing: 0.5, fontFamily: "'DM Mono', monospace",
  },
  vcMeta: {
    display: "flex", gap: 10, marginTop: 4,
    fontFamily: "'DM Mono', monospace", fontSize: 10, color: "#6b6b80",
  },
  vcScore: {
    display: "flex", flexDirection: "column", alignItems: "center",
    fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 20,
    padding: "6px 10px", background: "#1a1a24",
    border: "1px solid rgba(255,255,255,0.07)", borderRadius: 9,
    flexShrink: 0,
  },
  vcScoreLabel: {
    fontSize: 8, color: "#6b6b80", fontFamily: "'DM Mono', monospace",
    fontWeight: 400, marginTop: 1,
  },
  vcPrices: {
    display: "flex", gap: 12, flexWrap: "wrap",
  },
  vcPriceItem: { display: "flex", flexDirection: "column", gap: 2 },
  vcPriceLabel: {
    fontFamily: "'DM Mono', monospace", fontSize: 9,
    color: "#6b6b80", textTransform: "uppercase", letterSpacing: 0.5,
  },
  vcPriceVal: {
    fontFamily: "'Syne', sans-serif", fontWeight: 700, fontSize: 13,
  },
};

const css = `
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=DM+Mono:wght@300;400;500&display=swap');

  @keyframes blipIn {
    from { opacity: 0; transform: scale(0); }
    to { opacity: 1; transform: scale(1); }
  }
  @keyframes userPulse {
    0%, 100% { r: 5; opacity: 0.5; }
    50% { r: 8; opacity: 0.1; }
  }
  @keyframes blipRing {
    from { r: 6; opacity: 0.6; }
    to { r: 10; opacity: 0; }
  }
  @keyframes blinkDot {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }
  @keyframes scanBtnPop {
    from { transform: scale(0.9); opacity: 0; }
    to { transform: scale(1); opacity: 1; }
  }
  @keyframes vcFadeIn {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .blip-in { animation: blipIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) forwards; }
  .user-pulse { animation: userPulse 2s ease-in-out infinite; }
  .blip-ring { animation: blipRing 1.5s ease-out infinite; }
  .blink-dot {
    display: inline-block; width: 6px; height: 6px; border-radius: 50%;
    background: #00e5ff; animation: blinkDot 1s infinite;
  }
  .scan-btn { animation: scanBtnPop 0.3s ease; }
  .vendor-card { animation: vcFadeIn 0.4s ease both; }
  .vendor-card:hover { transform: translateX(3px); border-color: rgba(255,255,255,0.15) !important; }
  .vendor-selected { transform: translateX(3px); }

  .vc-btn {
    padding: 8px 14px;
    background: transparent;
    border: 1px solid;
    border-radius: 9px;
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .vc-btn:hover {
    background: rgba(255,255,255,0.05);
    transform: scale(1.04);
    box-shadow: 0 0 14px rgba(0,229,255,0.15);
  }

  .map-pin { transition: all 0.2s ease; }
  .map-pin:hover circle { filter: brightness(1.3); }
`;