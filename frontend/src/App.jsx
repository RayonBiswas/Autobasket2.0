import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { ToastProvider } from "./components/Toast";
import { Icon } from "./lib/icons";
import Dashboard from "./pages/Dashboard";
import Detection from "./pages/Detection";
import Login from "./pages/Login";
import Settings from "./pages/Settings";
import Slots from "./pages/Slots";
import ShopLayout from "./pages/shop/ShopLayout";
import ShopOrders from "./pages/shop/ShopOrders";
import ShopProducts from "./pages/shop/ShopProducts";
import ShopSettings from "./pages/shop/ShopSettings";
import { clearToken, getToken } from "./services/auth";

const THEME_KEY = "ab_theme";

function readTheme() {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch { /* storage unavailable */ }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}


const HOME_NAV = [
  { to: "/", label: "Your fridge", icon: Icon.fridge, end: true },
  { to: "/shelves", label: "Shelves", icon: Icon.shelves },
  { to: "/camera", label: "Camera", icon: Icon.camera },
  { to: "/settings", label: "Settings", icon: Icon.gear },
];

const SHOP_NAV = [
  { to: "/shop", label: "Orders", icon: Icon.inbox, end: true },
  { to: "/shop/products", label: "Products", icon: Icon.tag },
  { to: "/shop/settings", label: "Shop details", icon: Icon.gear },
];

function Shell({ theme, onToggleTheme, onSignOut }) {
  const { pathname } = useLocation();
  const shopSide = pathname.startsWith("/shop");
  const links = shopSide ? SHOP_NAV : HOME_NAV;

  const nav = links.map((l) => (
    <NavLink key={l.to} to={l.to} end={l.end} className="rail-link">
      {l.icon}
      <span>{l.label}</span>
    </NavLink>
  ));

  return (
    <div className="shell" data-side={shopSide ? "shop" : "home"}>
      <aside className="rail">
        <div className="rail-brand">
          <div className="rail-mark">{shopSide ? "S" : "A"}</div>
          <div>
            <strong>{shopSide ? "Shop portal" : "AutoBasket"}</strong>
            <span>{shopSide ? "Orders from nearby homes" : "Knows what's in your fridge"}</span>
          </div>
        </div>
        <nav className="rail-nav" aria-label="Main">
          {nav}
          <div className="rail-gap" />
          <NavLink to={shopSide ? "/" : "/shop"} className="rail-link rail-switch">
            {shopSide ? Icon.back : Icon.shop}
            <span>{shopSide ? "Back to my fridge" : "I run a shop"}</span>
          </NavLink>
        </nav>
        <div className="rail-foot">
          <button className="rail-link" onClick={onToggleTheme}>
            {theme === "dark" ? Icon.sun : Icon.moon}
            <span>{theme === "dark" ? "Light mode" : "Dark mode"}</span>
          </button>
          <button className="btn btn-ghost btn-sm" onClick={onSignOut}>Sign out</button>
        </div>
      </aside>

      <main className="main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/shelves" element={<Slots />} />
          <Route path="/camera" element={<Detection />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/shop" element={<ShopLayout />}>
            <Route index element={<ShopOrders />} />
            <Route path="products" element={<ShopProducts />} />
            <Route path="settings" element={<ShopSettings />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>

      <nav className="bottom-nav" aria-label="Main">
        {nav}
        <NavLink to={shopSide ? "/" : "/shop"} className="rail-link">
          {shopSide ? Icon.fridge : Icon.shop}
          <span>{shopSide ? "My fridge" : "My shop"}</span>
        </NavLink>
      </nav>
    </div>
  );
}

function App() {
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

  return (
    <ToastProvider>
      <BrowserRouter>
        {token
          ? <Shell theme={theme} onToggleTheme={toggleTheme} onSignOut={signOut} />
          : <Login onLogin={setToken} theme={theme} onToggleTheme={toggleTheme} />}
      </BrowserRouter>
    </ToastProvider>
  );
}

export default App;
