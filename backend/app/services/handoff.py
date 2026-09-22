"""Deep links for delivery apps. We never check out on their behalf; we open their search for the product."""

from urllib.parse import quote

SEARCH_URLS = {
    "blinkit": "https://blinkit.com/s/?q={q}",
    "zepto": "https://www.zeptonow.com/search?query={q}",
    "instamart": "https://www.swiggy.com/instamart/search?custom_back=true&query={q}",
    "bigbasket": "https://www.bigbasket.com/ps/?q={q}",
}


def handoff_url(vendor_name: str, product_name: str) -> str | None:
    template = SEARCH_URLS.get(vendor_name.strip().lower())
    return template.format(q=quote(product_name)) if template else None
