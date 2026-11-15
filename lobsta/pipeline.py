"""photo -> read (AI) -> numbers, checks, matching, price memory (code) ->
owner confirms -> store writes. The model's output never reaches the store
without passing through check() and a human OK."""
from __future__ import annotations

from . import checks, i18n, matcher, pricing, reader


def process(image_path: str, cfg: dict, store, which: str | None = None, raw: dict | None = None) -> dict:
    raw = raw or reader.read_invoice(image_path, which)
    inv = checks.normalize(raw)
    flags = checks.check(inv)
    matcher.match_lines(inv, cfg, store)
    # re-derive cost for lines whose pack size came from a saved match
    from .parse import base_quantity, unit_cost
    for ln in inv["lines"]:
        ln["unit_cost"], ln["cost_per"] = unit_cost(ln["unit_price"], ln["unit"], ln["pack"])
        ln["base_qty"] = base_quantity(ln["quantity"], ln["unit"], ln["pack"])
    if store.find_duplicate(inv["supplier"], inv["invoice_number"]):
        flags.append({"code": "duplicate", "line": None})
    alerts = pricing.alerts_for(inv, cfg, store)
    questions = [{"code": "unknown_item", "line": ln["n"]} for ln in inv["lines"] if ln["match"] == "unknown"]
    invoice_id = store.save_pending(inv, flags + alerts, image_path)
    return view(invoice_id, inv, flags, alerts, questions, cfg)


def view(invoice_id, inv, flags, alerts, questions, cfg) -> dict:
    lang = cfg["owner_language"]
    say = lambda f: {**f, "text": i18n.flag_text(f, inv, cfg, lang)}
    return {
        "id": invoice_id, "invoice": inv,
        "errors": [say(f) for f in flags],        # the numbers don't add up
        "alerts": [say(a) for a in alerts],       # the numbers add up but cost you money
        "questions": [say(q) for q in questions],  # one-time item matches
        "ok": not flags,
        "summary": i18n.t(lang, "clean") if not flags else "",
        "money_found": round(sum(max(0, f.get("diff", 0)) for f in flags if f["code"] == "line_math")
                             + sum(a.get("extra", 0) for a in alerts if a["code"] in ("price_jump", "shrink")), 2),
    }


def confirm(invoice_id: int, cfg: dict, store, item_keys: dict | None = None) -> str:
    """item_keys: {line number: item key} for matches the owner picked or corrected."""
    rec = store.get_invoice(invoice_id)
    inv = rec["inv"]
    for ln in inv["lines"]:
        k = (item_keys or {}).get(str(ln["n"]), (item_keys or {}).get(ln["n"]))
        if k:
            ln["item_key"] = k
    store.confirm(invoice_id, inv)
    lang = cfg["owner_language"]
    return i18n.t(lang, "saved", n=len(inv["lines"]), supplier=inv["supplier"], total=i18n.money(inv["total"], lang))
