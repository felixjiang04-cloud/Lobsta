"""The front desk: every message from the owner lands here.

With an API key it is a tool-using agent: the model decides which tool to call
and phrases the answer, but every number comes out of a tool (plain code over
the store). Without a key it falls back to keyword rules over the same tools,
so the demo still works offline.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, timedelta

from . import i18n, stock
from .config import item_name
from .matcher import norm_desc

# ---------- spoken counts -> numbers (code, so "六箱" is always 6) ----------
_CN = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "兩": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
          "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "half": 0.5,
          "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "sept": 7, "huit": 8,
          "neuf": 9, "dix": 10, "onze": 11, "douze": 12}


def cn_number(s: str) -> float | None:
    """'六' 6, '十二' 12, '二十五' 25, '一百二十' 120, '三点五' 3.5, '半' 0.5."""
    if not s:
        return None
    if s == "半":
        return 0.5
    if "点" in s:
        a, _, b = s.partition("点")
        whole = cn_number(a) if a else 0
        frac = "".join(str(_CN[c]) for c in b if c in _CN)
        return float(f"{int(whole or 0)}.{frac}") if frac else whole
    total, cur = 0, 0
    for ch in s:
        if ch in _CN:
            cur = _CN[ch]
        elif ch == "十":
            total += (cur or 1) * 10
            cur = 0
        elif ch == "百":
            total += (cur or 1) * 100
            cur = 0
        else:
            return None
    return float(total + cur)


_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?|[零〇一二两兩三四五六七八九十百点半]+|\b(?:" + "|".join(_WORDS) + r")\b", re.I)
_UNIT_AFTER = re.compile(r"\s*(箱|袋|包|瓶|个|個|公斤|斤|磅|kg|kilos?|lbs?|cases?|caisses?|bags?|sacs?|boxes|box)", re.I)
_UNIT_CANON = {"箱": "case", "case": "case", "cases": "case", "caisse": "case", "caisses": "case", "box": "case",
               "boxes": "case", "袋": "bag", "包": "bag", "bag": "bag", "bags": "bag", "sac": "bag", "sacs": "bag",
               "公斤": "kg", "kg": "kg", "kilo": "kg", "kilos": "kg", "斤": "jin", "磅": "lb", "lb": "lb", "lbs": "lb",
               "瓶": "ea", "个": "ea", "個": "ea"}
_TO_KG = {"kg": 1.0, "jin": 0.5, "lb": 0.45359237}


def _num(tok: str) -> float | None:
    tok = tok.lower()
    if tok in _WORDS:
        return float(_WORDS[tok])
    if re.match(r"\d", tok):
        return float(tok.replace(",", "."))
    return cn_number(tok)


def parse_counts(text: str, cfg: dict) -> list[dict]:
    """'六箱番茄，两袋面粉' -> [{'item_key': 'tomato', 'qty': 6 cases in base units}, ...]"""
    out = []
    for clause in re.split(r"[，、;；。\n]|,(?!\d)|(?<!\d)\.|\.(?!\d)|\band\b|\bet\b|还有|和", text):
        low = clause.lower()
        hit = None
        for it in cfg.get("items", []):
            for kw in sorted(it.get("keywords", []), key=len, reverse=True):
                pos = low.find(kw.lower())
                if pos >= 0 and (hit is None or len(kw) > hit[2]):
                    hit = (it, pos, len(kw))
        if not hit:
            continue
        it, pos, klen = hit
        rest = clause[:pos] + " " * klen + clause[pos + klen:]   # don't read digits inside the item name
        nums = [(m, _num(m.group(0))) for m in _NUM_RE.finditer(rest)]
        nums = [(m, v) for m, v in nums if v is not None]
        if not nums:
            continue
        m, val = min(nums, key=lambda mv: min(abs(mv[0].start() - pos), abs(mv[0].end() - pos)))
        um = _UNIT_AFTER.match(rest, m.end())
        said = _UNIT_CANON.get(um.group(1).lower()) if um else None
        if um and rest[um.end():um.end() + 1] == "半":      # 三箱半 = 3.5 cases
            val += 0.5
        base = it.get("base_unit", "kg")
        qty = val
        if said and said != base:
            per = (it.get("count_units") or {}).get(said)
            if per:
                qty = val * per
            elif base == "kg" and said in _TO_KG:
                qty = val * _TO_KG[said]
        out.append({"item_key": it["key"], "qty": round(qty, 2), "said": f"{val:g} {said or base}"})
    return out


# ---------- tools: plain code over the store ----------
def period(text: str, today: date) -> tuple[str, str]:
    t = text.lower()
    if any(k in t for k in ("last month", "上个月", "上個月", "mois dernier", "mois passé")):
        end = today.replace(day=1) - timedelta(days=1)
        return end.replace(day=1).isoformat(), end.isoformat()
    if any(k in t for k in ("this week", "这周", "本周", "這週", "这个星期", "cette semaine")):
        return (today - timedelta(days=today.weekday())).isoformat(), today.isoformat()
    if any(k in t for k in ("last week", "上周", "上个星期", "semaine dernière", "semaine passée")):
        mon = today - timedelta(days=today.weekday() + 7)
        return mon.isoformat(), (mon + timedelta(days=6)).isoformat()
    if any(k in t for k in ("this year", "今年", "cette année")):
        return today.replace(month=1, day=1).isoformat(), today.isoformat()
    if any(k in t for k in ("3 months", "three months", "三个月", "trois mois", "3 mois")):
        return (today - timedelta(days=92)).isoformat(), today.isoformat()
    return today.replace(day=1).isoformat(), today.isoformat()


def find_item(text: str, cfg: dict) -> str | None:
    low, best = text.lower(), None
    for it in cfg.get("items", []):
        for kw in it.get("keywords", []):
            if kw.lower() in low and (best is None or len(kw) > best[1]):
                best = (it["key"], len(kw))
    return best[0] if best else None


class Tools:
    def __init__(self, cfg: dict, store, today: date | None = None):
        self.cfg, self.store, self.today = cfg, store, today or date.today()
        self.lang = cfg["owner_language"]
        self.actions: list[dict] = []

    def get_spend(self, item_key: str | None = None, start: str | None = None, end: str | None = None) -> dict:
        start = start or self.today.replace(day=1).isoformat()
        end = end or self.today.isoformat()
        res = {"start": start, "end": end, **self.store.spend(item_key, start, end)}
        if item_key:
            res["item_key"] = item_key
            res["unit"] = self.cfg["items_by_key"].get(item_key, {}).get("base_unit", "kg")
        else:
            res["top"] = self.store.spend_by_item(start, end)[:3]
        return res

    def get_price_history(self, item_key: str) -> dict:
        h = self.store.price_history(item_key, limit=8)
        return {"item_key": item_key, "history": [
            {"date": r["date"], "unit_cost": r["unit_cost"], "per": r["cost_per"], "supplier": r["supplier"]} for r in h]}

    def get_stock(self, item_key: str | None = None) -> dict:
        items = [self.cfg["items_by_key"][item_key]] if item_key in self.cfg["items_by_key"] else self.cfg["items"]
        return {"stock": [stock.status(it, self.store, self.today) for it in items]}

    def record_counts(self, counts: list[dict]) -> dict:
        saved = []
        for c in counts:
            if c.get("item_key") in self.cfg["items_by_key"]:
                self.store.add_count(c["item_key"], float(c["qty"]), self.today.isoformat())
                saved.append({"item_key": c["item_key"], "qty": float(c["qty"]),
                              "unit": self.cfg["items_by_key"][c["item_key"]].get("base_unit", "kg")})
        return {"saved": saved}

    def adjust_stock(self, changes: list[dict], sign: int) -> dict:
        """'add 34 tomatoes' / 'used 5 kg salmon': on hand goes up or down by that much.
        Code reads the current figure and writes the new count; the model never writes."""
        done = []
        for c in changes:
            it = self.cfg["items_by_key"].get(c.get("item_key"))
            if not it:
                continue
            before = stock.status(it, self.store, self.today)["on_hand"] or 0
            now = round(max(0, before + sign * float(c["qty"])), 2)
            # a count is "what was there at that moment", so store it net of today's receipts
            got_today = self.store.received(it["key"], self.today.isoformat(), self.today.isoformat())
            self.store.add_count(it["key"], round(now - got_today, 2), self.today.isoformat())
            now = stock.status(it, self.store, self.today)["on_hand"]
            done.append({"item_key": it["key"], "qty": float(c["qty"]), "now": now, "unit": it.get("base_unit", "kg")})
        return {"changed": done, "sign": sign}

    def get_reorder_plan(self) -> dict:
        plan = stock.reorder(self.cfg, self.store, self.today)
        drafts = stock.order_messages(self.cfg, plan)
        if drafts:
            self.actions.append({"type": "order_drafts", "drafts": drafts})
        return {**plan, "drafts": drafts}

    def compare_prices(self, item_key: str | None = None) -> dict:
        from . import benchmark
        return benchmark.compare(self.cfg, self.store, item_key if item_key in self.cfg["items_by_key"] else None)

    def get_briefing(self) -> dict:
        """What a good secretary would say first thing: what runs out, what went wrong, what was spent."""
        mon = self.today - timedelta(days=self.today.weekday())
        plan = stock.reorder(self.cfg, self.store, self.today)
        flags = self.store.recent_flags((self.today - timedelta(days=6)).isoformat())
        worth = sum(max(0, f["flag"].get("diff", 0)) if f["flag"]["code"] == "line_math" else f["flag"].get("extra", 0)
                    for f in flags)
        return {"reorder": plan, "flags": flags, "flags_total": round(worth, 2),
                "spend_this_week": self.store.spend(None, mon.isoformat(), self.today.isoformat())["total"],
                "spend_last_week": self.store.spend(None, (mon - timedelta(days=7)).isoformat(),
                                                    (mon - timedelta(days=1)).isoformat())["total"]}


# ---------- offline: keyword rules ----------
_INTENTS = [
    ("briefing", ("brief", "summary", "今天要注意", "汇报", "早报", "总结", "résumé", "resume", "quoi de neuf", "what's new")),
    ("compare", ("overpay", "别家", "别的店", "买贵", "贵不贵", "market", "benchmark", "compare", "other shops", "trop cher",
                 "autres commerces", "comparer")),
    ("reorder", ("订", "訂", "order", "commander", "commande", "补货", "run out", "用完", "缺")),
    ("stock", ("还剩", "還剩", "库存", "庫存", "剩", "left", "stock", "reste", "inventory", "on hand")),
    ("price", ("价格", "價格", "涨", "price", "prix", "多少钱一")),
    ("spend", ("花", "spend", "spent", "dépens", "depens", "cost", "多少钱", "combien")),
]


_ADD = re.compile(r"\b(add|added|received|got|plus|ajoute[rz]?|ajouté|reçu)\b|加|进了|到了|收到|多了", re.I)
_USE = re.compile(r"\b(used|use up|remove|removed|minus|threw|wasted|utilisé|enlève|retire|jeté)\b|用了|用掉|扔了|减|少了", re.I)


def answer_rules(text: str, cfg: dict, store, today: date | None = None, intent: str | None = None,
                 key: str | None = None) -> dict:
    """Code-written answers. `intent` (and `key`) can be forced by a model that only chose the tool."""
    tools = Tools(cfg, store, today)
    lang, low = tools.lang, text.lower()
    m = lambda v: i18n.money(v, lang)
    name = lambda k: item_name(cfg, k, lang)
    uw = lambda u, q=None: i18n.unit_word(u, lang, q)
    forced = intent is not None
    sign = 1 if _ADD.search(low) else -1 if _USE.search(low) else 0
    if sign and intent in (None, "count", "help", "stock", "reorder"):
        changes = parse_counts(text, cfg)
        if changes:
            done = tools.adjust_stock(changes, sign)["changed"]
            lines = [i18n.t(lang, "adj_line", item=name(d["item_key"]), sign="+" if sign > 0 else "-", qty=d["qty"],
                            unit=uw(d["unit"], d["qty"]), now=d["now"], unit_now=uw(d["unit"], d["now"])) for d in done]
            return {"text": "\n".join(lines), "actions": [], "intent": "adjust", "changed": done}
    if not forced:
        intent = next((n for n, kws in _INTENTS if any(k in low for k in kws)), None)
    if intent in (None, "count", "help"):
        counts = parse_counts(text, cfg)
        if counts:
            saved = tools.record_counts(counts)["saved"]
            items = "、".join(f"{name(s['item_key'])} {s['qty']:g} {uw(s['unit'], s['qty'])}" for s in saved) if lang == "zh" \
                else ", ".join(f"{name(s['item_key'])} {s['qty']:g} {uw(s['unit'], s['qty'])}" for s in saved)
            return {"text": i18n.t(lang, "counted", items=items), "actions": [], "intent": "count"}
        return {"text": i18n.t(lang, "help"), "actions": [], "intent": "help"}
    key = key if key in cfg["items_by_key"] else find_item(text, cfg)
    if intent == "compare":
        r = tools.compare_prices(key)
        if not r["rows"]:
            return {"text": i18n.t(lang, "cmp_none"), "actions": [], "intent": intent}
        lines = [i18n.t(lang, "cmp_head", shops=r["shops"], area=r["area"], sim=i18n.t(lang, "cmp_sim") if r["simulated"] else "")]
        for row in r["rows"][:6]:
            lines.append(i18n.t(lang, "cmp_line", item=name(row["item_key"]), mine=m(row["mine"]), median=m(row["median"]),
                                per=uw(row["per"]), pct=f"{row['pct']:+g}")
                         + (i18n.t(lang, "cmp_high") if row["band"] == "high" else i18n.t(lang, "cmp_low") if row["band"] == "low" else ""))
        return {"text": "\n".join(lines), "actions": [], "intent": intent, "simulated": r["simulated"]}
    if intent == "briefing":
        b = tools.get_briefing()
        plan = b["reorder"]
        lines = [i18n.t(lang, "brief_order", n=len(plan["lines"]), day=plan["next_delivery"],
                        items=("、" if lang == "zh" else ", ").join(name(l["item_key"]) for l in plan["lines"]))
                 if plan["lines"] else i18n.t(lang, "brief_order_none")]
        if b["flags"]:
            lines.append(i18n.t(lang, "brief_flags", total=m(b["flags_total"])))
            lines += ["- " + i18n.flag_text(f["flag"], f["inv"], cfg, lang) for f in b["flags"][:4]]
        else:
            lines.append(i18n.t(lang, "brief_flags_none"))
        lines.append(i18n.t(lang, "brief_spend", this=m(b["spend_this_week"]), last=m(b["spend_last_week"])))
        return {"text": "\n".join(lines), "actions": [], "intent": intent}
    if intent == "spend":
        start, end = period(text, tools.today)
        r = tools.get_spend(key, start, end)
        if not r["lines"]:
            return {"text": i18n.t(lang, "no_data"), "actions": [], "intent": intent}
        if key:
            txt = i18n.t(lang, "spend", total=m(r["total"]), item=name(key), start=start, end=end,
                         qty=r["qty"], unit=uw(r["unit"], r["qty"]))
        else:
            top = ", ".join(f"{name(x['item_key'])} {m(x['total'])}" for x in r["top"])
            txt = i18n.t(lang, "spend_all", total=m(r["total"]), start=start, end=end, top=top)
        return {"text": txt, "actions": [], "intent": intent}
    if intent == "price":
        if not key:
            return {"text": i18n.t(lang, "help"), "actions": [], "intent": intent}
        h = tools.get_price_history(key)["history"]
        if not h:
            return {"text": i18n.t(lang, "no_data"), "actions": [], "intent": intent}
        pts = " → ".join(f"{r['date'][5:]} {m(r['unit_cost'])}/{uw(r['per'])}" for r in reversed(h))
        return {"text": i18n.t(lang, "price_hist", item=name(key), points=pts), "actions": [], "intent": intent,
                "chart": [{"date": r["date"], "value": r["unit_cost"]} for r in reversed(h)]}
    if intent == "stock":
        rows = tools.get_stock(key)["stock"]
        if not key:
            rows = [s for s in rows if s["on_hand"] is not None]
            if not rows:
                return {"text": i18n.t(lang, "stock_none"), "actions": [], "intent": intent}
            rows.sort(key=lambda s: s["days_left"] if s["days_left"] is not None else 1e9)
        lines = [i18n.t(lang, "stock_line", item=name(s["item_key"]), on_hand=s["on_hand"], unit=uw(s["unit"], s["on_hand"]),
                        days=f"{s['days_left']:g}" if s["days_left"] is not None else "?")
                 if s["on_hand"] is not None else i18n.t(lang, "stock_unknown", item=name(s["item_key"]))
                 for s in rows]
        return {"text": "\n".join(lines), "actions": [], "intent": intent, "stock": rows}
    plan = tools.get_reorder_plan()
    if not plan["lines"]:
        return {"text": i18n.t(lang, "reorder_none"), "actions": [], "intent": "reorder"}
    lines = [i18n.t(lang, "reorder_head", day=plan["next_delivery"])]
    lines += [i18n.t(lang, "reorder_line", item=name(l["item_key"]), on_hand=l["on_hand"], unit=uw(l["unit"], l["on_hand"]),
                     days=f"{l['days_left']:g}", order=i18n.order_text(l, lang)) for l in plan["lines"]]
    return {"text": "\n".join(lines), "actions": tools.actions, "intent": "reorder"}


# ---------- online: tool-using agent ----------
TOOL_SPECS = [
    {"name": "get_spend", "description": "Total spent and quantity bought in a date range, for one item or overall.",
     "input_schema": {"type": "object", "properties": {
         "item_key": {"type": "string", "description": "Item key, omit for all items"},
         "start": {"type": "string", "description": "YYYY-MM-DD"}, "end": {"type": "string", "description": "YYYY-MM-DD"}}}},
    {"name": "get_price_history", "description": "Recent cost per kg (or per unit) for one item, newest first.",
     "input_schema": {"type": "object", "properties": {"item_key": {"type": "string"}}, "required": ["item_key"]}},
    {"name": "get_stock", "description": "On-hand quantity, daily use and days left, for one item or all.",
     "input_schema": {"type": "object", "properties": {"item_key": {"type": "string"}}}},
    {"name": "record_counts", "description": "Save the owner's closing stock counts. qty is in the item's base unit.",
     "input_schema": {"type": "object", "properties": {"counts": {"type": "array", "items": {
         "type": "object", "properties": {"item_key": {"type": "string"}, "qty": {"type": "number"}},
         "required": ["item_key", "qty"]}}}, "required": ["counts"]}},
    {"name": "compare_prices", "description": "Compare the shop's latest prices with the median across other shops. "
     "The result says whether the network data is simulated; if it is, say so.",
     "input_schema": {"type": "object", "properties": {"item_key": {"type": "string"}}}},
    {"name": "get_briefing", "description": "What needs attention today: items running out, problems found on this "
     "week's invoices, and spend this week against last week.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_reorder_plan", "description": "Items that will run out before the delivery after next, with a "
     "draft order message per supplier. The owner sends the draft themselves; you never send anything.",
     "input_schema": {"type": "object", "properties": {}}},
]


def _system(cfg: dict, today: date) -> str:
    lang = {"zh": "Simplified Chinese", "fr": "French", "en": "English"}.get(cfg["owner_language"], "English")
    items = "\n".join(f"- {it['key']}: {' / '.join(it.get('name', {}).values())} (base unit {it.get('base_unit', 'kg')}"
                      + (f", {json.dumps(it['count_units'], ensure_ascii=False)} base units per spoken unit" if it.get("count_units") else "")
                      + ")" for it in cfg["items"])
    return f"""You are the front desk of Lobsta, an inventory helper for {cfg.get('business', 'a small restaurant')}.
