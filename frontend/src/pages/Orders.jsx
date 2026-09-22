import { useCallback, useEffect, useState } from "react";
import API from "../services/api";
import { errorText, useToast } from "../lib/toast";
import { cap, orderStage } from "../lib/format";

const REFRESH_MS = 8000;

// The journey a kirana order takes, in the household's words. Handoff orders have a shorter one.
const KIRANA_STEPS = [
  ["confirmed", "Sent to the shop"],
  ["paid", "Paid"],
  ["accepted", "Being packed"],
  ["delivered", "Delivered"],
  ["verified", "Back on the shelf"],
];
const HANDOFF_STEPS = [
  ["handoff", "Opened in their app"],
  ["verified", "Back on the shelf"],
];
const RANK = { proposed: 0, pending_confirmation: 0, confirmed: 1, paid: 2, accepted: 3, delivering: 3, delivered: 4, handoff: 1, verified: 5 };

const styles = `
  .orders-page { max-width: 760px; }
  .order { display: flex; flex-direction: column; gap: 14px; }
  .order-head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; flex-wrap: wrap; }
  .order-head h3 { font-size: 1.1rem; }
  .order-items { color: var(--muted); font-size: 15px; }
  .steps { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
  .step { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--muted); }
  .step::before { content: ""; width: 10px; height: 10px; border-radius: 50%; border: 2px solid var(--line); background: var(--surface); }
  .step.done { color: var(--text); }
  .step.done::before { background: var(--ok); border-color: var(--ok); }
  .step.now { color: var(--accent); font-weight: 500; }
  .step.now::before { background: var(--accent); border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
  .step + .step { margin-left: 6px; }
  .order-foot { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
  .order-amt { font-size: 1.25rem; font-weight: 600; }
  .actions { display: flex; gap: 8px; flex-wrap: wrap; }
  .stars { display: inline-flex; gap: 2px; }
  .stars button { font-size: 1.5rem; line-height: 1; background: none; border: none; cursor: pointer; color: var(--line); padding: 2px; }
  .stars button:hover, .stars button.on { color: var(--warn); }
  .filter { display: inline-flex; gap: 6px; }
`;

function Steps({ order }) {
  const steps = order.channel === "handoff" ? HANDOFF_STEPS : KIRANA_STEPS;
  const rank = RANK[order.status] ?? 0;
  if (order.status === "cancelled") return null;
  return (
    <div className="steps" aria-label="Order progress">
      {steps.map(([key, label]) => {
        const r = RANK[key];
        const cls = r < rank ? "done" : r === rank ? "now" : "";
        return <span key={key} className={`step ${cls}`}>{label}</span>;
      })}
    </div>
  );
}

function Stars({ onRate }) {
  const [hover, setHover] = useState(0);
  return (
    <span className="stars" role="group" aria-label="Rate this delivery">
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" className={n <= hover ? "on" : ""} aria-label={`${n} star${n > 1 ? "s" : ""}`}
          onMouseEnter={() => setHover(n)} onMouseLeave={() => setHover(0)} onClick={() => onRate(n)}>★</button>
      ))}
    </span>
  );
}

function OrderCard({ order, onAct }) {
  const stage = orderStage(order.status);
  const open = !["verified", "cancelled"].includes(order.status);
  return (
    <article className="card order">
      <div className="order-head">
        <h3>{order.vendor_name}</h3>
        <span className={`pill ${stage.pill}`}>{stage.label}</span>
      </div>
      <div className="order-items">{order.items.map((i) => `${cap(i.name)} × ${i.qty}`).join(", ")}</div>
      <Steps order={order} />
      <div className="order-foot">
        <div className="order-amt">₹{order.total_amount}</div>
        <div className="actions">
          {(order.status === "proposed" || order.status === "pending_confirmation") && (
            <>
              <button className="btn btn-primary" onClick={() => onAct(order, "confirm")}>Yes, order it</button>
              <button className="btn btn-ghost" onClick={() => onAct(order, "cancel")}>No</button>
            </>
          )}
          {order.status === "confirmed" && order.payment_url && (
            <a className="btn btn-primary" href={order.payment_url}>Pay ₹{order.total_amount}</a>
          )}
          {order.status === "handoff" && order.handoff_url && (
            <a className="btn btn-primary" href={order.handoff_url} target="_blank" rel="noreferrer">Open {order.vendor_name}</a>
          )}
          {["delivered", "verified"].includes(order.status) && order.rating == null && (
            <Stars onRate={(n) => onAct(order, "rate", n)} />
          )}
          {order.rating != null && <span className="muted small">You rated {order.rating} out of 5</span>}
          {open && !["proposed", "pending_confirmation", "delivered"].includes(order.status) && (
            <button className="btn btn-ghost btn-sm" onClick={() => onAct(order, "cancel")}>Cancel</button>
          )}
        </div>
      </div>
    </article>
  );
}

function Orders() {
  const notify = useToast();
  const [orders, setOrders] = useState(null);
  const [onlyOpen, setOnlyOpen] = useState(true);
  const [tick, setTick] = useState(0);
  const refresh = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let alive = true;
    const run = () => API.get("/orders").then((r) => alive && setOrders(r.data.orders)).catch((err) => {
      if (alive) { notify(errorText(err, "We couldn't load your orders."), "error"); setOrders([]); }
    });
    run();
    const id = setInterval(run, REFRESH_MS);
    return () => { alive = false; clearInterval(id); };
  }, [notify, tick]);

  const onAct = async (order, action, stars) => {
    try {
      if (action === "rate") {
        await API.post(`/orders/${order.order_id}/rate`, { stars });
        notify(`Thanks. ${order.vendor_name} now knows how it went.`);
      } else {
        const res = await API.post(`/orders/${order.order_id}/${action}`);
        if (action === "confirm" && res.data.handoff_url) window.open(res.data.handoff_url, "_blank", "noopener");
        notify(action === "confirm" ? (res.data.payment_url ? `Sent to ${order.vendor_name}. Pay when you're ready.` : `Finish in ${order.vendor_name}'s app.`) : "Order cancelled.");
      }
      refresh();
    } catch (err) {
      notify(errorText(err, "That didn't go through. Try again."), "error");
    }
  };

  const rows = (orders ?? []).filter((o) => !onlyOpen || !["verified", "cancelled"].includes(o.status));

  return (
    <div className="page orders-page">
      <style>{styles}</style>
      <div className="page-head">
        <h1>Orders</h1>
        <p>Every order, from your yes to the moment it's back on the shelf.</p>
      </div>
      <div className="section-title">
        <h2>{onlyOpen ? "In progress" : "All orders"}</h2>
        <div className="filter">
          <button className="btn btn-ghost btn-sm" onClick={() => setOnlyOpen((v) => !v)}>{onlyOpen ? "Show all" : "Only in progress"}</button>
        </div>
      </div>
      {orders === null && <p className="muted">Loading your orders…</p>}
      {orders && rows.length === 0 && (
        <div className="card empty">
          <h2>{onlyOpen ? "Nothing on the way" : "No orders yet"}</h2>
          <p>When something runs low we'll suggest where to buy it. Say yes and it shows up here.</p>
        </div>
      )}
      {rows.map((o) => <OrderCard key={o.order_id} order={o} onAct={onAct} />)}
    </div>
  );
}

export default Orders;
