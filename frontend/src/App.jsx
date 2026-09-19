import { useEffect, useState } from "react";
import Dashboard from "./pages/Dashboard";
import Camera from "./pages/Camera";
import Login from "./pages/Login";
import Slots from "./pages/Slots";
import { clearToken, getToken } from "./services/auth";

const styles = `
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg: #0a0a0f;
    --surface: #111118;
    --surface2: #1a1a24;
    --border: rgba(255,255,255,0.08);
    --accent: #00e5ff;
    --accent2: #7b61ff;
    --danger: #ff4d6d;
    --success: #00c896;
    --warning: #ffb627;
    --text: #f0f0f8;
    --muted: #6b6b80;
  }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Mono', monospace;
    min-height: 100vh;
  }

  /* ── App shell ── */
  .app-shell {
    display: flex;
    min-height: 100vh;
  }

  /* ── Sidebar ── */
  .app-sidebar {
    width: 220px;
    flex-shrink: 0;
    background: var(--surface);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    z-index: 20;
  }

  .sidebar-logo {
    padding: 28px 22px 24px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .sidebar-logo-icon {
    width: 32px;
    height: 32px;
    border-radius: 9px;
    background: linear-gradient(135deg, var(--accent2), var(--accent));
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    flex-shrink: 0;
    box-shadow: 0 4px 14px rgba(0,229,255,0.25);
  }

  .sidebar-logo-text {
    font-family: 'Syne', sans-serif;
    font-weight: 800;
    font-size: 17px;
    letter-spacing: -0.5px;
    line-height: 1;
  }

  .sidebar-logo-sub {
    font-size: 9px;
    color: var(--muted);
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-top: 3px;
  }

  .sidebar-nav {
    padding: 16px 12px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    flex: 1;
  }

  .sidebar-section-label {
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--muted);
    padding: 10px 10px 6px;
  }

  .nav-btn {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 11px 12px;
    border-radius: 10px;
    border: none;
    background: transparent;
    color: var(--muted);
    font-family: 'DM Mono', monospace;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.18s;
    text-align: left;
    width: 100%;
    position: relative;
  }

  .nav-btn:hover {
    background: var(--surface2);
    color: var(--text);
  }

  .nav-btn.active {
    background: var(--surface2);
    color: var(--text);
    border: 1px solid var(--border);
  }

  .nav-btn.active::before {
    content: '';
    position: absolute;
    left: 0;
    top: 8px;
    bottom: 8px;
    width: 3px;
    border-radius: 0 3px 3px 0;
    background: linear-gradient(180deg, var(--accent2), var(--accent));
  }

  .nav-icon {
    width: 30px;
    height: 30px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    flex-shrink: 0;
    background: var(--surface);
    border: 1px solid var(--border);
    transition: all 0.18s;
  }

  .nav-btn.active .nav-icon {
    background: linear-gradient(135deg, rgba(123,97,255,0.2), rgba(0,229,255,0.1));
    border-color: rgba(0,229,255,0.2);
  }

  .nav-label { line-height: 1; }

  .nav-badge {
    margin-left: auto;
    font-size: 9px;
    padding: 2px 6px;
    border-radius: 20px;
    background: rgba(0,229,255,0.1);
    border: 1px solid rgba(0,229,255,0.2);
    color: var(--accent);
    letter-spacing: 0.5px;
    text-transform: uppercase;
  }

  /* Sidebar footer */
  .sidebar-footer {
    padding: 16px 12px;
    border-top: 1px solid var(--border);
  }

  .sidebar-version {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    border-radius: 10px;
    background: var(--surface2);
    border: 1px solid var(--border);
  }

  .sidebar-version-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--success);
    box-shadow: 0 0 8px var(--success);
    animation: pulse 2s infinite;
    flex-shrink: 0;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }

  .sidebar-version-text {
    font-size: 11px;
    color: var(--muted);
    line-height: 1;
  }

  .sidebar-version-label {
    font-size: 9px;
    color: var(--success);
    letter-spacing: 0.5px;
    margin-top: 2px;
  }

  /* ── Main content ── */
  .app-main {
    margin-left: 220px;
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 100vh;
  }

  /* ── Top bar ── */
  .app-topbar {
    height: 60px;
    border-bottom: 1px solid var(--border);
    background: rgba(10,10,15,0.9);
    backdrop-filter: blur(20px);
    position: sticky;
    top: 0;
    z-index: 10;
    display: flex;
    align-items: center;
    padding: 0 32px;
    gap: 16px;
  }

  .topbar-breadcrumb {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--muted);
  }

  .topbar-breadcrumb-sep { opacity: 0.3; }

  .topbar-breadcrumb-current {
    color: var(--text);
    font-family: 'Syne', sans-serif;
    font-weight: 700;
  }

  .topbar-spacer { flex: 1; }

  .topbar-status {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: var(--muted);
    padding: 6px 12px;
    border-radius: 20px;
    border: 1px solid var(--border);
    background: var(--surface2);
  }

  .topbar-status-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--success);
    animation: pulse 2s infinite;
    flex-shrink: 0;
  }

  /* ── Page content ── */
  .app-page {
    flex: 1;
    animation: pageIn 0.2s ease;
  }

  @keyframes pageIn {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
  }

  /* ── Mobile nav (bottom bar) ── */
  @media (max-width: 700px) {
    .app-sidebar { display: none; }
    .app-main { margin-left: 0; }

    .app-mobile-nav {
      display: flex !important;
    }
  }

  .app-mobile-nav {
    display: none;
    position: fixed;
    bottom: 0; left: 0; right: 0;
    background: var(--surface);
    border-top: 1px solid var(--border);
    z-index: 30;
    padding: 8px 16px 16px;
    gap: 8px;
  }

  .mobile-nav-btn {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 5px;
    padding: 10px 8px;
    border-radius: 12px;
    border: none;
    background: transparent;
    color: var(--muted);
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    cursor: pointer;
    transition: all 0.18s;
  }

  .mobile-nav-btn.active {
    background: var(--surface2);
    color: var(--accent);
    border: 1px solid var(--border);
  }

  .mobile-nav-icon { font-size: 20px; }

  .sidebar-signout {
    margin-top: 10px; width: 100%; padding: 9px; border-radius: 10px; cursor: pointer;
    border: 1px solid var(--border); background: transparent; color: var(--muted);
    font-family: 'DM Mono', monospace; font-size: 12px;
  }
  .sidebar-signout:hover { color: var(--text); border-color: var(--accent); }
`;

