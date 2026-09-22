import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import API from "../services/api";
import { errorText, useToast } from "../lib/toast";

const REFRESH_MS = 15000;

const styles = `
  .asks { display: flex; flex-direction: column; gap: 12px; }
  .ask { display: flex; flex-direction: column; gap: 12px; border-color: var(--accent); }
  .ask-title { font-size: 1.15rem; font-weight: 600; }
  .ask-offers { display: flex; flex-direction: column; gap: 8px; }
  .ask-offer { display: grid; grid-template-columns: 1fr auto auto; gap: 12px; align-items: center; padding: 10px 12px; border: 1px solid var(--line); border-radius: var(--r-control); background: var(--surface); }
  .ask-offer.top { background: var(--accent-soft); border-color: var(--accent); }
  .ask-offer strong { display: block; }
  .ask-offer span { color: var(--muted); font-size: 14px; }
  .ask-price { font-weight: 600; font-size: 1.1rem; white-space: nowrap; }
  .ask-foot { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
  @media (max-width: 520px) { .ask-offer { grid-template-columns: 1fr auto; } .ask-offer .btn { grid-column: 1 / -1; } }
`;

// "Milk runs out tomorrow. Yes #1 / Yes #2 / Yes #3 / Skip" — the same asks that go to Telegram.
function Proposals({ onOrdered }) {
  const notify = useToast();
  const [asks, setAsks] = useState([]);
  const [tick, setTick] = useState(0);
  const refresh = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let alive = true;
    const run = () =>
      API.get("/notifications", { params: { unanswered: true } })
        .then((r) => alive && setAsks(r.data.notifications.filter((n) => n.kind === "reorder_offer")))
        .catch(() => {});
    run();
    const id = setInterval(run, REFRESH_MS);
    return () => { alive = false; clearInterval(id); };
  }, [tick]);

  const answer = async (ask, choice) => {
    try {
      const res = await API.post(`/notifications/${ask.id}/respond`, { choice });
      const order = res.data.order;
      if (!order) notify("Skipped. We'll ask again tomorrow if it's still low.");
      else if (order.handoff_url) {
        window.open(order.handoff_url, "_blank", "noopener");
        notify(`Finish the ${order.vendor_name} order in their app.`);
      } else notify(`Ordered from ${order.vendor_name} for ₹${order.total_amount}. Pay from the Orders page.`);
      refresh();
      onOrdered?.();
    } catch (err) {
      notify(errorText(err, "That didn't go through. Try again."), "error");
    }
  };

  if (asks.length === 0) return null;

  return (
    <section>
      <style>{styles}</style>
      <div className="section-title">
        <h2>Needs your yes</h2>
        <span>One tap places the order</span>
      </div>
      <div className="asks">
        {asks.map((ask) => (
          <article key={ask.id} className="card ask">
            <div className="ask-title">{ask.title}</div>
            <div className="ask-offers">
              {ask.payload.offers.map((o, i) => (
                <div key={o.vendor_id} className={`ask-offer${i === 0 ? " top" : ""}`}>
                  <div>
                    <strong>{o.vendor_name}</strong>
                    <span>{o.reason}</span>
                  </div>
                  <div className="ask-price">₹{o.price}</div>
                  <button className={`btn btn-sm ${i === 0 ? "btn-primary" : ""}`} onClick={() => answer(ask, String(i + 1))}>Yes</button>
                </div>
              ))}
            </div>
            <div className="ask-foot">
              <Link className="small" to="/settings">Change what matters most</Link>
              <button className="btn btn-ghost btn-sm" onClick={() => answer(ask, "skip")}>Not now</button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export default Proposals;
