import { useEffect, useState } from "react";
import Dashboard from "./pages/Dashboard";
import Detection from "./pages/Detection";
import Login from "./pages/Login";
import Slots from "./pages/Slots";
import { clearToken, getToken } from "./services/auth";

const THEME_KEY = "ab_theme";

function readTheme() {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch { /* storage unavailable */ }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

const Icon = {
  fridge: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="5" y="2.5" width="14" height="19" rx="2" /><path d="M5 10h14M9 6v1.5M9 13.5v2.5" />
    </svg>
  ),
  shelves: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="16" rx="2" /><path d="M3 10h18M3 15h18" />
    </svg>
  ),
  camera: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 8h3l2-3h6l2 3h3v11H4z" /><circle cx="12" cy="13" r="3.5" />
    </svg>
  ),
  sun: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
      <circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  ),
  moon: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z" />
    </svg>
  ),
};

const pages = [
  { id: "dashboard", label: "Your fridge", icon: Icon.fridge },
  { id: "slots", label: "Shelves", icon: Icon.shelves },
  { id: "detection", label: "Camera", icon: Icon.camera },
];

function App() {
  const [page, setPage] = useState("dashboard");
  const [token, setToken] = useState(getToken());
  const [theme, setTheme] = useState(readTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem(THEME_KEY, theme); } catch { /* ignore */ }
  }, [theme]);

  // The API layer fires this when a request comes back 401 (expired/invalid token).
  useEffect(() => {
    const onLogout = () => setToken(null);
    window.addEventListener("ab:logout", onLogout);
    return () => window.removeEventListener("ab:logout", onLogout);
  }, []);

  const signOut = () => {
    clearToken();
    setToken(null);
  };

  const toggleTheme = () => setTheme((t) => (t === "dark" ? "light" : "dark"));

  if (!token) return <Login onLogin={setToken} theme={theme} onToggleTheme={toggleTheme} />;

  const nav = (extraClass = "") =>
    pages.map((p) => (
      <button
        key={p.id}
        className={`rail-link ${extraClass}`}
        aria-current={page === p.id ? "page" : undefined}
        onClick={() => setPage(p.id)}
      >
        {p.icon}
        {p.label}
      </button>
    ));

  return (
    <div className="shell">
      <aside className="rail">
        <div className="rail-brand">
          <div className="rail-mark">A</div>
          <div>
            <strong>AutoBasket</strong>
            <span>Knows what's in your fridge</span>
          </div>
        </div>
        <nav className="rail-nav" aria-label="Main">{nav()}</nav>
        <div className="rail-foot">
          <button className="rail-link" onClick={toggleTheme}>
            {theme === "dark" ? Icon.sun : Icon.moon}
            {theme === "dark" ? "Light mode" : "Dark mode"}
          </button>
          <button className="btn btn-ghost btn-sm" onClick={signOut}>Sign out</button>
        </div>
      </aside>

      <main className="main">
        {page === "dashboard" && <Dashboard />}
        {page === "slots" && <Slots />}
        {page === "detection" && <Detection />}
      </main>

      <nav className="bottom-nav" aria-label="Main">{nav()}</nav>
    </div>
  );
}

export default App;
