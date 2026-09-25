import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import API from "../services/api";
import { errorText, useToast } from "../lib/toast";
import { cap } from "../lib/format";

const styles = `
  .cam-page { max-width: 820px; }
  .shelf-card { display: flex; flex-direction: column; gap: 14px; }
  .shelf-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
  .shelf-head span { color: var(--muted); font-size: 14px; }
  .seen-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px; }
  .seen { display: flex; flex-direction: column; gap: 6px; padding: 14px; border-radius: var(--r-control); border: 1px solid var(--line); background: var(--surface-2); }
  .seen.match { border-color: var(--ok); }
  .seen.suggestion { border-color: var(--accent); background: var(--accent-soft); }
  .seen.mismatch { border-color: var(--warn); background: var(--warn-soft); }
  .seen-slot { font-size: 13px; color: var(--muted); }
  .seen-item { font-size: 1.05rem; font-weight: 600; }
  .seen-note { font-size: 13px; color: var(--muted); }
  .seen .btn { margin-top: 4px; }
`;

const NOTE = {
  match: "Camera and scale agree",
  suggestion: "Not assigned yet",
  mismatch: "Different from what's assigned",
  unknown: "Camera couldn't tell",
  unsure: "Camera isn't sure",
};

function SeenSlot({ slot, onUse }) {
  const v = slot.vision;
  const assigned = slot.product_name ? cap(slot.product_name) : "Nothing assigned";
  if (!v) {
    return (
      <div className="seen">
        <div className="seen-slot">Slot {slot.position}</div>
        <div className="seen-item">{assigned}</div>
        <div className="seen-note">No photo yet</div>
      </div>
    );
  }
  const canUse = (v.kind === "suggestion" || v.kind === "mismatch" || v.kind === "unsure") && v.matched_product_id;
  return (
    <div className={`seen ${v.kind}`}>
      <div className="seen-slot">Slot {slot.position} · you said {assigned.toLowerCase()}</div>
      <div className="seen-item">{v.matched_name ? cap(v.matched_name) : cap(v.item || "unknown")}</div>
      <div className="seen-note">{NOTE[v.kind] || v.kind}, {Math.round(v.confidence * 100)}% sure</div>
      {canUse && <button className="btn btn-sm btn-primary" onClick={() => onUse(slot, v)}>Use {v.matched_name}</button>}
    </div>
  );
}

function ShelfCard({ tray, onAnalyzed, onUse }) {
  const notify = useToast();
  const fileRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const last = tray.slots.map((s) => s.vision?.at).filter(Boolean).sort().at(-1);

  const upload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const body = new FormData();
    body.append("image", file);
    setBusy(true);
    try {
      await API.post(`/vision/trays/${tray.tray_id}/photo`, body, { headers: { "Content-Type": "multipart/form-data" } });
      notify("Looked at the shelf. Check what it saw below.");
      await onAnalyzed();
    } catch (err) {
      notify(errorText(err, "We couldn't read that photo."), "error");
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  };

  return (
    <section className="card shelf-card">
      <div className="shelf-head">
        <div>
          <h2>{tray.label || `Shelf ${tray.position}`}</h2>
          <span>{last ? `Last photo ${new Date(last).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}` : "No photo yet"}</span>
        </div>
        <button className="btn btn-primary" disabled={busy} onClick={() => fileRef.current?.click()}>{busy ? "Looking…" : "Take or upload a photo"}</button>
        <input ref={fileRef} type="file" accept="image/*" capture="environment" hidden onChange={upload} />
      </div>
      <div className="seen-grid">
        {tray.slots.map((s) => <SeenSlot key={s.slot_id} slot={s} onUse={onUse} />)}
      </div>
    </section>
  );
}

function Camera() {
  const notify = useToast();
  const [trays, setTrays] = useState(null);
  const [tick, setTick] = useState(0);
  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let alive = true;
    API.get("/households/me/slots").then((r) => alive && setTrays(r.data.trays)).catch((err) => {
      if (alive) { notify(errorText(err, "We couldn't load your shelves."), "error"); setTrays([]); }
    });
    return () => { alive = false; };
  }, [notify, tick]);

  const onUse = async (slot, v) => {
    try {
      await API.put(`/slots/${slot.slot_id}`, { product_id: v.matched_product_id });
      notify(`Slot ${slot.position} is now ${v.matched_name}. Tap "This is full" on Shelves once to teach the scale.`);
      reload();
    } catch (err) {
      notify(errorText(err, "We couldn't assign that."), "error");
    }
  };

  return (
    <div className="page cam-page">
      <style>{styles}</style>
      <div className="page-head">
        <h1>Camera</h1>
        <p>Photograph a shelf and the app names what sits in each slot. The scales still measure how much is left.</p>
      </div>

      {trays === null && <p className="muted">Loading your shelves…</p>}
      {trays && trays.length === 0 && (
        <div className="card empty">
          <h2>No shelves yet</h2>
          <p>Add a fridge or load the demo fridge on the Shelves page, then come back and photograph a shelf.</p>
          <Link className="btn btn-primary" to="/shelves">Go to Shelves</Link>
        </div>
      )}
      {trays && trays.map((t) => <ShelfCard key={t.tray_id} tray={t} onAnalyzed={async () => reload()} onUse={onUse} />)}

      <p className="small muted">
        Once the fridge camera is installed it sends a photo of each shelf whenever something is taken or put back, so you rarely need to do this by hand.
        Needs an image-capable model: set OPENAI_API_KEY (and VISION_MODEL) on the server.
      </p>
    </div>
  );
}

export default Camera;
