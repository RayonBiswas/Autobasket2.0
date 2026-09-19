import { useEffect, useRef, useState } from "react";
import API from "../services/api";

// ─── Load TF.js + COCO-SSD from CDN ─────────────────────────────────────────
function loadScript(src) {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) return resolve();
    const s = document.createElement("script");
    s.src = src; s.async = true;
    s.onload = resolve; s.onerror = reject;
    document.head.appendChild(s);
  });
}

const CLASS_COLORS = {
  bottle:     "#00e5ff",
  cup:        "#7b61ff",
  person:     "#00c896",
  cell_phone: "#ffb627",
  laptop:     "#ff4d6d",
  book:       "#f472b6",
  chair:      "#fb923c",
  default:    "#a78bfa",
};
const classColor = (c) => CLASS_COLORS[c.replace(/ /g, "_")] || CLASS_COLORS.default;
const TARGET_CLASSES = ["bottle", "cup"];

const styles = `
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&display=swap');

  :root {
    --bg: #0a0a0f;
    --surface: #111118;
    --surface2: #1a1a24;
    --border: rgba(255,255,255,0.08);
    --accent: #00e5ff;
    --accent2: #7b61ff;
    --danger: #ff4d6d;
    --success: #00c896;
    --warning: #ffb627;
    --text: #f0f0f8;
    --muted: #6b6b80;
  }

  .cam-root {
    min-height: 100vh;
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Mono', monospace;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .cam-header {
    width: 100%;
    padding: 20px 40px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--border);
    background: rgba(10,10,15,0.95);
    backdrop-filter: blur(20px);
    position: sticky;
    top: 0;
    z-index: 10;
    box-sizing: border-box;
  }

  .cam-logo {
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: 'Syne', sans-serif;
    font-weight: 800;
    font-size: 18px;
    letter-spacing: -0.5px;
  }

  .cam-logo-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--accent);
    box-shadow: 0 0 12px var(--accent);
    animation: blink 2s infinite;
  }

  @keyframes blink {
    0%, 100% { opacity: 1; transform: scale(1); }
    50%       { opacity: 0.5; transform: scale(0.8); }
  }

  .cam-badge {
    font-size: 11px; padding: 4px 10px; border-radius: 20px;
    border: 1px solid var(--border); color: var(--muted);
    letter-spacing: 1px; text-transform: uppercase;
  }

  .cam-body {
    width: 100%; max-width: 900px; padding: 40px 24px;
    display: flex; flex-direction: column; gap: 28px; box-sizing: border-box;
  }

  .cam-title {
    font-family: 'Syne', sans-serif; font-size: 32px;
    font-weight: 800; letter-spacing: -1px; line-height: 1;
  }

  .cam-subtitle { color: var(--muted); font-size: 13px; letter-spacing: 0.5px; margin-top: 6px; }

  .cam-card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 20px; overflow: hidden;
  }

  .cam-video-wrapper {
    position: relative; background: #000;
    aspect-ratio: 4/3; max-height: 420px; overflow: hidden;
  }

  .cam-video { width: 100%; height: 100%; object-fit: cover; display: block; }

  .cam-canvas {
    position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none;
  }

  .cam-overlay { position: absolute; inset: 0; pointer-events: none; }

  .cam-corner { position: absolute; width: 24px; height: 24px; border-color: var(--accent); border-style: solid; opacity: 0.6; }
  .cam-corner.tl { top: 16px; left: 16px; border-width: 2px 0 0 2px; border-radius: 2px 0 0 0; }
  .cam-corner.tr { top: 16px; right: 16px; border-width: 2px 2px 0 0; border-radius: 0 2px 0 0; }
  .cam-corner.bl { bottom: 16px; left: 16px; border-width: 0 0 2px 2px; border-radius: 0 0 0 2px; }
  .cam-corner.br { bottom: 16px; right: 16px; border-width: 0 2px 2px 0; border-radius: 0 0 2px 0; }

  .cam-scanline {
    position: absolute; left: 16px; right: 16px; height: 1px;
    background: linear-gradient(90deg, transparent, var(--accent), transparent);
    animation: scan 2.5s ease-in-out infinite; opacity: 0.7;
  }
  @keyframes scan { 0% { top: 15%; } 50% { top: 85%; } 100% { top: 15%; } }

  .cam-live-tag {
    position: absolute; top: 14px; right: 14px;
    display: flex; align-items: center; gap: 6px;
    background: rgba(0,0,0,0.75); border: 1px solid rgba(255,255,255,0.1);
    border-radius: 20px; padding: 4px 10px;
    font-size: 10px; letter-spacing: 1px; color: var(--danger); text-transform: uppercase;
  }
  .cam-live-tag::before {
    content: ''; width: 6px; height: 6px; border-radius: 50%;
    background: var(--danger); animation: blink 1.5s infinite; flex-shrink: 0;
  }

  /* Model status pill */
  .cam-model-status {
    position: absolute; bottom: 14px; left: 14px;
    display: flex; align-items: center; gap: 6px;
    background: rgba(0,0,0,0.75); border: 1px solid rgba(255,255,255,0.08);
    border-radius: 20px; padding: 4px 12px;
    font-size: 10px; letter-spacing: 0.5px; color: var(--muted);
  }
  .cam-model-status.ready { color: var(--success); border-color: rgba(0,200,150,0.3); }
  .cam-model-status.loading { color: var(--warning); border-color: rgba(255,182,39,0.3); }
  .cam-model-status-dot {
    width: 5px; height: 5px; border-radius: 50%; background: currentColor; flex-shrink: 0;
  }
  .cam-model-status.ready .cam-model-status-dot { animation: blink 2s infinite; }

  /* Detections sidebar inside footer */
  .cam-card-footer {
    padding: 20px 24px; display: flex; align-items: center;
    justify-content: space-between; border-top: 1px solid var(--border); gap: 16px;
  }

  .cam-detect-list {
    flex: 1; display: flex; flex-wrap: wrap; gap: 8px; min-width: 0;
  }

  .cam-detect-chip {
    display: flex; align-items: center; gap: 6px;
    padding: 5px 10px; border-radius: 8px;
    font-size: 11px; letter-spacing: 0.3px;
    border: 1px solid; background: rgba(0,0,0,0.3);
    transition: all 0.2s;
  }

  .cam-detect-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }

  .cam-no-data { color: var(--muted); font-size: 13px; }

  .cam-btn-scan {
    display: flex; align-items: center; gap: 10px;
    padding: 14px 28px; background: linear-gradient(135deg, var(--accent2), var(--accent));
    border: none; border-radius: 12px; color: #fff;
    font-family: 'Syne', sans-serif; font-size: 15px; font-weight: 700;
    cursor: pointer; transition: all 0.2s; white-space: nowrap; flex-shrink: 0;
  }
  .cam-btn-scan:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 8px 24px rgba(0,229,255,0.3); }
  .cam-btn-scan:disabled { opacity: 0.5; cursor: not-allowed; }

  /* Water / score area */
  .cam-score-area { display: flex; flex-direction: column; gap: 4px; flex-shrink: 0; }
  .cam-score-label-sm { font-size: 10px; text-transform: uppercase; letter-spacing: 1.5px; color: var(--muted); }
  .cam-score-value {
    font-family: 'Syne', sans-serif; font-size: 28px; font-weight: 800; line-height: 1;
    color: var(--accent); text-shadow: 0 0 20px rgba(0,229,255,0.4);
  }
  .cam-score-value.low { color: var(--danger); text-shadow: 0 0 20px rgba(255,77,109,0.4); }

  .cam-bar-wrap { flex: 1; display: flex; flex-direction: column; gap: 6px; }
  .cam-bar { height: 6px; background: var(--surface2); border-radius: 99px; overflow: hidden; border: 1px solid var(--border); }
  .cam-bar-fill {
    height: 100%; border-radius: 99px;
    transition: width 1s cubic-bezier(0.4,0,0.2,1);
    background: linear-gradient(90deg, var(--accent2), var(--accent));
    box-shadow: 0 0 8px rgba(0,229,255,0.4);
  }
  .cam-bar-fill.low { background: linear-gradient(90deg, #c0192e, var(--danger)); box-shadow: 0 0 8px rgba(255,77,109,0.4); }
  .cam-bar-status { font-size: 11px; color: var(--muted); }

  .cam-alert {
    background: rgba(255,77,109,0.07); border: 1px solid rgba(255,77,109,0.25);
    border-radius: 16px; padding: 16px 20px; display: flex; align-items: center; gap: 14px;
  }
  .cam-alert-icon { font-size: 22px; flex-shrink: 0; }
  .cam-alert-title { font-family: 'Syne', sans-serif; font-weight: 700; font-size: 14px; color: var(--danger); }
  .cam-alert-sub { font-size: 12px; color: var(--muted); margin-top: 2px; }

  .cam-section-header { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
  .cam-section-title { font-family: 'Syne', sans-serif; font-weight: 700; font-size: 18px; letter-spacing: -0.3px; white-space: nowrap; }
  .cam-section-line { flex: 1; height: 1px; background: var(--border); }
  .cam-count { font-size: 11px; padding: 3px 8px; border-radius: 6px; background: var(--surface2); border: 1px solid var(--border); color: var(--muted); }

  .cam-vendors { display: flex; flex-direction: column; gap: 12px; }
  .cam-vendor-card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
    padding: 18px 20px; display: flex; align-items: center; gap: 16px;
    transition: border-color 0.2s, transform 0.2s;
  }
  .cam-vendor-card.top { border-color: rgba(0,200,150,0.35); background: linear-gradient(135deg, rgba(0,200,150,0.04), var(--surface)); }
  .cam-vendor-card:hover { border-color: rgba(255,255,255,0.14); transform: translateX(2px); }

  .cam-rank {
    width: 40px; height: 40px; border-radius: 10px;
    background: var(--surface2); border: 1px solid var(--border);
    display: flex; align-items: center; justify-content: center;
    font-family: 'Syne', sans-serif; font-weight: 800; font-size: 16px; flex-shrink: 0; color: var(--muted);
  }
  .cam-rank.gold { background: rgba(255,182,39,0.1); border-color: rgba(255,182,39,0.35); color: var(--warning); }

  .cam-vinfo { flex: 1; min-width: 0; }
  .cam-vname { font-family: 'Syne', sans-serif; font-weight: 700; font-size: 15px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .cam-top-pill { font-size: 10px; padding: 2px 8px; border-radius: 20px; background: rgba(0,200,150,0.12); border: 1px solid rgba(0,200,150,0.3); color: var(--success); letter-spacing: 0.5px; }
  .cam-vmeta { display: flex; gap: 20px; margin-top: 6px; }
  .cam-vmeta-label { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }
  .cam-vmeta-val { font-size: 14px; color: var(--text); margin-top: 2px; }

  .cam-score-chip { padding: 8px 12px; border-radius: 10px; background: var(--surface2); border: 1px solid var(--border); font-family: 'Syne', sans-serif; font-weight: 700; font-size: 15px; color: var(--accent); text-align: center; flex-shrink: 0; }
  .cam-score-chip-label { font-size: 9px; color: var(--muted); font-family: 'DM Mono', monospace; font-weight: 400; letter-spacing: 0.5px; display: block; margin-top: 2px; }

  .cam-btn-order { padding: 10px 18px; background: transparent; border: 1px solid var(--border); border-radius: 10px; color: var(--text); font-family: 'DM Mono', monospace; font-size: 12px; cursor: pointer; transition: all 0.2s; flex-shrink: 0; white-space: nowrap; }
  .cam-btn-order:hover { border-color: var(--accent); color: var(--accent); box-shadow: 0 0 16px rgba(0,229,255,0.15); }
  .cam-btn-order.top { border-color: rgba(0,200,150,0.4); color: var(--success); }
  .cam-btn-order.top:hover { background: rgba(0,200,150,0.1); box-shadow: 0 0 16px rgba(0,200,150,0.2); }

  .cam-review-card { background: var(--surface); border: 1px solid rgba(123,97,255,0.3); border-radius: 20px; overflow: hidden; }
  .cam-review-header { padding: 24px 24px 0; }
  .cam-review-eyebrow { font-size: 10px; text-transform: uppercase; letter-spacing: 2px; color: var(--accent2); }
  .cam-review-title { font-family: 'Syne', sans-serif; font-weight: 700; font-size: 20px; letter-spacing: -0.3px; margin-top: 6px; }
  .cam-review-sub { font-size: 12px; color: var(--muted); margin-top: 4px; }

  .cam-stars { display: flex; gap: 10px; padding: 24px; flex-wrap: wrap; }
  .cam-star-btn {
    flex: 1; min-width: 70px; padding: 14px 8px;
    background: var(--surface2); border: 1px solid var(--border); border-radius: 14px;
    color: var(--text); font-size: 18px; cursor: pointer; transition: all 0.2s;
    display: flex; flex-direction: column; align-items: center; gap: 6px; font-family: 'DM Mono', monospace;
  }
  .cam-star-btn:hover { border-color: var(--warning); background: rgba(255,182,39,0.07); transform: translateY(-2px); box-shadow: 0 8px 20px rgba(255,182,39,0.12); }
  .cam-star-label { font-size: 10px; color: var(--muted); letter-spacing: 0.3px; }
`;

