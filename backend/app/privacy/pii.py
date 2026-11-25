"""Personal-data detection, minimisation and scrubbing.

Defaults: names and street addresses are dropped, emails and phones are hashed
with a local salt into stable customer ids, and free text is scrubbed of emails,
phone numbers, handles and links before it is ever sent to an AI service.
"""
from __future__ import annotations

import hashlib
import re

import pandas as pd

from ..config import SALT
from ..ingest.parsing import norm

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?<!\w)(\+?\d[\d\s().-]{7,}\d)(?!\w)")
HANDLE_RE = re.compile(r"(?<![\w.])@[A-Za-z0-9_.]{2,30}")
URL_RE = re.compile(r"https?://\S+|www\.\S+")

PII_HEADERS = {
    "name": ["name", "nombre", "first name", "last name", "apellido", "apellidos", "billing name", "shipping name", "reviewer name",
             "nombre de facturacion", "full name", "customer name", "nom", "cognoms", "author", "autor"],
    "email": ["email", "correo", "e mail", "correo electronico", "reviewer email", "correu"],
    "phone": ["phone", "telefono", "movil", "mobile", "billing phone", "telefono de facturacion", "whatsapp number"],
    "address": ["street", "address", "calle", "direccion", "billing street", "calle de facturacion", "zip", "postal", "codigo postal",
                "address1", "address2", "billing zip", "codigo postal de facturacion", "shipping street"],
    "username": ["username", "user name", "usuario", "handle de usuario", "from username", "instagram handle"],
}
DEFAULT_ACTION = {"name": "drop", "address": "drop", "email": "hash", "phone": "drop", "username": "hash"}
EXPLAIN = {
    "drop": "Not stored. We do not need it to find patterns.",
    "hash": "Replaced by an anonymous id so we can count repeat customers without storing the real value.",
    "keep": "Stored as is on this computer. Only choose this if you truly need it.",
}
# a column simply called "Cliente" or "Customer" holds names in hand-kept files (exact header only)
CUSTOMER_NAME_HEADERS = {"cliente", "clienta", "clientes", "client", "clients", "customer", "comprador", "compradora", "buyer",
                         "nombre cliente", "nombre del cliente", "nom client", "nom del client", "customer full name"}


def sample_is_ids(s: pd.Series) -> bool:
    """True when a customer column holds ids or emails rather than names."""
    v = s.dropna().astype(str).head(200)
    return bool(len(v)) and (v.str.contains(EMAIL_RE).mean() > 0.5 or v.str.fullmatch(r"[A-Za-z_-]{0,4}\d+").mean() > 0.5)


# columns that are product or order names, not people
NOT_PII = {"nombre del articulo", "lineitem name", "product name", "nombre", "name"}


def detect(df: pd.DataFrame, mapping: dict[str, dict] | None = None) -> list[dict]:
    """Return a list of personal-data columns with a recommended action."""
    mapped = {v["column"]: k for k, v in (mapping or {}).items()}
    found = []
    for col in df.columns:
        n = norm(col)
        canonical = mapped.get(col)
        kind = None
        if n in CUSTOMER_NAME_HEADERS and canonical not in {"customer_email"} and not sample_is_ids(df[col]):
            kind = "name"  # "Cliente: Laura Pérez" is a person's name, even when it was matched as the customer column
        elif canonical in {"customer_email"}:
            kind = "email"
        elif canonical in {"username"}:
            kind = "username"
        elif canonical in {"first_name", "last_name", "reviewer_name"}:
            kind = "name"
        elif canonical is not None and canonical not in {"first_name", "last_name"}:
            continue
        else:
            for k, heads in PII_HEADERS.items():
                if any(n == h or (len(h) > 4 and h in n) for h in heads):
                    if n in NOT_PII and canonical:
                        continue
                    kind = k
                    break
        sample = df[col].dropna().astype(str).head(200)
        if not kind and len(sample):
            if sample.str.contains(EMAIL_RE).mean() > 0.5:
                kind = "email"
            elif (sample.str.fullmatch(r"\+?[\d\s().-]{9,}") & ~sample.str.match(r"^\d{4}-\d{2}-\d{2}|^\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}")).mean() > 0.6:
                kind = "phone"
        if kind:
            found.append({"column": col, "kind": kind, "action": DEFAULT_ACTION[kind], "explain": EXPLAIN[DEFAULT_ACTION[kind]],
                          "example": mask_example(sample.iloc[0] if len(sample) else "")})
    return found


def mask_example(v: str) -> str:
    v = str(v)
    if len(v) <= 3:
        return "•••"
    return v[:2] + "•" * min(8, len(v) - 3) + v[-1]


def hash_value(v) -> str | None:
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == "":
        return None
    return "c_" + hashlib.sha256((SALT + str(v).strip().lower()).encode()).hexdigest()[:12]


def apply(df: pd.DataFrame, decisions: list[dict]) -> pd.DataFrame:
    out = df.copy()
    for d in decisions:
        col = d["column"]
        if col not in out.columns:
            continue
        if d["action"] == "drop":
            out = out.drop(columns=[col])
        elif d["action"] == "hash":
            out[col] = out[col].map(hash_value)
    return out


def scrub(text: str | None) -> str | None:
    """Remove emails, phone numbers, handles and links from free text."""
    if text is None:
        return None
    t = EMAIL_RE.sub("[email]", str(text))
    t = URL_RE.sub("[link]", t)
    t = HANDLE_RE.sub("[handle]", t)
    t = PHONE_RE.sub("[phone]", t)
    return t


def scrub_storage(text: str | None) -> str | None:
    """Lighter scrub applied before storing feedback: emails and phone numbers only."""
    if text is None:
        return None
    return PHONE_RE.sub("[phone]", EMAIL_RE.sub("[email]", str(text)))