const pages = [
  {
    id: "dashboard",
    label: "Dashboard",
    icon: "🛒",
    badge: null,
    description: "AI Marketplace",
  },
  {
    id: "slots",
    label: "Fridge Slots",
    icon: "▦",
    badge: null,
    description: "Trays & Slots",
  },
  {
    id: "camera",
    label: "Detection",
    icon: "◎",
    badge: "AI",
    description: "Water Level Scanner",
  },
];

function App() {
  const [page, setPage] = useState("dashboard");
  const [token, setToken] = useState(getToken());

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

  const current = pages.find(p => p.id === page);

  if (!token) {
    return (
      <>
        <style>{styles}</style>
        <Login onLogin={setToken} />
      </>
    );
  }

  return (
    <>
      <style>{styles}</style>
      <div className="app-shell">

        {/* ── Sidebar ── */}
        <aside className="app-sidebar">
          <div className="sidebar-logo">
            <div className="sidebar-logo-icon">🧺</div>
            <div>
              <div className="sidebar-logo-text">AutoBasket</div>
              <div className="sidebar-logo-sub">Smart Grocery AI</div>
            </div>
          </div>

          <nav className="sidebar-nav">
            <div className="sidebar-section-label">Navigation</div>

            {pages.map(p => (
              <button
                key={p.id}
                className={`nav-btn${page === p.id ? " active" : ""}`}
                onClick={() => setPage(p.id)}
              >
                <div className="nav-icon">{p.icon}</div>
                <div>
                  <div className="nav-label">{p.label}</div>
                </div>
                {p.badge && (
                  <span className="nav-badge">{p.badge}</span>
                )}
              </button>
            ))}
          </nav>

          <div className="sidebar-footer">
            <div className="sidebar-version">
              <div className="sidebar-version-dot" />
              <div>
                <div className="sidebar-version-text">System</div>
                <div className="sidebar-version-label">● Online</div>
              </div>
            </div>
            <button className="sidebar-signout" onClick={signOut}>Sign out</button>
          </div>
        </aside>

        {/* ── Main ── */}
        <main className="app-main">
          <div className="app-topbar">
            <div className="topbar-breadcrumb">
              <span>AutoBasket</span>
              <span className="topbar-breadcrumb-sep">/</span>
              <span className="topbar-breadcrumb-current">
                {current?.description}
              </span>
            </div>
            <div className="topbar-spacer" />
            <div className="topbar-status">
              <div className="topbar-status-dot" />
              All systems operational
            </div>
          </div>

          <div className="app-page" key={page}>
            {page === "dashboard" && <Dashboard />}
            {page === "slots" && <Slots />}
            {page === "camera" && <Camera />}
          </div>
        </main>

        {/* ── Mobile bottom nav ── */}
        <div className="app-mobile-nav">
          {pages.map(p => (
            <button
              key={p.id}
              className={`mobile-nav-btn${page === p.id ? " active" : ""}`}
              onClick={() => setPage(p.id)}
            >
              <span className="mobile-nav-icon">{p.icon}</span>
              {p.label}
            </button>
          ))}
        </div>

      </div>
    </>
  );
}

export default App;