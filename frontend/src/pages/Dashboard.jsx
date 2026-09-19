import { useCallback, useEffect, useState } from "react";
import API from "../services/api";
import AgentChatPanel from "../components/AgentChatPanel";

const REFRESH_MS = 10000;

const STATUS = {
  safe: { label: "Plenty", pill: "pill-ok", gauge: "" },
  warning: { label: "Getting low", pill: "pill-warn", gauge: "gauge-warn" },
  critical: { label: "Almost out", pill: "pill-danger", gauge: "gauge-danger" },
  unknown: { label: "Not measured yet", pill: "pill-muted", gauge: "" },
};

// "runs out tomorrow", "runs out on Thursday", "runs out on 3 Oct"
function runsOut(days) {
  if (days == null || days >= 999) return null;
  if (days < 1) return "runs out today";
  if (days < 2) return "runs out tomorrow";
  const d = new Date();
  d.setDate(d.getDate() + Math.round(days));
  if (days < 7) return `runs out on ${d.toLocaleDateString("en-IN", { weekday: "long" })}`;
  return `runs out on ${d.toLocaleDateString("en-IN", { day: "numeric", month: "short" })}`;
}

const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

const styles = `
  .lead-list { display: flex; flex-direction: column; gap: 6px; font-size: 1.25rem; line-height: 1.35; }
  .lead-list strong { font-weight: 600; }
  .lead-calm { font-size: 1.25rem; }
  .shelf { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 14px; }
  .tile { display: flex; flex-direction: column; gap: 12px; cursor: pointer; text-align: left; transition: border-color 0.15s; }
  .tile:hover { border-color: var(--accent); }
  .tile[aria-pressed="true"] { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-soft); }
  .tile-head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
  .tile-head h3 { font-size: 1.05rem; }
  .tile-qty { font-size: 14px; color: var(--muted); }
  .tile-when { font-size: 14px; }
  .offers { display: flex; flex-direction: column; gap: 10px; }
  .offer { display: grid; grid-template-columns: 1fr auto auto; gap: 16px; align-items: center; padding: 14px 16px; border: 1px solid var(--line); border-radius: var(--r-control); }
  .offer.best { border-color: var(--accent); background: var(--accent-soft); }
  .offer-name { font-weight: 600; }
  .offer-meta { color: var(--muted); font-size: 14px; }
  .offer-price { font-size: 1.25rem; font-weight: 600; white-space: nowrap; }
  .offer-why { font-size: 13px; color: var(--accent); }
  @media (max-width: 560px) { .offer { grid-template-columns: 1fr; } }
`;

