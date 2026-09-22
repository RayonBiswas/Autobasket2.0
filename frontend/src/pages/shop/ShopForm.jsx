import { useState } from "react";
import { errorText } from "../../lib/toast";

const EMPTY = {
  name: "", pincode: "", phone: "", address: "", opens_at: "07:00", closes_at: "22:00",
  eta_minutes: 30, delivery_radius_km: 3, min_order_amount: 0,
};

function Field({ id, label, hint, children }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children}
      {hint && <span className="small muted">{hint}</span>}
    </div>
  );
}

// Shared by "Set up your shop" and "Shop details". Sends only the fields a shop can edit.
function ShopForm({ initial, submitLabel, onSubmit }) {
  const [form, setForm] = useState({ ...EMPTY, ...(initial || {}) });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit({
        name: form.name.trim(),
        pincode: form.pincode.trim(),
        phone: form.phone.trim() || null,
        address: form.address.trim() || null,
        opens_at: form.opens_at || null,
        closes_at: form.closes_at || null,
        eta_minutes: Number(form.eta_minutes),
        delivery_radius_km: Number(form.delivery_radius_km),
        min_order_amount: Number(form.min_order_amount) || 0,
      });
    } catch (err) {
      setError(errorText(err, "We couldn't save the shop. Check the details and try again."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="card form-grid" onSubmit={submit}>
      <Field id="name" label="Shop name"><input id="name" className="input span" required minLength={2} value={form.name} onChange={set("name")} placeholder="Sharma Kirana" /></Field>
      <Field id="phone" label="Phone"><input id="phone" className="input" inputMode="tel" value={form.phone} onChange={set("phone")} placeholder="98765 43210" /></Field>
      <Field id="pincode" label="Pincode"><input id="pincode" className="input" required inputMode="numeric" pattern="[0-9]{6}" value={form.pincode} onChange={set("pincode")} placeholder="560001" /></Field>
      <Field id="eta" label="Delivery takes about" hint="minutes"><input id="eta" className="input" type="number" min={5} max={1440} value={form.eta_minutes} onChange={set("eta_minutes")} /></Field>
      <div className="span">
        <Field id="address" label="Address" hint="Shown to customers on their order"><input id="address" className="input" value={form.address} onChange={set("address")} placeholder="12, MG Road, opposite the temple" /></Field>
      </div>
      <Field id="opens" label="Opens at"><input id="opens" className="input" type="time" value={form.opens_at} onChange={set("opens_at")} /></Field>
      <Field id="closes" label="Closes at"><input id="closes" className="input" type="time" value={form.closes_at} onChange={set("closes_at")} /></Field>
      <Field id="radius" label="Delivers up to" hint="kilometres away"><input id="radius" className="input" type="number" min={0.5} max={50} step={0.5} value={form.delivery_radius_km} onChange={set("delivery_radius_km")} /></Field>
      <Field id="min" label="Minimum order" hint="₹, leave 0 for none"><input id="min" className="input" type="number" min={0} value={form.min_order_amount} onChange={set("min_order_amount")} /></Field>
      {error && <div className="span notice notice-warn" role="alert">{error}</div>}
      <div className="span">
        <button className="btn btn-primary btn-block" disabled={busy}>{busy ? "Saving…" : submitLabel}</button>
      </div>
    </form>
  );
}

export default ShopForm;
