import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import API from "../services/api";
import { errorText, useToast } from "../lib/toast";
import { cap } from "../lib/format";

// Stands in for the Razorpay page while no keys are configured. Real links never point here.
function Pay() {
  const { orderId } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const notify = useToast();
  const [order, setOrder] = useState(null);
  const [busy, setBusy] = useState(false);
  const isDev = (params.get("ref") || "").startsWith("dev_");

  useEffect(() => {
    let alive = true;
    API.get("/orders").then((r) => {
      if (!alive) return;
      setOrder(r.data.orders.find((o) => String(o.order_id) === orderId) || false);
    }).catch(() => alive && setOrder(false));
    return () => { alive = false; };
  }, [orderId]);

  const pay = async () => {
    setBusy(true);
    try {
      await API.post("/payments/dev/complete", { order_id: Number(orderId) });
      notify(`Paid ₹${order.total_amount} to ${order.vendor_name}. They'll start packing.`);
      navigate("/orders");
    } catch (err) {
      notify(errorText(err, "The test payment didn't go through."), "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page" style={{ maxWidth: 520 }}>
      <div className="page-head">
        <h1>Pay for your order</h1>
        <p>{isDev ? "Test mode: no real money moves. This page stands in for the payment provider until keys are set up." : "This order uses a real payment link. Open it from the Orders page."}</p>
      </div>
      {order === null && <p className="muted">Loading…</p>}
      {order === false && <div className="card empty"><h2>Order not found</h2><Link className="btn" to="/orders">Back to orders</Link></div>}
      {order && (
        <div className="sheet" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <div className="muted small">Paying</div>
            <div style={{ fontSize: "1.25rem", fontWeight: 600 }}>{order.vendor_name}</div>
          </div>
          <div className="muted">{order.items.map((i) => `${cap(i.name)} × ${i.qty}`).join(", ")}</div>
          <div style={{ fontSize: "2.2rem", fontWeight: 600, letterSpacing: "-0.01em" }}>₹{order.total_amount}</div>
          {order.status !== "confirmed" && <div className="notice notice-ok">This order is already {order.status.replaceAll("_", " ")}.</div>}
          {order.status === "confirmed" && isDev && (
            <button className="btn btn-primary btn-block" disabled={busy} onClick={pay}>{busy ? "Paying…" : "Pay (test)"}</button>
          )}
          <Link className="btn btn-ghost" to="/orders">Back to orders</Link>
        </div>
      )}
    </div>
  );
}

export default Pay;
