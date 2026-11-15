"""Lobsta web app. Run:  uvicorn app.server:app --host 0.0.0.0 --port 8080

  /            phone page: snap an invoice, confirm, talk to the front desk
  /sheet       projector page: the books, updating live as invoices are confirmed
  ?p=hotpot    switch restaurant (each has its own config and its own database)
"""
from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from lobsta import config, frontdesk, i18n, pipeline, reader, stock
from lobsta.config import item_name
from lobsta.store import open_store

ROOT = Path(__file__).resolve().parent.parent
UPLOADS = ROOT / "uploads"
UPLOADS.mkdir(exist_ok=True)
app = FastAPI(title="Lobsta")
_state: dict[str, tuple] = {}


def today() -> date:
    return date.fromisoformat(os.environ["LOBSTA_TODAY"]) if os.environ.get("LOBSTA_TODAY") else date.today()


LANGS = ("zh", "en", "fr")


def ctx(p: str | None, lang: str | None = None):
    """lang overrides the owner's language for this request only (the zh / EN / FR switch)."""
    p = p or os.environ.get("LOBSTA_PROFILE", "sushi")
    if not (ROOT / "configs" / f"{p}.json").exists():
        raise HTTPException(404, f"no config for {p}")
    if p not in _state:
        _state[p] = (config.load(p), open_store(str(ROOT / f"lobsta_{p}.db")))
    cfg, store = _state[p]
    if lang in LANGS and lang != cfg["owner_language"]:
        cfg = {**cfg, "owner_language": lang}
    return cfg, store


@app.get("/")
def index():
    return FileResponse(ROOT / "app" / "static" / "index.html")


@app.get("/intro")
def intro_page():
    return FileResponse(ROOT / "app" / "static" / "intro.html")


@app.get("/sheet")
def sheet_page():
    return FileResponse(ROOT / "app" / "static" / "sheet.html")


@app.get("/api/config")
def api_config(p: str | None = None, lang: str | None = None):
    cfg, _ = ctx(p, lang)
    lang = cfg["owner_language"]
    demo = sorted(f.name for f in (ROOT / "demo" / cfg["profile"]).glob("*.jpg")) if (ROOT / "demo" / cfg["profile"]).exists() else []
    return {"profile": cfg["profile"], "business": cfg.get("business"), "language": lang,
            "profiles": sorted(f.stem for f in (ROOT / "configs").glob("*.json")),
            "items": [{"key": it["key"], "name": item_name(cfg, it["key"], lang)} for it in cfg["items"]],
            "reader": reader.backend(),
            "chat": frontdesk.chat_mode(),
            "demo": demo, "today": today().isoformat(), "owner_language": ctx(p)[0]["owner_language"]}


@app.post("/api/invoice")
async def api_invoice(p: str | None = Form(None), demo: str | None = Form(None), file: UploadFile | None = File(None),
                      lang: str | None = Form(None)):
    cfg, store = ctx(p, lang)
    if demo:
        path = ROOT / "demo" / cfg["profile"] / Path(demo).name
        if not path.exists():
            raise HTTPException(404, "no such demo invoice")
    elif file:
        ext = Path(file.filename or "x.jpg").suffix.lower() or ".jpg"
        path = UPLOADS / f"{int(time.time() * 1000)}{ext}"
        path.write_bytes(await file.read())
    else:
        raise HTTPException(400, "send a photo")
    t0 = time.time()
    try:
        # demo invoices carry their own answer file, so they work with no API key
        which = "mock" if demo and reader.backend() == "mock" else None
        res = pipeline.process(str(path), cfg, store, which=which)
    except FileNotFoundError:
        raise HTTPException(400, "No reader is configured for real photos. Set ANTHROPIC_API_KEY, or "
                                 "LOBSTA_READER=local with your fine-tuned model running. See README.")
    except Exception as e:
        raise HTTPException(502, f"The reader failed: {e}")
    res["seconds"] = round(time.time() - t0, 1)
    res["reader"] = which or reader.backend()
    for ln in res["invoice"]["lines"]:
        ln["item_name"] = item_name(cfg, ln.get("item_key")) if ln.get("item_key") else None
        ln["unit"] = i18n.unit_word(ln.get("unit"), cfg["owner_language"], ln.get("quantity"))
    return res


class Confirm(BaseModel):
    item_keys: dict[str, str] = {}
    p: str | None = None
    lang: str | None = None


@app.post("/api/invoice/{invoice_id}/confirm")
def api_confirm(invoice_id: int, body: Confirm):
    cfg, store = ctx(body.p, body.lang)
    if not store.get_invoice(invoice_id):
        raise HTTPException(404, "no such invoice")
    return {"text": pipeline.confirm(invoice_id, cfg, store, body.item_keys)}


class Chat(BaseModel):
    text: str
    p: str | None = None
    lang: str | None = None


@app.post("/api/chat")
def api_chat(body: Chat):
    cfg, store = ctx(body.p, body.lang)
    out = frontdesk.answer(body.text, cfg, store, today())
    for a in out.get("actions", []):
        for d in a.get("drafts", []):
            d["sms"] = "sms:" + d["phone"] + "?&body=" + __import__("urllib.parse").parse.quote(d["text"])
    return out


@app.get("/api/sheet")
def api_sheet(p: str | None = None, limit: int = 40, lang: str | None = None):
    cfg, store = ctx(p, lang)
    rows = [dict(r) for r in store.db.execute(
        "select l.invoice_id, l.date, l.supplier, l.description, l.item_key, l.quantity, l.unit, l.unit_price,"
        " l.line_total, l.unit_cost, l.cost_per from lines l order by l.invoice_id desc, l.n asc limit ?", (limit,))]
    lang = cfg["owner_language"]
    for r in rows:
        r["item"] = item_name(cfg, r["item_key"]) if r["item_key"] else ""
        r["unit"] = i18n.unit_word(r["unit"], lang, r["quantity"])
        r["cost_per"] = i18n.unit_word(r["cost_per"], lang)
    tot = store.db.execute("select count(distinct invoice_id) n, coalesce(sum(line_total),0) t from lines").fetchone()
    stock_rows = [s for s in (stock.status(it, store, today()) for it in cfg["items"]) if s["on_hand"] is not None]
    for s in stock_rows:
        s["item"] = item_name(cfg, s["item_key"])
        s["unit"] = i18n.unit_word(s["unit"], lang, s["on_hand"])
    return {"business": cfg.get("business"), "language": lang, "rows": rows, "invoices": tot["n"], "total": round(tot["t"], 2),
            "stock": stock_rows, "sheet_url": (f"https://docs.google.com/spreadsheets/d/{os.environ['LOBSTA_SHEET_ID']}"
                                              if os.environ.get("LOBSTA_SHEET_ID") else None)}


@app.post("/api/reset")
def api_reset(p: str | None = None):
    """Demo helper: wipe this restaurant's data and reload the demo history."""
    cfg, store = ctx(p)
    from scripts.seed_demo import seed
    return seed(cfg["profile"], today(), rebuild=False, store=store)


@app.get("/demo-image/{profile}/{name}")
def demo_image(profile: str, name: str):
    path = ROOT / "demo" / Path(profile).name / Path(name).name
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path)


app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")
