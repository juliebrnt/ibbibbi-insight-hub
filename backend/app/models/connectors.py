"""Live connectors that work without platform app review.

- Shopify: a *custom app* created by the store owner in their own Shopify admin gives an Admin API
  access token. No Shopify review is needed for a single store. We read orders through the GraphQL
  Admin API and use the customer id (not the email) for repeat-customer counts.
- Judge.me: the store's *private API key* (Judge.me admin, Settings, Integrations, View API token).
  We read reviews (GET /reviews) and can publish public replies (POST /replies).

Fetched records are turned into the same tables an export would give and go through the normal
pipeline (privacy, validation, deduplication, provenance). Tokens are encrypted at rest with a local
key, never returned to the browser and never logged.
"""
from __future__ import annotations

import io
import json
from datetime import datetime

import httpx
import pandas as pd
from cryptography.fernet import Fernet, InvalidToken

from .. import db
from ..config import DATA_DIR

SHOPIFY_API_VERSION = "2025-01"
JUDGEME_BASE = "https://api.judge.me/api/v1"
TIMEOUT = 30.0


class ConnectorError(Exception):
    """A friendly message explaining why a connection or sync failed."""


# --------------------------------------------------------------------------------------
# Encrypted credential store
# --------------------------------------------------------------------------------------
def _fernet() -> Fernet:
    from ..config import CREDENTIALS_KEY

    if CREDENTIALS_KEY:
        return Fernet(CREDENTIALS_KEY.encode())
    path = DATA_DIR / ".credentials_key"
    if not path.exists():
        path.write_bytes(Fernet.generate_key())
        path.chmod(0o600)
    return Fernet(path.read_bytes())


def save_credentials(ws: str, key: str, creds: dict) -> None:
    blob = _fernet().encrypt(json.dumps(creds).encode()).decode()
    meta = get_meta(ws, key) or {}
    meta.update({"authorised_at": datetime.now().isoformat(timespec="seconds"), "status": "connected", "error": None,
                 "shop": creds.get("shop_domain")})
    db.set_setting(f"cred:{ws}:{key}", blob)
    db.set_setting(f"conn:{ws}:{key}", meta)


def load_credentials(ws: str, key: str) -> dict | None:
    blob = db.get_setting(f"cred:{ws}:{key}", None)
    if not blob:
        return None
    try:
        return json.loads(_fernet().decrypt(blob.encode()))
    except InvalidToken:
        return None


def get_meta(ws: str, key: str) -> dict | None:
    return db.get_setting(f"conn:{ws}:{key}", None)


def set_meta(ws: str, key: str, **kw) -> None:
    meta = get_meta(ws, key) or {}
    meta.update(kw)
    db.set_setting(f"conn:{ws}:{key}", meta)


def forget(ws: str, key: str) -> None:
    db.execute("DELETE FROM settings WHERE key IN (?, ?)", [f"cred:{ws}:{key}", f"conn:{ws}:{key}"])


def _shop(domain: str) -> str:
    d = (domain or "").strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
    if not d:
        raise ConnectorError("Please enter your shop address, for example your-store.myshopify.com.")
    if "." not in d:
        d += ".myshopify.com"
    return d


# --------------------------------------------------------------------------------------
# Shopify (GraphQL Admin API, custom app token)
# --------------------------------------------------------------------------------------
ORDERS_QUERY = """
query Orders($cursor: String, $q: String) {
  orders(first: 100, after: $cursor, query: $q, sortKey: CREATED_AT) {
    pageInfo { hasNextPage endCursor }
    edges { node {
      id name createdAt displayFinancialStatus sourceName note
      customAttributes { key value }
      customer { id }
      currentTotalPriceSet { shopMoney { amount currencyCode } }
      subtotalPriceSet { shopMoney { amount } }
      totalShippingPriceSet { shopMoney { amount } }
      totalDiscountsSet { shopMoney { amount } }
      discountCodes
      shippingAddress { city countryCodeV2 }
      lineItems(first: 50) { edges { node { name quantity sku originalUnitPriceSet { shopMoney { amount } } } } }
    } }
  }
}"""


