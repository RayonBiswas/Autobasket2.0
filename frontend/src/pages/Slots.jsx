import { useCallback, useEffect, useState } from "react";
import API from "../services/api";

const REFRESH_MS = 5000;

const styles = `
  .tray { display: flex; flex-direction: column; gap: 14px; }
  .tray-head { display: flex; align-items: baseline; justify-content: space-between; }
  .tray-head span { color: var(--muted); font-size: 14px; }
  .slot-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
  .slot { display: flex; flex-direction: column; gap: 10px; padding: 16px; border: 1px solid var(--line); border-radius: var(--r-control); background: var(--surface-2); }
  .slot.assigned { background: var(--surface); }
  .slot-top { display: flex; justify-content: space-between; align-items: baseline; font-size: 14px; color: var(--muted); }
  .slot-weight { font-size: 1.4rem; font-weight: 600; }
  .slot-weight small { font-size: 13px; font-weight: 400; color: var(--muted); margin-left: 6px; }
  .slot-cal { font-size: 13px; color: var(--muted); }
  .slot-actions { display: flex; gap: 8px; }
  .slot-actions .btn { flex: 1; }
  .token { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 13px; padding: 10px 12px; border-radius: 8px; background: var(--surface-2); word-break: break-all; user-select: all; }
  .head-actions { display: flex; gap: 8px; }
`;

function pct(fraction) {
  return fraction == null ? null : Math.round(fraction * 100);
}

function SlotCard({ slot, products, onChange }) {
  const [busy, setBusy] = useState(false);
  const p = pct(slot.remaining_fraction);
  const hasReading = slot.latest_weight_grams != null;
  const gaugeClass = p == null ? "" : p < 25 ? "gauge-danger" : p < 45 ? "gauge-warn" : "";

  const call = async (fn) => {
    setBusy(true);
    try {
      await fn();
      await onChange();
    } catch (err) {
      alert(err.response?.data?.detail || "That didn't work. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const assign = (e) => {
    const value = e.target.value;
    call(() => API.put(`/slots/${slot.slot_id}`, value === "" ? { clear_product: true } : { product_id: Number(value) }));
  };

  return (
    <div className={`slot${slot.product_id ? " assigned" : ""}`}>
      <div className="slot-top">
        <span>Slot {slot.position}</span>
        {p != null && <span>{p}% left</span>}
      </div>
      <select className="select" value={slot.product_id ?? ""} onChange={assign} disabled={busy} aria-label={`Product in slot ${slot.position}`}>
        <option value="">Nothing here</option>
        {products.map((pr) => (
          <option key={pr.id} value={pr.id}>{pr.name} ({pr.pack_size} {pr.unit})</option>
        ))}
      </select>
      <div className={`gauge gauge-slim ${gaugeClass}`} aria-hidden="true">
        <div className="gauge-fill" style={{ height: `${p ?? 0}%` }} />
      </div>
      <div className="slot-weight">
        {hasReading ? `${Math.round(slot.latest_weight_grams)} g` : "No weight yet"}
        {slot.latest_at && <small>{new Date(slot.latest_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</small>}
      </div>
      <div className="slot-cal">
        Empty {slot.tare_grams != null ? `${Math.round(slot.tare_grams)} g` : "not set"}, full {slot.full_grams != null ? `${Math.round(slot.full_grams)} g` : "not set"}
      </div>
      <div className="slot-actions">
        <button className="btn btn-sm" disabled={busy || !hasReading} onClick={() => call(() => API.post(`/slots/${slot.slot_id}/mark-empty`))}>
          This is empty
        </button>
        <button className="btn btn-sm" disabled={busy || !hasReading} onClick={() => call(() => API.post(`/slots/${slot.slot_id}/mark-full`))}>
          This is full
        </button>
      </div>
    </div>
  );
}

function Slots() {
  const [trays, setTrays] = useState(null);
  const [products, setProducts] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [newDevice, setNewDevice] = useState(null);

  const load = useCallback(async () => {
    try {
      const res = await API.get("/households/me/slots");
      setTrays(res.data.trays);
    } catch (err) {
      setMsg(err.response?.data?.detail || "We couldn't load your shelves.");
      setTrays([]);
    }
  }, []);

  useEffect(() => {
    load();
    API.get("/products").then((r) => setProducts(r.data.products)).catch(() => {});
    const id = setInterval(load, REFRESH_MS);
    return () => clearInterval(id);
  }, [load]);

  const seed = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const res = await API.post("/seed/dev");
      setMsg(res.data.message);
      if (res.data.device_token) setNewDevice({ name: "Demo fridge", token: res.data.device_token });
      const pr = await API.get("/products");
      setProducts(pr.data.products);
      await load();
    } catch (err) {
      setMsg(err.response?.data?.detail || "Loading the demo data failed.");
    } finally {
      setBusy(false);
    }
  };

  const addDevice = async () => {
    const name = window.prompt("What should we call this fridge?", "Kitchen fridge");
    if (!name) return;
    try {
      const res = await API.post("/devices", { name });
      setNewDevice({ name: res.data.name, token: res.data.token });
    } catch (err) {
      alert(err.response?.data?.detail || "We couldn't add the fridge. Try again.");
    }
  };

  return (
    <div className="page">
      <style>{styles}</style>
      <div className="page-head" style={{ display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap", alignItems: "flex-start" }}>
        <div>
          <h1>Shelves</h1>
          <p>Each slot is a scale. Tell it what sits there, then tap "This is empty" and "This is full" once to teach it.</p>
        </div>
        <div className="head-actions">
          <button className="btn" onClick={addDevice}>Add a fridge</button>
        </div>
      </div>

      {newDevice && (
        <div className="card empty">
          <h2>{newDevice.name} is ready to connect</h2>
          <p>Copy this key into the fridge device now. For safety it is shown only once.</p>
          <div className="token">{newDevice.token}</div>
          <p className="small muted">To try it without hardware: set AB_DEVICE_TOKEN to this key and run edge/simulator.py.</p>
          <button className="btn btn-sm" onClick={() => setNewDevice(null)}>Done</button>
        </div>
      )}

      {trays === null && <p className="muted">Checking the shelves…</p>}

      {trays && trays.length === 0 && (
        <div className="card empty">
          <h2>No fridge connected yet</h2>
          <p>Add a fridge to get a device key, or load the demo fridge with two shelves of four slots.</p>
          <button className="btn btn-primary" onClick={seed} disabled={busy}>{busy ? "Loading…" : "Load the demo fridge"}</button>
          {msg && <div className="notice">{msg}</div>}
        </div>
      )}

      {trays && trays.map((t) => (
        <section className="card tray" key={t.tray_id}>
          <div className="tray-head">
            <h2>{t.label || `Shelf ${t.position}`}</h2>
            <span>{t.device}</span>
          </div>
          <div className="slot-grid">
            {t.slots.map((s) => (
              <SlotCard key={s.slot_id} slot={s} products={products} onChange={load} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

export default Slots;
