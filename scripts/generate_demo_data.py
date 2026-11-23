"""Generate realistic, interrelated demo files for iBBIBBI Insight Hub.

Everything here is synthetic. Files deliberately mimic messy real-world exports
(mixed Spanish and English headers, day-first dates, comma decimals, comment
lines above headers, multi-sheet workbooks, pasted messages and one unknown file).

Usage: python scripts/generate_demo_data.py [--seed 7] [--orders-per-day 3.2] [--out demo_data]
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

START = date(2025, 1, 1)
END = date(2026, 11, 22)

# --------------------------------------------------------------------------------------
# Catalogue
# --------------------------------------------------------------------------------------
PRODUCTS = [
    # name, fabric, line, colour, price, type
    ("Turbante Luna", "bamboo", "women", "Arena", 39.0, "Turban"),
    ("Turbante Luna", "bamboo", "women", "Negro", 39.0, "Turban"),
    ("Turbante Luna", "bamboo", "women", "Terracota", 39.0, "Turban"),
    ("Gorro Nube", "bamboo", "women", "Gris perla", 29.0, "Cap"),
    ("Gorro Nube", "bamboo", "women", "Azul noche", 29.0, "Cap"),
    ("Gorro Descanso", "bamboo", "women", "Crudo", 24.0, "Sleep cap"),
    ("Pañuelo Brisa", "bamboo", "women", "Salvia", 34.0, "Scarf"),
    ("Turbante Alba", "cotton", "women", "Mostaza", 32.0, "Turban"),
    ("Turbante Alba", "cotton", "women", "Rayas marinas", 32.0, "Turban"),
    ("Gorro Paseo", "cotton", "women", "Topos", 26.0, "Cap"),
    ("Pañuelo Mediterráneo", "cotton", "women", "Estampado limón", 28.0, "Scarf"),
    ("Pañuelo Siena", "silk", "women", "Burdeos", 59.0, "Scarf"),
    ("Pañuelo Siena", "silk", "women", "Verde botella", 59.0, "Scarf"),
    ("Turbante Gala", "silk", "women", "Champán", 64.0, "Turban"),
    ("Gorrito Estrella", "bamboo", "children", "Rosa empolvado", 22.0, "Kids cap"),
    ("Gorrito Estrella", "bamboo", "children", "Azul cielo", 22.0, "Kids cap"),
    ("Gorrito Dino", "cotton", "children", "Verde", 21.0, "Kids cap"),
    ("Bandana Pirata", "cotton", "children", "Marino", 18.0, "Kids bandana"),
    ("Gorrito Arcoíris", "bamboo", "children", "Multicolor", 23.0, "Kids cap"),
    ("Pack Regalo Calma", "bamboo", "women", "Arena + crudo", 55.0, "Gift set"),
]
FABRIC_WEIGHT = {"bamboo": 2.0, "cotton": 1.0, "silk": 0.45}
FABRIC_ES = {"bamboo": "bambú", "cotton": "algodón", "silk": "seda"}
FABRIC_EN = {"bamboo": "bamboo", "cotton": "cotton", "silk": "silk"}


def sku_for(i: int, p) -> str:
    return f"IBB-{p[1][:3].upper()}-{i + 101}"


def product_title(p) -> str:
    return f"{p[0]} {FABRIC_ES[p[1]]} - {p[3]}"


# --------------------------------------------------------------------------------------
# People (all fake)
# --------------------------------------------------------------------------------------
FIRST = ["María", "Laura", "Carmen", "Núria", "Montse", "Ana", "Lucía", "Marta", "Elena", "Sara",
         "Paula", "Cristina", "Isabel", "Rosa", "Pilar", "Mercè", "Jordi", "Javier", "David", "Sofía",
         "Claire", "Emma", "Olivia", "Anna", "Teresa", "Alba", "Irene", "Clara", "Júlia", "Noelia"]
LAST = ["García", "Martínez", "Puig", "Soler", "López", "Ferrer", "Sánchez", "Vidal", "Romero", "Serra",
        "Navarro", "Torres", "Roca", "Font", "Morales", "Smith", "Brown", "Ruiz", "Gil", "Costa"]
CITIES = [("Barcelona", "08", "ES"), ("Madrid", "28", "ES"), ("Valencia", "46", "ES"), ("Girona", "17", "ES"),
          ("Sevilla", "41", "ES"), ("Bilbao", "48", "ES"), ("Palma", "07", "ES"), ("Zaragoza", "50", "ES"),
          ("Lleida", "25", "ES"), ("Tarragona", "43", "ES"), ("Lisboa", "11", "PT"), ("London", "SW", "GB")]


@dataclass
class Customer:
    idx: int
    first: str
    last: str
    email: str
    phone: str
    city: tuple
    language: str
    target_orders: int
    orders: list = field(default_factory=list)
    last_order: date | None = None


# --------------------------------------------------------------------------------------
# Feedback text bank (ES, CA, EN), tagged by theme and sentiment
# --------------------------------------------------------------------------------------
TEXT = {
    ("softness", "pos"): {
        "es": ["Suavísimo, no pica nada aunque tengo el cuero cabelludo muy sensible.",
               "Es tan suave que lo uso también para dormir.",
               "La tela de bambú es una caricia, de verdad."],
        "ca": ["És suavíssim, no pica gens.", "La roba de bambú és molt suau i fresca."],
        "en": ["Incredibly soft, no itching at all on a sensitive scalp.", "So soft I sleep in it."],
    },
    ("fit", "pos"): {
        "es": ["Se ajusta perfecto y no se mueve en todo el día.", "La talla es perfecta, queda muy natural."],
        "ca": ["S'ajusta molt bé i no es mou.", "La talla és perfecta."],
        "en": ["Fits perfectly and stays put all day.", "Great fit, it does not slip."],
    },
    ("fit", "neg"): {
        "es": ["Me queda un poco grande, ¿hay talla más pequeña?", "Se me resbala un poco al caminar."],
        "ca": ["Em queda una mica gran.", "Es mou una mica quan camino."],
        "en": ["A little too big for me, I wish there were sizes.", "It slips a bit when I walk."],
    },
    ("design", "pos"): {
        "es": ["Me encanta el estampado, me siento guapa otra vez.", "Los colores son preciosos y elegantes."],
        "ca": ["M'encanta l'estampat, em sento guapa.", "Uns colors preciosos."],
        "en": ["Beautiful print, I feel like myself again.", "The colours are gorgeous and elegant."],
    },
    ("design", "neg"): {
        "es": ["Echo de menos más colores, la gama es limitada.", "Me gustaría más variedad de colores y estampados.",
               "Pocos colores para elegir, ojalá hubiera tonos más vivos."],
        "ca": ["Trobo a faltar més colors, la gamma és limitada.", "Hi ha pocs colors per triar."],
        "en": ["Wish there were more colours, the range feels limited.", "Limited colour range, I'd love brighter options."],
    },
    ("fabric", "pos"): {
        "es": ["La seda es de muy buena calidad.", "El algodón es fresco, ideal para el verano."],
        "ca": ["La seda és de molt bona qualitat.", "El cotó és fresc per a l'estiu."],
        "en": ["The silk is excellent quality.", "Breathable cotton, perfect for summer."],
    },
    ("fabric", "neg"): {
        "es": ["La seda resbala un poco, cuesta anudarla.", "El algodón da algo de calor en agosto."],
        "ca": ["La seda rellisca una mica.",],
        "en": ["The silk is slippery and hard to tie.",],
    },
    ("shipping", "neg"): {
        "es": ["El envío tardó más de una semana, lo necesitaba antes de la quimio.", "El paquete llegó con retraso."],
        "ca": ["L'enviament va trigar massa.", "El paquet va arribar tard."],
        "en": ["Shipping took over a week, which was stressful.", "Delivery was late."],
    },
    ("shipping", "pos"): {
        "es": ["Llegó en dos días, rapidísimo.",], "ca": ["Va arribar en dos dies.",], "en": ["Arrived in two days, very quick.",],
    },
    ("price", "neg"): {
        "es": ["Es un poco caro para necesitar varios.", "El precio de la seda es alto."],
        "ca": ["És una mica car.",], "en": ["A bit pricey when you need several.",],
    },
    ("packaging", "pos"): {
        "es": ["El packaging es precioso, con una nota escrita a mano.", "Viene en una caja muy bonita, perfecto para regalar."],
        "ca": ["L'embolcall és preciós.",], "en": ["Lovely packaging with a handwritten note.",],
    },
    ("children", "pos"): {
        "es": ["A mi hija le encanta su gorrito de estrellas, quiere llevarlo al cole.", "Mi hijo dice que es un gorro de pirata y lo lleva orgulloso."],
        "ca": ["A la meva filla li encanta el seu barret.",], "en": ["My daughter loves her star cap and wears it to school.",],
    },
    ("children", "neg"): {
        "es": ["Faltan tallas para niños pequeños de 3 años.",], "ca": ["Falten talles per a nens petits.",],
        "en": ["Not enough sizes for toddlers.",],
    },
    ("gifting", "pos"): {
        "es": ["Lo compré para regalar a mi madre y se emocionó.", "Un regalo perfecto para mi amiga."],
        "ca": ["El vaig comprar per regalar a la meva mare.",], "en": ["Bought it as a gift for my sister, she cried.",],
    },
    ("emotional", "pos"): {
        "es": ["Gracias por hacerme sentir yo misma en un momento tan difícil.", "Me ha devuelto la confianza para salir a la calle.",
               "Por fin algo que no parece de hospital."],
        "ca": ["Gràcies per fer-me sentir jo mateixa.", "M'ha tornat la confiança."],
        "en": ["Thank you for making me feel like me again.", "It gave me my confidence back.", "Finally something that does not look medical."],
    },
    ("service", "pos"): {
        "es": ["La atención por WhatsApp fue cercana y rápida.", "Me ayudaron a elegir con mucho cariño."],
        "ca": ["L'atenció va ser molt propera.",], "en": ["Customer service was warm and quick.",],
    },
}
DISTRESS = ["Hoy ha sido un día muy duro, no puedo más con el tratamiento.",
            "Estoy pasando por un momento muy difícil y me siento sola.",
            "Avui no puc més, estic esgotada."]

THEME_WEIGHTS_REVIEW = [("softness", "pos", 22), ("fit", "pos", 12), ("fit", "neg", 6), ("design", "pos", 12),
                        ("design", "neg", 6), ("fabric", "pos", 6), ("fabric", "neg", 3), ("shipping", "neg", 6),
                        ("shipping", "pos", 3), ("price", "neg", 3), ("packaging", "pos", 5), ("gifting", "pos", 6),
                        ("emotional", "pos", 16), ("service", "pos", 4)]


def pick_text(rng: random.Random, theme: str, sent: str, lang: str) -> str:
    bank = TEXT.get((theme, sent), {})
    options = bank.get(lang) or bank.get("es") or ["Muy bien."]
    return rng.choice(options)


def weighted(rng, items):
    total = sum(w for *_, w in items)
    r = rng.uniform(0, total)
    for it in items:
        r -= it[-1]
        if r <= 0:
            return it
    return items[-1]


def eu_num(x: float, decimals: int = 2) -> str:
    s = f"{x:,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


# --------------------------------------------------------------------------------------
# Social posts
# --------------------------------------------------------------------------------------
CAPTIONS = {
    "mission": ["Ella es Rosa. Hoy compartimos su historia, con su permiso. Tu estilo, tu identidad. 💛 #cancerdemama #juntas",
                "Normalizar también es esto: salir a la calle con tu turbante favorito. #comunidad #oncologia",
                "Este mes donamos parte de cada venta a la asociación local. Gracias por formar parte. #octubrerosa",
                "Mensaje de una clienta: 'me he vuelto a reconocer en el espejo'. Gracias por confiar. #comunidad",
                "No estás sola. Hoy hablamos de autoestima durante el tratamiento. #juntas #autoestima"],
    "product": ["Nuevo Turbante Luna en terracota. Bambú suave, ajuste perfecto. #turbante #bambu",
                "Pañuelo Siena de seda: elegancia para cualquier ocasión. #pañuelo #seda",
                "Gorrito Estrella para los más peques ⭐ #niños #gorro",
                "Vuelve el Gorro Nube en azul noche. #gorro #nuevacoleccion"],
    "behind": ["Así preparamos cada pedido, con una nota escrita a mano. #detrasdelascamaras",
               "Un día en el taller: cortando bambú. #hechoenespaña",
               "Las fundadoras eligiendo los colores de la próxima colección."],
    "education": ["3 formas de anudar un pañuelo en 60 segundos. Guarda este post. #tutorial",
                  "Cómo cuidar el cuero cabelludo durante la quimio: consejos de una dermatóloga. #consejos",
                  "¿Bambú, algodón o seda? Te explicamos cuál elegir. #guia"],
}


def generate(out: Path, seed: int = 7, orders_per_day: float = 3.2, sessions_per_day: int = 90) -> None:
    rng = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)
    days = [(START + timedelta(days=i)) for i in range((END - START).days + 1)]

    # ---------------- social posts (drives some web traffic) ----------------
    posts = []
    d = START
    pid = 1790000000000
    while d <= END:
        consistent = d >= date(2026, 3, 1)
        if consistent:
            # regular cadence: Mon, Wed, Fri with small jitter
            if d.weekday() in (0, 2, 4) and rng.random() < 0.92:
                n = 1
            else:
                n = 0
        else:
            # bursty: weeks of activity then silence
            week = (d - START).days // 7
            active_week = (week * 7919 + seed) % 5 in (0, 1)
            n = 1 if (active_week and rng.random() < 0.45) else 0
        for _ in range(n):
            pillar = weighted(rng, [("mission", 3 if d.month == 10 else 2), ("product", 4), ("behind", 1.5), ("education", 1.5)])[0]
            fmt = weighted(rng, [("IG reel", 3 if consistent else 1.5), ("IG carousel", 2.5), ("IG image", 3 if not consistent else 1.5)])[0]
            followers = 1800 + (d - START).days * 4.2
            fmt_mult = {"IG reel": 2.1, "IG carousel": 1.2, "IG image": 1.0}[fmt]
            reach = int(followers * 0.28 * fmt_mult * rng.uniform(0.7, 1.35))
            likes = int(reach * rng.uniform(0.04, 0.07) * (1.3 if pillar == "mission" else 1))
            save_rate = {"mission": 0.034, "education": 0.03, "product": 0.009, "behind": 0.011}[pillar]
            saves = int(reach * save_rate * rng.uniform(0.7, 1.3) * (1.4 if fmt == "IG reel" else 1))
            shares = int(reach * (0.02 if pillar == "mission" else 0.006) * rng.uniform(0.6, 1.4) * (1.5 if fmt == "IG reel" else 1))
            hour = rng.choice([9, 12, 13, 19, 20, 21])
            posts.append({
                "id": str(pid), "date": d, "time": f"{hour:02d}:{rng.randint(0, 59):02d}", "pillar": pillar, "format": fmt,
                "caption": rng.choice(CAPTIONS[pillar]), "reach": reach, "likes": likes, "saves": saves, "shares": shares,
                "comments": max(0, int(likes * rng.uniform(0.03, 0.09))), "views": int(reach * (1.6 if fmt == "IG reel" else 0)),
                "follows": int(reach * rng.uniform(0.002, 0.006)),
            })
            pid += rng.randint(1000, 9000)
        d += timedelta(days=1)

    mission_by_day = {}
    for p in posts:
        if p["pillar"] == "mission":
            mission_by_day[p["date"]] = mission_by_day.get(p["date"], 0) + 1

    def ig_boost(day: date) -> float:
        return sum(mission_by_day.get(day - timedelta(days=k), 0) for k in range(0, 7))

    # ---------------- orders and customers ----------------
    weights = [FABRIC_WEIGHT[p[1]] * (0.55 if p[2] == "children" else 1.0) for p in PRODUCTS]
    customers: list[Customer] = []
    orders = []
    order_no = 1001
    for day in days:
        t = (day - START).days / len(days)
        season = {10: 1.8, 11: 1.15, 12: 1.35, 8: 0.7, 1: 0.85}.get(day.month, 1.0)
        if day.month == 2 and day.day <= 6:  # World Cancer Day, 4 February
            season *= 1.4
        lam = orders_per_day * (0.75 + 0.6 * t) * season * (1 + 0.04 * ig_boost(day))
        n = poisson(rng, lam)
        for _ in range(n):
            eligible = [c for c in customers[-900:] if len(c.orders) < c.target_orders and c.last_order and (day - c.last_order).days > 25]
            if eligible and rng.random() < 0.42:
                cust = rng.choice(eligible)
            else:
                lang = weighted(rng, [("es", 65), ("ca", 20), ("en", 15)])[0]
                fn, ln = rng.choice(FIRST), rng.choice(LAST)
                tgt = weighted(rng, [(1, 60), (rng.randint(2, 3), 25), (rng.randint(4, 7), 15)])[0]
                cust = Customer(len(customers), fn, ln,
                                f"{fn.lower().replace('í', 'i').replace('ú', 'u').replace('è', 'e').replace('ñ', 'n').replace('ó','o').replace('é','e').replace('á','a')}.{ln.lower().replace('í', 'i').replace('á', 'a').replace('é','e').replace('ó','o')}{len(customers)}@example.com",
                                f"+34 6{rng.randint(10, 99)} {rng.randint(100, 999)} {rng.randint(100, 999)}",
                                rng.choice(CITIES), lang, tgt)
                customers.append(cust)
            n_items = weighted(rng, [(1, 62), (2, 28), (3, 10)])[0]
            items = []
            for _ in range(n_items):
                pi = rng.choices(range(len(PRODUCTS)), weights=weights)[0]
                items.append((pi, 1 if rng.random() < 0.88 else 2))
            subtotal = sum(PRODUCTS[pi][4] * q for pi, q in items)
            code, disc = "", 0.0
            r = rng.random()
            if day.month == 10 and r < 0.35:
                code, disc = "OCTUBRE15", round(subtotal * 0.15, 2)
            elif not cust.orders and r < 0.18:
                code, disc = "BIENVENIDA10", round(subtotal * 0.10, 2)
            elif r < 0.05:
                code, disc = "AMIGA10", round(subtotal * 0.10, 2)
            shipping = 0.0 if subtotal >= 45 else 4.95
            total = round(subtotal - disc + shipping, 2)
            gift = rng.random() < 0.30
            source = weighted(rng, [("web", 70), ("instagram", 14 + 2 * ig_boost(day)), ("pos", 6), ("wholesale", 3 if day.year == 2026 else 0.5)])[0]
            created = datetime(day.year, day.month, day.day, rng.randint(8, 23), rng.randint(0, 59), rng.randint(0, 59))
            o = {"name": f"#{order_no}", "cust": cust, "created": created, "items": items, "subtotal": subtotal,
                 "discount_code": code, "discount": disc, "shipping": shipping, "total": total, "gift": gift, "source": source}
            orders.append(o)
            cust.orders.append(o)
            cust.last_order = day
            order_no += 1

    # ---------------- Shopify orders: 2025 in English, 2026 in Spanish/EU format ----------------
    en_head = ["Name", "Email", "Financial Status", "Paid at", "Fulfillment Status", "Currency", "Subtotal", "Shipping", "Taxes",
               "Total", "Discount Code", "Discount Amount", "Created at", "Lineitem quantity", "Lineitem name", "Lineitem price",
               "Lineitem sku", "Billing Name", "Billing Street", "Billing City", "Billing Zip", "Billing Country", "Billing Phone",
               "Notes", "Note Attributes", "Source", "Tags"]
    es_head = ["Nombre", "Correo electrónico", "Estado financiero", "Pagado el", "Estado de preparación", "Moneda", "Subtotal", "Envío",
               "Impuestos", "Total", "Código de descuento", "Importe del descuento", "Creado el", "Cantidad del artículo",
               "Nombre del artículo", "Precio del artículo", "SKU del artículo", "Nombre de facturación", "Calle de facturación",
               "Ciudad de facturación", "Código postal de facturación", "País de facturación", "Teléfono de facturación", "Notas",
               "Atributos de nota", "Origen", "Etiquetas"]

    def order_rows(o, eu: bool):
        c = o["cust"]
        rows = []
        for k, (pi, q) in enumerate(o["items"]):
            p = PRODUCTS[pi]
            num = (lambda x: eu_num(x)) if eu else (lambda x: f"{x:.2f}")
            if eu:
                created = o["created"].strftime("%d/%m/%Y %H:%M")
            else:
                created = o["created"].strftime("%Y-%m-%d %H:%M:%S +0100")
            first = k == 0
            note = ""
            attrs = ""
            if o["gift"] and first:
                if eu:
                    note = rng.choice(["Es un regalo, por favor sin precio", "Para mi madre", "Regalo para una amiga"])
                    attrs = "regalo: sí"
                else:
                    note = rng.choice(["It's a gift", "Gift for my sister", "Please include gift note"])
                    attrs = "gift: true"
            street = f"Carrer {rng.choice(LAST)} {rng.randint(1, 140)}"
            rows.append([
                o["name"], c.email,
                ("pagado" if eu else "paid") if first else "",
                created if first else "",
                ("preparado" if eu else "fulfilled") if first else "",
                "EUR" if first else "",
                num(o["subtotal"]) if first else "",
                num(o["shipping"]) if first else "",
                num(round(o["total"] * 0.21 / 1.21, 2)) if first else "",
                num(o["total"]) if first else "",
                o["discount_code"] if first else "",
                num(o["discount"]) if first else "",
                created,
                q, product_title(p), num(p[4]), sku_for(pi, p),
                f"{c.first} {c.last}" if first else "", street if first else "", c.city[0] if first else "",
                f"{c.city[1]}{rng.randint(100, 999)}" if first else "", c.city[2] if first else "",
                c.phone if first else "", note, attrs, o["source"] if first else "",
                ("cliente-recurrente" if len(c.orders) > 1 else "") if first else "",
            ])
        return rows

    with open(out / "shopify_orders_export_2025.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(en_head)
        for o in orders:
            if o["created"].year == 2025:
                w.writerows(order_rows(o, eu=False))
    with open(out / "pedidos_shopify_2026.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(es_head)
        for o in orders:
            if o["created"].year == 2026:
                w.writerows(order_rows(o, eu=True))

    # ---------------- products ----------------
    with open(out / "products_export.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Handle", "Title", "Vendor", "Type", "Tags", "Option1 Name", "Option1 Value", "Variant SKU", "Variant Price",
                    "Variant Inventory Qty", "Status"])
        for i, p in enumerate(PRODUCTS):
            tags = f"{FABRIC_EN[p[1]]}, {'kids' if p[2] == 'children' else 'women'}"
            w.writerow([p[0].lower().replace(" ", "-").replace("ñ", "n").replace("í", "i"), product_title(p), "iBBIBBI", p[5], tags,
                        "Color", p[3], sku_for(i, p), f"{p[4]:.2f}", rng.randint(0, 60), "active"])

    # ---------------- customers ----------------
    with open(out / "customers_export.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["First Name", "Last Name", "Email", "Accepts Email Marketing", "Default Address City", "Default Address Country Code",
                    "Phone", "Total Spent", "Total Orders", "Tags", "Language"])
        for c in customers:
            if not c.orders:
                continue
            w.writerow([c.first, c.last, c.email, rng.choice(["yes", "yes", "no"]), c.city[0], c.city[2], c.phone,
                        f"{sum(o['total'] for o in c.orders):.2f}", len(c.orders), "", c.language])

    # ---------------- reviews (Judge.me style) ----------------
    reviews = []
    for o in orders:
        for pi, _q in o["items"]:
            p = PRODUCTS[pi]
            prob = 0.025 if p[2] == "children" else 0.10
            if rng.random() > prob:
                continue
            lang = o["cust"].language
            if p[2] == "children":
                theme, sent = ("children", "pos") if rng.random() < 0.8 else ("children", "neg")
            else:
                theme, sent, _ = weighted(rng, THEME_WEIGHTS_REVIEW)
            if p[1] == "bamboo":
                base = 4.7 if sent == "pos" else 3.6
            elif p[1] == "silk":
                base = 4.3 if sent == "pos" else 3.0
            else:
                base = 4.25 if sent == "pos" else 3.1
            rating = max(1, min(5, round(rng.gauss(base, 0.55))))
            body = pick_text(rng, theme, sent, lang)
            if rng.random() < 0.35:
                t2, s2, _ = weighted(rng, THEME_WEIGHTS_REVIEW)
                if s2 == sent:
                    body += " " + pick_text(rng, t2, s2, lang)
            rd = o["created"].date() + timedelta(days=rng.randint(6, 25))
            if rd > END:
                continue
            reviews.append([rd.isoformat(), rating, "", body, f"{o['cust'].first} {o['cust'].last[0]}.", o["cust"].email,
                            p[0].lower().replace(" ", "-").replace("ñ", "n").replace("í", "i"), product_title(p), "web", "published"])
    with open(out / "judgeme_reviews_export.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["review_date", "rating", "title", "body", "reviewer_name", "reviewer_email", "product_handle", "product_title", "source", "curated"])
        w.writerows(reviews)

    # ---------------- Instagram posts (Meta Business Suite style) and comments ----------------
    with open(out / "instagram_posts_meta_export.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Post ID", "Account username", "Description", "Duration (sec)", "Publish time", "Permalink", "Post type",
                    "Date", "Views", "Reach", "Likes", "Shares", "Follows", "Comments", "Saves"])
        for p in posts:
            w.writerow([p["id"], "ibbibbi", p["caption"], 23 if p["format"] == "IG reel" else 0,
                        f"{p['date'].strftime('%m/%d/%Y')} {p['time']}", f"https://www.instagram.com/p/{p['id'][-8:]}/", p["format"],
                        "Lifetime", p["views"], p["reach"], p["likes"], p["shares"], p["follows"], p["comments"], p["saves"]])

    comment_bank = [
        ("praise", 40, ["¡Qué bonito! 😍", "Me encanta, lo tengo en negro y es comodísimo", "Preciós! 💛", "Love this!", "Gracias por visibilizar 🙏"]),
        ("request", 12, ["¿Lo vais a sacar en verde?", "¿Tenéis algún modelo en estampado de flores?", "Would love this in navy!",
                         "Feu-ne de colors més vius, si us plau!", "¿Para cuándo más colores en seda?"]),
        ("sizing", 10, ["¿Qué talla para una niña de 6 años?", "¿Sirve para cabeza pequeña?", "Quina talla em recomaneu?",
                        "Does it fit a larger head?"]),
        ("partnership", 4, ["Hola, somos una asociación de pacientes oncológicas en Valencia. ¿Podemos hablar de una colaboración?",
                            "Soy farmacéutica en Girona, ¿hacéis venta a farmacias?",
                            "Treballo a l'hospital de dia, us podem escriure per a una col·laboració?"]),
        ("emotional", 8, ["Mi madre lo lleva y está guapísima", "Esto me habría ayudado tanto hace dos años ❤️", "Fuerza a todas 💪"]),
        ("distress", 1, DISTRESS),
    ]
    comments = []
    for p in posts:
        for _ in range(p["comments"]):
            kind, bank, _w = weighted(rng, [(k, b, w) for k, w, b in comment_bank])
            cd = p["date"] + timedelta(days=rng.choice([0, 0, 0, 1, 2]))
            if cd > END:
                continue
            replied = rng.random() < (0.35 if kind in ("request", "sizing", "partnership") else 0.6)
            comments.append({"post_id": p["id"], "timestamp": f"{cd.isoformat()}T{rng.randint(8, 23):02d}:{rng.randint(0, 59):02d}:00+0000",
                             "username": f"user_{rng.randint(1000, 99999)}", "text": rng.choice(bank), "like_count": rng.randint(0, 12),
                             "replied_by_brand": replied})
    with open(out / "instagram_comments.json", "w", encoding="utf-8") as f:
        json.dump({"data": comments, "exported_from": "Instagram Graph API (demo)"}, f, ensure_ascii=False, indent=1)

    # ---------------- TikTok (just started) ----------------
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Content"
    ws.append(["Video title", "Video link", "Post time", "Total likes", "Total comments", "Total shares", "Total views", "Saves"])
    td = date(2026, 9, 8)
    while td <= END:
        if rng.random() < 0.3:
            pillar = rng.choice(["mission", "education", "product", "behind"])
            views = int(rng.uniform(400, 6000) * (2 if pillar == "education" else 1))
            ws.append([rng.choice(CAPTIONS[pillar])[:80], f"https://www.tiktok.com/@ibbibbi/video/{rng.randint(10**18, 10**19)}",
                       datetime(td.year, td.month, td.day, 19, 30), int(views * 0.06), int(views * 0.004), int(views * 0.01), views,
                       int(views * 0.012)])
        td += timedelta(days=1)
    wb.save(out / "tiktok_content_analytics.xlsx")

    # ---------------- GA4 sessions export (comment lines above header) ----------------
    with open(out / "ga4_traffic_acquisition.csv", "w", newline="", encoding="utf-8") as f:
        f.write("# ----------------------------------------\n# Traffic acquisition: Session source / medium\n")
        f.write(f"# Account: iBBIBBI\n# Property: iBBIBBI Web\n# Start date: {START.strftime('%Y%m%d')}\n# End date: {END.strftime('%Y%m%d')}\n")
        f.write("# ----------------------------------------\n")
        w = csv.writer(f)
        w.writerow(["Date", "Session source / medium", "Landing page", "Device category", "Sessions", "Total users", "Key events", "Total revenue"])
        sources = [("google / organic", 0.34, "/"), ("instagram.com / referral", 0.2, "/pages/nuestra-historia"),
                   ("(direct) / (none)", 0.22, "/"), ("klaviyo / email", 0.1, "/collections/turbantes"),
                   ("facebook.com / referral", 0.06, "/"), ("asociacion-pacientes.org / referral", 0.03, "/pages/hospitales")]
        orders_by_day = {}
        for o in orders:
            orders_by_day[o["created"].date()] = orders_by_day.get(o["created"].date(), 0) + 1
        for day in days:
            t = (day - START).days / len(days)
            total = sessions_per_day * (0.7 + 0.7 * t) * {10: 1.6, 12: 1.2, 8: 0.75}.get(day.month, 1)
            for src, share, lp in sources:
                s = total * share
                if src.startswith("instagram"):
                    s *= 1 + 0.18 * ig_boost(day)
                for dev, dshare in (("mobile", 0.74), ("desktop", 0.26)):
                    sess = max(0, int(rng.gauss(s * dshare, max(1, s * dshare * 0.15))))
                    if sess == 0:
                        continue
                    conv_rate = 0.018 if dev == "mobile" else 0.03
                    ke = sum(1 for _ in range(sess) if rng.random() < conv_rate)
                    w.writerow([day.strftime("%Y%m%d"), src, lp, dev, sess, int(sess * 0.86), ke, f"{ke * rng.uniform(35, 50):.2f}"])

    # ---------------- Klaviyo campaigns ----------------
    with open(out / "klaviyo_campaigns.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Campaign Name", "Send Time", "Total Recipients", "Unique Opens", "Open Rate", "Unique Clicks", "Click Rate",
                    "Placed Order", "Revenue"])
        cd = date(2025, 1, 14)
        names = ["Novedades de temporada", "Historias de nuestra comunidad", "Guía: cómo anudar tu pañuelo", "Octubre: juntas",
                 "Ideas de regalo", "Rebajas de invierno", "Vuelta al cole: gorritos"]
        while cd <= END:
            rec = int(900 + (cd - START).days * 2.2)
            name = rng.choice(names) if cd.month != 10 else "Octubre: juntas"
            orate = rng.uniform(0.36, 0.52) * (1.15 if "comunidad" in name or "Octubre" in name else 1)
            opens = int(rec * orate)
            clicks = int(opens * rng.uniform(0.05, 0.11))
            po = int(clicks * rng.uniform(0.04, 0.09))
            w.writerow([name, cd.strftime("%Y-%m-%d 10:00"), rec, opens, f"{orate * 100:.1f}%", clicks, f"{clicks / rec * 100:.2f}%",
                        po, f"{po * rng.uniform(38, 55):.2f}"])
            cd += timedelta(days=rng.choice([10, 14, 14, 21]))

    # ---------------- NPS survey (Google Forms) workbook with two sheets ----------------
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Respuestas de formulario 1"
    ws.append(["Marca temporal", "Del 0 al 10, ¿qué probabilidad hay de que recomiendes iBBIBBI a una amiga?", "¿Por qué?",
               "¿Cómo nos conociste?", "¿Qué producto compraste?", "Idioma", "¿Podemos citar tu respuesta? (sí/no)"])
    heard = [("Instagram", 34), ("Una amiga o familiar", 26), ("Hospital o asociación", 16), ("Google", 14), ("Farmacia", 5), ("Mercadillo", 5)]
    for _ in range(320):
        rd = START + timedelta(days=rng.randint(30, (END - START).days))
        cat = weighted(rng, [("pro", 60), ("pas", 28), ("det", 12)])[0]
        score = {"pro": rng.choice([9, 10, 10]), "pas": rng.choice([7, 8]), "det": rng.choice([3, 4, 5, 6])}[cat]
        lang = weighted(rng, [("es", 68), ("ca", 22), ("en", 10)])[0]
        if cat == "det":
            why = pick_text(rng, "design", "neg", lang) if rng.random() < 0.6 else pick_text(rng, rng.choice(["shipping", "price"]), "neg", lang)
        elif cat == "pas":
            why = pick_text(rng, rng.choice(["fit", "design", "fabric"]), rng.choice(["pos", "neg"]), lang)
        else:
            why = pick_text(rng, rng.choice(["softness", "emotional", "service", "gifting"]), "pos", lang)
        p = PRODUCTS[rng.choices(range(len(PRODUCTS)), weights=[w * (0.25 if q[2] == "children" else 1) for w, q in zip(weights, PRODUCTS)])[0]]
        ws.append([datetime(rd.year, rd.month, rd.day, rng.randint(8, 22), rng.randint(0, 59)), score, why, weighted(rng, heard)[0],
                   product_title(p), {"es": "Castellano", "ca": "Català", "en": "English"}[lang], rng.choice(["sí", "no", "no"])])
    ws2 = wb.create_sheet("Mensajes tienda")
    ws2.append(["Fecha", "Canal", "Mensaje"])
    for _ in range(60):
        rd = START + timedelta(days=rng.randint(0, (END - START).days))
        theme, sent, _ = weighted(rng, THEME_WEIGHTS_REVIEW + [("children", "neg", 4), ("children", "pos", 3)])
        lang = weighted(rng, [("es", 65), ("ca", 25), ("en", 10)])[0]
        ws2.append([rd.strftime("%d/%m/%Y"), rng.choice(["WhatsApp", "Email", "Teléfono", "Tienda física"]), pick_text(rng, theme, sent, lang)])
    wb.save(out / "encuesta_nps_y_mensajes.xlsx")

    # ---------------- pasted messages ----------------
    msgs = []
    for _ in range(24):
        theme, sent, _ = weighted(rng, THEME_WEIGHTS_REVIEW)
        lang = weighted(rng, [("es", 60), ("ca", 25), ("en", 15)])[0]
        msgs.append(pick_text(rng, theme, sent, lang) + (" " + pick_text(rng, "emotional", "pos", lang) if rng.random() < 0.3 else ""))
    msgs.insert(7, DISTRESS[0] + " Gracias por estar ahí.")
    msgs.insert(15, "Hola! Soc de l'associació d'oncologia infantil de Lleida, voldríem parlar amb vosaltres sobre els gorrets per a nens.")
    with open(out / "mensajes_whatsapp_pegados.txt", "w", encoding="utf-8") as f:
        f.write("\n\n".join(msgs) + "\n")

    # ---------------- deliberately unknown file: market stall sales ----------------
    with open(out / "mercadillo_ventas.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Fecha", "Mercadillo", "Piezas vendidas", "Caja (€)", "Tiempo", "Comentario"])
        md = date(2025, 3, 1)
        while md <= END:
            if md.weekday() == 5 and rng.random() < 0.55:
                pieces = rng.randint(3, 18) + (8 if md.month in (10, 12) else 0) + (9 if md >= date(2026, 7, 1) else 0)
                w.writerow([md.strftime("%d/%m/%Y"), rng.choice(["Mercat de Sant Antoni", "Fira de Gràcia", "Mercadillo solidario Hospital"]),
                            pieces, eu_num(pieces * rng.uniform(26, 34)), rng.choice(["Sol", "Nublado", "Lluvia"]),
                            rng.choice(["", "Mucha gente preguntando por niños", "Buen día", "Pidieron más colores"])])
            md += timedelta(days=1)

    print(f"Wrote demo data to {out}: {len(orders)} orders, {len(customers)} customers, {len(reviews)} reviews, "
          f"{len(posts)} posts, {len(comments)} comments")


def poisson(rng: random.Random, lam: float) -> int:
    L, k, p = math.exp(-lam), 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= L:
            return k - 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--orders-per-day", type=float, default=3.2)
    ap.add_argument("--sessions-per-day", type=int, default=90)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "demo_data"))
    a = ap.parse_args()
    generate(Path(a.out), a.seed, a.orders_per_day, a.sessions_per_day)
