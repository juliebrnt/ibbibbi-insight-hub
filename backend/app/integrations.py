"""Integrations registry: what each platform offers, how it authenticates, and its honest status.

No live API connection is implemented yet (each needs a registered developer app, platform
approval and a hosted backend to keep tokens safe). So live connections always show as
"Coming soon". Data that arrived through file uploads is shown as such, with its real sync time.
Nothing here ever reports a connection that does not exist.
"""
from __future__ import annotations

from datetime import datetime

from . import db
from .models import connectors

CATEGORIES = [
    {"key": "sales", "label": "E-commerce and sales"},
    {"key": "email", "label": "Email marketing and CRM"},
    {"key": "social", "label": "Social media"},
    {"key": "web", "label": "Website and digital performance"},
    {"key": "voice", "label": "Reviews and customer feedback"},
    {"key": "other", "label": "Additional business data"},
]


def I(key, name, category, icon, *, account, auth, permissions, data, limits, approval, upload=None, matches=None,
      reply=None, admin_url=None, docs=None):
    return {"key": key, "name": name, "category": category, "icon": icon, "account": account, "auth": auth,
            "permissions": permissions, "data": data, "limits": limits, "approval": approval, "upload": upload,
            "matches": matches or {}, "reply": reply, "admin_url": admin_url, "docs": docs}


