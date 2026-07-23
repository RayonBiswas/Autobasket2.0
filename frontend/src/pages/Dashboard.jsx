import { useState, useEffect, useRef } from "react";
import API from "../services/api";
import AgentChatPanel from "../components/AgentChatPanel";
import VendorRadar from "./VendorRadar";

// ─── Constants ────────────────────────────────────────────────────────────────
const COMMISSION_RATE = 0.05; // 5% per order

// Seeded historical consumption (%) — 14 days, ending at "today"
// These are the REAL first values — subsequent ticks are simulated depletion
const SEED_HISTORY = {
  rice:  [94, 91, 88, 84, 81, 78, 74, 71, 68, 65, 61, 58, 55, 52],
  milk:  [97, 94, 90, 87, 83, 80, 76, 73, 69, 65, 61, 57, 53, 49],
  water: [99, 96, 93, 90, 86, 83, 79, 76, 72, 68, 64, 60, 56, 52],
};

const DAILY_USAGE_UNITS = { rice: 2.8, milk: 1.5, water: 4.2 };  // actual units/day
const MAX_STOCK         = { rice: 100, milk: 60,  water: 120 };   // max units
const ITEM_COLORS       = { rice: "#ffb627", milk: "#7b61ff", water: "#00e5ff" };
const ITEM_ICONS        = { rice: "🍚",      milk: "🥛",      water: "💧" };
const ITEM_UNIT         = { rice: "kg",       milk: "L",       water: "L"  };

// Pre-seeded order history with commissions (5 dummy orders)
const SEED_ORDERS = [
  { id:"ORD-001", date:"Feb 20", vendor:"FreshMart Express", item:"rice",  price:580, qty:"10kg" },
  { id:"ORD-002", date:"Feb 22", vendor:"GreenLeaf Grocers", item:"milk",  price:210, qty:"6L"   },
  { id:"ORD-003", date:"Feb 25", vendor:"QuickBasket Co.",   item:"water", price:140, qty:"20L"  },
  { id:"ORD-004", date:"Feb 27", vendor:"FreshMart Express", item:"rice",  price:580, qty:"10kg" },
  { id:"ORD-005", date:"Mar 01", vendor:"GreenLeaf Grocers", item:"milk",  price:210, qty:"6L"   },
].map(o => ({ ...o, commission: Math.round(o.price * COMMISSION_RATE) }));

// ─── Helpers ──────────────────────────────────────────────────────────────────
function daysLeft(pct, item) {
  const unitsLeft = (pct / 100) * MAX_STOCK[item];
  return DAILY_USAGE_UNITS[item] > 0
    ? Math.max(0, Math.round(unitsLeft / DAILY_USAGE_UNITS[item]))
    : 999;
}
function runoutLabel(days) {
  if (days === 0) return "Out of stock";
  if (days === 1) return "Tomorrow";
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toLocaleDateString("en-IN", { day:"numeric", month:"short" });
}

// ─── Sparkline SVG ────────────────────────────────────────────────────────────
function Sparkline({ data, color, height = 38 }) {
  const W = 130, H = height, P = 4;
  const mn = Math.min(...data), mx = Math.max(...data), rng = mx - mn || 1;
  const pts = data.map((v, i) => {
    const x = P + (i / (data.length - 1)) * (W - P * 2);
    const y = H - P - ((v - mn) / rng) * (H - P * 2);
    return [x, y];
  });
  const d = pts.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${d} L${pts.at(-1)[0].toFixed(1)},${H} L${pts[0][0].toFixed(1)},${H} Z`;
  return (
    <svg width={W} height={H} style={{ display:"block", overflow:"visible" }}>
      <defs>
        <linearGradient id={`sg-${color.replace("#","")}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#sg-${color.replace("#","")})`}/>
      <path d={d} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      <circle cx={pts.at(-1)[0]} cy={pts.at(-1)[1]} r="3.5" fill={color} />
    </svg>
  );
}

