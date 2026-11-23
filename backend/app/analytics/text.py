"""Rule-based multilingual text analysis (Spanish, Catalan, English).

Works with no AI key: language detection, sentiment, themes, comment categories,
content pillars and gentle detection of distress language.
"""
from __future__ import annotations

import re
from functools import lru_cache

from ..ingest.parsing import norm

# Editable taxonomy: theme -> keywords (accents stripped, lower case, prefix match)
THEMES: dict[str, dict] = {
    "softness": {"label": "Softness and comfort", "kw": ["suav", "comod", "pica", "soft", "comfort", "itch", "carici", "fresc", "dorm", "sleep"]},
    "fit": {"label": "Fit and sizing", "kw": ["talla", "ajust", "grande", "pequen", "resbal", "se mueve", "es mou", "fit", "size", "slip",
                                             "too big", "too small", "talles", "queda", "rellisca"]},
    "design": {"label": "Colour and design range", "kw": ["color", "colour", "estampad", "diseno", "disseny", "print", "gamma", "gama",
                                                         "variedad", "tonos", "elegan", "bonit", "precios", "gorgeous", "beautiful"]},
    "fabric": {"label": "Fabric quality", "kw": ["seda", "silk", "algodon", "cotton", "coto", "bambu", "bamboo", "tela", "tejido",
                                                "fabric", "calidad", "qualitat", "quality", "transpir", "breath"]},
    "shipping": {"label": "Shipping and delivery", "kw": ["envio", "enviament", "shipping", "deliver", "entrega", "paquet", "llego",
                                                         "arrived", "va arribar", "retras", "tard", "late"]},
    "price": {"label": "Price", "kw": ["caro", "car ", "precio", "price", "pricey", "expensive", "barato", "preu"]},
    "packaging": {"label": "Packaging", "kw": ["packaging", "caja", "embolcall", "envoltorio", "nota escrita", "handwritten", "box"]},
    "children": {"label": "Children's needs", "kw": ["hija", "hijo", "nina", "nino", "ninos", "filla", "fill", "nens", "daughter",
                                                    "son ", "kid", "child", "toddler", "cole", "school", "infantil", "peques"]},
    "gifting": {"label": "Gifting", "kw": ["regal", "gift", "madre", "amiga", "sister", "hermana", "mare", "present"]},
    "emotional": {"label": "Emotional value", "kw": ["gracias", "gracies", "thank", "confianza", "confianca", "confidence", "yo misma",
                                                    "jo mateixa", "like me", "like myself", "emocion", "llor", "cried", "guapa", "hospital",
                                                    "medical", "reconoc", "autoestima"]},
    "service": {"label": "Customer service", "kw": ["atencion", "atencio", "service", "whatsapp", "ayudaron", "helped", "cercan", "trato"]},
}

POS = ["encant", "precios", "perfect", "suav", "genial", "gracias", "gracies", "love", "beautiful", "gorgeous", "great", "excellent",
       "rapid", "quick", "bonit", "comod", "ideal", "maravill", "feliz", "happy", "recomien", "orgullos", "confianza", "elegan",
       "calidad", "quality", "fresc", "cariño", "carino", "guapa", "excelente", "molt be", "molt bona", "soft", "fits", "magnific",
       "brillant", "fantastic", "best", "mejor", "estupend", "cercana", "warm"]
NEG = ["tard", "retras", "late", "caro", "pricey", "expensive", "limitad", "limited", "pocos", "poques", "pocas", "falt", "echo de menos",
       "trobo a faltar", "wish", "ojala", "resbal", "rellisca", "slip", "grande", "too big", "mal", "bad", "roto", "broken", "decepcion",
       "disappoint", "problema", "problem", "queja", "pica", "calor", "cuesta", "hard to", "no me gusta", "dont like", "worst", "peor",
       "lento", "slow", "stressful", "estres"]
NEGATORS = ["no ", "nada", "gens", "not ", "never", "nunca", "sin "]
DISTRESS = ["no puedo mas", "no puc mes", "muy duro", "momento muy dificil", "me siento sola", "esgotad", "can t cope", "cant cope",
            "hopeless", "sin fuerzas", "quiero rendirme", "give up", "muy sola", "desesper", "no aguanto"]

COMMENT_CATS = {
    "partnership": ["asociacion", "associacio", "association", "colabor", "col labor", "farmac", "pharmac", "hospital", "fundacion",
                    "fundacio", "charity", "partnership", "venta a", "wholesale", "mayorista"],
    "sizing": ["talla", "size", "cabeza pequena", "larger head", "que talla", "quina talla", "anos", "years old", "fit a"],
    "request": ["lo vais a sacar", "teneis", "para cuando", "would love", "feu", "mas colores", "more colours", "more colors",
                "en verde", "in navy", "si us plau", "please make", "ojala", "estampado de flores"],
    "question": ["?", "como", "cuanto", "when", "how", "where", "donde", "quan", "on "],
}

# The brief's categories; each theme belongs to one.
THEME_GROUPS = {"quality": "Product quality", "delivery": "Delivery", "service": "Customer service", "pricing": "Pricing",
                "experience": "User experience", "expectations": "Product expectations", "positive": "Positive product attributes"}
THEME_GROUP_OF = {"fabric": "quality", "softness": "positive", "fit": "expectations", "design": "expectations", "shipping": "delivery",
                  "price": "pricing", "packaging": "experience", "children": "expectations", "gifting": "positive", "emotional": "positive",
                  "service": "service", "website": "experience"}
