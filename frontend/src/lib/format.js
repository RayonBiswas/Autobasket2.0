// Small formatting helpers shared by the household and shop pages.

export const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : "");

export const rupees = (n) => `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

// "runs out today", "runs out tomorrow", "runs out on Thursday", "runs out on 3 Oct"
export function runsOut(days) {
  if (days == null || days >= 999) return null;
  if (days < 1) return "runs out today";
  if (days < 2) return "runs out tomorrow";
  const d = new Date();
  d.setDate(d.getDate() + Math.round(days));
  if (days < 7) return `runs out on ${d.toLocaleDateString("en-IN", { weekday: "long" })}`;
  return `runs out on ${d.toLocaleDateString("en-IN", { day: "numeric", month: "short" })}`;
}

// What an order status means to the household, in plain words.
export const ORDER_STAGE = {
  proposed: { label: "Waiting for your yes", pill: "pill-warn" },
  pending_confirmation: { label: "Waiting for your yes", pill: "pill-warn" },
  confirmed: { label: "Sent to the shop", pill: "pill-muted" },
  paid: { label: "Paid, shop notified", pill: "pill-muted" },
  accepted: { label: "Shop is packing it", pill: "pill-ok" },
  delivering: { label: "On the way", pill: "pill-ok" },
  delivered: { label: "Delivered", pill: "pill-ok" },
  verified: { label: "Delivered, back on the shelf", pill: "pill-ok" },
  handoff: { label: "Finish in their app", pill: "pill-muted" },
  cancelled: { label: "Cancelled", pill: "pill-muted" },
};

export function orderStage(status) {
  return ORDER_STAGE[status] || { label: status.replaceAll("_", " "), pill: "pill-muted" };
}