function Camera() {
  const videoRef    = useRef(null);
  const canvasRef   = useRef(null);
  const modelRef    = useRef(null);
  const rafRef      = useRef(null);
  const detectionsRef = useRef([]);

  const [modelStatus, setModelStatus]   = useState("loading"); // loading | ready
  const [liveDetections, setLiveDetections] = useState([]);    // [{class, score, bbox}]
  const [waterLevel, setWaterLevel]     = useState(null);
  const [vendors, setVendors]           = useState([]);
  const [selectedVendor, setSelectedVendor] = useState(null);
  const [reviewMode, setReviewMode]     = useState(false);
  const [scanning, setScanning]         = useState(false);

  // ── 1. Start camera ──────────────────────────────────────────────────────
  useEffect(() => {
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: "user" } })
      .then((stream) => { videoRef.current.srcObject = stream; })
      .catch((err) => console.error("Camera error:", err));
  }, []);

  // ── 2. Load TF.js + COCO-SSD from CDN, then start live detection loop ───
  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        await loadScript("https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.20.0/dist/tf.min.js");
        await loadScript("https://cdn.jsdelivr.net/npm/@tensorflow-models/coco-ssd@2.2.3/dist/coco-ssd.min.js");
        if (cancelled) return;

        // Wait for video to be ready
        await new Promise((res) => {
          const check = () => videoRef.current?.readyState >= 2 ? res() : setTimeout(check, 100);
          check();
        });

        const model = await window.cocoSsd.load();
        modelRef.current = model;
        setModelStatus("ready");
        runLoop(model);
      } catch (e) {
        console.error("Model load error:", e);
      }
    }

    function runLoop(model) {
      const canvas = canvasRef.current;
      const video  = videoRef.current;
      if (!canvas || !video || cancelled) return;

      const ctx = canvas.getContext("2d");

      const tick = async () => {
        if (cancelled) return;

        if (video.readyState >= 2) {
          // Sync canvas size to video
          if (canvas.width !== video.videoWidth)  canvas.width  = video.videoWidth;
          if (canvas.height !== video.videoHeight) canvas.height = video.videoHeight;

          // Run model
          const preds = await model.detect(video);
          detectionsRef.current = preds;
          setLiveDetections([...preds]);

          // Draw
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          preds.forEach((pred) => {
            const [bx, by, bw, bh] = pred.bbox;
            const color = classColor(pred.class);
            const conf  = Math.round(pred.score * 100);

            // Filled tinted box
            ctx.fillStyle = color + "12";
            ctx.fillRect(bx, by, bw, bh);

            // Border
            ctx.shadowColor = color;
            ctx.shadowBlur  = 16;
            ctx.strokeStyle = color;
            ctx.lineWidth   = 2;
            ctx.strokeRect(bx, by, bw, bh);

            // Corner accents
            ctx.lineWidth  = 3;
            ctx.shadowBlur = 22;
            [[bx, by], [bx + bw, by], [bx, by + bh], [bx + bw, by + bh]].forEach(([cx, cy], ci) => {
              const sx = ci % 2 === 0 ? 1 : -1;
              const sy = ci < 2 ? 1 : -1;
              const cs = 16;
              ctx.beginPath();
              ctx.moveTo(cx + sx * cs, cy);
              ctx.lineTo(cx, cy);
              ctx.lineTo(cx, cy + sy * cs);
              ctx.stroke();
            });

            // Label pill
            ctx.shadowBlur = 0;
            const label = `${pred.class}  ${conf}%`;
            ctx.font = "bold 12px 'DM Mono', monospace";
            const tw = ctx.measureText(label).width;
            const ph = 22, pw = tw + 18;
            const px = bx;
            const py = by >= ph + 6 ? by - ph - 4 : by + 4;

            ctx.fillStyle   = color + "33";
            ctx.strokeStyle = color;
            ctx.lineWidth   = 1;
            ctx.shadowBlur  = 8;
            ctx.beginPath();
            ctx.roundRect(px, py, pw, ph, 5);
            ctx.fill();
            ctx.stroke();

            ctx.shadowBlur  = 0;
            ctx.fillStyle   = color;
            ctx.fillText(label, px + 9, py + 15);
          });
        }

        rafRef.current = requestAnimationFrame(tick);
      };

      rafRef.current = requestAnimationFrame(tick);
    }

    init();
    return () => {
      cancelled = true;
      cancelAnimationFrame(rafRef.current);
    };
  }, []);

  // ── 3. Capture & call API ─────────────────────────────────────────────────
  const captureImage = async () => {
    setScanning(true);
    const canvas = document.createElement("canvas");
    canvas.width  = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;
    canvas.getContext("2d").drawImage(videoRef.current, 0, 0);
    const imageData = canvas.toDataURL("image/png");

    try {
      const res = await API.post("/vision/water-level", { image: imageData });
      setWaterLevel(res.data.water_percentage);

      // Check if a target class (bottle/cup) is currently detected live
      const hasTarget = detectionsRef.current.some(d => TARGET_CLASSES.includes(d.class));
      if (res.data.low || hasTarget) {
        const vendorRes = await API.get("/vendors/compare/water");
        setVendors(vendorRes.data);
      } else {
        setVendors([]);
      }
    } catch (err) {
      console.error("Vision error:", err);
    } finally {
      setScanning(false);
    }
  };

  const placeOrder = (vendor) => {
    alert(`Ordering from ${vendor.vendor_name} for ₹${vendor.price}`);
    setSelectedVendor(vendor);
    setReviewMode(true);
  };

  const submitReview = async (rating) => {
    const res = await API.post("/vendors/review", null, {
      params: { vendor_id: selectedVendor.vendor_id, new_rating: rating },
    });
    alert(`Rating Updated!\nOld: ${res.data.old_rating}\nNew: ${res.data.new_rating}`);
    const updated = await API.get("/vendors/compare/water");
    setVendors(updated.data);
    setReviewMode(false);
    setSelectedVendor(null);
  };

  const isLow = waterLevel !== null && waterLevel < 30;
  const topDetections = liveDetections.slice(0, 5);

  return (
    <>
      <style>{styles}</style>
      <div className="cam-root">

        {/* ── Header ── */}
        <header className="cam-header">
          <div className="cam-logo">
            <div className="cam-logo-dot" />
            VisionAI
          </div>
          <div className="cam-badge">COCO-SSD · Real-time</div>
        </header>

        <div className="cam-body">

          {/* ── Title ── */}
          <div>
            <div className="cam-title">Intelligent Object Scanner</div>
            <div className="cam-subtitle">
              Live AI detection — 80 object classes, continuous frame analysis
            </div>
          </div>

          {/* ── Camera card ── */}
          <div className="cam-card">
            <div className="cam-video-wrapper">
              <video ref={videoRef} autoPlay playsInline muted className="cam-video" />
              <canvas ref={canvasRef} className="cam-canvas" />

              <div className="cam-overlay">
                <div className="cam-corner tl" /><div className="cam-corner tr" />
                <div className="cam-corner bl" /><div className="cam-corner br" />
                {scanning && <div className="cam-scanline" />}
              </div>

              <div className="cam-live-tag">Live</div>

              {/* Model status */}
              <div className={`cam-model-status ${modelStatus}`}>
                <div className="cam-model-status-dot" />
                {modelStatus === "loading" ? "Loading model…" : "COCO-SSD Ready"}
              </div>
            </div>

            {/* Footer — live detection chips + scan button */}
            <div className="cam-card-footer">
              <div className="cam-detect-list">
                {topDetections.length > 0 ? (
                  topDetections.map((d, i) => (
                    <div
                      key={i}
                      className="cam-detect-chip"
                      style={{
                        borderColor: classColor(d.class) + "66",
                        color: classColor(d.class),
                      }}
                    >
                      <div
                        className="cam-detect-dot"
                        style={{ background: classColor(d.class) }}
                      />
                      {d.class}
                      <span style={{ opacity: 0.6, marginLeft: 2 }}>
                        {Math.round(d.score * 100)}%
                      </span>
                    </div>
                  ))
                ) : (
                  <div className="cam-no-data">
                    {modelStatus === "loading" ? "Initializing model…" : "No objects detected"}
                  </div>
                )}
              </div>

              <button
                className="cam-btn-scan"
                onClick={captureImage}
                disabled={scanning || modelStatus === "loading"}
              >
                {scanning ? "⏳ Analyzing…" : "◎ Run Scan"}
              </button>
            </div>
          </div>

          {/* ── Score / bar (after API scan) ── */}
          {waterLevel !== null && (
            <div className="cam-card" style={{ padding: "20px 24px", display: "flex", alignItems: "center", gap: 16 }}>
              <div className="cam-score-area">
                <div className="cam-score-label-sm">Detection Score</div>
                <div className={`cam-score-value${isLow ? " low" : ""}`}>{waterLevel}%</div>
              </div>
              <div className="cam-bar-wrap">
                <div className="cam-bar">
                  <div className={`cam-bar-fill${isLow ? " low" : ""}`} style={{ width: `${waterLevel}%` }} />
                </div>
                <div className="cam-bar-status">
                  {isLow ? "⚠ Below threshold — action recommended" : "✓ Analysis complete — levels nominal"}
                </div>
              </div>
            </div>
          )}

          {/* ── Alert ── */}
          {isLow && vendors.length > 0 && !reviewMode && (
            <div className="cam-alert">
              <div className="cam-alert-icon">⚠️</div>
              <div>
                <div className="cam-alert-title">Anomaly Detected</div>
                <div className="cam-alert-sub">Score below threshold — recommended providers listed below</div>
              </div>
            </div>
          )}

          {/* ── Vendor list ── */}
          {vendors.length > 0 && !reviewMode && (
            <div>
              <div className="cam-section-header">
                <div className="cam-section-title">Recommended Providers</div>
                <div className="cam-section-line" />
                <div className="cam-count">{vendors.length} found</div>
              </div>
              <div className="cam-vendors">
                {vendors.map((v, i) => (
                  <div key={i} className={`cam-vendor-card${i === 0 ? " top" : ""}`}>
                    <div className={`cam-rank${i === 0 ? " gold" : ""}`}>{i === 0 ? "★" : `#${i + 1}`}</div>
                    <div className="cam-vinfo">
                      <div className="cam-vname">
                        {v.vendor_name}
                        {i === 0 && <span className="cam-top-pill">BEST PICK</span>}
                      </div>
                      <div className="cam-vmeta">
                        <div><div className="cam-vmeta-label">Price</div><div className="cam-vmeta-val">₹{v.price}</div></div>
                        <div><div className="cam-vmeta-label">Rating</div><div className="cam-vmeta-val">⭐ {v.rating}</div></div>
                      </div>
                    </div>
                    <div className="cam-score-chip">
                      {v.final_score}
                      <span className="cam-score-chip-label">SCORE</span>
                    </div>
                    <button className={`cam-btn-order${i === 0 ? " top" : ""}`} onClick={() => placeOrder(v)}>
                      Order →
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Review ── */}
          {reviewMode && selectedVendor && (
            <div className="cam-review-card">
              <div className="cam-review-header">
                <div className="cam-review-eyebrow">Experience Feedback</div>
                <div className="cam-review-title">Rate {selectedVendor.vendor_name}</div>
                <div className="cam-review-sub">Your rating helps the community find the best providers</div>
              </div>
              <div className="cam-stars">
                {[5, 4, 3, 2, 1].map((r) => (
                  <button key={r} className="cam-star-btn" onClick={() => submitReview(r)}>
                    {"⭐".repeat(r)}
                    <span className="cam-star-label">{r} star{r !== 1 ? "s" : ""}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

        </div>
      </div>
    </>
  );
}

export default Camera;