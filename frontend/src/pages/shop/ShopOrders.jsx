import { useCallback, useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import API from "../../services/api";
import { errorText, useToast } from "../../lib/toast";
import { cap } from "../../lib/format";

const REFRESH_MS = 10000;

// What the shopkeeper sees for each status, and what they can do next.
const STAGE = {
  confirmed: { label: "New order", pill: "pill-warn", next: [["accept", "Accept"], ["reject", "Can't do it"]] },
  paid: { label: "Paid, waiting for you", pill: "pill-warn", next: [["accept", "Accept"], ["reject", "Can't do it"]] },
  accepted: { label: "You're packing it", pill: "pill-ok", next: [["deliver", "Delivered"]] },
  delivering: { label: "On the way", pill: "pill-ok", next: [["deliver", "Delivered"]] },
  delivered: { label: "Delivered", pill: "pill-muted", next: [] },
  verified: { label: "Delivered and confirmed", pill: "pill-muted", next: [] },
  cancelled: { label: "Cancelled", pill: "pill-muted", next: [] },
};

function when(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const today = new Date().toDateString() === d.toDateString();
  return today
    ? `today ${d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}`
    : d.toLocaleDateString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

function OrderCard({ order, onAct }) {
  const [busy, setBusy] = useState(false);
  const stage = STAGE[order.status] || { label: order.status, pill: "pill-muted", next: [] };

  const act = async (action) => {
    setBusy(true);
    try { await onAct(order, action); } finally { setBusy(false); }
  };

  return (
    <article className="card order-card">
      <div className="order-top">
        <h3>Order #{order.order_id}</h3>
        <span className={`pill ${stage.pill}`}>{stage.label}</span>
      </div>
      <div className="small muted">Placed {when(order.created_at)}</div>
      <div className="order-lines">
        {order.items.map((i) => (
          <div className="order-line" key={i.product_id}>
            <span>{cap(i.name)} <span className="muted">× {i.qty}</span></span>
            <span>₹{(i.unit_price * i.qty).toFixed(0)}</span>
          </div>
        ))}
      </div>
      <div className="order-total"><span>Total</span><span>₹{order.total_amount}</span></div>
      {stage.next.length > 0 && (
        <div className="order-actions">
          {stage.next.map(([action, label], idx) => (
            <button key={action} className={`btn ${idx === 0 ? "btn-primary" : ""}`} disabled={busy} onClick={() => act(action)}>
              {label}
            </button>
          ))}
        </div>
      )}
    </article>
  );
}

function ShopOrders() {
  const { shop, reload } = useOutletContext();
  const notify = useToast();
  const [orders, setOrders] = useState(null);
  const [showAll, setShowAll] = useState(false);
  const [tick, setTick] = useState(0);
  const load = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let alive = true;
    const run = () =>
      API.get("/vendor/orders", { params: { status: showAll ? "all" : "open" } })
        .then((res) => { if (alive) setOrders(res.data.orders); })
        .catch((err) => {
          if (!alive) return;
          notify(errorText(err, "We couldn't load your orders."), "error");
          setOrders([]);
        });
    run();
    const id = setInterval(run, REFRESH_MS);
    return () => { alive = false; clearInterval(id); };
  }, [showAll, notify, tick]);

  const onAct = async (order, action) => {
    try {
      await API.post(`/vendor/orders/${order.order_id}/${action}`);
      notify({ accept: "Accepted. The customer knows you're packing it.", reject: "Order cancelled.", deliver: "Marked delivered." }[action]);
      load();
      reload();
    } catch (err) {
      notify(errorText(err, "That didn't go through. Try again."), "error");
    }
  };

  const open = shop.open_orders;

  return (
    <div className="page shop-page">
      <div className="page-head">
        <h1>{shop.name}</h1>
        <p className="lead-calm">
          {open === 0 ? "No new orders right now." : open === 1 ? "One order waiting for you." : `${open} orders waiting for you.`}
        </p>
      </div>

      <div className="section-title">
        <h2>{showAll ? "All orders" : "Open orders"}</h2>
        <button className="btn btn-ghost btn-sm" onClick={() => setShowAll((s) => !s)}>{showAll ? "Only open" : "Show all"}</button>
      </div>

      {orders === null && <p className="muted">Checking for orders…</p>}
      {orders && orders.length === 0 && (
        <div className="card empty">
          <h2>Nothing here yet</h2>
          <p>When a nearby home orders from you, it appears here and you can accept it in one tap. Make sure your products have prices.</p>
        </div>
      )}
      {orders && orders.map((o) => <OrderCard key={o.order_id} order={o} onAct={onAct} />)}
    </div>
  );
}

export default ShopOrders;