REGISTRY = [
    I("shopify", "Shopify", "sales", "siShopify",
      account="Shopify store owner or staff with app permissions",
      auth="OAuth through a Shopify app installed on the store (never a password)",
      permissions=["read_orders", "read_products", "read_customers (optional, emails are anonymised on arrival)"],
      data=["Orders and line items", "Products, prices and stock", "Customers (anonymised)", "Discount codes and sales channel"],
      limits="Orders older than 60 days need the read_all_orders scope, which Shopify must approve. API rate limits apply.",
      approval="Create a Shopify Partner app. Public apps go through Shopify app review; a custom app for one store does not.",
      upload="Orders, Products or Customers export (Shopify admin, Export, CSV)",
      matches={"types": ["orders", "products", "customers"]}, admin_url="https://admin.shopify.com",
      docs="https://shopify.dev/docs/apps/auth"),
    I("amazon", "Amazon Seller Central", "sales", "siAmazon",
      account="Professional seller account",
      auth="Selling Partner API authorisation (Login with Amazon OAuth) plus AWS request signing",
      permissions=["Orders", "Catalogue items", "Sales and traffic reports", "Product reviews are not available through the API"],
      data=["Marketplace orders", "Product performance", "Sales and traffic by product"],
      limits="Personal buyer data needs extra Amazon approval and is restricted. Reports arrive with a delay of up to 24 to 72 hours.",
      approval="Register as an SP-API developer and complete Amazon's data protection review.",
      upload="Business Reports or Order report (Seller Central, Reports, CSV)",
      matches={"labels": ["Amazon"]}, admin_url="https://sellercentral.amazon.es", docs="https://developer-docs.amazon.com/sp-api/"),
    I("woocommerce", "WooCommerce", "sales", "siWoocommerce",
      account="WordPress administrator", auth="WooCommerce REST API keys created by the store owner, stored only on the server",
      permissions=["Read orders", "Read products"], data=["Orders", "Products", "Customers (anonymised)"],
      limits="The site must be reachable over HTTPS.", approval="No platform approval needed.",
      upload="Orders export (WooCommerce, Analytics, Download CSV)", matches={"labels": ["WooCommerce"]}),
    I("etsy", "Etsy", "sales", "siEtsy", account="Etsy shop owner", auth="OAuth 2.0 with PKCE",
      permissions=["transactions_r", "listings_r"], data=["Orders", "Listings", "Shop reviews"],
      limits="Some buyer information is not shared with third-party apps.", approval="Etsy must approve the app before production use.",
      upload="Orders CSV (Shop Manager, Settings, Options, Download data)", matches={"labels": ["Etsy"]}),

    I("klaviyo", "Klaviyo", "email", None,
      account="Klaviyo account owner or admin",
      auth="OAuth for Klaviyo apps, or a private API key created by the owner and kept only on the server",
      permissions=["campaigns:read", "metrics:read", "lists:read"],
      data=["Campaigns, recipients, opens and clicks", "Revenue attributed to email", "List growth"],
      limits="Attribution follows Klaviyo's own attribution window.", approval="Public OAuth apps need Klaviyo app review.",
      upload="Campaigns export (Analytics, Campaigns, Export CSV)", matches={"types": ["email_campaigns"]},
      docs="https://developers.klaviyo.com/en/docs/set_up_oauth"),
    I("mailchimp", "Mailchimp", "email", "siMailchimp", account="Mailchimp account owner", auth="OAuth 2.0",
      permissions=["Read campaigns and reports"], data=["Campaigns", "Opens and clicks", "Audience growth"],
      limits="Revenue only if Mailchimp e-commerce tracking is set up.", approval="Register an app in Mailchimp.",
      upload="Campaign report export (Reports, Download CSV)", matches={"labels": ["Mailchimp"]}),
    I("hubspot", "HubSpot", "email", "siHubspot", account="HubSpot super admin", auth="OAuth 2.0 (public app) or private app token on the server",
      permissions=["crm.objects.contacts.read", "marketing email read"], data=["Contacts (anonymised)", "Email performance", "Deals"],
      limits="Available data depends on the HubSpot subscription tier.", approval="Marketplace listing needs HubSpot review.",
      upload="Any HubSpot report exported as CSV", matches={"labels": ["HubSpot"]}),

    I("instagram", "Instagram", "social", "siInstagram",
      account="Instagram Professional account (Business or Creator) linked to a Facebook Page",
      auth="Meta Login (OAuth) through a Meta developer app",
      permissions=["instagram_basic", "instagram_manage_insights", "instagram_manage_comments (needed to read and reply to comments)", "pages_show_list"],
      data=["Posts and Reels with reach, likes, comments, saves, shares and views", "Comments on your posts", "Follower count"],
      limits="Insights are kept for a limited time (about two years). Story insights expire after 24 hours. Personal accounts are not supported.",
      approval="Meta App Review and Business Verification are required before other businesses can connect.",
      upload="Content export (Meta Business Suite, Insights, Content, Export) or comments export",
      matches={"labels": ["Instagram", "Instagram comments"]}, reply="api_possible", admin_url="https://business.facebook.com",
      docs="https://developers.facebook.com/docs/instagram-platform"),
    I("tiktok", "TikTok", "social", "siTiktok",
      account="TikTok Business or Creator account",
      auth="TikTok Login Kit (OAuth) for the Display/Business API",
      permissions=["user.info.basic", "video.list", "Business API insights scopes"],
      data=["Videos with views, likes, comments and shares", "Follower count", "Watch time where the API provides it"],
      limits="Metrics available differ between the Display API and the Business API. Comment reading needs extra scopes.",
      approval="TikTok must approve the app and each scope.", upload="Content analytics export (TikTok Studio, Analytics, Download data)",
      matches={"labels": ["TikTok"]}, admin_url="https://www.tiktok.com/tiktokstudio", docs="https://developers.tiktok.com/"),
    I("linkedin", "LinkedIn", "social", "siLinkedin",
      account="Admin of a LinkedIn Company Page",
      auth="LinkedIn OAuth 2.0 through the Community Management API",
      permissions=["r_organization_social", "rw_organization_admin (page statistics)"],
      data=["Page posts with impressions, reactions, comments and shares", "Follower growth"],
      limits="Only company pages, not personal profiles.",
      approval="Access to the Community Management API requires LinkedIn approval.", upload="Page analytics export (Page, Analytics, Export)",
      matches={"labels": ["LinkedIn"]}, admin_url="https://www.linkedin.com/company/", docs="https://learn.microsoft.com/linkedin/marketing/"),
    I("facebook", "Facebook Page", "social", "siFacebook", account="Facebook Page admin", auth="Meta Login (OAuth)",
      permissions=["pages_read_engagement", "read_insights"], data=["Page posts and engagement", "Comments"],
      limits="Some page metrics were retired by Meta; only available metrics are shown.", approval="Meta App Review.",
      upload="Content export from Meta Business Suite", matches={"labels": ["Facebook"]}),

    I("ga4", "Google Analytics 4", "web", "siGoogleanalytics",
      account="Viewer access to the GA4 property", auth="Google OAuth (Google Analytics Data API)",
      permissions=["analytics.readonly"], data=["Sessions and users by day", "Traffic sources", "Landing pages", "Devices", "Key events and revenue"],
      limits="Thresholding may hide small numbers. Data can take up to 48 hours to finalise.",
      approval="Google OAuth verification for the read-only analytics scope.", upload="Traffic acquisition report (Reports, Share, Download CSV)",
      matches={"types": ["web_sessions"]}, docs="https://developers.google.com/analytics/devguides/reporting/data/v1"),
    I("search_console", "Google Search Console", "web", "siGooglesearchconsole",
      account="Verified owner or user of the site property", auth="Google OAuth (Search Console API)",
      permissions=["webmasters.readonly"], data=["Search queries", "Clicks, impressions and position", "Top pages"],
      limits="Data covers the last 16 months; very rare queries are hidden for privacy.", approval="Google OAuth verification.",
      upload="Performance report export (Search results, Export)", matches={"labels": ["Search Console"]}),

    I("judgeme", "Judge.me reviews", "voice", None,
      account="Shopify store with Judge.me installed", auth="Judge.me API token created in the Judge.me dashboard, stored on the server",
      permissions=["Read reviews", "Reply to reviews (Judge.me paid plan)"], data=["Product reviews with rating, text and date"],
      limits="Replying through the API depends on the Judge.me plan.", approval="No platform review; the store owner creates the token.",
      upload="Reviews export (Judge.me, Manage reviews, Export)", matches={"types": ["reviews"]}, reply="api_possible",
      admin_url="https://judge.me/admin"),
    I("google_reviews", "Google Business Profile", "voice", None,
      account="Owner or manager of the Business Profile", auth="Google OAuth (Business Profile API)",
      permissions=["business.manage"], data=["Google reviews with rating and text", "Reply to reviews"],
      limits="API access must be requested from Google.", approval="Google must grant Business Profile API access.",
      upload="Reviews copied or exported to a spreadsheet", matches={"labels": ["Google reviews"]}, reply="api_possible",
      admin_url="https://business.google.com"),
    I("trustpilot", "Trustpilot", "voice", "siTrustpilot", account="Trustpilot Business account", auth="Trustpilot API key and OAuth (business plans)",
      permissions=["Read reviews", "Reply to reviews"], data=["Reviews with rating and text"], limits="API access depends on the Trustpilot plan.",
      approval="Request API access from Trustpilot.", upload="Reviews export (Trustpilot Business, Reviews, Export)",
      matches={"labels": ["Trustpilot"]}, reply="api_possible", admin_url="https://businessapp.b2b.trustpilot.com"),
    I("surveys", "Surveys (Google Forms, Typeform)", "voice", "siGoogleforms", account="Owner of the form",
      auth="Google OAuth or Typeform OAuth", permissions=["Read form responses"], data=["Survey answers, NPS scores and comments"],
      limits="Only forms you own.", approval="Google OAuth verification / Typeform app registration.",
      upload="Responses exported to CSV or Excel, or the built-in feedback form in Collect", matches={"types": ["survey_responses"]}),
    I("messages", "Customer messages and notes", "voice", "siWhatsapp", account="None",
      auth="Not applicable: paste or upload messages (WhatsApp Business API is possible later)", permissions=[],
      data=["Free-text customer messages in any language"], limits="Contact details are removed automatically.",
      approval="WhatsApp Business API would need Meta approval.", upload="Paste messages, or upload a text, Word or spreadsheet file",
      matches={"types": ["feedback"]}),

    I("ads", "Advertising (Meta Ads, Google Ads)", "other", "siMeta", account="Ad account access", auth="Meta Login / Google Ads OAuth plus developer token",
      permissions=["ads_read", "Google Ads read-only"], data=["Spend, impressions, clicks and conversions by campaign"],
      limits="Planned for a later version.", approval="Both platforms require app review.", upload=None, matches={"labels": ["Ads"]}),
    I("support", "Customer support (Zendesk, Gorgias)", "other", "siZendesk", account="Support admin", auth="OAuth",
      permissions=["Read tickets"], data=["Support tickets and topics"], limits="Planned for a later version.", approval="App registration.",
      upload="Ticket export as CSV (analysed as customer feedback)", matches={"labels": ["Zendesk"]}),
    I("own_files", "Your own spreadsheets", "other", None, account="None", auth="Not applicable: upload any file",
      permissions=[], data=["Anything with dates and numbers, such as market stall sales"], limits="Shown as trends and text analysis.",
      approval="None.", upload="Any CSV, Excel, PDF, Word or ZIP file", matches={"types": ["flexible"]}),
]
BY_KEY = {i["key"]: i for i in REGISTRY}


