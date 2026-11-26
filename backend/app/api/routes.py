"""HTTP API. Every endpoint takes a workspace ('demo' or 'mine') so data is never mixed."""
from __future__ import annotations

import io
import json
import pickle
import zipfile
from datetime import datetime, timedelta

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from pydantic import BaseModel

from .. import db
from ..ai import ask as ask_mod
from ..ai import client as ai_client
from ..ai import narrate
from ..analytics import common, cross, feedback, metrics, sales, social
from ..analytics import text as tx
from ..config import DEMO_DIR, MAX_UPLOAD_MB, STAGING_DIR
from ..demo import loader
from ..ingest import checklist, pipeline, vision
from ..ingest.explain import explain as explain_dataset
from ..ingest.readers import ReadError
from ..insights import briefing, plan, rules
from ..models import connectors
from .. import integrations as integ
from ..analytics import voice
from ..insights import alerts as alerts_mod
from ..privacy.pii import hash_value, scrub_storage

router = APIRouter(prefix="/api")
WS = Query("demo", pattern="^(demo|mine)$")


def _ws(ws: str) -> str:
    if ws not in ("demo", "mine"):
        raise HTTPException(400, "Unknown workspace")
    return ws


# --------------------------------------------------------------------------------------
# Status and home
# --------------------------------------------------------------------------------------
@router.get("/status")
def status(ws: str = WS):
    counts = {t: common.has(t, ws) for t in db.CANONICAL_TABLES}
    from .. import profile as prof

    return {"ws": ws, "profile": prof.get(ws), "counts": counts, "has_data": any(counts.values()), "latest": common.latest_date(ws).isoformat(),
            "ai_configured": ai_client.configured(), "ai_enabled": ai_client.enabled(), "demo_loaded": common.has("orders", "demo") > 0,
            "datasets": db.one("SELECT count(*) FROM datasets WHERE ws = ?", [ws])}


@router.get("/home")
def home(ws: str = WS, range: str = "28d"):
    p = common.period(ws, range)
    ctx = rules.context(ws, p)
    res = rules.run(ws, p, ctx)
    ins = res["insights"]
    if ai_client.enabled():
        ins = [narrate.narrate(i) for i in ins[:3]] + ins[3:]
    s, f, so = ctx["sales"], ctx["feedback"], ctx["social"]
    kpis = []
    if not s.get("empty"):
        k = s["kpis"]
        kpis += [{"key": "revenue", "label": "Revenue", "value": k["revenue"]["value"], "unit": "eur", "change": k["revenue"]["change"],
                  "spark": k["revenue"]["spark"], "help": "Total order value including shipping, from your Shopify orders."},
                 {"key": "orders", "label": "Orders", "value": k["orders"]["value"], "unit": "count", "change": k["orders"]["change"],
                  "spark": k["orders"]["spark"], "help": "Number of orders placed in the period."}]
    if not f.get("empty"):
        r = f["kpis"]["rating"]
        kpis.append({"key": "rating", "label": "Average rating", "value": r["value"], "unit": "stars",
                     "change": round((r["value"] - r["prev"]) / r["prev"] * 100, 1) if r["value"] and r["prev"] else None,
                     "help": "Average star rating of reviews written in this period."})
        if f["kpis"]["nps"]["value"] is not None:
            kpis.append({"key": "nps", "label": "NPS", "value": f["kpis"]["nps"]["value"], "unit": "score", "change": None,
                         "help": "How likely customers are to recommend you, from -100 to 100 (last 12 months of survey answers)."})
    if not so.get("empty"):
        weekly = social.weekly_series(ws)[-12:]
        kpis.append({"key": "saves", "label": "Saves per post", "value": so["kpis"]["saves"]["value"], "unit": "count",
                     "change": so["kpis"]["saves"]["change"], "spark": [w["saves"] / max(w["posts"], 1) for w in weekly],
                     "help": "How often people save your Instagram posts to come back to. The strongest sign content is useful."})
        kpis.append({"key": "per_week", "label": "Posts per week", "value": so["kpis"]["per_week"]["value"], "unit": "count",
                     "change": None, "help": "posts_per_week"})
    ist = integ.status(ws)
    connected = set(ist["connected"])
    unlock = [{"key": i["key"], "name": i["name"], "icon": i["icon"], "unlocks": i["data"][:2]} for i in ist["integrations"]
              if i["key"] in ("shopify", "instagram", "judgeme", "ga4", "klaviyo", "tiktok", "surveys") and i["key"] not in connected][:4]
    return {"period": {"label": p.label, "start": p.start.isoformat(), "end": p.end.isoformat()}, "kpis": kpis,
            "alerts": alerts_mod.build(ws, p), "sources": [i for i in ist["integrations"] if i["key"] in connected],
            "last_refresh": ist["last_refresh"], "unlock": unlock,
            "changed": rules.what_changed(ws, p), "insights": ins, "waiting": res["waiting"],
            "goals": plan.list_goals(ws), "due": [d for d in plan.list_decisions(ws) if d.get("due")],
            "care": len(f.get("care", [])) if not f.get("empty") else 0}


