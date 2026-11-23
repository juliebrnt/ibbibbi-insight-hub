"""Consolidated customer voice: every review, survey answer, message and social comment in one filterable list,
with honest reply options and editable reply drafts."""
from __future__ import annotations

from .. import db
from .text import THEMES, comment_category, themes as theme_of

# Where a reply can be written. 'api' = possible once the platform is connected (not yet), so today all link out.
REPLY = {
    "review": {"integration": "judgeme", "how": "Reply in Judge.me. Direct replies from here will work once Judge.me is connected (coming soon).",
               "url": "https://judge.me/admin"},
    "comment": {"integration": "instagram", "how": "Reply on Instagram. Direct replies from here need the Instagram connection (coming soon).",
                "url": "https://business.facebook.com/latest/inbox"},
    "survey": {"integration": "surveys", "how": "Survey answers are anonymous, so there is no one to reply to. Use what they say in your plan.", "url": None},
    "message": {"integration": "messages", "how": "Reply in the app the message came from (WhatsApp, email or Instagram). Contact details are not stored here.",
                "url": None},
}


def items(ws: str, source: str | None = None, rating: str | None = None, sentiment: str | None = None, theme: str | None = None,
          date_from: str | None = None, date_to: str | None = None, q: str | None = None, limit: int = 60) -> dict:
    base = """
        SELECT _key AS id, date, kind, source, text, rating, nps, product, language, sentiment, themes, distress, consent_quote, NULL AS replied,
               platform, external_id, reply_status, reply_text
        FROM feedback WHERE ws = ? AND text IS NOT NULL AND length(text) > 2
        UNION ALL
        SELECT _key, date, 'comment', platform || ' comment', text, NULL, NULL, NULL, language, sentiment, NULL, distress, FALSE, replied,
               platform, NULL, NULL, NULL
        FROM social_comments WHERE ws = ?"""
    where, args = [], [ws, ws]
    if source:
        where.append("source = ?"); args.append(source)
    if sentiment:
        where.append("sentiment = ?"); args.append(sentiment)
    if rating == "low":
        where.append("rating <= 3")
    elif rating == "high":
        where.append("rating >= 4")
    elif rating in {"1", "2", "3", "4", "5"}:
        where.append("rating = ?"); args.append(int(rating))
    if date_from:
        where.append("date >= ?"); args.append(date_from)
    if date_to:
        where.append("date <= ?"); args.append(date_to)
    if q:
        where.append("text ILIKE ?"); args.append(f"%{q}%")
    w = (" WHERE " + " AND ".join(where)) if where else ""
    rows = db.rows(f"SELECT * FROM ({base}) {w} ORDER BY date DESC NULLS LAST LIMIT 2000", args)
    for r in rows:
        if r["kind"] == "comment":
            r["themes"] = ",".join(theme_of(r["text"]))
            r["category"] = comment_category(r["text"])
    if theme:
        rows = [r for r in rows if theme in (r["themes"] or "").split(",")]
    total = len(rows)
    sources = db.rows(f"SELECT source, count(*) n FROM ({base}) GROUP BY 1 ORDER BY n DESC", [ws, ws])
    from ..models import connectors

    judgeme_live = ws == "mine" and connectors.load_credentials(ws, "judgeme") is not None
    out = []
    for r in rows[:limit]:
        info = REPLY.get(r["kind"], REPLY["message"])
        direct = bool(judgeme_live and r["kind"] == "review" and r.get("external_id") and (r.get("platform") or "").startswith("Judge"))
        how = "Your reply is published on the review in Judge.me and shown on your store." if direct else info["how"]
        out.append({**r, "theme_labels": [THEMES[t]["label"] for t in (r["themes"] or "").split(",") if t in THEMES],
                    "reply": {"direct": direct, "how": how, "url": info["url"], "possible": r["kind"] in ("review", "comment"),
                              "status": r.get("reply_status"), "text": r.get("reply_text")}})
    return {"items": out, "total": total, "sources": sources, "themes": [{"key": k, "label": v["label"]} for k, v in THEMES.items()]}