THEMES["website"] = {"label": "Website and checkout", "kw": ["web", "pagina", "checkout", "pago", "payment", "carrito", "cart", "app ", "login", "website", "online"]}

PILLARS = {
    "mission": ["historia", "story", "comunidad", "community", "normaliz", "juntas", "no estas sola", "donamos", "asociacion", "autoestima",
                "octubrerosa", "cancer", "gracias por", "mensaje de una clienta", "together", "mission"],
    "education": ["consejo", "tips", "tutorial", "como ", "how to", "guia", "guide", "formas de", "te explicamos", "cuidar", "aprende"],
    "behind": ["detras", "behind", "taller", "workshop", "fundadoras", "founders", "preparamos", "un dia en", "proceso"],
    "product": ["nuevo", "new", "coleccion", "collection", "vuelve", "disponible", "turbante", "panuelo", "gorro", "shop", "compra"],
}
PILLAR_LABELS = {"mission": "Mission and community", "product": "Product", "behind": "Behind the scenes", "education": "Education"}


@lru_cache(maxsize=1)
def _detector():
    try:
        from lingua import Language, LanguageDetectorBuilder

        langs = [Language.SPANISH, Language.CATALAN, Language.ENGLISH, Language.FRENCH, Language.PORTUGUESE]
        return LanguageDetectorBuilder.from_languages(*langs).with_preloaded_language_models().build()
    except Exception:  # noqa: BLE001
        return None


_ISO = {"SPANISH": "es", "CATALAN": "ca", "ENGLISH": "en", "FRENCH": "fr", "PORTUGUESE": "pt", "ITALIAN": "it", "GERMAN": "de"}
LANG_NAMES = {"es": "Spanish", "ca": "Catalan", "en": "English", "fr": "French", "pt": "Portuguese", "it": "Italian", "de": "German",
              "unknown": "Unknown"}
_LANG_ALIASES = {"castellano": "es", "espanol": "es", "spanish": "es", "es": "es", "catala": "ca", "catalan": "ca", "ca": "ca",
                 "english": "en", "ingles": "en", "en": "en", "angles": "en"}


def language_from_label(v) -> str | None:
    if v is None:
        return None
    return _LANG_ALIASES.get(norm(str(v)))


def detect_language(text: str | None) -> str:
    if not text or len(text.strip()) < 3:
        return "unknown"
    t = text.lower()
    # quick Catalan markers help with short texts
    if re.search(r"\b(molt|gràcies|gracies|m'encanta|meva|perquè|també|amb|és|feu|vosaltres|gens)\b", t):
        return "ca"
    det = _detector()
    if det is None:
        return "unknown"
    lang = det.detect_language_of(text)
    return _ISO.get(lang.name, "unknown") if lang else "unknown"


def _has(t: str, kws: list[str]) -> bool:
    return any(k in t for k in kws)


def sentiment(text: str | None, rating: float | None = None) -> tuple[str, float]:
    """Return (label, score in -1..1). Rating, when present, dominates."""
    if rating is not None and rating == rating:
        r = float(rating)
        if r > 5:  # 0-10 scale
            score = (r - 7) / 3
        else:
            score = (r - 3) / 2
        score = max(-1.0, min(1.0, score))
    else:
        t = " " + norm(text or "") + " "
        pos = sum(1 for k in POS if k in t)
        neg = sum(1 for k in NEG if k in t)
        # "no pica" is positive; negators near positive words flip them
        if re.search(r"\b(no|not|gens|nada)\b \w* ?(pica|itch)", t):
            neg = max(0, neg - 1)
            pos += 1
        score = (pos - neg) / max(1, pos + neg)
    label = "positive" if score > 0.2 else "negative" if score < -0.2 else "neutral"
    return label, round(score, 3)


def themes(text: str | None) -> list[str]:
    t = " " + norm(text or "") + " "
    return [k for k, v in THEMES.items() if _has(t, v["kw"])]


def is_distress(text: str | None) -> bool:
    return _has(norm(text or ""), DISTRESS)


def comment_category(text: str | None) -> str:
    t = " " + norm(text or "") + " "
    raw = text or ""
    for cat in ("partnership", "sizing", "request"):
        if _has(t, COMMENT_CATS[cat]):
            return cat
    if is_distress(text):
        return "sensitive"
    if "?" in raw:
        return "question"
    return "praise" if sentiment(text)[0] == "positive" else "other"


def pillar(caption: str | None) -> str:
    t = " " + norm(caption or "") + " "
    for p in ("mission", "education", "behind", "product"):
        if _has(t, PILLARS[p]):
            return p
    return "product"


def topic_words(texts: list[str], n: int = 12) -> list[tuple[str, int]]:
    """Simple frequent-word discovery for 'other' feedback (no AI)."""
    stop = set("""de la que el en y a los se del las un por con no una su para es al lo como mas pero sus le ya o este si porque esta
    entre cuando muy sin sobre tambien me hasta hay donde quien desde todo nos durante todos uno les ni contra otros ese eso ante ellos
    e esto mi antes algunos que unos yo otro otras otra el tanto esa estos mucho quienes nada muchos cual poco ella estar estas algunas
    algo nosotros the and to of a in is it for on with i my this was that so be at you are very me but not have he she they we our an
    els les amb per dels una al molt em és i ho lo va""".split())
    counts: dict[str, int] = {}
    for tx in texts:
        for w in re.findall(r"[a-záéíóúñçàèòïü]{4,}", (tx or "").lower()):
            if w not in stop:
                counts[w] = counts.get(w, 0) + 1
    return sorted(counts.items(), key=lambda kv: -kv[1])[:n]
