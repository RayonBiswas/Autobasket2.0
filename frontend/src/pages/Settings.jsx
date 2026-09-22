import { useEffect, useState } from "react";
import API from "../services/api";
import { errorText, useToast } from "../lib/toast";

const PRIORITIES = [
  { id: "balanced", title: "Balanced", blurb: "A fair mix of price, speed and how reliable the shop has been." },
  { id: "price", title: "Lowest price", blurb: "Cheapest first, even if it takes a little longer to arrive." },
  { id: "speed", title: "Fastest delivery", blurb: "Quickest first, even if it costs a few rupees more." },
];

const HABITS = [
  { id: "veg", label: "Vegetarian" },
  { id: "mixed", label: "Mixed" },
  { id: "non-veg", label: "Non-vegetarian" },
];

const styles = `
  .settings { max-width: 720px; }
  .choice-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
  .choice { display: flex; flex-direction: column; gap: 6px; padding: 16px; border: 1px solid var(--line); border-radius: var(--r-tile); background: var(--surface); cursor: pointer; text-align: left; }
  .choice:hover { border-color: var(--accent); }
  .choice[aria-pressed="true"] { border-color: var(--accent); background: var(--accent-soft); }
  .choice strong { font-size: 1.05rem; }
  .choice span { font-size: 14px; color: var(--muted); }
  .size-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; align-items: end; }
  .seg { display: inline-flex; border: 1px solid var(--line); border-radius: var(--r-control); overflow: hidden; }
  .seg button { padding: 10px 14px; border: none; background: var(--surface); color: var(--muted); cursor: pointer; }
  .seg button[aria-pressed="true"] { background: var(--accent-soft); color: var(--accent); font-weight: 500; }
  .seg button + button { border-left: 1px solid var(--line); }
  @media (max-width: 640px) { .choice-grid, .size-grid { grid-template-columns: 1fr; } }
`;

function Settings() {
  const notify = useToast();
  const [home, setHome] = useState(null);
  const [form, setForm] = useState({ adults: 2, children: 1, food_habit: "mixed", pincode: "" });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    API.get("/households/me")
      .then((res) => {
        if (!alive) return;
        setHome(res.data);
        setForm({ adults: res.data.adults, children: res.data.children, food_habit: res.data.food_habit, pincode: res.data.pincode || "" });
      })
      .catch((err) => alive && notify(errorText(err, "We couldn't load your settings."), "error"));
    return () => { alive = false; };
  }, [notify]);

  const choosePriority = async (priority) => {
    if (!home || home.priority === priority) return;
    try {
      const res = await API.put("/households/me/priority", { priority });
      setHome(res.data);
      notify(`Got it. We'll rank shops by ${PRIORITIES.find((p) => p.id === priority).title.toLowerCase()}.`);
    } catch (err) {
      notify(errorText(err, "We couldn't save that."), "error");
    }
  };

  const saveHousehold = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const res = await API.patch("/households/me", {
        adults: Number(form.adults), children: Number(form.children), food_habit: form.food_habit,
        pincode: form.pincode.trim() || null,
      });
      setHome(res.data);
      notify("Saved. Your 'runs out' guesses use this until the fridge has learned your habits.");
    } catch (err) {
      notify(errorText(err, "We couldn't save that."), "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page settings">
      <style>{styles}</style>
      <div className="page-head">
        <h1>Settings</h1>
        <p>How we choose where to buy, and who lives at home.</p>
      </div>

      <section>
        <div className="section-title"><h2>What matters most when we pick a shop</h2></div>
        <div className="choice-grid">
          {PRIORITIES.map((p) => (
            <button key={p.id} type="button" className="choice" aria-pressed={home?.priority === p.id} onClick={() => choosePriority(p.id)}>
              <strong>{p.title}</strong>
              <span>{p.blurb}</span>
            </button>
          ))}
        </div>
      </section>

      <section>
        <div className="section-title"><h2>Who lives at home</h2><span>Used as the starting guess for how fast things run out</span></div>
        <form className="card" onSubmit={saveHousehold} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="size-grid">
            <div className="field">
              <label htmlFor="adults">Adults</label>
              <input id="adults" className="input" type="number" min={1} max={12} value={form.adults} onChange={(e) => setForm({ ...form, adults: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="children">Children</label>
              <input id="children" className="input" type="number" min={0} max={12} value={form.children} onChange={(e) => setForm({ ...form, children: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="pincode">Pincode</label>
              <input id="pincode" className="input" inputMode="numeric" pattern="[0-9]{6}" placeholder="560001" value={form.pincode} onChange={(e) => setForm({ ...form, pincode: e.target.value })} />
            </div>
          </div>
          <div className="field">
            <label>Food habit</label>
            <div className="seg" role="group" aria-label="Food habit">
              {HABITS.map((h) => (
                <button key={h.id} type="button" aria-pressed={form.food_habit === h.id} onClick={() => setForm({ ...form, food_habit: h.id })}>{h.label}</button>
              ))}
            </div>
          </div>
          <div>
            <button className="btn btn-primary" disabled={busy || !home}>{busy ? "Saving…" : "Save changes"}</button>
          </div>
        </form>
      </section>
    </div>
  );
}

export default Settings;