function Dashboard() {
  const [inventory, setInventory] = useState(null);
  const [selected, setSelected] = useState(null);
  const [offers, setOffers] = useState([]);
  const [orders, setOrders] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [toast, setToast] = useState(null);

  const loadInventory = useCallback(async () => {
    try {
      const res = await API.get("/inventory");
      setInventory(res.data.inventory);
    } catch (err) {
      setMsg(err.response?.data?.detail || "We couldn't load your fridge. Check that the app is running.");
      setInventory([]);
    }
  }, []);

  const loadOrders = useCallback(async () => {
    try {
      const res = await API.get("/orders");
      setOrders(res.data.orders.slice(0, 8));
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
    const id = setTimeout(() => setToast(null), 4000);
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
      setToast(`Ordered ${selected.name} from ${offer.vendor_name} for ₹${res.data.total_amount}. Waiting for the shop to accept.`);
      loadOrders();
    } catch (err) {
      alert(err.response?.data?.detail || "The order didn't go through. Try again.");
    }
  };

  const seed = async () => {
    setBusy(true);
    try {
      const res = await API.post("/seed/dev");
      setMsg(res.data.message);
      await loadInventory();
    } catch (err) {
      setMsg(err.response?.data?.detail || "Loading the demo data failed.");
    } finally {
      setBusy(false);
    }
  };

  const low = (inventory ?? []).filter((r) => r.status === "critical" || r.status === "warning")
    .sort((a, b) => a.days_left - b.days_left);

  return (
    <div className="page">
      <style>{styles}</style>

      <div className="page-head">
        <h1>Your fridge</h1>
        {inventory === null && <p>Checking the shelves…</p>}
        {inventory && inventory.length > 0 && (
          low.length === 0
            ? <p className="lead-calm">Everything is stocked. Nothing to buy right now.</p>
            : (
              <div className="lead-list">
                {low.slice(0, 3).map((r) => (
                  <div key={r.product_id}><strong>{cap(r.name)}</strong> {runsOut(r.days_left)}.</div>
                ))}
                {low.length > 3 && <div className="muted">and {low.length - 3} more getting low</div>}
              </div>
            )
        )}
      </div>

      {inventory && inventory.length === 0 && (
        <div className="card empty">
          <h2>Nothing is being tracked yet</h2>
          <p>Put products on your shelves from the Shelves page, or load the demo fridge to see how it works.</p>
          <button className="btn btn-primary" onClick={seed} disabled={busy}>{busy ? "Loading…" : "Load the demo fridge"}</button>
          {msg && <div className="notice">{msg}</div>}
        </div>
      )}

      {inventory && inventory.length > 0 && (
        <section>
          <div className="section-title">
            <h2>On the shelves</h2>
            <span>Choose an item to see where to buy it</span>
          </div>
          <div className="shelf">
            {inventory.map((r) => {
              const s = STATUS[r.status] || STATUS.unknown;
              return (
                <button key={r.product_id} className={`card tile ${s.gauge}`} aria-pressed={selected?.product_id === r.product_id} onClick={() => select(r)}>
                  <div className="tile-head">
                    <h3>{cap(r.name)}</h3>
                    <span className={`pill ${s.pill}`}>{s.label}</span>
                  </div>
                  <div className={`gauge ${s.gauge}`} role="img" aria-label={`${Math.round(r.remaining_fraction * 100)} percent left`}>
                    <div className="gauge-fill" style={{ height: `${Math.round(r.remaining_fraction * 100)}%` }} />
                  </div>
                  <div className="tile-qty">{r.remaining_qty} of {r.pack_size} {r.unit} left</div>
                  <div className="tile-when">{runsOut(r.days_left) ? cap(runsOut(r.days_left)) : "Usage not known yet"}</div>
                </button>
              );
            })}
          </div>
        </section>
      )}

      {selected && (
        <section className="sheet">
          <div className="section-title">
            <h2>Where to buy {selected.name}</h2>
            <span>Best value first</span>
          </div>
          {offers.length === 0 && <p className="muted">No shop near you sells this yet.</p>}
          <div className="offers">
            {offers.map((o, i) => (
              <div key={o.vendor_id} className={`offer${i === 0 ? " best" : ""}`}>
                <div>
                  <div className="offer-name">{o.vendor_name}</div>
                  <div className="offer-meta">
                    {o.vendor_kind === "kirana" ? "Local shop" : "Delivery app"}
                    {o.eta_minutes != null && `, about ${o.eta_minutes} min`}
                    {`, rated ${o.rating} out of 5`}
                  </div>
                  {i === 0 && <div className="offer-why">Cheapest and well rated</div>}
                </div>
                <div className="offer-price">₹{o.price}</div>
                <button className={`btn ${i === 0 ? "btn-primary" : ""}`} onClick={() => order(o)}>
                  Order from {o.vendor_name.split(" ")[0]}
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

      {orders.length > 0 && (
        <section>
          <div className="section-title">
            <h2>Recent orders</h2>
          </div>
          <div className="card" style={{ padding: "4px 8px" }}>
            <table className="table">
              <thead>
                <tr><th>Items</th><th>Shop</th><th className="num">Total</th><th>Status</th></tr>
              </thead>
              <tbody>
                {orders.map((o) => (
                  <tr key={o.order_id}>
                    <td>{o.items.map((i) => `${cap(i.name)} ×${i.qty}`).join(", ")}</td>
                    <td>{o.vendor_name}</td>
                    <td className="num">₹{o.total_amount}</td>
                    <td><span className="pill pill-muted">{o.status.replace("_", " ")}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <AgentChatPanel />

      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}

export default Dashboard;
