import { useOutletContext } from "react-router-dom";
import API from "../../services/api";
import { useToast } from "../../lib/toast";
import ShopForm from "./ShopForm";

function ShopSettings() {
  const { shop, reload } = useOutletContext();
  const notify = useToast();

  return (
    <div className="page shop-page">
      <div className="page-head">
        <h1>Shop details</h1>
        <p>Customers see your hours, delivery time and area when they choose where to buy.</p>
      </div>
      <div className="shop-summary">
        <div><strong>{shop.rating}</strong> out of 5 from {shop.review_count} review{shop.review_count === 1 ? "" : "s"}</div>
        <div><strong>{shop.offer_count}</strong> products listed</div>
        <div><strong>{shop.open_orders}</strong> open orders</div>
      </div>
      <ShopForm
        initial={shop}
        submitLabel="Save changes"
        onSubmit={async (body) => {
          await API.put("/vendor/shop", body);
          await reload();
          notify("Saved.");
        }}
      />
    </div>
  );
}

export default ShopSettings;