@router.get("/insights")
def insights(ws: str = WS, range: str = "90d"):
    p = common.period(ws, range)
    return rules.run(ws, p)


@router.get("/sales")
def sales_page(ws: str = WS, range: str = "90d"):
    p = common.period(ws, range)
    flex = []
    for ds in db.rows("SELECT id, file_name, flex_config FROM datasets WHERE ws = ? AND flexible", [ws]):
        cfg = json.loads(ds["flex_config"] or "{}")
        if cfg.get("trend"):
            flex.append({"id": ds["id"], "title": cfg.get("title"), "trend": cfg["trend"], "series": flex_series(ds["id"])["rows"]})
    return {"sales": sales.overview(ws, p), "web": sales.web(ws, p), "email": sales.email(ws, p), "flex": flex}


@router.get("/feedback")
def feedback_page(ws: str = WS, range: str = "90d"):
    return feedback.overview(ws, common.period(ws, range))


@router.get("/social")
def social_page(ws: str = WS, range: str = "90d", platform: str | None = None):
    p = common.period(ws, range)
    out = social.overview(ws, p, platform)
    out["account"] = social.account(ws, p)
    if not out.get("empty"):
        out["cross"] = cross.mission_effect(ws)
    return out


@router.get("/integrations")
def integrations_page(ws: str = WS):
    return integ.status(ws)


class RefreshBody(BaseModel):
    ws: str = "demo"


@router.post("/refresh")
def refresh(b: RefreshBody):
    return integ.refresh(_ws(b.ws))


@router.get("/alerts")
def alerts(ws: str = WS, range: str = "28d"):
    return alerts_mod.build(ws, common.period(ws, range))


@router.get("/voice")
def voice_items(ws: str = WS, source: str | None = None, rating: str | None = None, sentiment: str | None = None, theme: str | None = None,
                date_from: str | None = None, date_to: str | None = None, q: str | None = None, limit: int = 60):
    return voice.items(ws, source, rating, sentiment, theme, date_from, date_to, q, min(limit, 200))


class DraftBody(BaseModel):
    ws: str = "demo"
    text: str
    sentiment: str | None = None
    themes: list[str] | None = None
    language: str | None = None
    distress: bool = False


@router.post("/reply/draft")
def reply_draft(b: DraftBody):
    return voice.draft(b.text, b.sentiment, b.themes, b.language, b.distress, ws=b.ws)


class ConnectBody(BaseModel):
    shop_domain: str
    token: str
    ws: str = "mine"


def _is_phone(request: Request) -> bool:
    ua = (request.headers.get("user-agent") or "").lower()
    return any(k in ua for k in ("iphone", "android", "mobile"))


@router.post("/connections/{key}")
def connect(key: str, b: ConnectBody, request: Request):
    if _is_phone(request):
        return {"ok": False, "error": "For security, accounts can only be connected from a computer."}
    try:
        res = connectors.connect(_ws(b.ws), key, b.shop_domain, b.token)
    except connectors.ConnectorError as e:
        return {"ok": False, "error": str(e)}
    first = connectors.sync(b.ws, key)
    return {**res, "sync": first}


