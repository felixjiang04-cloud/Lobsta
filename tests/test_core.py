"""Run: python -m pytest -q   (no API key, GPU or network needed)"""
import json
from datetime import date
from pathlib import Path

import pytest

from lobsta import checks, config, frontdesk, matcher, pipeline, reader, stock
from lobsta.parse import parse_number, parse_pack, price_per_kg, unit_cost
from lobsta.store import Store

ROOT = Path(__file__).resolve().parent.parent
TODAY = date(2026, 11, 15)


@pytest.mark.parametrize("raw,hint,want", [
    ("17,50 $", ",", 17.5), ("1 234,56", ",", 1234.56), ("$1,234.56", ".", 1234.56), ("1,234", ".", 1234.0),
    ("1,234", ",", 1.234), ("12,4", ",", 12.4), ("0,5", None, 0.5), ("1.234,50", None, 1234.5),
    ("(12.00)", None, -12.0), ("", None, None), ("n/a", None, None), (7, None, 7.0)])
def test_parse_number(raw, hint, want):
    assert parse_number(raw, hint) == want


@pytest.mark.parametrize("text,key,want", [
    ("Tomates Roma 25 lb", "kg", 11.3398), ("Riz Calrose 4 x 5 kg", "kg", 20.0), ("TOM ROMA 25#", "kg", 11.3398),
    ("金针菇 25 x 200g", "kg", 5.0), ("大白菜 50磅", "kg", 22.6796), ("Sauce soya 6 x 1,8 L", "l", 10.8),
    ("Nori 10/100 g", "kg", 1.0)])
def test_parse_pack(text, key, want):
    assert parse_pack(text)[key] == pytest.approx(want, abs=1e-3)


def test_pack_absent():
    assert parse_pack("Avocat Hass 48 un") is None and parse_pack("香菜 30把") is None


def test_cost_per_kg():
    assert price_per_kg(17.5, "kg", None) == 17.5
    assert price_per_kg(4.5, "lb", None) == pytest.approx(9.92, abs=0.01)
    assert price_per_kg(42, "caisse", parse_pack("25 lb")) == pytest.approx(3.70, abs=0.01)
    assert unit_cost(46, "caisse", None) == (46, "case")


RAW = {"supplier": "X", "invoice_number": "1", "date": "2026-11-01", "language": "fr",
       "lines": [{"description": "Saumon", "quantity": "12,4", "unit": "kg", "unit_price": "17,50", "line_total": "217,00"},
                 {"description": "Nori", "quantity": "10", "unit": "un", "unit_price": "4,50", "line_total": "45,00"}],
       "subtotal": "262,00", "taxes": [{"name": "TPS", "amount": "0,00"}], "total": "262,00"}


def test_checks_clean():
    assert checks.check(checks.normalize(RAW)) == [] and checks.is_clean(RAW)


def test_checks_catch_line_error():
    bad = json.loads(json.dumps(RAW))
    bad["lines"][1]["line_total"] = "54,00"
    flags = checks.check(checks.normalize(bad))
    assert {f["code"] for f in flags} == {"line_math", "subtotal_math"}
    assert next(f for f in flags if f["code"] == "line_math")["diff"] == 9.0
    assert not checks.is_clean(bad)


def test_checks_catch_misread_digit():
    bad = json.loads(json.dumps(RAW))
    bad["lines"][0]["unit_price"] = "11,50"      # a 7 read as a 1
    assert any(f["code"] == "line_math" for f in checks.check(checks.normalize(bad)))


def test_extract_json():
    assert reader.extract_json('Sure!\n```json\n{"a": {"b": "}"}}\n```\nDone')["a"]["b"] == "}"


def test_matcher():
    cfg = config.load("sushi")
    assert matcher.suggest("SAUMON ATL. FRAIS FILET", cfg)[0] == "salmon"
    assert matcher.suggest("Riz Calrose 20 kg", cfg)[0] == "rice"
    assert matcher.suggest("Frais de livraison", cfg)[0] is None
    assert matcher.norm_desc("Riz Calrose 20 kg") == matcher.norm_desc("RIZ CALROSE 18 KG")


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    from scripts.seed_demo import seed
    out = {}
    for prof in ("sushi", "hotpot"):
        db = tmp_path_factory.mktemp(prof) / "t.db"
        seed(prof, TODAY, str(db))
        out[prof] = (config.load(prof), Store(str(db)))
    return out


def run(seeded, prof, stem):
    cfg, st = seeded[prof]
    return pipeline.process(str(ROOT / "demo" / prof / f"{prof}_{stem}.jpg"), cfg, st, which="mock")


def test_demo_price_jump(seeded):
    r = run(seeded, "sushi", "1_fish")
    assert r["ok"] and [a["code"] for a in r["alerts"]] == ["price_jump"]
    a = r["alerts"][0]
    assert a["pct"] == 20.0 and a["extra"] == 43.4 and r["money_found"] == 43.4


def test_demo_shrink_and_math_error(seeded):
    r = run(seeded, "sushi", "2_dry")
    assert not r["ok"] and r["errors"][0]["code"] == "line_math" and r["errors"][0]["diff"] == 9.0
    sh = next(a for a in r["alerts"] if a["code"] == "shrink")
    assert sh["pack_before"] == 20 and sh["pack_now"] == 18 and sh["pct"] == 11.1


