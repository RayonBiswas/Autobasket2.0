import { useCallback, useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import API from "../../services/api";
import { errorText, useToast } from "../../lib/toast";
import ShopForm from "./ShopForm";

export const shopStyles = `
  .shop-page { max-width: 720px; }
  .shop-summary { display: flex; flex-wrap: wrap; gap: 12px 28px; align-items: baseline; color: var(--muted); font-size: 14px; }
  .shop-summary strong { color: var(--text); font-size: 1.05rem; }
  .order-card { display: flex; flex-direction: column; gap: 12px; }
  .order-top { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
  .order-top h3 { font-size: 1.1rem; }
  .order-lines { display: flex; flex-direction: column; gap: 4px; font-size: 15px; }
  .order-line { display: flex; justify-content: space-between; gap: 12px; }
  .order-total { display: flex; justify-content: space-between; font-weight: 600; border-top: 1px solid var(--line); padding-top: 10px; }
  .order-actions { display: flex; gap: 8px; flex-wrap: wrap; }
  .order-actions .btn { flex: 1; min-width: 120px; padding: 12px 16px; }
  .listing { display: grid; grid-template-columns: 1fr 104px 190px; gap: 10px; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--line); }
  .listing:last-child { border-bottom: none; }
  .listing-name { display: flex; flex-direction: column; }
  .listing-name span { color: var(--muted); font-size: 13px; }
  .listing .input { padding: 9px 12px; }
  .stock { display: inline-flex; align-items: center; gap: 8px; font-size: 14px; color: var(--muted); cursor: pointer; white-space: nowrap; }
  .stock input { width: 18px; height: 18px; accent-color: var(--accent); }
  .csv-row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
  .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .form-grid .span { grid-column: 1 / -1; }
  @media (max-width: 560px) {
    .form-grid { grid-template-columns: 1fr; }
    .listing { grid-template-columns: 1fr 96px; }
    .listing .stock { grid-column: 1 / -1; }
  }
`;

// The shop portal: loads the caller's shop once and shares it with the tab pages through Outlet context.
function ShopLayout() {
  const notify = useToast();
  const [shop, setShop] = useState(undefined); // undefined = loading, null = none yet
  const [tick, setTick] = useState(0);
  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let alive = true;
    API.get("/vendor/shop")
      .then((res) => { if (alive) setShop(res.data ?? null); })
      .catch((err) => { if (alive) notify(errorText(err, "We couldn't load your shop."), "error"); });
    return () => { alive = false; };
  }, [notify, tick]);

  if (shop === undefined) {
    return <div className="page shop-page"><style>{shopStyles}</style><p className="muted">Opening your shop…</p></div>;
  }

  if (shop === null) {
    return (
      <div className="page shop-page">
        <style>{shopStyles}</style>
        <div className="page-head">
          <h1>Set up your shop</h1>
          <p>Homes nearby will see your prices and can order in one tap. Takes two minutes.</p>
        </div>
        <ShopForm
          submitLabel="Open my shop"
          onSubmit={async (body) => {
            const res = await API.post("/vendor/shop", body);
            setShop(res.data);
            notify(`${res.data.name} is open. Add your products next.`);
          }}
        />
      </div>
    );
  }

  return (
    <>
      <style>{shopStyles}</style>
      <Outlet context={{ shop, reload }} />
    </>
  );
}

export default ShopLayout;
