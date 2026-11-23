"""Connector adapters (stubs). Live data later is a credentials change, not a rebuild.

Each connector returns raw tables in the same shape as an uploaded export, so they
flow through the identical pipeline (classification, privacy, validation, provenance).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Connector:
    key: str
    name: str
    produces: list[str]
    env: list[str]
    docs: str

    def configured(self) -> bool:
        import os

        return all(os.getenv(e) for e in self.env)

    def fetch(self, since: str | None = None):  # pragma: no cover - stub
        raise NotImplementedError(f"{self.name} connector is a stub. Set {', '.join(self.env)} and implement fetch().")


CONNECTORS = [
    Connector("shopify", "Shopify", ["orders", "products", "customers"], ["SHOPIFY_STORE", "SHOPIFY_ADMIN_TOKEN"],
              "Admin API: orders.json, products.json, customers.json"),
    Connector("ga4", "Google Analytics 4", ["web_sessions"], ["GA4_PROPERTY_ID", "GOOGLE_APPLICATION_CREDENTIALS"],
              "Data API runReport: date, sessionSourceMedium, landingPage, deviceCategory"),
    Connector("instagram", "Instagram Graph API", ["social_posts", "social_comments"], ["IG_BUSINESS_ID", "META_ACCESS_TOKEN"],
              "/{ig-user-id}/media with insights; /{media-id}/comments"),
    Connector("tiktok", "TikTok Business API", ["social_posts"], ["TIKTOK_BUSINESS_ID", "TIKTOK_ACCESS_TOKEN"], "video/list with metrics"),
    Connector("klaviyo", "Klaviyo", ["email_campaigns"], ["KLAVIYO_PRIVATE_KEY"], "Campaign values reports"),
]


def status() -> list[dict]:
    return [{"key": c.key, "name": c.name, "produces": c.produces, "configured": c.configured(), "env": c.env, "docs": c.docs}
            for c in CONNECTORS]