def _datasets(ws: str) -> list[dict]:
    return db.rows("""SELECT id, table_type, source_label, file_name, rows_imported, date_min, date_max, created_at
        FROM datasets WHERE ws = ? ORDER BY created_at""", [ws])


def _belongs(integ: dict, ds: dict) -> bool:
    m = integ["matches"]
    if ds["table_type"] in m.get("types", []):
        return True
    return any((ds["source_label"] or "").startswith(lbl) for lbl in m.get("labels", []))


def status(ws: str) -> dict:
    """Integration list with honest statuses for one workspace."""
    datasets = _datasets(ws)
    last_refresh = db.get_setting(f"last_refresh:{ws}", None)
    out = []
    for integ in REGISTRY:
        mine = [d for d in datasets if _belongs(integ, d)]
        if integ["key"] == "messages":
            mine = [d for d in mine if not (d["source_label"] or "").startswith(("Judge", "Google Forms"))]
        rows = sum(d["rows_imported"] or 0 for d in mine)
        dmin = min((d["date_min"] for d in mine if d["date_min"]), default=None)
        dmax = max((d["date_max"] for d in mine if d["date_max"]), default=None)
        last_sync = max((d["created_at"] for d in mine), default=None)
        if mine:
            state = "demo" if ws == "demo" else "uploaded"
        else:
            state = "available" if integ["upload"] else "coming_soon"
        live = "available" if integ["key"] in connectors.LIVE else "coming_soon"
        meta = connectors.get_meta(ws, integ["key"]) if live == "available" else None
        authorised = None
        if meta and connectors.load_credentials(ws, integ["key"]):
            state = meta.get("status", "connected")  # connected | error | expired
            authorised = meta.get("authorised_at")
            last_sync = meta.get("synced_at") or last_sync
        out.append({**{k: v for k, v in integ.items() if k != "matches"},
                    "status": state, "live": live, "datasets": len(mine), "rows": rows, "account": (meta or {}).get("account"),
                    "error": (meta or {}).get("error"), "guide": connectors.GUIDES.get(integ["key"]),
                    "date_min": dmin, "date_max": dmax, "last_synced": last_sync, "last_authorised": authorised})
    return {"categories": CATEGORIES, "integrations": out, "last_refresh": last_refresh,
            "connected": [i["key"] for i in out if i["status"] in ("uploaded", "demo", "connected", "error", "expired")]}