def publish_reply(ws: str, item_id: str, text: str, client=None) -> dict:
    """Publish a reply through the platform's official API. Only works where a live connection allows it."""
    from datetime import datetime

    from ..models import connectors

    row = db.rows("SELECT platform, external_id, kind FROM feedback WHERE ws = ? AND _key = ?", [ws, item_id])
    if not row:
        return {"ok": False, "error": "We could not find this review."}
    r = row[0]
    if not (r["kind"] == "review" and r["external_id"] and (r["platform"] or "").startswith("Judge")):
        return {"ok": False, "error": "This platform does not allow replies from here yet. Copy your reply and post it on the platform."}
    c = connectors.connector(ws, "judgeme", client)
    if not c:
        return {"ok": False, "error": "Connect Judge.me on the Integrations page to reply from here."}
    if not text or len(text.strip()) < 2:
        return {"ok": False, "error": "Write a reply first."}
    try:
        c.reply(int(r["external_id"]), text.strip())
    except (connectors.ConnectorError, ValueError) as e:
        db.execute("UPDATE feedback SET reply_status = 'failed', reply_text = ? WHERE ws = ? AND _key = ?", [text, ws, item_id])
        return {"ok": False, "error": str(e)}
    db.execute("UPDATE feedback SET reply_status = 'published', reply_text = ?, replied_at = ? WHERE ws = ? AND _key = ?",
               [text, datetime.now(), ws, item_id])
    return {"ok": True, "status": "published"}


# Clearly labelled, made-up reviews that show the structure before any platform is connected.
EXAMPLES = [
    {"platform": "Judge.me", "date": "2026-11-18", "rating": 5, "product": "Turbante Luna bambú - Arena", "language": "es", "sentiment": "positive",
     "text": "Suavísimo y no se mueve en todo el día. Me he vuelto a sentir guapa.", "themes": ["Softness and comfort", "Emotional value"]},
    {"platform": "Judge.me", "date": "2026-11-15", "rating": 2, "product": "Pañuelo Siena seda - Burdeos", "language": "es", "sentiment": "negative",
     "text": "Precioso, pero el envío tardó diez días y lo necesitaba antes del tratamiento.", "themes": ["Shipping and delivery"]},
    {"platform": "Shopify Product Reviews", "date": "2026-11-12", "rating": 4, "product": "Gorrito Estrella bambú - Azul cielo", "language": "es", "sentiment": "positive",
     "text": "A mi hija le encanta. Echo de menos una talla más pequeña para niños de 3 años.", "themes": ["Children's needs", "Fit and sizing"]},
    {"platform": "Amazon", "date": "2026-11-10", "rating": 3, "product": "Gorro Nube bambú - Gris perla", "language": "en", "sentiment": "neutral",
     "text": "Comfortable fabric, but I wish there were more colours to choose from.", "themes": ["Colour and design range", "Softness and comfort"]},
    {"platform": "Google", "date": "2026-11-06", "rating": 5, "product": None, "language": "ca", "sentiment": "positive",
     "text": "Atenció molt propera i el paquet venia amb una nota escrita a mà. Gràcies!", "themes": ["Customer service", "Packaging"]},
    {"platform": "Judge.me", "date": "2026-11-02", "rating": 1, "product": "Turbante Alba algodón - Mostaza", "language": "en", "sentiment": "negative",
     "text": "Too big for me and it slips when I walk. Is there a smaller size?", "themes": ["Fit and sizing"]},
]


def examples() -> dict:
    out = []
    for i, e in enumerate(EXAMPLES):
        out.append({**e, "id": f"example_{i}", "example": True,
                    "reply": {"direct": False, "how": "Example review. Once your store is connected, real reviews appear here with a Reply button.",
                              "url": None, "possible": True}})
    return {"items": out, "note": "These are made-up example reviews to show how reviews from every platform will appear. They are not real and are not counted in any figure."}


