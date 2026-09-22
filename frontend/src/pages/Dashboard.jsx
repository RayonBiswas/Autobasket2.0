import { useCallback, useEffect, useState } from "react";
import API from "../services/api";
import { Link } from "react-router-dom";
import AgentChatPanel from "../components/AgentChatPanel";
import Proposals from "../components/Proposals";
import Gauge from "../components/Gauge";
import { errorText, useToast } from "../lib/toast";
import { cap, orderStage, runsOut } from "../lib/format";

const REFRESH_MS = 10000;

const PRIORITY_LABEL = { balanced: "Balanced pick", price: "Cheapest first", speed: "Fastest first" };

const STATUS = {
  safe: { label: "Plenty for now", pill: "pill-ok" },
  warning: { label: "Runs out this week", pill: "pill-warn" },
  critical: { label: "Order soon", pill: "pill-danger" },
  unknown: { label: "Not measured yet", pill: "pill-muted" },
};


// Where the "runs out" number comes from, so a young guess is not over-trusted.
function provenance(r) {
  const days = Math.round(r.observed_days ?? 0);
  if (r.rate_method === "learned") return `Based on ${days} days of use`;
  if (r.rate_method === "blended") return `Learning, ${days} day${days === 1 ? "" : "s"} so far`;
  return "Estimated from household size";
}

const styles = `
  .lead-list { display: flex; flex-direction: column; gap: 6px; font-size: 1.25rem; line-height: 1.35; }
  .lead-list strong { font-weight: 600; }
  .shelf { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 14px; }
  .tile { display: flex; flex-direction: column; gap: 12px; cursor: pointer; text-align: left; transition: border-color 0.15s; }
  .tile:hover { border-color: var(--accent); }
  .tile[aria-pressed="true"] { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-soft); }
  .tile-head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
  .tile-head h3 { font-size: 1.05rem; }
  .tile-qty { font-size: 14px; color: var(--muted); }
  .tile-qty strong { color: var(--text); font-weight: 600; }
  .tile-when { font-size: 14px; }
  .picks { display: grid; grid-template-columns: 1.4fr 1fr 1fr; gap: 12px; align-items: stretch; }
  .pick { display: flex; flex-direction: column; gap: 8px; padding: 18px; border: 1px solid var(--line); border-radius: var(--r-tile); background: var(--surface); }
  .pick.best { border-color: var(--accent); background: var(--accent-soft); }
  .pick-tag { font-size: 13px; color: var(--accent); font-weight: 500; }
  .pick-name { font-size: 1.15rem; font-weight: 600; }
  .pick.best .pick-name { font-size: 1.4rem; }
  .pick-price { font-size: 1.6rem; font-weight: 600; letter-spacing: -0.01em; }
  .pick.best .pick-price { font-size: 2rem; }
  .pick-meta { font-size: 14px; color: var(--muted); }
  .pick-why { font-size: 15px; }
  .pick .btn { margin-top: auto; }
  .pick-stale { font-size: 13px; color: var(--warn); }
  @media (max-width: 720px) { .picks { grid-template-columns: 1fr; } }
  .row-actions { display: inline-flex; gap: 6px; }
  @media (max-width: 560px) { .offer { grid-template-columns: 1fr; } }
`;

