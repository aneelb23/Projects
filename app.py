"""
TCGplayer Card Search - Search Yu-Gi-Oh! cards by name and price.
Uses YGOPRODeck API (free) for live card data with TCGplayer prices.
"""
import urllib.parse
from pathlib import Path

import requests
from flask import Flask, render_template, request, url_for

app = Flask(__name__)

# YGOPRODeck API - free, no key required (rate limit: 20 req/sec)
YGOPRODECK_API = "https://db.ygoprodeck.com/api/v7/cardinfo.php"

# TCGplayer search URL for Yu-Gi-Oh!
TCGPLAYER_SEARCH_BASE = "https://www.tcgplayer.com/search/yugioh/product"

# =============================================================================
# IN STOCK FILTER - Adds param to TCGplayer URLs when "In stock only" is checked.
# TCGplayer's URL params may vary; edit below if the filter doesn't work.
# =============================================================================
IN_STOCK_PARAM = "availability"
IN_STOCK_VALUE = "in_stock"

# =============================================================================
# DEMO CARDS - Edit this list to add/remove cards in the dropdown.
# Use direct TCGplayer product URLs (not search) so users land on the product page.
# Format: {"name": "Card Name", "set": "Set Name", "market_price": 0.00,
#          "low": 0.00, "high": 0.00, "url": "https://www.tcgplayer.com/product/..."}
# =============================================================================
DEMO_CARDS = [
    {"name": "Breaker the Magical Warrior", "set": "Magician's Force", "market_price": 3.99, "low": 1.50, "high": 15.00, "url": "https://www.tcgplayer.com/product/21804/yugioh-magicians-force-breaker-the-magical-warrior"},
    {"name": "Yubel - The Ultimate Nightmare", "set": "Phantom Darkness", "market_price": 12.99, "low": 8.00, "high": 25.00, "url": "https://www.tcgplayer.com/product/26609/yugioh-phantom-darkness-yubel-the-ultimate-nightmare"},
    {"name": "Cyberdark Edge (UTR)", "set": "Cyberdark Impact (CDIP)", "market_price": 8.99, "low": 5.00, "high": 20.00, "url": "https://www.tcgplayer.com/product/27469/yugioh-cyberdark-impact-cyberdark-edge-utr"},
    {"name": "Mystical Space Typhoon", "set": "Magic Ruler (MRL)", "market_price": 23.00, "low": 12.00, "high": 50.00, "url": "https://www.tcgplayer.com/product/22255/yugioh-magic-ruler-mystical-space-typhoon"},
    {"name": "Curse of Dragon", "set": "The Legend of Blue Eyes White Dragon (LOB)", "market_price": 5.42, "low": 2.50, "high": 15.00, "url": "https://www.tcgplayer.com/product/21851/yugioh-the-legend-of-blue-eyes-white-dragon-curse-of-dragon"},
    {"name": "Celtic Guardian", "set": "The Legend of Blue Eyes White Dragon (LOB)", "market_price": 5.43, "low": 3.00, "high": 20.00, "url": "https://www.tcgplayer.com/product/21823/yugioh-the-legend-of-blue-eyes-white-dragon-celtic-guardian"},
    {"name": "Jinzo", "set": "Pharaoh's Servant (PSV)", "market_price": 37.70, "low": 20.00, "high": 80.00, "url": "https://www.tcgplayer.com/product/22111/yugioh-pharaohs-servant-jinzo"},
    {"name": "Black Luster Soldier - Envoy of the Beginning", "set": "Invasion of Chaos (IOC)", "market_price": 29.29, "low": 25.00, "high": 100.00, "url": "https://www.tcgplayer.com/product/23112/yugioh-invasion-of-chaos-black-luster-soldier-envoy-of-the-beginning"},
    {"name": "Neo-Spacian Grand Mole (UTR)", "set": "Strike of Neos (STON)", "market_price": 47.79, "low": 35.00, "high": 95.00, "url": "https://www.tcgplayer.com/product/58550/yugioh-strike-of-neos-neo-spacian-grand-mole-utr"},
    {"name": "Barrel Dragon", "set": "Metal Raiders (MRD)", "market_price": 7.34, "low": 3.00, "high": 50.00, "url": "https://www.tcgplayer.com/product/21770/yugioh-metal-raiders-barrel-dragon"},
    {"name": "Injection Fairy Lily", "set": "Legacy of Darkness (LOD)", "market_price": 15.70, "low": 10.00, "high": 70.00, "url": "https://www.tcgplayer.com/product/22975/yugioh-legacy-of-darkness-injection-fairy-lily"},
]


def _extract_product_url(set_url: str | None) -> str | None:
    """
    Extract clean TCGplayer product URL from YGOPRODeck's partner set_url.
    Partner format: https://partner.tcgplayer.com/...?u=https%3A%2F%2Fwww.tcgplayer.com%2Fproduct%2F...
    Returns the decoded product URL or None.
    """
    if not set_url:
        return None
    if "tcgplayer.com/product/" in set_url and "partner." not in set_url:
        return set_url
    parsed = urllib.parse.urlparse(set_url)
    if parsed.netloc == "partner.tcgplayer.com" and parsed.query:
        params = urllib.parse.parse_qs(parsed.query)
        u = params.get("u", [None])[0]
        if u:
            return urllib.parse.unquote(u)
    return None


def get_tcgplayer_search_url(
    query: str, first_edition: bool = False, in_stock: bool = False
) -> str:
    """Build TCGplayer search URL with query. Optionally append '1st edition' and in-stock filter."""
    if first_edition and query:
        query = f"{query} 1st edition"
    params = {"q": query} if query else {}
    if in_stock:
        params[IN_STOCK_PARAM] = IN_STOCK_VALUE
    return f"{TCGPLAYER_SEARCH_BASE}?{urllib.parse.urlencode(params)}" if params else TCGPLAYER_SEARCH_BASE