@router.delete("/connections/{key}")
def disconnect(key: str, request: Request, ws: str = WS, delete_data: bool = False):
    if _is_phone(request):
        return {"ok": False, "error": "Connections can only be changed from a computer."}
    connectors.forget(ws, key)
    removed = 0
    if delete_data:
        for d in db.rows("SELECT id FROM datasets WHERE ws = ? AND file_name LIKE ?", [ws, f"{key}_%_live.csv"]):
            pipeline.undo(d["id"])
            removed += 1
    return {"ok": True, "removed_datasets": removed,
            "note": "Disconnected. Your access key was deleted here; also remove the app or key in the platform to fully revoke access."}


class ReplyBody(BaseModel):
    id: str
    text: str
    ws: str = "mine"


@router.post("/reply")
def publish_reply(b: ReplyBody):
    return voice.publish_reply(_ws(b.ws), b.id, b.text)


@router.get("/reviews/examples")
def review_examples():
    return voice.examples()


@router.get("/metrics")
def metric_list():
    return [{"key": k, **v} for k, v in metrics.METRICS.items()]


# --------------------------------------------------------------------------------------
# Upload and data
# --------------------------------------------------------------------------------------
@router.post("/upload")
async def upload(files: list[UploadFile] = File(...), ws: str = Form("mine")):
    _ws(ws)
    out = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
            out.append({"file_name": f.filename, "error": f"This file is larger than {MAX_UPLOAD_MB} MB. Try exporting a shorter date range.", "tables": []})
            continue
        out.append(pipeline.stage(f.filename or "upload", data, ws))
    return out


class Paste(BaseModel):
    text: str
    ws: str = "mine"
    name: str | None = None


@router.post("/upload/paste")
def upload_paste(body: Paste):
    _ws(body.ws)
    if not body.text.strip():
        raise HTTPException(400, "Paste some text first.")
    return pipeline.stage(body.name or f"pasted_{datetime.now():%Y%m%d_%H%M}.txt", body.text.encode("utf-8"), body.ws)


@router.post("/upload/{upload_id}/{index}/extract")
def extract_image(upload_id: str, index: int):
    path = STAGING_DIR / f"{upload_id}.pkl"
    if not path.exists():
        raise HTTPException(404, "Upload expired. Please drop the file again.")
    st = pickle.loads(path.read_bytes())
    from ..config import UPLOAD_DIR

    raw = next(UPLOAD_DIR.glob(f"{upload_id}_*"), None)
    if not raw:
        raise HTTPException(404, "Original file not found.")
    if not ai_client.enabled():
        return {"ok": False, "error": "Reading screenshots needs AI analysis. Add an API key and switch AI analysis on in Settings."}
    rt = vision.extract(st["file_name"], raw.read_bytes())
    if not rt:
        return {"ok": False, "error": "We could not read a table from this image. Try a clearer screenshot, or type the numbers in a CSV."}
    st["tables"][index] = rt
    path.write_bytes(pickle.dumps(st))
    return {"ok": True, "table": pipeline.analyse_table(rt, index)}


class ImportBody(BaseModel):
    upload_id: str
    index: int = 0
    table_type: str | None = None
    mapping: dict | None = None
    privacy: list[dict] | None = None
    mode: str = "new_only"
    flexible: bool = False
    save_recipe: bool = True
    ws: str = "mine"


@router.post("/import")
def do_import(b: ImportBody):
    _ws(b.ws)
    try:
        res = pipeline.confirm(b.upload_id, b.index, b.table_type, b.mapping, b.privacy, b.mode, b.save_recipe, b.flexible, b.ws)
        if res.get("ok") and res.get("dataset_id"):
            ds = db.rows("SELECT * FROM datasets WHERE id = ?", [res["dataset_id"]])
            if ds:
                res["explain"] = explain_dataset(ds[0])
        return res
    except ReadError as e:
        return {"ok": False, "error": str(e)}


