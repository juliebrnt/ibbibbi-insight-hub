"""Central settings, read from environment (and .env if present)."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
STAGING_DIR = DATA_DIR / "staging"
STAGING_DIR.mkdir(exist_ok=True)
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
DB_PATH = Path(os.getenv("DB_PATH", DATA_DIR / "insight_hub.duckdb"))
DEMO_DIR = ROOT / "demo_data"
FRONTEND_DIST = ROOT / "frontend" / "dist"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
AI_MODEL = os.getenv("AI_MODEL", "claude-sonnet-5-5")
APP_PASSWORD = os.getenv("APP_PASSWORD", "").strip()
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))
TIMEZONE = "Europe/Madrid"
CURRENCY = "EUR"


def _salt() -> str:
    """A local salt for hashing emails and phones. Created once, never leaves the machine."""
    path = DATA_DIR / ".salt"
    if not path.exists():
        path.write_text(secrets.token_hex(16))
    return path.read_text().strip()


SALT = os.getenv("HASH_SALT", "") or _salt()