class Shopify:
    key = "shopify"

    def __init__(self, creds: dict, client: httpx.Client | None = None):
        self.shop = _shop(creds.get("shop_domain", ""))
        self.token = creds.get("token", "").strip()
        self.client = client or httpx.Client(timeout=TIMEOUT)

    def _post(self, query: str, variables: dict) -> dict:
        try:
            r = self.client.post(f"https://{self.shop}/admin/api/{SHOPIFY_API_VERSION}/graphql.json", json={"query": query, "variables": variables},
                                 headers={"X-Shopify-Access-Token": self.token, "Content-Type": "application/json"})
        except httpx.HTTPError as e:
            raise ConnectorError(f"We could not reach {self.shop}. Check the shop address and your internet connection.") from e
        if r.status_code in (401, 403):
            raise ConnectorError("Shopify did not accept this access token. Check it was copied fully and that the app has read_orders access.")
        if r.status_code == 404:
            raise ConnectorError(f"No Shopify store found at {self.shop}.")
        if r.status_code >= 400:
            raise ConnectorError(f"Shopify returned an error ({r.status_code}). Try again in a few minutes.")
        body = r.json()
        if body.get("errors"):
            msg = str(body["errors"])[:200]
            if "access" in msg.lower() or "scope" in msg.lower():
                raise ConnectorError("This access token is missing a permission. In your Shopify custom app, enable read_orders and read_products.")
            raise ConnectorError(f"Shopify reported a problem: {msg}")
        return body["data"]

    def test(self) -> str:
        data = self._post("{ shop { name } }", {})
        return data["shop"]["name"]

    def fetch(self, since: str | None = None, max_pages: int = 50) -> list[tuple[str, bytes]]:
        rows, cursor = [], None
        q = f"created_at:>={since}" if since else None
        for _ in range(max_pages):
            data = self._post(ORDERS_QUERY, {"cursor": cursor, "q": q})["orders"]
            for e in data["edges"]:
                o = e["node"]
                attrs = "; ".join(f"{a['key']}: {a['value']}" for a in o.get("customAttributes") or [])
                money = lambda k: ((o.get(k) or {}).get("shopMoney") or {}).get("amount")  # noqa: E731
                items = [i["node"] for i in (o.get("lineItems") or {}).get("edges", [])] or [{}]
                for n, it in enumerate(items):
                    first = n == 0
                    rows.append({
                        "Name": o["name"], "Customer ID": (o.get("customer") or {}).get("id"), "Created at": o["createdAt"],
                        "Financial Status": o.get("displayFinancialStatus") if first else None,
                        "Currency": ((o.get("currentTotalPriceSet") or {}).get("shopMoney") or {}).get("currencyCode") if first else None,
                        "Subtotal": money("subtotalPriceSet") if first else None, "Shipping": money("totalShippingPriceSet") if first else None,
                        "Total": money("currentTotalPriceSet") if first else None, "Discount Amount": money("totalDiscountsSet") if first else None,
                        "Discount Code": ", ".join(o.get("discountCodes") or []) if first else None,
                        "Lineitem name": it.get("name"), "Lineitem quantity": it.get("quantity"), "Lineitem sku": it.get("sku"),
                        "Lineitem price": ((it.get("originalUnitPriceSet") or {}).get("shopMoney") or {}).get("amount"),
                        "Notes": o.get("note") if first else None, "Note Attributes": attrs if first else None,
                        "Source": o.get("sourceName") if first else None,
                        "Billing City": ((o.get("shippingAddress") or {}).get("city")) if first else None,
                        "Billing Country": ((o.get("shippingAddress") or {}).get("countryCodeV2")) if first else None,
                    })
            if not data["pageInfo"]["hasNextPage"]:
                break
            cursor = data["pageInfo"]["endCursor"]
        if not rows:
            return []
        return [("shopify_orders_live.csv", pd.DataFrame(rows).to_csv(index=False).encode())]


