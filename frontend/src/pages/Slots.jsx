import { useCallback, useEffect, useState } from "react";
import API from "../services/api";

const REFRESH_MS = 5000;

const styles = `
  .slots-root { padding: 32px; display: flex; flex-direction: column; gap: 24px; max-width: 1000px; }
  .slots-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
  .slots-title { font-family: 'Syne', sans-serif; font-size: 28px; font-weight: 800; letter-spacing: -1px; }
  .slots-sub { color: var(--muted); font-size: 13px; margin-top: 6px; }
  .tray-card { background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 18px 20px; }
  .tray-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
  .tray-name { font-family: 'Syne', sans-serif; font-weight: 700; font-size: 15px; }
  .tray-device { font-size: 11px; color: var(--muted); }
  .slot-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; }
  .slot {
    border: 1px dashed var(--border); border-radius: 12px; padding: 14px 12px;
    display: flex; flex-direction: column; gap: 8px; background: var(--surface2);
  }
  .slot.filled { border-style: solid; border-color: rgba(0,229,255,0.35); }
  .slot-pos { font-size: 10px; letter-spacing: 1.5px; text-transform: uppercase; color: var(--muted); display: flex; justify-content: space-between; }
  .slot-select {
    width: 100%; padding: 8px 10px; border-radius: 8px; border: 1px solid var(--border);
    background: var(--surface); color: var(--text); font-family: 'DM Mono', monospace; font-size: 12px;
  }
  .slot-weight { font-family: 'Syne', sans-serif; font-weight: 800; font-size: 20px; }
  .slot-weight small { font-family: 'DM Mono', monospace; font-weight: 400; font-size: 11px; color: var(--muted); margin-left: 6px; }
  .slot-bar { height: 6px; background: var(--surface); border-radius: 99px; overflow: hidden; border: 1px solid var(--border); }
  .slot-bar-fill { height: 100%; border-radius: 99px; background: linear-gradient(90deg, var(--accent2), var(--accent)); transition: width 0.6s; }
  .slot-bar-fill.low { background: linear-gradient(90deg, #c0192e, var(--danger)); }
  .slot-meta { font-size: 10px; color: var(--muted); }
  .slot-actions { display: flex; gap: 6px; }
  .slot-btn {
    flex: 1; padding: 7px 8px; border-radius: 8px; cursor: pointer; font-size: 11px;
    border: 1px solid var(--border); background: transparent; color: var(--text); font-family: 'DM Mono', monospace;
  }
  .slot-btn:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
  .slot-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .slots-btn {
    padding: 11px 18px; border: none; border-radius: 10px; cursor: pointer; color: #fff;
    background: linear-gradient(135deg, var(--accent2), var(--accent));
    font-family: 'Syne', sans-serif; font-weight: 700; font-size: 13px; white-space: nowrap;
  }
  .slots-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .slots-empty {
    background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 28px;
    display: flex; flex-direction: column; gap: 12px; align-items: flex-start;
  }
  .slots-msg { font-size: 12px; color: var(--muted); }
  .token-card {
    background: rgba(0,200,150,0.06); border: 1px solid rgba(0,200,150,0.3); border-radius: 14px; padding: 16px 18px;
    display: flex; flex-direction: column; gap: 8px; font-size: 12px;
  }
  .token-card code { display: block; padding: 10px; border-radius: 8px; background: var(--surface2); word-break: break-all; font-size: 12px; user-select: all; }
  .token-card strong { color: var(--success); }
`;

function pct(fraction) {
  return fraction == null ? null : Math.round(fraction * 100);
}