Today is {today.isoformat()} ({today.strftime('%A')}). Reply in {lang}, in one to three short sentences a busy owner can read at a glance.
Every number you say must come from a tool result in this conversation. Never estimate, never do arithmetic
on your own beyond what a tool returned, and if a tool has no data say so plainly.
When the owner dictates closing counts, convert them to each item's base unit and call record_counts.
When asked what to order, call get_reorder_plan and summarise it; the app shows the draft messages.
Items:
{items}"""


def answer_agent(text: str, cfg: dict, store, today: date | None = None, history: list | None = None) -> dict:
    import anthropic
    tools = Tools(cfg, store, today)
    client = anthropic.Anthropic()
    msgs = list(history or []) + [{"role": "user", "content": text}]
    for _ in range(6):
        resp = client.messages.create(
            model=os.environ.get("LOBSTA_CHAT_MODEL", "claude-haiku-5-5"), max_tokens=1024,
            system=_system(cfg, tools.today), tools=TOOL_SPECS, messages=msgs)
        if resp.stop_reason != "tool_use":
            return {"text": "".join(b.text for b in resp.content if b.type == "text").strip(),
                    "actions": tools.actions, "intent": "agent"}
        msgs.append({"role": "assistant", "content": resp.content})
        results = []
        for b in resp.content:
            if b.type == "tool_use":
                try:
                    out = getattr(tools, b.name)(**(b.input or {}))
                except Exception as e:
                    out = {"error": str(e)}
                results.append({"type": "tool_result", "tool_use_id": b.id,
                                "content": json.dumps(out, ensure_ascii=False)})
        msgs.append({"role": "user", "content": results})
    return {"text": i18n.t(cfg["owner_language"], "help"), "actions": tools.actions, "intent": "agent"}


# ---------- open model: it routes and phrases, code answers and checks ----------
ROUTES = {
    "briefing": "a summary of what needs attention today",
    "compare": "how the shop's prices compare with other shops, or whether it is overpaying",
    "reorder": "what to order, what will run out, drafting a supplier order",
    "stock": "how much of something is left, inventory on hand",
    "price": "the price history of ONE named item",
    "spend": "how much money was spent, on one item or overall",
    "count": "the owner is REPORTING quantities counted at closing (not asking)",
    "chat": "anything else: greetings, advice, how-to questions, thanks",
}
_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def llm_chat(messages: list[dict], max_tokens: int = 300) -> str:
    """Text-only call to the open model on the GPU box (same server as the invoice reader)."""
    import httpx
    base = os.environ.get("LOBSTA_CHAT_URL") or os.environ.get("LOBSTA_LOCAL_URL", "http://localhost:8000/v1")
    r = httpx.post(base.rstrip("/") + "/chat/completions", timeout=60,
                   headers={"Authorization": f"Bearer {os.environ.get('LOBSTA_LOCAL_KEY', 'none')}"},
                   json={"model": os.environ.get("LOBSTA_LOCAL_MODEL", "lobsta-reader"), "temperature": 0,
                         "max_tokens": max_tokens, "adapter": False, "messages": messages})
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _numbers(text: str) -> set[float]:
    t = re.sub(r"(?m)^\s*\d+[.)、]\s", "", text)                        # list markers "1. " are not data
    t = re.sub(r"(?<=\d)[,\u00a0 ](?=\d{3}(?!\d))", "", t)             # 1,146.32 and 1 146,32 -> 1146.32
    out = set()
    for tok in _NUM.findall(t):
        try:
            out.add(round(float(tok.replace(",", ".")), 2))
        except ValueError:
            pass
    return out


def numbers_ok(reply: str, *sources: str) -> bool:
    """Every number the model wrote must already appear in what code produced
    (or in what the owner typed). Otherwise the model's wording is discarded."""
    allowed = set()
    for src in sources:
        allowed |= _numbers(src)
    return _numbers(reply) <= allowed