DRAFTS = {
    "en": {
        "positive": "Thank you so much for your kind words{about}. It means a lot to us that it feels right for you. Take care, the {brand} team",
        "negative": "Thank you for telling us, and we are sorry{about}. We would like to put this right: could you send us a message so we can help personally? The {brand} team",
        "question": "Thanks for your question! {answer}If you need anything else, just send us a message. The {brand} team",
        "care": "Thank you for sharing this with us. We are thinking of you, and we are here if you would like to talk or need anything. With warmth, the {brand} team",
        "about": {"shipping": " about the delay with your order", "fit": " that the fit was not right", "design": " that you could not find the colour you wanted",
                  "price": " that the price felt high", "softness": " about the comfort and softness", "emotional": "", "fabric": " about the fabric"},
        "answer": {"sizing": "Our size guide on each product page shows the head measurement for every size. ", "request": "We are noting every colour request for the next collection. "},
    },
    "es": {
        "positive": "¡Muchísimas gracias por tus palabras{about}! Nos alegra mucho que te sientas tan bien. Un abrazo, el equipo de {brand}",
        "negative": "Gracias por contárnoslo y lo sentimos mucho{about}. Queremos solucionarlo: ¿nos escribes un mensaje para ayudarte personalmente? El equipo de {brand}",
        "question": "¡Gracias por tu pregunta! {answer}Si necesitas cualquier otra cosa, escríbenos. El equipo de {brand}",
        "care": "Gracias por compartirlo con nosotras. Te tenemos muy presente y aquí estamos si quieres hablar o necesitas algo. Con cariño, el equipo de {brand}",
        "about": {"shipping": " por el retraso de tu pedido", "fit": " porque la talla no te quedó bien", "design": " por no encontrar el color que buscabas",
                  "price": " porque el precio te pareció alto", "softness": " sobre la suavidad", "emotional": "", "fabric": " sobre el tejido"},
        "answer": {"sizing": "En cada producto tienes una guía de tallas con la medida de la cabeza. ", "request": "Apuntamos cada petición de color para la próxima colección. "},
    },
    "ca": {
        "positive": "Moltíssimes gràcies per les teves paraules{about}! Ens alegra molt que et sentis tan bé. Una abraçada, l'equip de {brand}",
        "negative": "Gràcies per explicar-nos-ho i ho sentim molt{about}. Ho volem solucionar: ens escrius un missatge perquè et puguem ajudar? L'equip de {brand}",
        "question": "Gràcies per la teva pregunta! {answer}Si necessites qualsevol altra cosa, escriu-nos. L'equip de {brand}",
        "care": "Gràcies per compartir-ho amb nosaltres. Et tenim molt present i som aquí si vols parlar o necessites res. Amb afecte, l'equip de {brand}",
        "about": {"shipping": " pel retard de la comanda", "fit": " perquè la talla no et va quedar bé", "design": " per no trobar el color que buscaves",
                  "price": " perquè el preu et va semblar alt", "softness": "", "emotional": "", "fabric": ""},
        "answer": {"sizing": "A cada producte tens una guia de talles. ", "request": "Apuntem cada petició de color per a la propera col·lecció. "},
    },
}


def draft(text: str, sentiment: str | None, themes: list[str] | None, language: str | None, distress: bool = False,
          brand: str | None = None, ws: str = "demo") -> dict:
    """A starting point for a reply. The user always edits and approves it; nothing is sent from here."""
    from .. import profile as prof

    brand = brand or prof.get(ws)["name"]
    lang = language if language in DRAFTS else "en"
    t = DRAFTS[lang]
    th = themes or theme_of(text)
    cat = comment_category(text)
    if distress:
        kind = "care"
    elif cat in ("sizing", "request", "question") and "?" in (text or ""):
        kind = "question"
    elif sentiment == "negative":
        kind = "negative"
    else:
        kind = "positive"
    about = next((t["about"][x] for x in th if x in t["about"]), "")
    answer = t["answer"].get(cat, "")
    body = t[kind].format(about=about, brand=brand, answer=answer)
    from ..ai import client as ai

    ai_used = False
    if ai.enabled() and kind != "care":
        from ..privacy.pii import scrub

        better = ai.complete("You draft short, warm replies from a small brand to its customers. Same language as the customer. "
                             "Never promise refunds, discounts or medical advice. Never use em dashes. Under 60 words.",
                             f"Customer wrote: {scrub(text)}\nStarting draft: {body}\nImprove the draft. Reply with the draft only.", max_tokens=300)
        if better and "—" not in better:
            body, ai_used = better.strip(), True
    return {"draft": body, "kind": kind, "language": lang, "ai_written": ai_used}