# --------------------------------------------------------------------------------------
# Judge.me (REST, private API key)
# --------------------------------------------------------------------------------------
class Judgeme:
    key = "judgeme"

    def __init__(self, creds: dict, client: httpx.Client | None = None):
        self.shop = _shop(creds.get("shop_domain", ""))
        self.token = creds.get("token", "").strip()
        self.client = client or httpx.Client(timeout=TIMEOUT)

    def _req(self, method: str, path: str, **kw) -> httpx.Response:
        params = {**kw.pop("params", {}), "shop_domain": self.shop}
        try:
            r = self.client.request(method, f"{JUDGEME_BASE}{path}", params=params, headers={"X-Api-Token": self.token}, **kw)
        except httpx.HTTPError as e:
            raise ConnectorError("We could not reach Judge.me. Check your internet connection and try again.") from e
        if r.status_code in (401, 403):
            raise ConnectorError("Judge.me did not accept this key. Use the private API token (Judge.me, Settings, Integrations) and the shop's myshopify.com address.")
        return r

    def test(self) -> str:
        r = self._req("GET", "/reviews", params={"per_page": 1, "page": 1})
        if r.status_code >= 400:
            raise ConnectorError(f"Judge.me returned an error ({r.status_code}).")
        return self.shop

    def fetch(self, since: str | None = None, max_pages: int = 100) -> list[tuple[str, bytes]]:
        rows = []
        for page in range(1, max_pages + 1):
            r = self._req("GET", "/reviews", params={"per_page": 100, "page": page})
            if r.status_code >= 400:
                raise ConnectorError(f"Judge.me returned an error ({r.status_code}) while reading reviews.")
            reviews = r.json().get("reviews") or []
            for rv in reviews:
                if rv.get("hidden"):
                    continue
                rows.append({"review_id": rv.get("id"), "review_date": rv.get("created_at"), "rating": rv.get("rating"),
                             "title": rv.get("title"), "body": rv.get("body"), "product_title": rv.get("product_title"),
                             "reviewer_email": (rv.get("reviewer") or {}).get("email"), "reviewer_name": (rv.get("reviewer") or {}).get("name"),
                             "source": rv.get("source"), "verified": rv.get("verified"), "platform": "Judge.me"})
            if len(reviews) < 100:
                break
        if not rows:
            return []
        return [("judgeme_reviews_live.csv", pd.DataFrame(rows).to_csv(index=False).encode())]

    def reply(self, review_id: int, content: str, email_reviewer: bool = False) -> None:
        r = self._req("POST", "/replies", json={"review_id": int(review_id), "send_reply_email": email_reviewer, "reply": {"content": content}})
        if r.status_code == 422:
            raise ConnectorError(f"Judge.me could not publish the reply: {r.json().get('error', 'unknown reason')}.")
        if r.status_code >= 400:
            raise ConnectorError(f"Judge.me returned an error ({r.status_code}) while publishing the reply.")


LIVE = {"shopify": Shopify, "judgeme": Judgeme}

GUIDES = {
    "shopify": ["In Shopify admin, open Settings, then Apps and sales channels, then Develop apps (allow custom app development if asked).",
                "Create an app called 'Insight Hub'. Under Configuration, Admin API scopes, tick read_orders and read_products. Save.",
                "Click Install app, then reveal the Admin API access token once and copy it.",
                "Paste the token and your shop address (your-store.myshopify.com) here. No Shopify review is needed for your own store."],
    "judgeme": ["In Shopify admin, open the Judge.me app.", "Go to Settings, then Integrations, then Developers (or 'View API token').",
                "Copy the private API token.", "Paste it with your shop address (your-store.myshopify.com) here."],
}


def connector(ws: str, key: str, client: httpx.Client | None = None):
    creds = load_credentials(ws, key)
    if not creds:
        return None
    return LIVE[key](creds, client)


def connect(ws: str, key: str, shop_domain: str, token: str, client: httpx.Client | None = None) -> dict:
    if key not in LIVE:
        raise ConnectorError("This platform cannot be connected directly yet. Upload an export instead.")
    if ws != "mine":
        raise ConnectorError("Connections are only for My data. Switch to My data first.")
    if not token or len(token.strip()) < 10:
        raise ConnectorError("Please paste the full access token.")
    c = LIVE[key]({"shop_domain": shop_domain, "token": token}, client)
    name = c.test()  # raises ConnectorError with a friendly message on failure
    save_credentials(ws, key, {"shop_domain": c.shop, "token": c.token})
    set_meta(ws, key, account=name)
    return {"ok": True, "account": name}


def sync(ws: str, key: str, client: httpx.Client | None = None) -> dict:
    """Fetch from a connected platform and run the records through the normal import pipeline."""
    from ..ingest import pipeline

    c = connector(ws, key, client)
    if not c:
        return {"key": key, "status": "not_connected"}
    try:
        files = c.fetch()
    except ConnectorError as e:
        expired = "did not accept" in str(e)
        set_meta(ws, key, status="expired" if expired else "error", error=str(e), last_attempt=datetime.now().isoformat(timespec="seconds"))
        return {"key": key, "status": "expired" if expired else "error", "message": str(e)}
    imported = 0
    for name, data in files:
        for r in pipeline.auto_import(name, data, ws):
            imported += (r.get("report") or {}).get("imported", 0)
    now = datetime.now().isoformat(timespec="seconds")
    set_meta(ws, key, status="connected", error=None, synced_at=now, last_attempt=now)
    return {"key": key, "status": "ok", "imported": imported,
            "message": f"Fetched the latest data: {imported:,} new records." if imported else "Up to date: no new records since the last refresh."}


def status() -> list[dict]:  # kept for the Settings page
    return [{"key": k, "name": k.title(), "configured": False} for k in LIVE]


__all__ = ["connect", "sync", "connector", "forget", "get_meta", "ConnectorError", "GUIDES", "LIVE", "io"]