function Dashboard() {
  const notify = useToast();
  const [inventory, setInventory] = useState(null);
  const [selected, setSelected] = useState(null);
  const [picks, setPicks] = useState(null);
  const [orders, setOrders] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

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
      setOrders(res.data.orders.filter((o) => !['verified', 'cancelled'].includes(o.status)).slice(0, 5));
    } catch { /* keep previous */ }
  }, []);

  useEffect(() => {
    loadInventory();
    loadOrders();
    const id = setInterval(loadInventory, REFRESH_MS);
    return () => clearInterval(id);
  }, [loadInventory, loadOrders]);

  const select = async (row) => {
    if (selected?.product_id === row.product_id) { setSelected(null); setPicks(null); return; }
    setSelected(row);
    setPicks(null);
    try {
      const res = await API.get(`/recommendations/${row.name}`);
      setPicks(res.data);
    } catch (err) {
      setPicks({ offers: [], considered: 0 });
      notify(errorText(err, "We couldn't fetch prices just now."), "error");
    }
  };

  const order = async (offer) => {
    try {
      const res = await API.post("/orders", { vendor_id: offer.vendor_id, items: [{ product_id: selected.product_id, qty: 1 }] });
      notify(`Ordered ${selected.name} from ${offer.vendor_name} for ₹${res.data.total_amount}. Say yes below to send it.`);
      loadOrders();
    } catch (err) {
      notify(errorText(err, "The order didn't go through. Try again."), "error");
    }
  };

  const decide = async (o, action) => {
    try {
      await API.post(`/orders/${o.order_id}/${action}`);
      notify(action === "confirm" ? `Sent to ${o.vendor_name}. They'll accept it shortly.` : "Order cancelled.");
      loadOrders();
    } catch (err) {
      notify(errorText(err, "That didn't go through. Try again."), "error");
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
        {inventory === null && <p className="lead-calm muted">Checking the shelves…</p>}
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

      {inventory === null && (
        <section aria-hidden="true">
          <div className="shelf">
            {[0, 1, 2].map((i) => (
              <div key={i} className="card tile">
                <div className="skeleton" style={{ width: "40%", height: 18 }} />
                <div className="skeleton" style={{ height: 88 }} />
                <div className="skeleton" style={{ width: "60%", height: 14 }} />
              </div>
            ))}
          </div>
        </section>
      )}

      {inventory && inventory.length === 0 && (
        <div className="card empty">
          <h2>Nothing is being tracked yet</h2>
          <p>Put products on your shelves from the Shelves page, or load the demo fridge to see how it works.</p>
          <button className="btn btn-primary" onClick={seed} disabled={busy}>{busy ? "Loading…" : "Load the demo fridge"}</button>
          {msg && <div className="notice">{msg}</div>}
        </div>
      )}

      {inventory && inventory.length > 0 && <Proposals onOrdered={loadOrders} />}

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
                <button key={r.product_id} className="card tile" aria-pressed={selected?.product_id === r.product_id} onClick={() => select(r)}>
                  <div className="tile-head">
                    <h3>{cap(r.name)}</h3>
                    <span className={`pill ${s.pill}`}>{s.label}</span>
                  </div>
                  <Gauge fraction={r.remaining_fraction} label={`${Math.round(r.remaining_fraction * 100)} percent left, ${r.remaining_qty} ${r.unit} of ${r.pack_size} ${r.unit}`} />
                  <div className="tile-qty"><strong>{r.remaining_qty} {r.unit}</strong> left of {r.pack_size} {r.unit}</div>
                  <div className="tile-when">{runsOut(r.days_left) ? cap(runsOut(r.days_left)) : "Usage not known yet"}</div>
                  <div className="small muted">{provenance(r)}</div>
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
            <span>{picks ? PRIORITY_LABEL[picks.priority] || "" : "Checking prices…"}</span>
          </div>
          {picks && picks.offers.length === 0 && <p className="muted">No shop near you sells this yet.</p>}
          {picks && picks.offers.length > 0 && (
            <div className="picks">
              {picks.offers.map((o, i) => (
                <article key={o.vendor_id} className={`pick${i === 0 ? " best" : ""}`}>
                  {i === 0 && <div className="pick-tag">Best for you</div>}
                  <div className="pick-name">{o.vendor_name}</div>
                  <div className="pick-price">₹{o.price}</div>
                  <div className="pick-why">{o.reason}</div>
                  <div className="pick-meta">
                    {o.vendor_kind === "kirana" ? "Local shop" : "Delivery app"}
                    {o.distance_km != null && `, ${o.distance_km} km away`}
                    {`, rated ${o.rating} out of 5`}
                  </div>
                  {o.stale && <div className="pick-stale">Price from earlier today</div>}
                  <button className={`btn ${i === 0 ? "btn-primary" : ""}`} onClick={() => order(o)}>
                    Order from {o.vendor_name}
                  </button>
                </article>
              ))}
            </div>
          )}
          {picks && picks.considered > picks.offers.length && (
            <p className="small muted" style={{ marginTop: 12 }}>Picked from {picks.considered} sellers. Change what matters most in Settings.</p>
          )}
        </section>
      )}

      {orders.length > 0 && (
        <section>
          <div className="section-title">
            <h2>Recent orders</h2>
            <Link to="/orders">See all orders</Link>
          </div>
          <div className="card" style={{ padding: "4px 8px" }}>
            <table className="table">
              <thead>
                <tr><th>Items</th><th>Shop</th><th className="num">Total</th><th>Status</th><th></th></tr>
              </thead>
              <tbody>
                {orders.map((o) => (
                  <tr key={o.order_id}>
                    <td>{o.items.map((i) => `${cap(i.name)} ×${i.qty}`).join(", ")}</td>
                    <td>{o.vendor_name}</td>
                    <td className="num">₹{o.total_amount}</td>
                    <td><span className={`pill ${orderStage(o.status).pill}`}>{orderStage(o.status).label}</span></td>
                    <td className="num">
                      {(o.status === "proposed" || o.status === "pending_confirmation") && (
                        <span className="row-actions">
                          <button className="btn btn-primary btn-sm" onClick={() => decide(o, "confirm")}>Yes, order it</button>
                          <button className="btn btn-ghost btn-sm" onClick={() => decide(o, "cancel")}>No</button>
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <AgentChatPanel />
    </div>
  );
}

export default Dashboard;