def append_params_to_url(url: str, first_edition: bool = False, in_stock: bool = False) -> str:
    """
    Append first_edition and/or in_stock params to a TCGplayer URL.
    For search URLs: adds '1st edition' to query. For product URLs: only in_stock applies.
    """
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)
    is_product_url = "/product/" in url
    if first_edition and qs.get("q") and not is_product_url:
        qs["q"] = [f"{qs['q'][0]} 1st edition"]
    if in_stock:
        qs[IN_STOCK_PARAM] = [IN_STOCK_VALUE]
    new_query = urllib.parse.urlencode(qs, doseq=True)
    return urllib.parse.urlunparse(parsed._replace(query=new_query))


def append_first_edition_to_url(url: str) -> str:
    """Append '1st edition' to the search query in a TCGplayer URL."""
    return append_params_to_url(url, first_edition=True)


def fetch_ygoprodeck_cards(
    query: str, first_edition: bool = False, in_stock: bool = False
) -> list[dict]:
    """
    Fetch cards from YGOPRODeck API (fuzzy search by name).
    Returns list of dicts with name, set, market_price, low, high, url.
    """
    if not query or not query.strip():
        return []
    try:
        resp = requests.get(
            YGOPRODECK_API,
            params={"fname": query.strip(), "num": 100, "tcgplayer_data": "yes"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        cards_data = data.get("data", data) if isinstance(data, dict) else data
        if not isinstance(cards_data, list):
            return []
        result = []
        for c in cards_data:
            name = c.get("name", "")
            prices = (c.get("card_prices") or [{}])[0] if c.get("card_prices") else {}
            tcg_price_str = prices.get("tcgplayer_price") or "0"
            try:
                market_price = float(tcg_price_str)
            except (ValueError, TypeError):
                market_price = 0
            sets_list = c.get("card_sets") or []
            set_name = sets_list[0].get("set_name", "") if sets_list else ""
            # Prefer direct product URL from set_url (when tcgplayer_data=yes)
            card_url = None
            for s in sets_list:
                product_url = _extract_product_url(s.get("set_url"))
                if product_url:
                    if first_edition and "1st" in (s.get("set_edition") or "").lower():
                        card_url = product_url
                        break
                    if card_url is None:
                        card_url = product_url
            if not card_url:
                search_term = (name + " 1st edition") if first_edition else name
                card_url = f"{TCGPLAYER_SEARCH_BASE}?q={urllib.parse.quote_plus(search_term)}"
            if in_stock:
                card_url = append_params_to_url(card_url, first_edition=False, in_stock=True)
            result.append({
                "name": name,
                "set": set_name,
                "market_price": market_price,
                "low": market_price * 0.8,
                "high": market_price * 1.3,
                "url": card_url,
            })
        return result
    except Exception:
        return []


def filter_by_price(cards: list, min_price: float | None, max_price: float | None) -> list:
    """Filter demo cards by price range."""
    result = cards
    if min_price is not None:
        result = [c for c in result if (c.get("market_price") or 0) >= min_price]
    if max_price is not None:
        result = [c for c in result if (c.get("market_price") or 0) <= max_price]
    return result


def filter_demo_by_name(cards: list, query: str) -> list:
    """Filter demo cards by search query."""
    if not query or not query.strip():
        return cards
    q = query.strip().lower()
    return [c for c in cards if q in (c.get("name") or "").lower() or q in (c.get("set") or "").lower()]


@app.route("/")
def index():
    return render_template("index.html", demo_cards=DEMO_CARDS)


@app.route("/search", methods=["GET"])
def search():
    query = request.args.get("q", "").strip()
    try:
        min_price = float(request.args.get("min_price")) if request.args.get("min_price") else None
    except (TypeError, ValueError):
        min_price = None
    try:
        max_price = float(request.args.get("max_price")) if request.args.get("max_price") else None
    except (TypeError, ValueError):
        max_price = None
    sort = request.args.get("sort", "price_asc")
    first_edition = request.args.get("first_edition") == "on"
    in_stock = request.args.get("in_stock") == "on"

    # Use YGOPRODeck API for live search when user has a query
    if query:
        cards = fetch_ygoprodeck_cards(query, first_edition, in_stock)
        if not cards:
            cards = filter_demo_by_name(list(DEMO_CARDS), query)
    else:
        cards = list(DEMO_CARDS)

    cards = filter_by_price(cards, min_price, max_price)

    # Sort
    if sort == "price_asc":
        cards.sort(key=lambda c: c.get("market_price") or 0)
    elif sort == "price_desc":
        cards.sort(key=lambda c: c.get("market_price") or 0, reverse=True)
    elif sort == "name":
        cards.sort(key=lambda c: (c.get("name") or "").lower())

    # Apply 1st edition and in-stock to card URLs when checked
    if (first_edition or in_stock) and cards:
        cards = [
            {
                **c,
                "url": append_params_to_url(c.get("url", ""), first_edition, in_stock),
            }
            for c in cards
        ]
    tcgplayer_url = get_tcgplayer_search_url(query, first_edition, in_stock) if query else TCGPLAYER_SEARCH_BASE

    return render_template(
        "results.html",
        cards=cards,
        query=query,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
        first_edition=first_edition,
        in_stock=in_stock,
        tcgplayer_url=tcgplayer_url,
        demo_cards=DEMO_CARDS,
        has_filters=bool(query or min_price is not None or max_price is not None),
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
