import { useCallback, useEffect, useState } from "react";
import API from "../services/api";

const styles = `
  .slots-root { padding: 32px; display: flex; flex-direction: column; gap: 24px; max-width: 900px; }
  .slots-title { font-family: 'Syne', sans-serif; font-size: 28px; font-weight: 800; letter-spacing: -1px; }
  .slots-sub { color: var(--muted); font-size: 13px; margin-top: 6px; }
  .tray-card { background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 18px 20px; }
  .tray-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
  .tray-name { font-family: 'Syne', sans-serif; font-weight: 700; font-size: 15px; }
  .tray-device { font-size: 11px; color: var(--muted); }
  .slot-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; }
  .slot {
    border: 1px dashed var(--border); border-radius: 12px; padding: 14px 12px; min-height: 84px;
    display: flex; flex-direction: column; gap: 6px; background: var(--surface2);
  }
  .slot.filled { border-style: solid; border-color: rgba(0,229,255,0.35); }
  .slot-pos { font-size: 10px; letter-spacing: 1.5px; text-transform: uppercase; color: var(--muted); }
  .slot-body { font-size: 13px; }
  .slot-empty { color: var(--muted); font-style: italic; }
  .slots-empty {
    background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 28px;
    display: flex; flex-direction: column; gap: 12px; align-items: flex-start;
  }
  .slots-btn {
    padding: 11px 18px; border: none; border-radius: 10px; cursor: pointer; color: #fff;
    background: linear-gradient(135deg, var(--accent2), var(--accent));
    font-family: 'Syne', sans-serif; font-weight: 700; font-size: 13px;
  }
  .slots-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .slots-msg { font-size: 12px; color: var(--muted); }
`;

function Slots() {
  const [trays, setTrays] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  const load = useCallback(async () => {
    try {
      const res = await API.get("/households/me/slots");
      setTrays(res.data.trays);
    } catch (err) {
      setMsg(err.response?.data?.detail || "Could not load slots.");
      setTrays([]);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const seed = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const res = await API.post("/seed/dev");
      setMsg(res.data.message);
      await load();
    } catch (err) {
      setMsg(err.response?.data?.detail || "Seeding failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <style>{styles}</style>
      <div className="slots-root">
        <div>
          <div className="slots-title">Fridge Slots</div>
          <div className="slots-sub">One card per load cell. Assigning products to slots arrives in Phase 2.</div>
        </div>

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
                <div className={`slot${s.product_id ? " filled" : ""}`} key={s.slot_id}>
                  <div className="slot-pos">Slot {s.position}</div>
                  <div className="slot-body">
                    {s.product_id ? `Product #${s.product_id}` : <span className="slot-empty">Empty</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

export default Slots;