def refresh(ws: str) -> dict:
    """Re-read every connected source. Live API connections: none exist yet, so nothing is fetched from them.
    Uploaded data is re-enriched (product attributes, themes) so every page and recommendation is recalculated."""
    from .ingest.pipeline import enrich

    st = status(ws)
    results = []
    live = 0
    for i in st["integrations"]:
        if i["status"] in ("connected", "error", "expired"):
            live += 1
            r = connectors.sync(ws, i["key"])
            results.append({"key": i["key"], "name": i["name"], "status": r["status"], "message": r.get("message", "")})
    with db.locked() as c:
        try:
            enrich(c, ws)
            ok = True
        except Exception:  # noqa: BLE001
            ok = False
    for i in st["integrations"]:
        if i["status"] in ("uploaded", "demo") and i["key"] not in {r["key"] for r in results}:
            results.append({"key": i["key"], "name": i["name"], "status": "ok" if ok else "error",
                            "message": ("Recalculated from your uploaded files. Upload a newer export to add recent data."
                                        if ws == "mine" else "Demo data is a fixed sample; recalculated.") if ok else
                            "We could not recalculate this source. Your data is unchanged."})
    now = datetime.now().isoformat(timespec="seconds")
    ok = ok and all(r["status"] == "ok" for r in results)
    if any(r["status"] == "ok" for r in results):
        db.set_setting(f"last_refresh:{ws}", now)
    failed = [r["name"] for r in results if r["status"] != "ok"]
    note = (f"Fetched live data from {live} connected account{'s' if live != 1 else ''}." if live else
            "Demo workspace: the sample data was recalculated. Nothing is fetched from real accounts." if ws == "demo" else
            "No accounts are connected live yet, so figures were recalculated from your uploaded files.")
    if failed:
        note += f" Could not refresh: {', '.join(failed)}."
    return {"ok": ok, "refreshed_at": db.get_setting(f"last_refresh:{ws}", None), "results": results, "live_connections": live, "note": note}
