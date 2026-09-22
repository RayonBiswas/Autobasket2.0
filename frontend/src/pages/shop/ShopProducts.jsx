import { useCallback, useEffect, useRef, useState } from "react";
import { useOutletContext } from "react-router-dom";
import API from "../../services/api";
import { errorText, useToast } from "../../lib/toast";
import { cap } from "../../lib/format";

// One catalog row: the price box is the whole interaction. Save happens on blur or Enter.
function Listing({ product, onSave, onRemove }) {
  const [price, setPrice] = useState(product.price ?? "");
  const [inStock, setInStock] = useState(product.in_stock ?? true);
  const [busy, setBusy] = useState(false);
  const listed = product.price != null;

  useEffect(() => { setPrice(product.price ?? ""); setInStock(product.in_stock ?? true); }, [product.price, product.in_stock]);

  const save = async (nextStock = inStock) => {
    const value = Number(price);
    if (!value || value <= 0) return;
    if (value === product.price && nextStock === product.in_stock) return;
    setBusy(true);
    try { await onSave(product, value, nextStock); } finally { setBusy(false); }
  };

  const toggleStock = async (e) => {
    const next = e.target.checked;
    setInStock(next);
    if (listed) await save(next);
  };

  return (
    <div className="listing">
      <div className="listing-name">
        <strong>{cap(product.name)}</strong>
        <span>{product.pack_size} {product.unit}{product.brand ? `, ${product.brand}` : ""}</span>
      </div>
      <input
        className="input" inputMode="decimal" placeholder="₹" aria-label={`Price for ${product.name}`}
        value={price} disabled={busy}
        onChange={(e) => setPrice(e.target.value)}
        onBlur={() => save()}
        onKeyDown={(e) => e.key === "Enter" && e.target.blur()}
      />
      {listed ? (
        <label className="stock">
          <input type="checkbox" checked={inStock} onChange={toggleStock} disabled={busy} />
          {inStock ? "In stock" : "Out of stock"}
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => onRemove(product)}>Remove</button>
        </label>
      ) : (
        <span className="stock muted">Not listed yet</span>
      )}
    </div>
  );
}

function ShopProducts() {
  const { shop, reload } = useOutletContext();
  const notify = useToast();
  const [products, setProducts] = useState(null);
  const [q, setQ] = useState("");
  const [onlyMine, setOnlyMine] = useState(false);
  const fileRef = useRef(null);

  const load = useCallback(async () => {
    try {
      const res = await API.get("/vendor/catalog", { params: { q } });
      setProducts(res.data.products);
    } catch (err) {
      notify(errorText(err, "We couldn't load the catalog."), "error");
      setProducts([]);
    }
  }, [q, notify]);

  useEffect(() => { load(); }, [load]);

  const onSave = async (product, price, inStock) => {
    try {
      await API.put("/vendor/offers", { offers: [{ product_id: product.id, price, in_stock: inStock }] });
      notify(`${cap(product.name)} listed at ₹${price}${inStock ? "" : ", out of stock"}.`);
      await load();
      reload();
    } catch (err) {
      notify(errorText(err, "We couldn't save that price."), "error");
    }
  };

  const onRemove = async (product) => {
    try {
      await API.delete(`/vendor/offers/${product.id}`);
      notify(`${cap(product.name)} removed from your shop.`);
      await load();
      reload();
    } catch (err) {
      notify(errorText(err, "We couldn't remove that product."), "error");
    }
  };

  const uploadCsv = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const body = new FormData();
    body.append("file", file);
    try {
      const res = await API.post("/vendor/offers/csv", body, { headers: { "Content-Type": "multipart/form-data" } });
      const { added, updated, unknown } = res.data;
      const skipped = unknown.length ? ` Skipped ${unknown.length} we don't know: ${unknown.slice(0, 3).join(", ")}${unknown.length > 3 ? "…" : ""}.` : "";
      notify(`Added ${added}, updated ${updated}.${skipped}`, unknown.length ? "error" : "info");
      await load();
      reload();
    } catch (err) {
      notify(errorText(err, "That file didn't work. It needs 'product' and 'price' columns."), "error");
    } finally {
      e.target.value = "";
    }
  };

  const rows = (products ?? []).filter((p) => !onlyMine || p.price != null);

  return (
    <div className="page shop-page">
      <div className="page-head">
        <h1>Products</h1>
        <p>{shop.offer_count === 0 ? "Type a price next to anything you sell. It goes live straight away." : `You list ${shop.offer_count} product${shop.offer_count === 1 ? "" : "s"}. Change a price and it updates for customers instantly.`}</p>
      </div>

      <div className="csv-row">
        <input className="input" style={{ flex: 1, minWidth: 180 }} placeholder="Search the catalog" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search products" />
        <label className="stock"><input type="checkbox" checked={onlyMine} onChange={(e) => setOnlyMine(e.target.checked)} />Only my products</label>
        <button className="btn" onClick={() => fileRef.current?.click()}>Upload a price list</button>
        <input ref={fileRef} type="file" accept=".csv,text/csv" hidden onChange={uploadCsv} />
      </div>
      <p className="small muted">Price list format: a CSV with columns <code>product, price, in_stock</code>. Product names match the catalog.</p>

      <div className="card" style={{ padding: "4px 20px" }}>
        {products === null && <p className="muted" style={{ padding: 12 }}>Loading the catalog…</p>}
        {products && rows.length === 0 && <p className="muted" style={{ padding: 12 }}>{onlyMine ? "You haven't listed anything yet." : "Nothing matches that search."}</p>}
        {rows.map((p) => <Listing key={p.id} product={p} onSave={onSave} onRemove={onRemove} />)}
      </div>
    </div>
  );
}

export default ShopProducts;
