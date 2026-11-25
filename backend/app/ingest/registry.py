"""Registry of known table types and their canonical fields.

Each field lists synonyms in English, Spanish and Catalan (accents removed, lower case).
Matching is fuzzy, so exact column names are not required.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Field:
    name: str
    label: str
    kind: str  # date | number | text | id | bool | category | email | pii
    synonyms: list[str]
    required: bool = False


@dataclass
class TableType:
    key: str
    label: str
    description: str
    fields: list[Field]
    filename_hints: list[str] = field(default_factory=list)
    natural_key: list[str] = field(default_factory=list)


F = Field
TYPES: dict[str, TableType] = {}


def _t(t: TableType):
    TYPES[t.key] = t


_t(TableType("orders", "Orders and sales", "One row per order or per line item",
    [F("order_id", "Order number", "id", ["name", "order", "order id", "order number", "order name", "nombre", "pedido", "numero de pedido",
                                           "n pedido", "comanda", "id pedido", "order no"]),
     F("date", "Order date", "date", ["created at", "creado el", "fecha", "date", "order date", "fecha del pedido", "data",
                                      "processed at", "fecha de creacion"], True),
     F("total", "Order total", "number", ["total", "importe total", "total price", "order total", "amount", "importe", "total eur"], True),
     F("customer_email", "Customer email", "email", ["email", "correo electronico", "correo", "e mail", "customer email", "correu",
                                                      "correu electronic"]),
     F("customer_ref", "Customer id", "id", ["customer id", "customer_id", "id cliente", "customer"]),
     F("subtotal", "Subtotal", "number", ["subtotal"]),
     F("discount_code", "Discount code", "text", ["discount code", "codigo de descuento", "coupon", "cupon", "codi de descompte",
                                                   "promo code"]),
     F("discount", "Discount amount", "number", ["discount amount", "importe del descuento", "descuento", "discount"]),
     F("shipping", "Shipping", "number", ["shipping", "envio", "shipping cost", "gastos de envio"]),
     F("channel", "Sales channel", "category", ["source", "origen", "channel", "canal", "sales channel", "canal de venta"]),
     F("notes", "Order notes", "text", ["notes", "notas", "note", "nota"]),
     F("note_attributes", "Note attributes", "text", ["note attributes", "atributos de nota", "gift", "regalo", "is gift"]),
     F("item_name", "Product", "text", ["lineitem name", "nombre del articulo", "product", "producto", "product title", "item",
                                        "articulo", "product name"]),
     F("item_qty", "Quantity", "number", ["lineitem quantity", "cantidad del articulo", "quantity", "cantidad", "qty", "units",
                                          "unidades", "quantitat"]),
     F("item_price", "Unit price", "number", ["lineitem price", "precio del articulo", "price", "precio", "unit price", "preu"]),
     F("item_sku", "SKU", "text", ["lineitem sku", "sku del articulo", "sku", "variant sku"]),
     F("city", "City", "category", ["billing city", "ciudad de facturacion", "city", "ciudad", "shipping city", "ciutat"]),
     F("country", "Country", "category", ["billing country", "pais de facturacion", "country", "pais", "shipping country"]),
     F("currency", "Currency", "category", ["currency", "moneda"]),
     F("financial_status", "Payment status", "category", ["financial status", "estado financiero", "payment status"]),
     ], ["order", "pedido", "shopify", "sales", "ventas", "comanda"], ["order_id", "item_name", "item_sku"]))

_t(TableType("products", "Products", "Your product catalogue",
    [F("product", "Product name", "text", ["title", "product title", "product", "producto", "nombre", "name", "titulo"], True),
     F("price", "Price", "number", ["variant price", "price", "precio", "preu", "pvp"], True),
     F("sku", "SKU", "text", ["variant sku", "sku", "referencia"]),
     F("type", "Product type", "category", ["type", "product type", "tipo", "categoria", "category"]),
     F("tags", "Tags", "text", ["tags", "etiquetas"]),
     F("colour", "Colour", "category", ["option1 value", "color", "colour", "variant color", "color option"]),
     F("inventory", "Stock", "number", ["variant inventory qty", "inventory", "stock", "inventario", "existencias"]),
     F("handle", "Handle", "text", ["handle", "url handle"]),
     ], ["product", "producto", "catalog", "catalogo"], ["sku", "product"]))

_t(TableType("customers", "Customers", "Your customer list",
    [F("customer_email", "Email", "email", ["email", "correo electronico", "correo", "e mail", "correu"], True),
     F("first_name", "First name", "pii", ["first name", "nombre", "name", "nom"]),
     F("last_name", "Last name", "pii", ["last name", "apellidos", "apellido", "cognoms", "surname"]),
     F("city", "City", "category", ["default address city", "city", "ciudad", "ciutat"]),
     F("country", "Country", "category", ["default address country code", "country", "pais", "country code"]),
     F("orders_count", "Number of orders", "number", ["total orders", "orders count", "numero de pedidos", "orders", "pedidos"]),
     F("total_spent", "Total spent", "number", ["total spent", "gasto total", "lifetime value", "total gastado"]),
     F("accepts_marketing", "Accepts marketing", "bool", ["accepts email marketing", "accepts marketing", "acepta marketing",
                                                          "email marketing consent"]),
     F("language", "Language", "category", ["language", "idioma", "locale"]),
     ], ["customer", "cliente", "clients"], ["customer_email"]))

_t(TableType("reviews", "Product reviews", "Ratings and written reviews",
    [F("date", "Review date", "date", ["review date", "review_date", "created at", "fecha", "date", "fecha de la resena", "data"], True),
     F("rating", "Rating", "number", ["rating", "stars", "estrellas", "valoracion", "puntuacion", "score", "review rating", "nota"], True),
     F("text", "Review text", "text", ["body", "review", "review body", "comment", "comentario", "opinion", "texto", "review content",
                                       "resena", "content"], True),
     F("title", "Title", "text", ["title", "titulo", "review title"]),
     F("product", "Product", "text", ["product title", "product", "producto", "product name"]),
     F("customer_email", "Reviewer email", "email", ["reviewer email", "email", "correo"]),
     F("reviewer_name", "Reviewer name", "pii", ["reviewer name", "name", "author", "nombre", "autor"]),
     F("external_id", "Review id on the platform", "id", ["review id", "review_id", "judgeme id", "id de la resena"]),
     F("platform", "Review platform", "category", ["platform", "plataforma", "review platform"]),
     ], ["review", "resena", "judge", "opinion", "valoracion"], ["date", "text", "customer_email"]))

_t(TableType("survey_responses", "Survey or NPS responses", "Answers from Google Forms, Typeform or similar",
    [F("nps", "Likelihood to recommend (0 to 10)", "number", ["recommend", "recomiend", "recomanar", "likely", "probabilidad", "nps",
                                                              "0 al 10", "0 to 10", "net promoter"], True),
     F("date", "Submitted", "date", ["marca temporal", "timestamp", "submitted at", "fecha", "date", "data", "submit date"]),
     F("text", "Reason / comment", "text", ["por que", "why", "reason", "motivo", "comment", "comentario", "perque", "comments",
                                            "what could we improve", "que mejorarias"]),
     F("heard_from", "How they found you", "category", ["como nos conociste", "how did you hear", "conociste", "where did you hear",
                                                        "com ens vas coneixer", "how did you find us"]),
     F("product", "Product", "text", ["que producto", "product", "producto", "which product"]),
     F("language", "Language", "category", ["idioma", "language", "llengua"]),
     F("consent_quote", "OK to quote", "bool", ["citar", "quote", "consent", "consentimiento", "podemos citar", "may we quote"]),
     F("rating", "Satisfaction rating", "number", ["satisfaccion", "satisfaction", "rating", "valoracion"]),
     F("customer_email", "Email", "email", ["email", "correo", "email address"]),
     ], ["survey", "encuesta", "nps", "form", "formulario", "typeform", "enquesta"], ["date", "nps", "text"]))

_t(TableType("feedback", "Customer feedback", "Free-text messages, comments or notes from customers",
    [F("text", "Message", "text", ["message", "mensaje", "text", "texto", "comment", "comentario", "feedback", "body", "missatge",
                                   "opinion", "nota", "notes"], True),
     F("date", "Date", "date", ["fecha", "date", "data", "timestamp", "marca temporal", "received", "created at"]),
     F("source", "Where it came from", "category", ["channel", "canal", "source", "origen", "via", "medio"]),
     F("rating", "Rating", "number", ["rating", "valoracion", "stars", "puntuacion"]),
     F("customer_email", "Email", "email", ["email", "correo"]),
     F("language", "Language", "category", ["language", "idioma"]),
     ], ["feedback", "mensaje", "message", "comentario", "whatsapp", "opinion"], ["date", "text"]))

_t(TableType("social_posts", "Social media posts", "Instagram or TikTok post performance",
    [F("date", "Published", "date", ["publish time", "post time", "date", "timestamp", "fecha de publicacion", "created time",
                                     "published", "fecha", "posted"], True),
     F("caption", "Caption", "text", ["description", "caption", "video title", "texto", "title", "post caption", "descripcion"]),
     F("format", "Format", "category", ["post type", "media type", "type", "format", "tipo", "media product type"]),
     F("reach", "Reach", "number", ["reach", "alcance", "accounts reached"]),
     F("views", "Views", "number", ["views", "impressions", "total views", "reproducciones", "impresiones", "plays", "video views"]),
     F("likes", "Likes", "number", ["likes", "total likes", "me gusta", "like count"]),
     F("comments", "Comments", "number", ["comments", "total comments", "comentarios", "comments count"]),
     F("shares", "Shares", "number", ["shares", "total shares", "compartidos", "veces compartido"]),
     F("saves", "Saves", "number", ["saves", "guardados", "saved", "total saves"]),
     F("follows", "Follows", "number", ["follows", "new followers", "seguidores"]),
     F("post_id", "Post id", "id", ["post id", "media id", "video link", "permalink", "id", "link"]),
     ], ["instagram", "tiktok", "post", "content", "insights", "publicaciones", "reels"], ["post_id", "date", "caption"]))

_t(TableType("social_comments", "Social media comments", "Comments left on your posts",
    [F("text", "Comment", "text", ["text", "comment", "comentario", "message", "comment text"], True),
     F("date", "Date", "date", ["timestamp", "date", "created time", "fecha", "time"], True),
     F("post_id", "Post id", "id", ["post id", "media id", "post_id", "media"]),
     F("username", "Username", "pii", ["username", "user", "from username", "author", "usuario"]),
     F("likes", "Likes", "number", ["like count", "likes"]),
     F("replied", "Replied by you", "bool", ["replied by brand", "replied", "respondido", "answered"]),
     ], ["comment", "comentario", "instagram"], ["post_id", "date", "text"]))

_t(TableType("web_sessions", "Website visits", "Google Analytics or similar traffic report",
    [F("date", "Date", "date", ["date", "fecha", "day", "dia"], True),
     F("sessions", "Sessions", "number", ["sessions", "sesiones", "visits", "visitas"], True),
     F("source", "Where visitors came from", "category", ["session source medium", "source medium", "source", "fuente", "session source",
                                                          "first user source", "channel"]),
     F("landing_page", "Landing page", "text", ["landing page", "pagina de destino", "landing page query string", "page"]),
     F("device", "Device", "category", ["device category", "device", "dispositivo"]),
     F("users", "Users", "number", ["total users", "users", "usuarios", "active users"]),
     F("conversions", "Purchases / key events", "number", ["key events", "conversions", "conversiones", "transactions", "purchases"]),
     F("revenue", "Revenue", "number", ["total revenue", "revenue", "ingresos", "purchase revenue"]),
     ], ["ga4", "analytics", "traffic", "trafico", "sessions"], ["date", "source", "landing_page", "device"]))

_t(TableType("email_campaigns", "Email campaigns", "Klaviyo or Mailchimp campaign results",
    [F("campaign", "Campaign", "text", ["campaign name", "campaign", "campana", "subject", "asunto"], True),
     F("date", "Sent", "date", ["send time", "sent at", "date", "fecha de envio", "send date", "fecha"], True),
     F("recipients", "Recipients", "number", ["total recipients", "recipients", "destinatarios", "delivered", "sent"], True),
     F("opens", "Opens", "number", ["unique opens", "opens", "aperturas"]),
     F("clicks", "Clicks", "number", ["unique clicks", "clicks", "clics"]),
     F("orders", "Orders", "number", ["placed order", "orders", "conversions", "pedidos"]),
     F("revenue", "Revenue", "number", ["revenue", "ingresos"]),
     ], ["klaviyo", "email", "campaign", "mailchimp", "newsletter"], ["campaign", "date"]))


TYPE_LABELS = {k: t.label for k, t in TYPES.items()}