def test_demo_clean(seeded):
    for prof in ("sushi", "hotpot"):
        r = run(seeded, prof, "3_clean")
        assert r["ok"] and not r["alerts"] and not r["questions"] and r["money_found"] == 0


def test_demo_hotpot(seeded):
    r = run(seeded, "hotpot", "1_meat")
    a = r["alerts"][0]
    assert a["code"] == "price_jump" and a["per_shown"] == "lb" and a["now_shown"] == 7.9 and a["extra"] == 44.0
    r = run(seeded, "hotpot", "2_veg")
    assert r["errors"][0]["diff"] == 10.0 and any(a["code"] == "shrink" and a["pct"] == 33.3 for a in r["alerts"])


def test_nothing_saved_until_confirmed(seeded):
    cfg, st = seeded["sushi"]
    before = st.spend(None, "2026-11-15", "2026-11-15")["lines"]
    r = run(seeded, "sushi", "3_clean")
    assert st.spend(None, "2026-11-15", "2026-11-15")["lines"] == before
    pipeline.confirm(r["id"], cfg, st)
    assert st.spend(None, "2026-11-15", "2026-11-15")["lines"] == before + 3
    assert any(f["code"] == "duplicate" for f in run(seeded, "sushi", "3_clean")["errors"])


def test_counts_from_speech():
    cfg = config.load("hotpot")
    got = {c["item_key"]: c["qty"] for c in frontdesk.parse_counts("大白菜两箱，金针菇三箱半，肥牛十二公斤", cfg)}
    assert got == {"napa": 45.36, "enoki": 17.5, "beef_roll": 12.0}
    assert frontdesk.cn_number("二十五") == 25 and frontdesk.cn_number("三点五") == 3.5


def test_frontdesk_rules(seeded):
    cfg, st = seeded["hotpot"]
    a = frontdesk.answer_rules("该订什么", cfg, st, TODAY)
    assert a["intent"] == "reorder" and a["actions"][0]["drafts"]
    assert "肥牛卷" in a["text"]
    assert frontdesk.answer_rules("这个月肥牛花了多少", cfg, st, TODAY)["intent"] == "spend"
    assert frontdesk.answer_rules("你好", cfg, st, TODAY)["intent"] == "help"


def test_stock_math(tmp_path):
    cfg = config.load("sushi")
    st = Store(str(tmp_path / "s.db"))
    it = cfg["items_by_key"]["salmon"]
    st.add_count("salmon", 22, "2026-11-12")
    st.add_count("salmon", 9, "2026-11-14")
    s = stock.status(it, st, TODAY)
    assert s["on_hand"] == 9 and s["use_per_day"] == 6.5 and s["days_left"] == 1.4
    plan = stock.reorder(cfg, st, TODAY)
    assert plan["next_delivery"] == "2026-11-17" and plan["lines"][0]["item_key"] == "salmon"


# ---- open-model front desk: the model routes and phrases, code answers and checks ----
def fake_chat(route_json, reply):
    calls = []

    def chat(messages, max_tokens=300):
        calls.append(messages)
        return route_json if len(calls) == 1 else reply
    chat.calls = calls
    return chat


def test_local_frontdesk_uses_model_wording_when_numbers_match(seeded):
    cfg, st = seeded["hotpot"]
    base = frontdesk.answer_rules("x", cfg, st, TODAY, intent="reorder")["text"]
    reply = "老板，" + base + "\n建议今天就把单发出去。"
    a = frontdesk.answer_local("帮我看看要补什么货", cfg, st, TODAY, chat=fake_chat('{"route": "reorder", "item": ""}', reply))
    assert a["via"] == "model" and a["text"] == reply and a["actions"][0]["drafts"]


def test_local_frontdesk_rejects_changed_numbers(seeded):
    cfg, st = seeded["hotpot"]
    base = frontdesk.answer_rules("x", cfg, st, TODAY, intent="stock")["text"]
    a = frontdesk.answer_local("库存怎么样", cfg, st, TODAY, chat=fake_chat('{"route": "stock"}', "肥牛卷还剩 99 公斤，放心。"))
    assert a["via"] == "code-after-check" and a["text"] == base


def test_local_frontdesk_bad_route_falls_back(seeded):
    cfg, st = seeded["hotpot"]
    a = frontdesk.answer_local("该订什么", cfg, st, TODAY, chat=fake_chat("I think you should order beef", "x"))
    assert a["via"] == "rules" and a["intent"] == "reorder"


def test_numbers_ok():
    facts = "Spent this week: $1,146.32. Last week: $848.81. Delivery 2026-11-17."
    assert frontdesk.numbers_ok("1. You spent $1,146.32 this week, up from $848.81.\n2. Next delivery is on the 17.", facts)
    assert frontdesk.numbers_ok("Cette semaine : 1 146,32 $.", facts)
    assert not frontdesk.numbers_ok("You spent $1,146.32, about 35% more than last week.", facts)


def test_compare_and_briefing(seeded):
    cfg, st = seeded["sushi"]
    c = frontdesk.answer_rules("Am I overpaying?", {**cfg, "owner_language": "en"}, st, TODAY)
    assert c["intent"] == "compare" and c["simulated"] and "simulated" in c["text"]
    b = frontdesk.answer_rules("brief me", {**cfg, "owner_language": "en"}, st, TODAY)
    assert b["intent"] == "briefing" and "Spent this week" in b["text"]