def answer_local(text: str, cfg: dict, store, today: date | None = None, chat=llm_chat) -> dict:
    lang = cfg["owner_language"]
    lang_name = {"zh": "Simplified Chinese", "fr": "French", "en": "English"}.get(lang, "English")
    items = "; ".join(f"{it['key']} = {' / '.join(it.get('name', {}).values())}" for it in cfg["items"])
    routes = "\n".join(f"- {k}: {v}" for k, v in ROUTES.items())
    raw = chat([{"role": "system", "content":
                 "You route a restaurant owner's message to one route. Reply with ONE JSON object and nothing else: "
                 '{"route": "<name>", "item": "<item key or empty>"}\nRoutes:\n' + routes + "\nItem keys: " + items},
                {"role": "user", "content": text}], max_tokens=40)
    try:
        from .reader import extract_json
        choice = extract_json(raw)
    except Exception:
        choice = {}
    route, key = choice.get("route"), choice.get("item") or None
    if route not in ROUTES:
        return {**answer_rules(text, cfg, store, today), "via": "rules"}
    if route == "chat":
        reply = chat([{"role": "system", "content":
                       f"You are the front desk of Lobsta, a helpful secretary for {cfg.get('business', 'a small restaurant')}. "
                       f"Reply in {lang_name}, two or three short sentences, practical and warm. You have no access to the "
                       "shop's numbers in this message, so do not state any prices, quantities or totals; if the owner "
                       "wants those, tell them to ask what's left, what to order, what was spent, or for a briefing."},
                      {"role": "user", "content": text}], max_tokens=200)
        return {"text": reply, "actions": [], "intent": "chat", "via": "model"}
    base = answer_rules(text, cfg, store, today, intent=route, key=key)      # numbers come from here
    if base["intent"] in ("help", "count") or len(base["text"]) < 12:
        return {**base, "via": "code"}
    try:
        reply = chat([{"role": "system", "content":
                       f"You are the front desk of Lobsta, a secretary for {cfg.get('business', 'a small restaurant')}. "
                       f"Rewrite the FACTS below as a reply to the owner in {lang_name}: natural, brief, most urgent first. "
                       "Copy every number, price, date and unit exactly as written. Do not add, convert, round or "
                       "calculate any number. End with one short practical suggestion that follows from the facts."},
                      {"role": "user", "content": f"Owner asked: {text}\n\nFACTS:\n{base['text']}"}], max_tokens=320)
    except Exception as e:
        print("model phrasing failed, using code text:", e)
        return {**base, "via": "code"}
    if reply and numbers_ok(reply, base["text"], text):
        return {**base, "text": reply, "facts": base["text"], "via": "model"}
    return {**base, "via": "code-after-check"}       # the model changed a number: show the code's wording


def chat_mode() -> str:
    mode = os.environ.get("LOBSTA_CHAT")
    if mode in ("rules", "local", "agent"):
        return mode
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "agent"
    return "local" if os.environ.get("LOBSTA_READER") == "local" or os.environ.get("LOBSTA_CHAT_URL") else "rules"


def answer(text: str, cfg: dict, store, today: date | None = None, history: list | None = None) -> dict:
    mode = chat_mode()
    try:
        if mode == "agent":
            return answer_agent(text, cfg, store, today, history)
        if mode == "local":
            return answer_local(text, cfg, store, today)
    except Exception as e:
        print(f"{mode} front desk failed, using rules:", e)
    return {**answer_rules(text, cfg, store, today), "via": "rules"}
