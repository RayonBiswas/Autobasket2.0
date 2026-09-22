// Line icons used by the navigation. One stroke weight, one family.
const stroke = { fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round" };
export const Icon = {
  fridge: <svg viewBox="0 0 24 24" {...stroke}><rect x="5" y="2.5" width="14" height="19" rx="2" /><path d="M5 10h14M9 6v1.5M9 13.5v2.5" /></svg>,
  shelves: <svg viewBox="0 0 24 24" {...stroke}><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M3 10h18M3 15h18" /></svg>,
  camera: <svg viewBox="0 0 24 24" {...stroke}><path d="M4 8h3l2-3h6l2 3h3v11H4z" /><circle cx="12" cy="13" r="3.5" /></svg>,
  shop: <svg viewBox="0 0 24 24" {...stroke}><path d="M3 9l1.5-5h15L21 9M3 9v11h18V9M3 9h18M9 20v-6h6v6" /></svg>,
  inbox: <svg viewBox="0 0 24 24" {...stroke}><path d="M4 4h16v16H4zM4 14h4l2 3h4l2-3h4" /></svg>,
  tag: <svg viewBox="0 0 24 24" {...stroke}><path d="M3 12V4h8l9 9-8 8z" /><circle cx="7.5" cy="8.5" r="1.2" /></svg>,
  gear: <svg viewBox="0 0 24 24" {...stroke}><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1" /></svg>,
  sun: <svg viewBox="0 0 24 24" {...stroke}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>,
  moon: <svg viewBox="0 0 24 24" {...stroke}><path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z" /></svg>,
  back: <svg viewBox="0 0 24 24" {...stroke}><path d="M15 5l-7 7 7 7" /></svg>,
};