// ─── Mini bar chart ───────────────────────────────────────────────────────────
function MiniBarChart({ data, color }) {
  const mx = Math.max(...data, 1);
  return (
    <div style={{ display:"flex", alignItems:"flex-end", gap:2, height:44 }}>
      {data.map((v, i) => {
        const isLatest = i === data.length - 1;
        const h = Math.max(4, (v / mx) * 100);
        return (
          <div key={i} style={{ flex:1, position:"relative", height:"100%", display:"flex", alignItems:"flex-end" }}>
            <div style={{
              width:"100%", height:`${h}%`, borderRadius:"3px 3px 0 0",
              background: isLatest ? color : color + "38",
              transition:"height 0.6s ease",
            }}/>
            {isLatest && (
              <div style={{
                position:"absolute", bottom:"calc(100% + 3px)", left:"50%",
                transform:"translateX(-50%)", fontSize:8, color,
                fontFamily:"'Syne',sans-serif", fontWeight:800, whiteSpace:"nowrap",
              }}>{Math.round(v)}%</div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const styles = `
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&display=swap');

  :root {
    --bg:#0a0a0f; --surface:#111118; --surface2:#1a1a24; --surface3:#20202e;
    --border:rgba(255,255,255,0.08); --border2:rgba(255,255,255,0.13);
    --accent:#00e5ff; --accent2:#7b61ff;
    --danger:#ff4d6d; --success:#00c896; --warning:#ffb627;
    --text:#f0f0f8; --muted:#6b6b80;
  }
  *{box-sizing:border-box;margin:0;padding:0;}

  .db-root{min-height:100vh;background:var(--bg);color:var(--text);font-family:'DM Mono',monospace;display:flex;flex-direction:column;align-items:center;}

  /* Header */
  .db-header{width:100%;padding:20px 40px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--border);background:rgba(10,10,15,0.96);backdrop-filter:blur(24px);position:sticky;top:0;z-index:20;}
  .db-logo{display:flex;align-items:center;gap:10px;font-family:'Syne',sans-serif;font-weight:800;font-size:18px;letter-spacing:-0.5px;}
  .db-logo-dot{width:8px;height:8px;border-radius:50%;background:var(--accent2);box-shadow:0 0 12px var(--accent2);animation:blink 2s infinite;}
  .db-badge{font-size:11px;padding:4px 10px;border-radius:20px;border:1px solid var(--border);color:var(--muted);letter-spacing:1px;text-transform:uppercase;}

  /* Animations */
  @keyframes blink{0%,100%{opacity:1;transform:scale(1);}50%{opacity:.5;transform:scale(.8);}}
  @keyframes fadeIn{from{opacity:0;transform:translateY(8px);}to{opacity:1;transform:translateY(0);}}
  @keyframes slideUp{from{opacity:0;transform:translateY(16px);}to{opacity:1;transform:translateY(0);}}
  @keyframes pulseGlow{0%,100%{box-shadow:0 0 0 0 rgba(255,182,39,0.4);}50%{box-shadow:0 0 0 8px rgba(255,182,39,0);}}

  /* Body */
  .db-body{width:100%;max-width:1040px;padding:40px 24px 80px;display:flex;flex-direction:column;gap:28px;}

  /* Mode tabs */
  .db-tabs{display:flex;gap:0;background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:5px;width:fit-content;flex-wrap:wrap;gap:4px;}
  .db-tab{padding:9px 20px;border-radius:10px;border:none;background:transparent;color:var(--muted);font-family:'Syne',sans-serif;font-weight:700;font-size:12px;cursor:pointer;transition:all .2s;letter-spacing:.3px;white-space:nowrap;}
  .db-tab.active{background:linear-gradient(135deg,var(--accent2),var(--accent));color:#fff;box-shadow:0 4px 16px rgba(0,229,255,.2);}
  .db-tab:not(.active):hover{color:var(--text);background:var(--surface2);}

  /* Section header */
  .db-section-header{display:flex;align-items:center;gap:12px;margin-bottom:20px;}
  .db-section-title{font-family:'Syne',sans-serif;font-size:26px;font-weight:800;letter-spacing:-.8px;}
  .db-section-line{flex:1;height:1px;background:var(--border);}

  /* Items */
  .db-items{display:flex;flex-direction:column;gap:16px;}
  .db-item-row{background:var(--surface);border:1px solid var(--border);border-radius:16px;overflow:hidden;transition:border-color .2s;}
  .db-item-row.selected{border-color:rgba(123,97,255,.35);}
  .db-item-toggle{display:flex;align-items:center;gap:14px;padding:18px 22px;cursor:pointer;user-select:none;}
  .db-checkbox{width:20px;height:20px;border-radius:6px;border:2px solid var(--border);background:var(--surface2);display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:all .15s;font-size:12px;}
  .db-checkbox.checked{background:var(--accent2);border-color:var(--accent2);box-shadow:0 0 10px rgba(123,97,255,.4);}
  .db-item-name{font-family:'Syne',sans-serif;font-weight:700;font-size:16px;text-transform:capitalize;}
  .db-item-sub{font-size:11px;color:var(--muted);margin-left:auto;letter-spacing:.5px;}

  /* Vendors */
  .db-vendors-wrap{padding:0 22px 22px;display:flex;flex-direction:column;gap:10px;animation:fadeIn .25s ease;}
  .db-vendor-row{background:var(--surface2);border:1px solid var(--border);border-radius:14px;padding:16px 18px;display:flex;align-items:center;gap:14px;transition:all .2s;}
  .db-vendor-row.top{border-color:rgba(0,200,150,.35);background:linear-gradient(135deg,rgba(0,200,150,.05),var(--surface2));}
  .db-vendor-row:hover{border-color:rgba(255,255,255,.14);transform:translateX(2px);}
  .db-vrank{width:36px;height:36px;border-radius:9px;background:var(--surface);border:1px solid var(--border);display:flex;align-items:center;justify-content:center;font-family:'Syne',sans-serif;font-weight:800;font-size:14px;color:var(--muted);flex-shrink:0;}
  .db-vrank.gold{background:rgba(255,182,39,.1);border-color:rgba(255,182,39,.35);color:var(--warning);}
  .db-vinfo{flex:1;min-width:0;}
  .db-vname{font-family:'Syne',sans-serif;font-weight:700;font-size:14px;display:flex;align-items:center;gap:8px;flex-wrap:wrap;}
  .db-top-pill{font-size:9px;padding:2px 7px;border-radius:20px;background:rgba(0,200,150,.12);border:1px solid rgba(0,200,150,.3);color:var(--success);letter-spacing:.5px;}
  .db-vmeta{display:flex;gap:16px;margin-top:5px;}
  .db-vmeta-label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;}
  .db-vmeta-val{font-size:13px;color:var(--text);margin-top:1px;}
  .db-vscore{padding:6px 10px;border-radius:8px;background:var(--surface);border:1px solid var(--border);font-family:'Syne',sans-serif;font-weight:700;font-size:13px;color:var(--accent);text-align:center;flex-shrink:0;}
  .db-vscore-label{font-size:9px;color:var(--muted);font-family:'DM Mono',monospace;font-weight:400;display:block;margin-top:1px;}
  .db-btn-add{padding:9px 16px;background:transparent;border:1px solid var(--border);border-radius:9px;color:var(--text);font-family:'DM Mono',monospace;font-size:11px;cursor:pointer;transition:all .2s;white-space:nowrap;flex-shrink:0;}
  .db-btn-add:hover{border-color:var(--accent);color:var(--accent);box-shadow:0 0 14px rgba(0,229,255,.15);}
  .db-btn-add.in-cart{border-color:var(--accent2);color:var(--accent2);}

  /* Radar */
  .db-radar-divider{display:flex;align-items:center;gap:12px;padding:0 22px;margin-bottom:4px;animation:fadeIn .3s ease;}
  .db-radar-divider-line{flex:1;height:1px;background:linear-gradient(90deg,transparent,rgba(0,229,255,.2),transparent);}
  .db-radar-divider-label{font-size:10px;text-transform:uppercase;letter-spacing:2px;color:var(--accent);font-family:'DM Mono',monospace;display:flex;align-items:center;gap:6px;}
  .db-radar-divider-dot{width:5px;height:5px;border-radius:50%;background:var(--accent);box-shadow:0 0 6px var(--accent);animation:blink 1.5s infinite;}
  .db-radar-inline{padding:0 22px 22px;animation:fadeIn .4s ease;}

  /* Smart */
  .db-smart-card{background:var(--surface);border:1px solid var(--border);border-radius:20px;padding:28px;display:flex;flex-direction:column;gap:22px;}
  .db-smart-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;}
  @media(max-width:600px){.db-smart-grid{grid-template-columns:1fr;}}
  .db-field{display:flex;flex-direction:column;gap:6px;}
  .db-field-label{font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:var(--muted);}
  .db-input,.db-select{background:var(--surface2);border:1px solid var(--border);border-radius:10px;padding:11px 14px;color:var(--text);font-family:'DM Mono',monospace;font-size:14px;outline:none;transition:border-color .2s;width:100%;}
  .db-input:focus,.db-select:focus{border-color:var(--accent2);box-shadow:0 0 0 3px rgba(123,97,255,.1);}
  .db-select option{background:var(--surface2);}
  .db-consumption-pair{display:flex;gap:10px;}
  .db-consumption-pair .db-input{flex:1;}
  .db-btn-predict{display:flex;align-items:center;justify-content:center;gap:10px;padding:14px 28px;background:linear-gradient(135deg,var(--accent2),var(--accent));border:none;border-radius:12px;color:#fff;font-family:'Syne',sans-serif;font-size:15px;font-weight:700;cursor:pointer;transition:all .2s;align-self:flex-start;}
  .db-btn-predict:hover{transform:translateY(-1px);box-shadow:0 8px 24px rgba(0,229,255,.3);}
  .db-prediction{background:var(--surface2);border:1px solid var(--border);border-radius:16px;padding:22px;display:flex;flex-direction:column;gap:14px;animation:fadeIn .3s ease;}
  .db-pred-label{font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:var(--muted);}
  .db-pred-row{display:flex;gap:24px;flex-wrap:wrap;}
  .db-pred-stat{display:flex;flex-direction:column;gap:4px;}
  .db-pred-val{font-family:'Syne',sans-serif;font-size:28px;font-weight:800;letter-spacing:-.5px;color:var(--accent);text-shadow:0 0 20px rgba(0,229,255,.3);}
  .db-pred-val.warning{color:var(--warning);text-shadow:0 0 20px rgba(255,182,39,.3);}
  .db-pred-val.danger{color:var(--danger);text-shadow:0 0 20px rgba(255,77,109,.3);}
  .db-progress{height:6px;background:var(--surface);border-radius:99px;overflow:hidden;border:1px solid var(--border);}
  .db-progress-fill{height:100%;border-radius:99px;transition:width .5s ease,background .5s ease;background:linear-gradient(90deg,var(--accent2),var(--accent));box-shadow:0 0 8px rgba(0,229,255,.4);}
  .db-progress-fill.warning{background:linear-gradient(90deg,var(--warning),#ffdb57);box-shadow:0 0 8px rgba(255,182,39,.4);}
  .db-progress-fill.danger{background:linear-gradient(90deg,#c0192e,var(--danger));box-shadow:0 0 8px rgba(255,77,109,.4);}
  .db-countdown{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--muted);}
  .db-countdown-dot{width:6px;height:6px;border-radius:50%;background:var(--success);animation:blink 1.2s infinite;flex-shrink:0;}
  .db-alert{background:rgba(255,77,109,.07);border:1px solid rgba(255,77,109,.25);border-radius:14px;padding:14px 18px;display:flex;align-items:center;gap:12px;animation:fadeIn .3s ease;}
  .db-alert-title{font-family:'Syne',sans-serif;font-weight:700;font-size:14px;color:var(--danger);}
  .db-alert-sub{font-size:11px;color:var(--muted);margin-top:2px;}

  /* Cart */
  .db-cart-card{background:var(--surface);border:1px solid var(--border);border-radius:20px;overflow:hidden;}
  .db-cart-header{padding:20px 24px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;}
  .db-cart-title{font-family:'Syne',sans-serif;font-weight:700;font-size:18px;}
  .db-cart-count{font-size:11px;padding:3px 8px;border-radius:6px;background:var(--surface2);border:1px solid var(--border);color:var(--muted);}
  .db-cart-empty{padding:32px;text-align:center;color:var(--muted);font-size:13px;}
  .db-cart-items{display:flex;flex-direction:column;}
  .db-cart-item{padding:14px 24px;display:flex;align-items:center;gap:14px;border-bottom:1px solid var(--border);}
  .db-cart-item:last-child{border-bottom:none;}
  .db-cart-dot{width:8px;height:8px;border-radius:50%;background:var(--accent2);flex-shrink:0;}
  .db-cart-item-name{font-family:'Syne',sans-serif;font-weight:700;font-size:14px;text-transform:capitalize;flex:1;}
  .db-cart-vendor{font-size:12px;color:var(--muted);}
  .db-cart-price{font-family:'Syne',sans-serif;font-weight:700;font-size:15px;color:var(--success);}
  .db-cart-comm{font-size:10px;color:var(--warning);margin-left:4px;white-space:nowrap;}
  .db-cart-footer{padding:18px 24px;border-top:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;background:var(--surface2);}
  .db-total-label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;}
  .db-total-val{font-family:'Syne',sans-serif;font-weight:800;font-size:24px;color:var(--text);margin-top:2px;}
  .db-cart-comm-total{font-size:11px;color:var(--warning);margin-top:3px;}
  .db-btn-order{padding:14px 28px;background:linear-gradient(135deg,var(--success),#00a87a);border:none;border-radius:12px;color:#fff;font-family:'Syne',sans-serif;font-size:15px;font-weight:700;cursor:pointer;transition:all .2s;}
  .db-btn-order:hover{transform:translateY(-1px);box-shadow:0 8px 24px rgba(0,200,150,.3);}

  /* Review */
  .db-review-card{background:var(--surface);border:1px solid rgba(123,97,255,.3);border-radius:20px;overflow:hidden;animation:fadeIn .3s ease;}
  .db-review-header{padding:24px 24px 0;}
  .db-review-eyebrow{font-size:10px;text-transform:uppercase;letter-spacing:2px;color:var(--accent2);}
  .db-review-title{font-family:'Syne',sans-serif;font-weight:700;font-size:20px;letter-spacing:-.3px;margin-top:6px;}
  .db-review-sub{font-size:12px;color:var(--muted);margin-top:4px;}
  .db-stars{display:flex;gap:10px;padding:24px;flex-wrap:wrap;}
  .db-star-btn{flex:1;min-width:70px;padding:14px 8px;background:var(--surface2);border:1px solid var(--border);border-radius:14px;color:var(--text);font-size:18px;cursor:pointer;transition:all .2s;display:flex;flex-direction:column;align-items:center;gap:6px;font-family:'DM Mono',monospace;}
  .db-star-btn:hover{border-color:var(--warning);background:rgba(255,182,39,.07);transform:translateY(-2px);box-shadow:0 8px 20px rgba(255,182,39,.12);}
  .db-star-label{font-size:10px;color:var(--muted);}

  /* ═══════════════════════════════════════════
     CONSUMPTION TRACKER
  ═══════════════════════════════════════════ */
  .ct-summary-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;}
  @media(max-width:640px){.ct-summary-strip{grid-template-columns:1fr 1fr;}}
  .ct-sum-card{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:18px 20px;display:flex;flex-direction:column;gap:6px;transition:border-color .2s;}
  .ct-sum-card:hover{border-color:var(--border2);}
  .ct-sum-label{font-size:9px;text-transform:uppercase;letter-spacing:1.5px;color:var(--muted);}
  .ct-sum-val{font-family:'Syne',sans-serif;font-weight:800;font-size:26px;letter-spacing:-.5px;line-height:1;}
  .ct-sum-sub{font-size:10px;color:var(--muted);margin-top:2px;}

  .ct-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;}
  @media(max-width:720px){.ct-grid{grid-template-columns:1fr;}}

  .ct-card{background:var(--surface);border:1px solid var(--border);border-radius:20px;padding:22px;display:flex;flex-direction:column;gap:16px;animation:slideUp .4s ease both;transition:border-color .2s;}
  .ct-card:hover{border-color:var(--border2);}
  .ct-card.low{border-color:rgba(255,77,109,.3);background:linear-gradient(160deg,rgba(255,77,109,.03),var(--surface));}
  .ct-card.warn{border-color:rgba(255,182,39,.3);background:linear-gradient(160deg,rgba(255,182,39,.03),var(--surface));}

  .ct-card-top{display:flex;align-items:flex-start;justify-content:space-between;}
  .ct-item-id{display:flex;align-items:center;gap:8px;}
  .ct-icon{font-size:24px;line-height:1;}
  .ct-item-name{font-family:'Syne',sans-serif;font-weight:800;font-size:17px;text-transform:capitalize;}
  .ct-status-pill{font-size:9px;padding:3px 8px;border-radius:20px;letter-spacing:.5px;font-weight:700;}
  .ct-status-pill.ok{background:rgba(0,200,150,.1);border:1px solid rgba(0,200,150,.3);color:var(--success);}
  .ct-status-pill.warn{background:rgba(255,182,39,.1);border:1px solid rgba(255,182,39,.3);color:var(--warning);animation:blink 3s infinite;}
  .ct-status-pill.low{background:rgba(255,77,109,.12);border:1px solid rgba(255,77,109,.35);color:var(--danger);animation:blink 2s infinite;}

  .ct-pct{font-family:'Syne',sans-serif;font-weight:800;font-size:42px;letter-spacing:-2px;line-height:1;}
  .ct-pct-unit{font-size:14px;font-weight:400;color:var(--muted);letter-spacing:0;margin-left:2px;}

  .ct-bar-wrap{display:flex;flex-direction:column;gap:5px;}
  .ct-bar{height:6px;background:var(--surface2);border-radius:99px;overflow:hidden;border:1px solid var(--border);}
  .ct-bar-fill{height:100%;border-radius:99px;transition:width .9s cubic-bezier(.4,0,.2,1),background .5s ease;}

  .ct-stats{display:grid;grid-template-columns:1fr 1fr;gap:10px;}
  .ct-stat{background:var(--surface2);border:1px solid var(--border);border-radius:10px;padding:10px 12px;}
  .ct-stat-label{font-size:9px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);}
  .ct-stat-val{font-family:'Syne',sans-serif;font-weight:700;font-size:15px;margin-top:3px;}

  .ct-runout{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--muted);padding:8px 0 0;}
  .ct-runout-date{font-family:'Syne',sans-serif;font-weight:700;font-size:12px;}

  .ct-chart-section{display:flex;flex-direction:column;gap:6px;}
  .ct-chart-label{font-size:9px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);}
  .ct-charts{display:flex;align-items:flex-end;justify-content:space-between;gap:8px;}

  .ct-tick-note{font-size:9px;color:var(--muted);padding:4px 0;display:flex;align-items:center;gap:5px;}
  .ct-tick-dot{width:5px;height:5px;border-radius:50%;background:var(--success);animation:blink 1.5s infinite;flex-shrink:0;}

  /* ═══════════════════════════════════════════
     COMMISSION PANEL
  ═══════════════════════════════════════════ */
  .cm-hero{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px;}
  @media(max-width:640px){.cm-hero{grid-template-columns:1fr 1fr;}}

  .cm-hero-card{background:var(--surface);border:1px solid var(--border);border-radius:18px;padding:20px 22px;display:flex;flex-direction:column;gap:6px;position:relative;overflow:hidden;transition:border-color .2s;}
  .cm-hero-card:hover{border-color:var(--border2);}
  .cm-hero-card.highlight{border-color:rgba(255,182,39,.3);background:linear-gradient(135deg,rgba(255,182,39,.05),var(--surface));}
  .cm-hero-card.highlight::before{content:'';position:absolute;inset:-1px;border-radius:18px;background:linear-gradient(135deg,rgba(255,182,39,.2),transparent,transparent);pointer-events:none;z-index:0;}
  .cm-hero-label{font-size:9px;text-transform:uppercase;letter-spacing:1.5px;color:var(--muted);position:relative;z-index:1;}
  .cm-hero-val{font-family:'Syne',sans-serif;font-weight:800;font-size:28px;letter-spacing:-1px;line-height:1;position:relative;z-index:1;}
  .cm-hero-sub{font-size:10px;color:var(--muted);position:relative;z-index:1;}
  .cm-rate-pill{font-size:10px;padding:3px 10px;border-radius:20px;background:rgba(255,182,39,.12);border:1px solid rgba(255,182,39,.3);color:var(--warning);letter-spacing:.5px;width:fit-content;margin-top:4px;}

  .cm-table{background:var(--surface);border:1px solid var(--border);border-radius:20px;overflow:hidden;}
  .cm-table-header{padding:16px 24px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;}
  .cm-table-title{font-family:'Syne',sans-serif;font-weight:700;font-size:16px;}
  .cm-table-sub{font-size:10px;color:var(--muted);margin-top:2px;}

  .cm-col-heads{display:grid;grid-template-columns:72px 1fr 80px 70px 80px;gap:8px;padding:10px 24px;border-bottom:1px solid var(--border);background:var(--surface2);}
  .cm-col-head{font-size:9px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);}
  .cm-col-head.right{text-align:right;}

  .cm-row{display:grid;grid-template-columns:72px 1fr 80px 70px 80px;gap:8px;padding:13px 24px;border-bottom:1px solid var(--border);align-items:center;transition:background .15s;animation:fadeIn .3s ease both;}
  .cm-row:last-child{border-bottom:none;}
  .cm-row:hover{background:rgba(255,255,255,.02);}

  .cm-row-id{font-size:10px;color:var(--muted);font-family:'DM Mono',monospace;}
  .cm-row-vendor{display:flex;flex-direction:column;gap:2px;min-width:0;}
  .cm-row-vendor-name{font-family:'Syne',sans-serif;font-weight:700;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:flex;align-items:center;gap:6px;}
  .cm-item-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;}
  .cm-row-date{font-size:10px;color:var(--muted);margin-top:1px;}
  .cm-row-qty{font-size:12px;color:var(--text);text-align:center;}
  .cm-row-price{font-size:13px;color:var(--text);text-align:right;}
  .cm-row-comm{display:flex;flex-direction:column;align-items:flex-end;gap:1px;}
  .cm-comm-val{font-family:'Syne',sans-serif;font-weight:700;font-size:14px;color:var(--warning);}
  .cm-comm-label{font-size:9px;color:var(--muted);}

  .cm-footer{padding:16px 24px;background:var(--surface2);border-top:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;}
  .cm-footer-left{display:flex;flex-direction:column;gap:3px;}
  .cm-footer-label{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);}
  .cm-footer-val{font-family:'Syne',sans-serif;font-weight:800;font-size:24px;color:var(--warning);text-shadow:0 0 20px rgba(255,182,39,.3);}
  .cm-footer-note{font-size:10px;color:var(--muted);}
  .cm-new-badge{font-size:9px;padding:2px 7px;border-radius:20px;background:rgba(0,200,150,.12);border:1px solid rgba(0,200,150,.3);color:var(--success);letter-spacing:.5px;animation:pulseGlow 2s infinite;}
`;

export default function Dashboard() {
  const items = ["rice", "milk", "water"];
  const [mode, setMode] = useState("manual");

  // ── Manual state ──
  const [selectedItems, setSelectedItems] = useState([]);
  const [vendorOptions, setVendorOptions] = useState({});
  const [cart, setCart]                   = useState([]);
  const [total, setTotal]                 = useState(0);
  const [reviewQueue, setReviewQueue]     = useState([]);
  const [currentReviewIndex, setCurrentReviewIndex] = useState(0);

  // ── Smart state ──
  const [smartItem, setSmartItem]             = useState("rice");
  const [orderedQty, setOrderedQty]           = useState(10);
  const [adults, setAdults]                   = useState(2);
  const [children, setChildren]               = useState(1);
  const [adultConsumption, setAdultConsumption] = useState(0.5);
  const [childConsumption, setChildConsumption] = useState(0.2);
  const [initialDays, setInitialDays]         = useState(null);
  const [currentDaysLeft, setCurrentDaysLeft] = useState(null);
  const [countdown, setCountdown]             = useState(null);
  const [smartVendors, setSmartVendors]       = useState([]);
  const [notificationTriggered, setNotificationTriggered] = useState(false);

  // ── Consumption tracker state ──
  // Each item: { pct: number, history: number[] }
  // pct ticks down every ~3s to simulate live depletion
  const [stockLevels, setStockLevels] = useState(() => ({
    rice:  { pct: SEED_HISTORY.rice.at(-1),  history: [...SEED_HISTORY.rice]  },
    milk:  { pct: SEED_HISTORY.milk.at(-1),  history: [...SEED_HISTORY.milk]  },
    water: { pct: SEED_HISTORY.water.at(-1), history: [...SEED_HISTORY.water] },
  }));
  const tickRef = useRef(0);

  // Simulate live depletion every 3 seconds
  useEffect(() => {
    const id = setInterval(() => {
      tickRef.current += 1;
      setStockLevels(prev => {
        const next = {};
        for (const item of Object.keys(prev)) {
          // Each tick = small random depletion (0.15–0.55%)
          const decay = +(Math.random() * 0.4 + 0.15).toFixed(2);
          const newPct = Math.max(1, +(prev[item].pct - decay).toFixed(2));
          // Push a new history point every 5 ticks (~15s = "new day" for demo)
          const updateHistory = tickRef.current % 5 === 0;
          const newHistory = updateHistory
            ? [...prev[item].history.slice(-13), Math.round(newPct)]
            : prev[item].history;
          next[item] = { pct: newPct, history: newHistory };
        }
        return next;
      });
    }, 3000);
    return () => clearInterval(id);
  }, []);

  // ── Order / commission history ──
  const [orderHistory, setOrderHistory] = useState(SEED_ORDERS);
  const [newOrderIds, setNewOrderIds]   = useState(new Set());

  // ── Manual logic ──
  const toggleItem = async (item) => {
    try {
      if (selectedItems.includes(item)) {
        const updated = selectedItems.filter(i => i !== item);
        setVendorOptions(prev => { const c={...prev}; delete c[item]; return c; });
        const updatedCart = cart.filter(c => c.item !== item);
        setCart(updatedCart);
        setTotal(updatedCart.reduce((s,c)=>s+c.price,0));
        setSelectedItems(updated);
      } else {
        const res = await API.get(`/vendors/compare/${item}`);
        setVendorOptions(prev => ({ ...prev, [item]: res.data }));
        setSelectedItems(prev => [...prev, item]);
      }
    } catch { alert("Vendor fetch failed."); }
  };

  const addToCart = (item, vendor) => {
    const entry = { item, vendor: vendor.vendor_name, vendor_id: vendor.vendor_id, price: vendor.price };
    const updated = [...cart.filter(c => c.item !== item), entry];
    setCart(updated);
    setTotal(updated.reduce((s,c)=>s+c.price,0));
  };

  const addRadarVendorToCart = (item, rv) => {
    const priceStr = rv.items?.[item] ?? rv.items?.rice ?? "₹0";
    const price = parseInt(priceStr.replace("₹","")) || 0;
    addToCart(item, { vendor_name: rv.name, vendor_id: rv.id, price });
  };

  // ── Smart logic ──
  const runSmartPrediction = async () => {
    const daily = (adults * adultConsumption) + (children * childConsumption);
    if (daily <= 0) { alert("Consumption must be > 0"); return; }
    const days = orderedQty / daily;
    setInitialDays(days); setCurrentDaysLeft(days);
    setNotificationTriggered(false); setSmartVendors([]);
    const simTime = days * 5000;
    const totalSec = Math.round(simTime / 1000);
    setCountdown(totalSec);
    const interval = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) { clearInterval(interval); setCurrentDaysLeft(0); return 0; }
        const s = prev - 1;
        const upd = (days * (s * 1000)) / simTime;
        setCurrentDaysLeft(upd.toFixed(2));
        if (upd <= 2 && !notificationTriggered) {
          API.get(`/vendors/compare/${smartItem}`).then(r => setSmartVendors(r.data));
          setNotificationTriggered(true);
        }
        return s;
      });
    }, 1000);
  };

  // ── Place order ── records in history + commission
  const placeOrder = () => {
    if (cart.length === 0) return;
    alert("Order Placed Successfully!");
    const today = new Date().toLocaleDateString("en-IN",{day:"numeric",month:"short"});
    const newOrders = cart.map((c, i) => {
      const id = `ORD-${String(orderHistory.length + i + 1).padStart(3,"0")}`;
      return {
        id, date: today,
        vendor: c.vendor, item: c.item,
        price: c.price, qty: "—",
        commission: Math.round(c.price * COMMISSION_RATE),
        isNew: true,
      };
    });
    setOrderHistory(prev => [...newOrders, ...prev]);
    setNewOrderIds(new Set(newOrders.map(o => o.id)));
    // Review queue
    const seen = new Set();
    const unique = cart.filter(c => { if(seen.has(c.vendor_id)) return false; seen.add(c.vendor_id); return true; });
    setReviewQueue(unique); setCurrentReviewIndex(0);
  };

  const submitReview = async (rating) => {
    const vendor = reviewQueue[currentReviewIndex];
    const res = await API.post("/vendors/review", null, { params: { vendor_id: vendor.vendor_id, new_rating: rating } });
    alert(`New Rating: ${res.data.new_rating}`);
    if (currentReviewIndex + 1 < reviewQueue.length) setCurrentReviewIndex(i => i+1);
    else { setReviewQueue([]); setCurrentReviewIndex(0); }
  };

  // ── Derived values ──
  const currentVendor  = reviewQueue[currentReviewIndex];
  const dailyUsage     = (adults * adultConsumption) + (children * childConsumption);
  const daysNum        = parseFloat(currentDaysLeft);
  const progressPct    = initialDays ? Math.max(0,(daysNum/initialDays)*100) : 0;
  const progressClass  = daysNum<=1?"danger":daysNum<=2?"warning":"";
  const cartCommTotal  = cart.reduce((s,c) => s + Math.round(c.price * COMMISSION_RATE), 0);
  const totalCommission = orderHistory.reduce((s,o) => s + (o.commission||0), 0);
  const totalRevenue   = orderHistory.reduce((s,o) => s + (o.price||0), 0);

  // Consumption card status helper
  const statusOf = pct => pct < 25 ? "low" : pct < 45 ? "warn" : "ok";
  const barGradient = (pct) =>
    pct < 25 ? "linear-gradient(90deg,#c0192e,#ff4d6d)"
    : pct < 45 ? "linear-gradient(90deg,#ffb627,#ffd966)"
    : `linear-gradient(90deg,var(--accent2),var(--accent))`;

  return (
    <>
      <style>{styles}</style>
      <div className="db-root">

        {/* Header */}
        <header className="db-header">
          <div className="db-logo"><div className="db-logo-dot"/>GrocerAI</div>
          <div className="db-badge">Smart Grocery v2</div>
        </header>

        <div className="db-body">

          {/* ── Tabs ── */}
          <div className="db-tabs">
            {[
              { key:"manual",     label:"🛒 AI Marketplace"  },
              { key:"smart",      label:"⚡ Smart Automator"  },
              { key:"tracker",    label:"📊 Consumption"       },
              { key:"commission", label:"💰 Commission"         },
            ].map(({key,label}) => (
              <button key={key}
                className={`db-tab${mode===key?" active":""}`}
                onClick={() => setMode(key)}>
                {label}
              </button>
            ))}
          </div>

          <div style={{ marginTop: 16 }}>
            <AgentChatPanel />
          </div>

          {/* ══════════════════════════════════════
              MANUAL MODE
          ══════════════════════════════════════ */}
          {mode === "manual" && (<>
            <div className="db-section-header">
              <div className="db-section-title">AI Grocery Marketplace</div>
              <div className="db-section-line"/>
            </div>
            <div className="db-items">
              {items.map(item => {
                const isSelected = selectedItems.includes(item);
                const inCart = cart.some(c => c.item === item);
                return (
                  <div key={item} className={`db-item-row${isSelected?" selected":""}`}>
                    <div className="db-item-toggle" onClick={() => toggleItem(item)}>
                      <div className={`db-checkbox${isSelected?" checked":""}`}>{isSelected&&"✓"}</div>
                      <div className="db-item-name">{item}</div>
                      {inCart && <div className="db-item-sub">IN CART</div>}
                    </div>
                    {vendorOptions[item] && (
                      <div className="db-vendors-wrap">
                        {vendorOptions[item].map((v,idx) => (
                          <div key={idx} className={`db-vendor-row${idx===0?" top":""}`}>
                            <div className={`db-vrank${idx===0?" gold":""}`}>{idx===0?"★":`#${idx+1}`}</div>
                            <div className="db-vinfo">
                              <div className="db-vname">{v.vendor_name}{idx===0&&<span className="db-top-pill">BEST PICK</span>}</div>
                              <div className="db-vmeta">
                                <div><div className="db-vmeta-label">Price</div><div className="db-vmeta-val">₹{v.price}</div></div>
                                <div><div className="db-vmeta-label">Rating</div><div className="db-vmeta-val">⭐ {v.rating}</div></div>
                              </div>
                            </div>
                            <div className="db-vscore">{v.final_score}<span className="db-vscore-label">SCORE</span></div>
                            <button
                              className={`db-btn-add${cart.some(c=>c.item===item&&c.vendor_id===v.vendor_id)?" in-cart":""}`}
                              onClick={() => addToCart(item, v)}>
                              {cart.some(c=>c.item===item&&c.vendor_id===v.vendor_id)?"✓ Added":"Add →"}
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                    {vendorOptions[item] && (<>
                      <div className="db-radar-divider">
                        <div className="db-radar-divider-line"/>
                        <div className="db-radar-divider-label">
                          <div className="db-radar-divider-dot"/>Nearby Vendor Radar
                        </div>
                        <div className="db-radar-divider-line"/>
                      </div>
                      <div className="db-radar-inline">
                        <VendorRadar onAddToCart={rv => addRadarVendorToCart(item, rv)}/>
                      </div>
                    </>)}
                  </div>
                );
              })}
            </div>
          </>)}

          {/* ══════════════════════════════════════
              SMART MODE
          ══════════════════════════════════════ */}
          {mode === "smart" && (<>
            <div className="db-section-header">
              <div className="db-section-title">AI Smart Automator</div>
              <div className="db-section-line"/>
            </div>
            <div className="db-smart-card">
              <div className="db-smart-grid">
                <div className="db-field">
                  <div className="db-field-label">Item</div>
                  <select className="db-select" value={smartItem} onChange={e=>setSmartItem(e.target.value)}>
                    <option value="rice">Rice</option>
                    <option value="milk">Milk</option>
                    <option value="water">Water</option>
                  </select>
                </div>
                <div className="db-field">
                  <div className="db-field-label">Quantity Ordered (units)</div>
                  <input type="number" className="db-input" value={orderedQty} onChange={e=>setOrderedQty(parseFloat(e.target.value))}/>
                </div>
                <div className="db-field">
                  <div className="db-field-label">Adults & Daily Consumption</div>
                  <div className="db-consumption-pair">
                    <input type="number" className="db-input" placeholder="Adults" value={adults} onChange={e=>setAdults(parseInt(e.target.value))}/>
                    <input type="number" step="0.1" className="db-input" placeholder="Units/day" value={adultConsumption} onChange={e=>setAdultConsumption(parseFloat(e.target.value))}/>
                  </div>
                </div>
                <div className="db-field">
                  <div className="db-field-label">Children & Daily Consumption</div>
                  <div className="db-consumption-pair">
                    <input type="number" className="db-input" placeholder="Children" value={children} onChange={e=>setChildren(parseInt(e.target.value))}/>
                    <input type="number" step="0.1" className="db-input" placeholder="Units/day" value={childConsumption} onChange={e=>setChildConsumption(parseFloat(e.target.value))}/>
                  </div>
                </div>
              </div>
              <button className="db-btn-predict" onClick={runSmartPrediction}>⚡ Run Prediction</button>
            </div>
            {initialDays && (
              <div className="db-prediction">
                <div className="db-pred-label">Consumption Forecast</div>
                <div className="db-pred-row">
                  <div className="db-pred-stat">
                    <div className="db-pred-label">Daily Usage</div>
                    <div className="db-pred-val">{dailyUsage.toFixed(2)}</div>
                    <div style={{fontSize:11,color:"var(--muted)"}}>units/day</div>
                  </div>
                  <div className="db-pred-stat">
                    <div className="db-pred-label">Total Duration</div>
                    <div className="db-pred-val">{initialDays.toFixed(1)}</div>
                    <div style={{fontSize:11,color:"var(--muted)"}}>days</div>
                  </div>
                  <div className="db-pred-stat">
                    <div className="db-pred-label">Days Remaining</div>
                    <div className={`db-pred-val${progressClass?` ${progressClass}`:""}`}>{currentDaysLeft??initialDays.toFixed(2)}</div>
                    <div style={{fontSize:11,color:"var(--muted)"}}>days left</div>
                  </div>
                </div>
                <div>
                  <div className="db-progress">
                    <div className={`db-progress-fill${progressClass?` ${progressClass}`:""}`} style={{width:`${progressPct}%`}}/>
                  </div>
                  {countdown!==null&&countdown>0&&(
                    <div className="db-countdown" style={{marginTop:8}}>
                      <div className="db-countdown-dot"/>Simulation running — {countdown}s elapsed
                    </div>
                  )}
                </div>
              </div>
            )}
            {smartVendors.length>0&&(<>
              <div className="db-alert">
                <span style={{fontSize:22,flexShrink:0}}>⚠️</span>
                <div>
                  <div className="db-alert-title">Only 2 Days of Stock Left!</div>
                  <div className="db-alert-sub">Best vendors ranked below — restock now</div>
                </div>
              </div>
              <div style={{display:"flex",flexDirection:"column",gap:10,animation:"fadeIn .3s ease"}}>
                {smartVendors.map((v,idx)=>(
                  <div key={idx} className={`db-vendor-row${idx===0?" top":""}`}
                    style={{background:"var(--surface)",border:"1px solid var(--border)",borderRadius:14,padding:"16px 18px"}}>
                    <div className={`db-vrank${idx===0?" gold":""}`}>{idx===0?"★":`#${idx+1}`}</div>
                    <div className="db-vinfo">
                      <div className="db-vname">{v.vendor_name}{idx===0&&<span className="db-top-pill">BEST PICK</span>}</div>
                      <div className="db-vmeta">
                        <div><div className="db-vmeta-label">Price</div><div className="db-vmeta-val">₹{v.price}</div></div>
                        <div><div className="db-vmeta-label">Rating</div><div className="db-vmeta-val">⭐ {v.rating}</div></div>
                      </div>
                    </div>
                    <button className="db-btn-add" onClick={()=>addToCart(smartItem,v)}>Add →</button>
                  </div>
                ))}
              </div>
            </>)}
          </>)}

          {/* ══════════════════════════════════════
              CONSUMPTION TRACKER
          ══════════════════════════════════════ */}
          {mode === "tracker" && (<>
            <div className="db-section-header">
              <div className="db-section-title">Consumption Tracker</div>
              <div className="db-section-line"/>
            </div>

            {/* Summary strip */}
            <div className="ct-summary-strip">
              {(() => {
                const avgPct = Object.values(stockLevels).reduce((s,v)=>s+v.pct,0)/3;
                const lowCount = Object.values(stockLevels).filter(v=>v.pct<25).length;
                const soonest = Object.entries(stockLevels)
                  .map(([item,{pct}])=>({item, days: daysLeft(pct,item)}))
                  .sort((a,b)=>a.days-b.days)[0];
                const totalUsagePerDay = Object.keys(DAILY_USAGE_UNITS).reduce((s,k)=>s+DAILY_USAGE_UNITS[k],0);
                return (<>
                  <div className="ct-sum-card">
                    <div className="ct-sum-label">Avg Stock Left</div>
                    <div className="ct-sum-val" style={{color:"var(--accent)"}}>{avgPct.toFixed(1)}<span style={{fontSize:16,color:"var(--muted)",fontWeight:400}}>%</span></div>
                    <div className="ct-sum-sub">across all items</div>
                  </div>
                  <div className="ct-sum-card">
                    <div className="ct-sum-label">Items Low</div>
                    <div className="ct-sum-val" style={{color: lowCount>0?"var(--danger)":"var(--success)"}}>{lowCount}<span style={{fontSize:16,color:"var(--muted)",fontWeight:400}}>/3</span></div>
                    <div className="ct-sum-sub">{lowCount===0?"all stocked":"below 25%"}</div>
                  </div>
                  <div className="ct-sum-card">
                    <div className="ct-sum-label">Next Runout</div>
                    <div className="ct-sum-val" style={{fontSize:20,color:"var(--warning)",paddingTop:4}}>{soonest.item}</div>
                    <div className="ct-sum-sub">in ~{soonest.days} days</div>
                  </div>
                  <div className="ct-sum-card">
                    <div className="ct-sum-label">Daily Total Use</div>
                    <div className="ct-sum-val" style={{fontSize:20,paddingTop:4,color:"var(--accent2)"}}>{totalUsagePerDay.toFixed(1)}</div>
                    <div className="ct-sum-sub">units/day all items</div>
                  </div>
                </>);
              })()}
            </div>

            {/* Per-item cards */}
            <div className="ct-grid">
              {Object.entries(stockLevels).map(([item,{pct,history}],cardIdx) => {
                const color  = ITEM_COLORS[item];
                const status = statusOf(pct);
                const days   = daysLeft(pct, item);
                const unitsLeft = +((pct/100)*MAX_STOCK[item]).toFixed(1);
                return (
                  <div key={item} className={`ct-card ${status}`}
                    style={{animationDelay:`${cardIdx*80}ms`}}>

                    {/* Top row */}
                    <div className="ct-card-top">
                      <div className="ct-item-id">
                        <div className="ct-icon">{ITEM_ICONS[item]}</div>
                        <div className="ct-item-name">{item}</div>
                      </div>
                      <span className={`ct-status-pill ${status}`}>
                        {status==="ok"?"● OK":status==="warn"?"▲ WATCH":"⚠ LOW"}
                      </span>
                    </div>

                    {/* Big percentage */}
                    <div>
                      <div className="ct-pct" style={{color}}>
                        {pct.toFixed(1)}<span className="ct-pct-unit">%</span>
                      </div>
                    </div>

                    {/* Bar */}
                    <div className="ct-bar-wrap">
                      <div className="ct-bar">
                        <div className="ct-bar-fill" style={{
                          width:`${pct}%`,
                          background: barGradient(pct),
                          boxShadow:`0 0 8px ${color}44`,
                        }}/>
                      </div>
                    </div>

                    {/* Stats */}
                    <div className="ct-stats">
                      <div className="ct-stat">
                        <div className="ct-stat-label">Stock Left</div>
                        <div className="ct-stat-val" style={{color}}>{unitsLeft} {ITEM_UNIT[item]}</div>
                      </div>
                      <div className="ct-stat">
                        <div className="ct-stat-label">Daily Use</div>
                        <div className="ct-stat-val">{DAILY_USAGE_UNITS[item]} {ITEM_UNIT[item]}</div>
                      </div>
                    </div>

                    {/* Run-out date */}
                    <div className="ct-runout">
                      🗓 Runs out:&nbsp;
                      <span className="ct-runout-date" style={{
                        color: status==="low"?"var(--danger)":status==="warn"?"var(--warning)":"var(--text)"
                      }}>
                        {runoutLabel(days)} ({days}d)
                      </span>
                    </div>

                    {/* Charts */}
                    <div className="ct-chart-section">
                      <div className="ct-chart-label">14-day trend</div>
                      <div className="ct-charts">
                        <Sparkline data={history} color={color}/>
                        <div style={{flex:1}}>
                          <MiniBarChart data={history} color={color}/>
                          <div style={{display:"flex",justifyContent:"space-between",fontSize:8,color:"var(--muted)",marginTop:3}}>
                            <span>14d ago</span><span>Now</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Live tick note */}
                    <div className="ct-tick-note">
                      <div className="ct-tick-dot"/>
                      Live — depleting {(DAILY_USAGE_UNITS[item]/24/3600*3).toFixed(4)} {ITEM_UNIT[item]}/tick
                    </div>

                  </div>
                );
              })}
            </div>
          </>)}

          {/* ══════════════════════════════════════
              COMMISSION
          ══════════════════════════════════════ */}
          {mode === "commission" && (<>
            <div className="db-section-header">
              <div className="db-section-title">Commission Earned</div>
              <div className="db-section-line"/>
            </div>

            {/* Hero stats */}
            <div className="cm-hero">
              <div className="cm-hero-card highlight">
                <div className="cm-hero-label">Total Earned</div>
                <div className="cm-hero-val" style={{color:"var(--warning)"}}>₹{totalCommission}</div>
                <div className="cm-hero-sub">lifetime commissions</div>
                <div className="cm-rate-pill">5% flat rate</div>
              </div>
              <div className="cm-hero-card">
                <div className="cm-hero-label">Order Volume</div>
                <div className="cm-hero-val" style={{color:"var(--success)"}}>₹{totalRevenue}</div>
                <div className="cm-hero-sub">gross order value</div>
              </div>
              <div className="cm-hero-card">
                <div className="cm-hero-label">Total Orders</div>
                <div className="cm-hero-val" style={{color:"var(--accent)"}}>{orderHistory.length}</div>
                <div className="cm-hero-sub">placed via GrocerAI</div>
              </div>
              <div className="cm-hero-card">
                <div className="cm-hero-label">Avg per Order</div>
                <div className="cm-hero-val" style={{color:"var(--accent2)"}}>
                  ₹{orderHistory.length ? Math.round(totalCommission/orderHistory.length) : 0}
                </div>
                <div className="cm-hero-sub">commission/order</div>
              </div>
            </div>

            {/* Order table */}
            <div className="cm-table">
              <div className="cm-table-header">
                <div>
                  <div className="cm-table-title">Order History</div>
                  <div className="cm-table-sub">All orders · newest first · commission at 5%</div>
                </div>
              </div>
              <div className="cm-col-heads">
                <div className="cm-col-head">Order</div>
                <div className="cm-col-head">Vendor</div>
                <div className="cm-col-head" style={{textAlign:"center"}}>Qty</div>
                <div className="cm-col-head right">Price</div>
                <div className="cm-col-head right">Commission</div>
              </div>
              <div>
                {orderHistory.map((o, idx) => (
                  <div key={o.id + idx} className="cm-row" style={{animationDelay:`${idx*40}ms`}}>
                    <div className="cm-row-id">
                      <div>{o.id}</div>
                      <div style={{fontSize:9,color:"var(--muted)",marginTop:2}}>{o.date}</div>
                    </div>
                    <div className="cm-row-vendor">
                      <div className="cm-row-vendor-name">
                        <div className="cm-item-dot" style={{background:ITEM_COLORS[o.item]||"var(--muted)"}}/>
                        {o.vendor}
                        {newOrderIds.has(o.id) && <span className="cm-new-badge">NEW</span>}
                      </div>
                      <div className="cm-row-date">{o.item}</div>
                    </div>
                    <div className="cm-row-qty">{o.qty}</div>
                    <div className="cm-row-price">₹{o.price}</div>
                    <div className="cm-row-comm">
                      <div className="cm-comm-val">+₹{o.commission}</div>
                      <div className="cm-comm-label">5% of ₹{o.price}</div>
                    </div>
                  </div>
                ))}
              </div>
              <div className="cm-footer">
                <div className="cm-footer-left">
                  <div className="cm-footer-label">Total Commission Earned</div>
                  <div className="cm-footer-note">{orderHistory.length} orders · 5% flat rate · lifetime</div>
                </div>
                <div className="cm-footer-val">₹{totalCommission}</div>
              </div>
            </div>
          </>)}

          {/* ══════════════════════════════════════
              CART — always visible at bottom
          ══════════════════════════════════════ */}
          <div className="db-cart-card">
            <div className="db-cart-header">
              <div className="db-cart-title">Cart</div>
              <div className="db-cart-count">{cart.length} item{cart.length!==1?"s":""}</div>
            </div>
            {cart.length===0 ? (
              <div className="db-cart-empty">No items added yet</div>
            ) : (<>
              <div className="db-cart-items">
                {cart.map((c,idx) => (
                  <div key={idx} className="db-cart-item">
                    <div className="db-cart-dot" style={{background:ITEM_COLORS[c.item]||"var(--accent2)"}}/>
                    <div className="db-cart-item-name">{c.item}</div>
                    <div className="db-cart-vendor">{c.vendor}</div>
                    <div className="db-cart-price">₹{c.price}</div>
                    <div className="db-cart-comm">+₹{Math.round(c.price*COMMISSION_RATE)} comm</div>
                  </div>
                ))}
              </div>
              <div className="db-cart-footer">
                <div>
                  <div className="db-total-label">Total</div>
                  <div className="db-total-val">₹{total}</div>
                  <div className="db-cart-comm-total">+₹{cartCommTotal} commission earned on this order</div>
                </div>
                <button className="db-btn-order" onClick={placeOrder}>Place Order →</button>
              </div>
            </>)}
          </div>

          {/* Review */}
          {currentVendor && (
            <div className="db-review-card">
              <div className="db-review-header">
                <div className="db-review-eyebrow">Post-Order Feedback</div>
                <div className="db-review-title">Rate {currentVendor.vendor}</div>
                <div className="db-review-sub">{currentReviewIndex+1} of {reviewQueue.length} vendors to review</div>
              </div>
              <div className="db-stars">
                {[5,4,3,2,1].map(r => (
                  <button key={r} className="db-star-btn" onClick={() => submitReview(r)}>
                    {"⭐".repeat(r)}
                    <span className="db-star-label">{r} star{r!==1?"s":""}</span>
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