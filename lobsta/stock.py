"""What's left, how fast it goes, and what to order. Arithmetic only.

on hand  = last count + everything received since that count
use/day  = (earlier count + received between the two counts - later count) / days
Until there are two counts, the config's rough daily_use is the fallback.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _d(s: str) -> date:
    return date.fromisoformat(s)


def status(item: dict, store, today: date | None = None) -> dict:
    today = today or date.today()
    cs = store.counts(item["key"], 6)
    out = {"item_key": item["key"], "unit": item.get("base_unit", "kg"), "on_hand": None,
           "use_per_day": item.get("daily_use"), "days_left": None, "par": item.get("par")}
    if not cs:
        return out
    last = cs[0]
    out["on_hand"] = round(last["qty"] + store.received(item["key"], last["date"], today.isoformat()), 2)
    rates = []
    for later, earlier in zip(cs, cs[1:]):
        days = (_d(later["date"]) - _d(earlier["date"])).days
        if days <= 0:
            continue
        used = earlier["qty"] + store.received(item["key"], earlier["date"], later["date"]) - later["qty"]
        if used >= 0:
            rates.append(used / days)
    if rates:
        out["use_per_day"] = round(sum(rates[:3]) / len(rates[:3]), 2)
    if out["use_per_day"]:
        out["days_left"] = round(max(0, out["on_hand"]) / out["use_per_day"], 1)
    return out


def next_delivery(cfg: dict, today: date | None = None, after: int = 0) -> date:
    """The delivery you can still order for. `after`=1 gives the one after that."""
    today = today or date.today()
    days = [DAYS.index(d) for d in cfg.get("delivery_days", ["tue", "fri"])]
    lead = cfg.get("order_lead_days", 1)
    found = []
    for i in range(lead, lead + 15):
        d = today + timedelta(days=i)
        if d.weekday() in days:
            found.append(d)
    return found[min(after, len(found) - 1)]


def reorder(cfg: dict, store, today: date | None = None) -> dict:
    """Items that won't last until the delivery after the next one arrives,
    so they have to go on the next order."""
    today = today or date.today()
    nxt, following = next_delivery(cfg, today), next_delivery(cfg, today, 1)
    cover_days = (following - today).days
    lines = []
    for it in cfg.get("items", []):
        st = status(it, store, today)
        if st["on_hand"] is None or not st["use_per_day"]:
            continue
        need = st["use_per_day"] * cover_days * (1 + cfg.get("safety_pct", 15) / 100)
        if st["on_hand"] >= need:
            continue
        target = max(it.get("par") or 0, need)
        qty = target - st["on_hand"]
        pack = it.get("order_pack") or 1
        qty = math.ceil(qty / pack) * pack
        packs = round(qty / pack, 2) if pack > 1 else None
        lines.append({**st, "order": round(qty, 2), "order_packs": packs, "order_unit": it.get("order_unit", "case"),
                      "supplier": it.get("supplier"),
                      "runs_out": (today + timedelta(days=st["days_left"])).isoformat()})
    lines.sort(key=lambda l: l["days_left"])
    return {"next_delivery": nxt.isoformat(), "lines": lines}


def order_messages(cfg: dict, plan: dict) -> list[dict]:
    """One draft text per supplier, in the supplier's language. Nothing is sent
    by Lobsta: the owner taps the draft and their own phone sends it."""
    from . import i18n
    from .config import item_name
    by: dict[str, list] = {}
    for ln in plan["lines"]:
        by.setdefault(ln["supplier"] or "", []).append(ln)
    sup = {s["name"]: s for s in cfg.get("suppliers", [])}
    hello = {"fr": "Bonjour, commande pour {biz}, livraison {day} :", "en": "Hi, order for {biz}, delivery {day}:",
             "zh": "您好，{biz} 订货，{day} 送："}
    bye = {"fr": "Merci!", "en": "Thanks!", "zh": "谢谢！"}
    out = []
    for name, lines in by.items():
        s = sup.get(name, {})
        lang = s.get("language", "en")
        body = [hello[lang].format(biz=cfg.get("business", ""), day=plan["next_delivery"])]
        for ln in lines:
            body.append(f"- {item_name(cfg, ln['item_key'], lang)}: {i18n.order_text(ln, lang)}")
        body.append(bye[lang])
        out.append({"supplier": name, "phone": s.get("phone", ""), "language": lang, "text": "\n".join(body)})
    return out