@router.get("/datasets")
def datasets(ws: str = WS):
    rows = db.rows("""SELECT id, file_name, sheet, table_type, source_label, rows_in, rows_imported, rows_skipped, rows_fixed, date_min, date_max,
        quality, created_at, flexible, report, flex_config FROM datasets WHERE ws = ? ORDER BY created_at DESC""", [ws])
    for r in rows:
        r["report"] = json.loads(r["report"]) if r["report"] else None
        r["flex_config"] = json.loads(r["flex_config"]) if r["flex_config"] else None
        r["explain"] = explain_dataset(r)
    present = {r["table_type"] for r in rows}
    labels = {r["source_label"] for r in rows}
    missing = []
    checks = [("orders", None, "Shopify orders", "No sales data yet. Export your orders from Shopify to see what sells.", "shopify"),
              ("reviews", None, "Reviews", "No product reviews yet. Export them from your reviews app.", "shopify"),
              ("social_posts", "Instagram", "Instagram", "No Instagram data yet. Here is how to export it.", "instagram"),
              ("social_posts", "TikTok", "TikTok", "No TikTok data yet. Here is how to export it.", "tiktok"),
              ("web_sessions", None, "Google Analytics", "No website data yet. Here is how to export it from Google Analytics 4.", "ga4"),
              ("email_campaigns", None, "Klaviyo", "No email results yet. Export your campaigns from Klaviyo.", "klaviyo"),
              ("survey_responses", None, "Survey", "No survey answers yet. Create a feedback form in Collect.", "forms")]
    for tt, lab, name, msg, guide in checks:
        if tt not in present or (lab and lab not in labels):
            missing.append({"type": tt, "name": name, "message": msg, "guide": guide})
    items = checklist.checklist(ws)
    return {"datasets": rows, "missing": missing, "checklist": items, "next": checklist.next_step(items)}


@router.post("/datasets/{dataset_id}/undo")
def undo(dataset_id: str):
    return pipeline.undo(dataset_id)


class FlexBody(BaseModel):
    trend: dict | None = None
    text_column: str | None = None
    title: str | None = None


@router.post("/datasets/{dataset_id}/flex")
def flex_config(dataset_id: str, b: FlexBody):
    try:
        return pipeline.configure_flexible(dataset_id, b.trend, b.text_column, b.title)
    except ReadError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/datasets/{dataset_id}/flex/series")
def flex_series(dataset_id: str):
    cfg = db.one("SELECT flex_config FROM datasets WHERE id = ?", [dataset_id])
    if not cfg:
        raise HTTPException(404, "Not found")
    cfg = json.loads(cfg)
    t = cfg.get("trend")
    if not t:
        return {"rows": []}
    rows = db.rows(f"""SELECT date_trunc('month', CAST("{t['date']}" AS DATE))::DATE AS period, sum("{t['value']}") AS value, count(*) n
        FROM "{cfg['table']}" WHERE "{t['date']}" IS NOT NULL GROUP BY 1 ORDER BY 1""")
    return {"rows": rows}


@router.get("/datasets/{dataset_id}/preview")
def dataset_preview(dataset_id: str):
    ds = db.rows("SELECT * FROM datasets WHERE id = ?", [dataset_id])
    if not ds:
        raise HTTPException(404, "Not found")
    d = ds[0]
    if d["flexible"]:
        cfg = json.loads(d["flex_config"])
        return {"rows": db.rows(f'SELECT * EXCLUDE (row_num) FROM "{cfg["table"]}" LIMIT 50'), "config": cfg}
    target = {"reviews": "feedback", "survey_responses": "feedback"}.get(d["table_type"], d["table_type"])
    return {"rows": db.rows(f"SELECT * EXCLUDE (ws, _key) FROM {target} WHERE dataset_id = ? LIMIT 50", [dataset_id])}


# --------------------------------------------------------------------------------------
# Quick capture and Collect
# --------------------------------------------------------------------------------------
class Quick(BaseModel):
    text: str
    source: str = "Quick capture"
    ws: str = "mine"
    rating: float | None = None
    consent_quote: bool = False
    line: str | None = None


