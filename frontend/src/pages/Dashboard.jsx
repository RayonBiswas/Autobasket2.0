import { useCallback, useEffect, useState } from "react";
import API from "../services/api";
import AgentChatPanel from "../components/AgentChatPanel";

const REFRESH_MS = 10000;
const ITEM_ICONS = { milk: "🥛", rice: "🍚", water: "💧", curd: "🥣", eggs: "🥚", bread: "🍞", tomato: "🍅", onion: "🧅", potato: "🥔", apple: "🍎", banana: "🍌", juice: "🧃", cola: "🥤", paneer: "🧀", cheese: "🧀", butter: "🧈", wheat: "🌾", dal: "🫘", coriander: "🌿", ketchup: "🍅" };

// ─── Sparkline (remaining % over the last 14 days) ────────────────────────────
function Sparkline({ points, color, width = 140, height = 36 }) {
  if (!points || points.length < 2) return <div className="db-spark-empty">no history yet</div>;
  const P = 3;
  const xs = points.map((_, i) => P + (i / (points.length - 1)) * (width - P * 2));
  const ys = points.map((p) => height - P - p.remaining_fraction * (height - P * 2));
  const d = xs.map((x, i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(" ");
  return (
    <svg width={width} height={height} style={{ display: "block", overflow: "visible" }}>
      <path d={d} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={xs.at(-1)} cy={ys.at(-1)} r="3" fill={color} />
    </svg>
  );
}

const styles = `
  .db-root { padding: 32px; display: flex; flex-direction: column; gap: 28px; max-width: 1100px; }
  .db-title { font-family: 'Syne', sans-serif; font-size: 28px; font-weight: 800; letter-spacing: -1px; }
  .db-sub { color: var(--muted); font-size: 13px; margin-top: 6px; }
  .db-section { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
  .db-section-title { font-family: 'Syne', sans-serif; font-weight: 700; font-size: 17px; white-space: nowrap; }
  .db-section-line { flex: 1; height: 1px; background: var(--border); }
  .db-count { font-size: 11px; padding: 3px 8px; border-radius: 6px; background: var(--surface2); border: 1px solid var(--border); color: var(--muted); }

  .db-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 14px; }
  .db-card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 16px 18px;
    display: flex; flex-direction: column; gap: 10px; cursor: pointer; transition: border-color .2s, transform .2s;
  }
  .db-card:hover { border-color: rgba(255,255,255,0.18); transform: translateY(-2px); }
  .db-card.selected { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent) inset; }
  .db-card-head { display: flex; align-items: center; justify-content: space-between; }
  .db-card-name { font-family: 'Syne', sans-serif; font-weight: 700; font-size: 15px; text-transform: capitalize; display: flex; gap: 8px; align-items: center; }
  .db-pill { font-size: 10px; padding: 3px 8px; border-radius: 20px; letter-spacing: .5px; text-transform: uppercase; border: 1px solid; }
  .db-pill.safe { color: var(--success); border-color: rgba(0,200,150,0.4); background: rgba(0,200,150,0.08); }
  .db-pill.warning { color: var(--warning); border-color: rgba(255,182,39,0.4); background: rgba(255,182,39,0.08); }
  .db-pill.critical { color: var(--danger); border-color: rgba(255,77,109,0.4); background: rgba(255,77,109,0.08); }
  .db-pill.unknown { color: var(--muted); border-color: var(--border); }
  .db-bar { height: 7px; background: var(--surface2); border-radius: 99px; overflow: hidden; border: 1px solid var(--border); }
  .db-bar-fill { height: 100%; border-radius: 99px; transition: width .8s cubic-bezier(.4,0,.2,1); }
  .db-card-meta { display: flex; justify-content: space-between; font-size: 11px; color: var(--muted); }
  .db-card-meta strong { color: var(--text); font-weight: 500; }
  .db-spark-empty { font-size: 10px; color: var(--muted); height: 36px; display: flex; align-items: center; }

  .db-offers { background: var(--surface); border: 1px solid rgba(123,97,255,0.3); border-radius: 18px; padding: 20px 22px; display: flex; flex-direction: column; gap: 12px; }
  .db-offer { display: flex; align-items: center; gap: 14px; padding: 12px 14px; border-radius: 12px; background: var(--surface2); border: 1px solid var(--border); }
  .db-offer.top { border-color: rgba(0,200,150,0.35); }
  .db-rank { width: 34px; height: 34px; border-radius: 9px; display: flex; align-items: center; justify-content: center; font-family: 'Syne', sans-serif; font-weight: 800; background: var(--surface); border: 1px solid var(--border); color: var(--muted); flex-shrink: 0; }
  .db-rank.gold { color: var(--warning); border-color: rgba(255,182,39,0.4); }
  .db-offer-info { flex: 1; min-width: 0; }
  .db-offer-name { font-family: 'Syne', sans-serif; font-weight: 700; font-size: 14px; display: flex; gap: 8px; align-items: center; }
  .db-offer-kind { font-size: 9px; padding: 2px 6px; border-radius: 10px; background: var(--surface); border: 1px solid var(--border); color: var(--muted); text-transform: uppercase; letter-spacing: .5px; }
  .db-offer-meta { font-size: 11px; color: var(--muted); margin-top: 4px; display: flex; gap: 14px; flex-wrap: wrap; }
  .db-offer-meta b { color: var(--text); font-weight: 500; }
  .db-score { font-family: 'Syne', sans-serif; font-weight: 800; font-size: 15px; color: var(--accent); text-align: center; }
  .db-score small { display: block; font-family: 'DM Mono', monospace; font-size: 9px; color: var(--muted); font-weight: 400; }
  .db-order-btn { padding: 9px 16px; border-radius: 10px; border: 1px solid var(--border); background: transparent; color: var(--text); font-family: 'DM Mono', monospace; font-size: 12px; cursor: pointer; white-space: nowrap; }
  .db-order-btn:hover { border-color: var(--accent); color: var(--accent); }
  .db-order-btn.top { border-color: rgba(0,200,150,0.4); color: var(--success); }

  .db-orders { background: var(--surface); border: 1px solid var(--border); border-radius: 16px; overflow: hidden; }
  .db-order-row { display: grid; grid-template-columns: 70px 1fr 1fr 90px 120px; gap: 12px; padding: 12px 18px; border-top: 1px solid var(--border); font-size: 12px; align-items: center; }
  .db-order-row.head { border-top: none; color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: 1px; }
  .db-status { font-size: 10px; padding: 3px 8px; border-radius: 20px; background: var(--surface2); border: 1px solid var(--border); text-transform: uppercase; letter-spacing: .5px; text-align: center; }

  .db-empty { background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 28px; display: flex; flex-direction: column; gap: 12px; align-items: flex-start; }
  .db-btn { padding: 11px 18px; border: none; border-radius: 10px; cursor: pointer; color: #fff; background: linear-gradient(135deg, var(--accent2), var(--accent)); font-family: 'Syne', sans-serif; font-weight: 700; font-size: 13px; }
  .db-btn:disabled { opacity: .5; cursor: not-allowed; }
  .db-msg { font-size: 12px; color: var(--muted); }
  .db-toast { position: fixed; bottom: 24px; right: 24px; background: var(--surface); border: 1px solid rgba(0,200,150,0.4); color: var(--success); padding: 12px 16px; border-radius: 12px; font-size: 12px; z-index: 50; box-shadow: 0 8px 24px rgba(0,0,0,.4); }
`;

const barColor = (status) =>
  status === "critical" ? "linear-gradient(90deg,#c0192e,var(--danger))"
  : status === "warning" ? "linear-gradient(90deg,#ffb627,#ffd966)"
  : "linear-gradient(90deg,var(--accent2),var(--accent))";

const sparkColor = (status) => (status === "critical" ? "#ff4d6d" : status === "warning" ? "#ffb627" : "#00e5ff");

function Dashboard() {
  const [inventory, setInventory] = useState(null);
  const [history, setHistory] = useState({});
  const [selected, setSelected] = useState(null);
  const [offers, setOffers] = useState([]);
  const [orders, setOrders] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [toast, setToast] = useState(null);

  const loadInventory = useCallback(async () => {
    try {
      const res = await API.get("/inventory");
      const rows = res.data.inventory;
      setInventory(rows);
      const entries = await Promise.all(
        rows.map((r) => API.get(`/inventory/${r.product_id}/history?days=14`).then((h) => [r.product_id, h.data.points]).catch(() => [r.product_id, []]))
      );
      setHistory(Object.fromEntries(entries));
    } catch (err) {
      setMsg(err.response?.data?.detail || "Could not load inventory.");
      setInventory([]);
    }
  }, []);

  const loadOrders = useCallback(async () => {
    try {
      const res = await API.get("/orders");
      setOrders(res.data.orders.slice(0, 10));
    } catch { /* keep previous */ }
  }, []);

  useEffect(() => {
    loadInventory();
    loadOrders();
    const id = setInterval(loadInventory, REFRESH_MS);
    return () => clearInterval(id);
  }, [loadInventory, loadOrders]);

  useEffect(() => {
    if (!toast) return undefined;
    const id = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(id);
  }, [toast]);

  const select = async (row) => {
    if (selected?.product_id === row.product_id) { setSelected(null); setOffers([]); return; }
    setSelected(row);
    try {
      const res = await API.get(`/vendors/compare/${row.name}`);
      setOffers(res.data.slice(0, 3));
    } catch {
      setOffers([]);
    }
  };

  const order = async (offer) => {
    try {
      const res = await API.post("/orders", { vendor_id: offer.vendor_id, items: [{ product_id: selected.product_id, qty: 1 }] });
      setToast(`Order #${res.data.order_id} proposed — ${selected.name} from ${offer.vendor_name} for ₹${res.data.total_amount}`);
      loadOrders();
    } catch (err) {
      alert(err.response?.data?.detail || "Order failed");
    }
  };

  const seed = async () => {
    setBusy(true);
    try {
      const res = await API.post("/seed/dev");
      setMsg(res.data.message);
      await loadInventory();
    } catch (err) {
      setMsg(err.response?.data?.detail || "Seeding failed.");
    } finally {
      setBusy(false);
    }
  };

  const critical = inventory?.filter((r) => r.status === "critical").length ?? 0;

  return (
    <>
      <style>{styles}</style>
      <div className="db-root">
        <div>
          <div className="db-title">Your fridge</div>
          <div className="db-sub">
            {inventory === null ? "Loading…" : inventory.length === 0 ? "Nothing tracked yet." : `${inventory.length} items tracked · ${critical} need attention · refreshes every 10 s`}
          </div>
        </div>

        <AgentChatPanel />

        {inventory && inventory.length === 0 && (
          <div className="db-empty">
            <div>No inventory yet. Assign products to fridge slots, or load the demo data.</div>
            <button className="db-btn" onClick={seed} disabled={busy}>{busy ? "Seeding…" : "Seed dev data"}</button>
            {msg && <div className="db-msg">{msg}</div>}
          </div>
        )}

        {inventory && inventory.length > 0 && (
          <div>
            <div className="db-section">
              <div className="db-section-title">Inventory</div>
              <div className="db-section-line" />
              <div className="db-count">tap an item for the best places to buy</div>
            </div>
            <div className="db-grid">
              {inventory.map((r) => (
                <div key={r.product_id} className={`db-card${selected?.product_id === r.product_id ? " selected" : ""}`} onClick={() => select(r)}>
                  <div className="db-card-head">
                    <div className="db-card-name"><span>{ITEM_ICONS[r.name] || "📦"}</span>{r.name}</div>
                    <span className={`db-pill ${r.status}`}>{r.status}</span>
                  </div>
                  <div className="db-bar"><div className="db-bar-fill" style={{ width: `${Math.round(r.remaining_fraction * 100)}%`, background: barColor(r.status) }} /></div>
                  <div className="db-card-meta">
                    <span><strong>{r.remaining_qty}</strong> / {r.pack_size} {r.unit}</span>
                    <span><strong>{r.days_left}</strong> days left</span>
                  </div>
                  <Sparkline points={history[r.product_id]} color={sparkColor(r.status)} />
                </div>
              ))}
            </div>
          </div>
        )}

        {selected && (
          <div className="db-offers">
            <div className="db-section" style={{ marginBottom: 4 }}>
              <div className="db-section-title">Best places to buy {selected.name}</div>
              <div className="db-section-line" />
              <div className="db-count">{offers.length} ranked</div>
            </div>
            {offers.length === 0 && <div className="db-msg">No vendor sells this yet.</div>}
            {offers.map((o, i) => (
              <div key={o.vendor_id} className={`db-offer${i === 0 ? " top" : ""}`}>
                <div className={`db-rank${i === 0 ? " gold" : ""}`}>{i === 0 ? "★" : `#${i + 1}`}</div>
                <div className="db-offer-info">
                  <div className="db-offer-name">{o.vendor_name}<span className="db-offer-kind">{o.vendor_kind}</span></div>
                  <div className="db-offer-meta">
                    <span>price <b>₹{o.price}</b></span>
                    <span>rating <b>{o.rating}★</b></span>
                    {o.eta_minutes != null && <span>eta <b>{o.eta_minutes} min</b></span>}
                    <span>{o.recommendation}</span>
                  </div>
                </div>
                <div className="db-score">{o.final_score}<small>score</small></div>
                <button className={`db-order-btn${i === 0 ? " top" : ""}`} onClick={() => order(o)}>Order →</button>
              </div>
            ))}
          </div>
        )}

        {orders.length > 0 && (
          <div>
            <div className="db-section">
              <div className="db-section-title">Recent orders</div>
              <div className="db-section-line" />
              <div className="db-count">{orders.length}</div>
            </div>
            <div className="db-orders">
              <div className="db-order-row head"><span>#</span><span>Vendor</span><span>Items</span><span>Total</span><span>Status</span></div>
              {orders.map((o) => (
                <div key={o.order_id} className="db-order-row">
                  <span>{o.order_id}</span>
                  <span>{o.vendor_name}</span>
                  <span>{o.items.map((i) => `${i.name} ×${i.qty}`).join(", ")}</span>
                  <span>₹{o.total_amount}</span>
                  <span className="db-status">{o.status.replace("_", " ")}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {toast && <div className="db-toast">{toast}</div>}
      </div>
    </>
  );
}

export default Dashboard;