function SlotCard({ slot, products, onChange }) {
  const [busy, setBusy] = useState(false);
  const p = pct(slot.remaining_fraction);
  const hasReading = slot.latest_weight_grams != null;

  const call = async (fn) => {
    setBusy(true);
    try {
      await fn();
      await onChange();
    } catch (err) {
      alert(err.response?.data?.detail || "Request failed");
    } finally {
      setBusy(false);
    }
  };

  const assign = (e) => {
    const value = e.target.value;
    const body = value === "" ? { clear_product: true } : { product_id: Number(value) };
    call(() => API.put(`/slots/${slot.slot_id}`, body));
  };

  return (
    <div className={`slot${slot.product_id ? " filled" : ""}`}>
      <div className="slot-pos">
        <span>Slot {slot.position}</span>
        {p != null && <span>{p}%</span>}
      </div>
      <select className="slot-select" value={slot.product_id ?? ""} onChange={assign} disabled={busy}>
        <option value="">— no product —</option>
        {products.map((pr) => (
          <option key={pr.id} value={pr.id}>{pr.name} · {pr.pack_size} {pr.unit}</option>
        ))}
      </select>
      <div className="slot-weight">
        {hasReading ? Math.round(slot.latest_weight_grams) : "—"}
        <small>g{slot.latest_at ? ` · ${new Date(slot.latest_at).toLocaleTimeString()}` : ""}</small>
      </div>
      <div className="slot-bar">
        <div className={`slot-bar-fill${p != null && p < 25 ? " low" : ""}`} style={{ width: `${p ?? 0}%` }} />
      </div>
      <div className="slot-meta">
        empty {slot.tare_grams != null ? `${Math.round(slot.tare_grams)} g` : "—"} · full {slot.full_grams != null ? `${Math.round(slot.full_grams)} g` : "—"}
      </div>
      <div className="slot-actions">
        <button className="slot-btn" disabled={busy || !hasReading} onClick={() => call(() => API.post(`/slots/${slot.slot_id}/mark-empty`))}>
          Mark empty
        </button>
        <button className="slot-btn" disabled={busy || !hasReading} onClick={() => call(() => API.post(`/slots/${slot.slot_id}/mark-full`))}>
          Mark full
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
      setMsg(err.response?.data?.detail || "Could not load slots.");
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
      if (res.data.device_token) setNewDevice({ name: "Dev Fridge", token: res.data.device_token });
      const pr = await API.get("/products");
      setProducts(pr.data.products);
      await load();
    } catch (err) {
      setMsg(err.response?.data?.detail || "Seeding failed.");
    } finally {
      setBusy(false);
    }
  };

  const addDevice = async () => {
    const name = window.prompt("Name for the new fridge device", "Kitchen fridge");
    if (!name) return;
    try {
      const res = await API.post("/devices", { name });
      setNewDevice({ name: res.data.name, token: res.data.token });
    } catch (err) {
      alert(err.response?.data?.detail || "Could not create device");
    }
  };

  return (
    <>
      <style>{styles}</style>
      <div className="slots-root">
        <div className="slots-head">
          <div>
            <div className="slots-title">Fridge Slots</div>
            <div className="slots-sub">One card per load cell. Pick what sits on it, then tap Mark empty / Mark full to calibrate. Refreshes every 5 s.</div>
          </div>
          <button className="slots-btn" onClick={addDevice}>+ Add device</button>
        </div>

        {newDevice && (
          <div className="token-card">
            <div><strong>{newDevice.name}</strong> created. Copy this token now — it is shown only once.</div>
            <code>{newDevice.token}</code>
            <div className="slots-msg">
              Run the simulator with it: <code style={{ display: "inline", padding: "2px 6px" }}>$env:AB_DEVICE_TOKEN="…"; python edge/simulator.py</code>
            </div>
            <button className="slot-btn" style={{ alignSelf: "flex-start" }} onClick={() => setNewDevice(null)}>Dismiss</button>
          </div>
        )}

        {trays === null && <div className="slots-msg">Loading…</div>}

        {trays && trays.length === 0 && (
          <div className="slots-empty">
            <div>No fridge is linked to this household yet.</div>
            <button className="slots-btn" onClick={seed} disabled={busy}>
              {busy ? "Seeding…" : "Seed dev data (2 trays × 4 slots)"}
            </button>
            {msg && <div className="slots-msg">{msg}</div>}
          </div>
        )}

        {trays && trays.map((t) => (
          <div className="tray-card" key={t.tray_id}>
            <div className="tray-head">
              <div className="tray-name">{t.label || `Tray ${t.position}`}</div>
              <div className="tray-device">{t.device}</div>
            </div>
            <div className="slot-grid">
              {t.slots.map((s) => (
                <SlotCard key={s.slot_id} slot={s} products={products} onChange={load} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

export default Slots;