def add_feedback(b: Quick, kind: str) -> dict:
    _ws(b.ws)
    text = scrub_storage(b.text.strip())[:4000]
    if len(text) < 2:
        raise HTTPException(400, "Write a few words first.")
    s, sc = tx.sentiment(text, b.rating)
    key = hash_value(f"{datetime.now().isoformat()}{text}")
    th = tx.themes(text)
    db.execute("""INSERT INTO feedback (ws, dataset_id, row_num, _key, date, kind, source, text, rating, language, consent_quote, sentiment,
        sentiment_score, themes, distress, line) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
               [b.ws, f"{kind}_capture", 0, key, common.latest_date(b.ws) if b.ws == "demo" else datetime.now().date(), kind, b.source, text,
                b.rating, tx.detect_language(text), b.consent_quote, s, sc, ",".join(th), tx.is_distress(text),
                b.line or ("children" if "children" in th else None)])
    return {"ok": True, "id": key, "sentiment": s, "themes": [tx.THEMES[t]["label"] for t in th], "distress": tx.is_distress(text)}


@router.post("/feedback/quick")
def quick_capture(b: Quick):
    return add_feedback(b, "message")


@router.delete("/feedback/{key}")
def delete_feedback(key: str, ws: str = WS):
    db.execute("DELETE FROM feedback WHERE _key = ? AND ws = ?", [key, ws])
    return {"ok": True}


class Consent(BaseModel):
    consent: bool


@router.patch("/feedback/{key}/consent")
def set_consent(key: str, b: Consent, ws: str = WS):
    db.execute("UPDATE feedback SET consent_quote = ? WHERE _key = ? AND ws = ?", [b.consent, key, ws])
    return {"ok": True}


@router.post("/collect/submit")
def collect_submit(b: Quick):
    b.source = b.source or "Feedback form"
    return add_feedback(b, "survey" if b.rating is not None else "message")


@router.get("/collect/qr")
def qr(url: str):
    import qrcode
    import qrcode.image.svg

    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=12, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return Response(buf.getvalue(), media_type="image/svg+xml")


# --------------------------------------------------------------------------------------
# Ask
# --------------------------------------------------------------------------------------
class AskBody(BaseModel):
    question: str
    ws: str = "demo"


@router.post("/ask")
def ask(b: AskBody):
    _ws(b.ws)
    return ask_mod.ask(b.ws, b.question)


@router.get("/ask/suggestions")
def ask_suggestions():
    return {"suggested": ask_mod.SUGGESTED, "functions": [{"key": k, "label": v[1]} for k, v in ask_mod.FUNCTIONS.items()]}


# --------------------------------------------------------------------------------------
# Plan
# --------------------------------------------------------------------------------------
@router.get("/plan")
def plan_page(ws: str = WS):
    ds = plan.list_decisions(ws)
    return {"goals": plan.list_goals(ws), "decisions": [d for d in ds if d["kind"] != "experiment"],
            "experiments": [d for d in ds if d["kind"] == "experiment"], "metrics": metric_list()}


class GoalBody(BaseModel):
    title: str
    metric: str
    target: float
    due: str | None = None
    ws: str = "demo"


@router.post("/goals")
def add_goal(b: GoalBody):
    try:
        return plan.add_goal(_ws(b.ws), b.title, b.metric, b.target, b.due)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


class GoalEdit(BaseModel):
    title: str | None = None
    target: float | None = None
    due: str | None = None
    ws: str = "demo"


@router.patch("/goals/{gid}")
def edit_goal(gid: str, b: GoalEdit):
    try:
        return plan.update_goal(_ws(b.ws), gid, b.title, b.target, b.due)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@router.delete("/goals/{gid}")
def del_goal(gid: str, ws: str = WS):
    plan.delete("goals", ws, gid)
    return {"ok": True}


class DecisionBody(BaseModel):
    title: str
    hypothesis: str = ""
    metric: str | None = None
    review_date: str | None = None
    owner: str | None = None
    insight_id: str | None = None
    linked_goal: str | None = None
    kind: str = "decision"
    ws: str = "demo"


@router.post("/decisions")
def add_decision(b: DecisionBody):
    return plan.add_decision(_ws(b.ws), b.title, b.hypothesis, b.metric, b.review_date, b.owner, b.insight_id, b.linked_goal, b.kind)


class ReviewBody(BaseModel):
    learning: str
    outcome: str = "kept"
    ws: str = "demo"


@router.post("/decisions/{did}/review")
def review_decision(did: str, b: ReviewBody):
    try:
        return plan.review(_ws(b.ws), did, b.learning, b.outcome)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@router.delete("/decisions/{did}")
def del_decision(did: str, ws: str = WS):
    plan.delete("decisions", ws, did)
    return {"ok": True}


# --------------------------------------------------------------------------------------
# Briefing
# --------------------------------------------------------------------------------------
@router.get("/briefing")
def get_briefing(ws: str = WS, range: str = "28d", format: str = "json", lang: str = "en"):
    from shared.i18n_core import translate_tree

    b = briefing.build(ws, range)
    if format in ("html", "md") and lang == "es":
        b = translate_tree(b, "es")
    if format == "html":
        return HTMLResponse(briefing.to_html(b, lang))
    if format == "md":
        return PlainTextResponse(briefing.to_markdown(b, lang), headers={"Content-Disposition": f'attachment; filename="briefing_{b["end"]}.md"'})
    return b


# --------------------------------------------------------------------------------------
# Demo, settings, control
# --------------------------------------------------------------------------------------
@router.post("/demo/load")
def demo_load():
    return loader.load("demo")


@router.get("/demo/files/{name}")
def demo_file(name: str):
    path = DEMO_DIR / name
    if path.parent != DEMO_DIR or not path.exists():
        raise HTTPException(404, "Not found")
    return Response(path.read_bytes(), media_type="application/octet-stream", headers={"Content-Disposition": f'attachment; filename="{name}"'})


class ProfileBody(BaseModel):
    ws: str = "mine"
    name: str | None = None
    industry: str | None = None
    mission: str | None = None
    sensitive: bool | None = None
    attribute_label: str | None = None
    line_label: str | None = None
    key_dates: list[dict] | None = None


@router.post("/profile")
def save_profile(b: ProfileBody):
    from .. import profile as prof

    return prof.save(_ws(b.ws), {k: v for k, v in b.model_dump().items() if k != "ws" and v is not None})


@router.get("/settings")
def get_settings(ws: str = WS):
    return {"ai_enabled": bool(db.get_setting("ai_enabled", True)), "ai_configured": ai_client.configured(),
            "priorities": rules.priorities(ws), "retention_days": db.get_setting("retention_days", None),
            "themes": {k: v["label"] for k, v in tx.THEMES.items()}, "connectors": connectors.status()}


class SettingsBody(BaseModel):
    lang: str | None = None
    ai_enabled: bool | None = None
    priorities: dict | None = None
    retention_days: int | None = None
    ws: str = "demo"


@router.post("/settings")
def save_settings(b: SettingsBody):
    if b.lang in ("en", "es"):
        db.set_setting("lang", b.lang)
    if b.ai_enabled is not None:
        db.set_setting("ai_enabled", b.ai_enabled)
    if b.priorities is not None:
        db.set_setting(f"priorities:{b.ws}", {k: float(v) for k, v in b.priorities.items()})
    if b.retention_days is not None:
        db.set_setting("retention_days", b.retention_days or None)
        apply_retention()
    return get_settings(b.ws)


def apply_retention() -> int:
    days = db.get_setting("retention_days", None)
    if not days:
        return 0
    cutoff = datetime.now().date() - timedelta(days=int(days))
    with db.locked() as c:
        for t in ("feedback", "social_comments"):
            c.execute(f"DELETE FROM {t} WHERE ws = 'mine' AND date < ?", [cutoff])
    return int(days)


@router.get("/export")
def export_all(ws: str = WS):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for t in db.CANONICAL_TABLES + ["datasets", "goals", "decisions"]:
            df = db.q(f"SELECT * FROM {t} WHERE ws = ?", [ws])
            z.writestr(f"{t}.csv", df.to_csv(index=False))
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="insight_hub_{ws}_{datetime.now():%Y%m%d}.zip"'})


class DeleteBody(BaseModel):
    ws: str | None = None
    confirm: str


@router.post("/delete-all")
def delete_all(b: DeleteBody):
    if b.confirm != "DELETE":
        raise HTTPException(400, "Type DELETE to confirm.")
    if b.ws:
        loader.clear(_ws(b.ws))
    else:
        db.reset_all()
    return {"ok": True}
