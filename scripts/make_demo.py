"""Build the demo story for one restaurant: weeks of ordinary invoices, then
today's invoices with three things planted for Lobsta to catch.

  python -m scripts.make_demo --profile sushi --today 2026-11-15

Writes demo/<profile>/history/*.json (past invoices, answers only) and
demo/<profile>/*.jpg (today's invoices as phone photos) with *_print.png
versions to print on paper and photograph live.
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
from datetime import date, timedelta
from pathlib import Path

from gen.generate import make_invoice, write

ROOT = Path(__file__).resolve().parent.parent

HERO = {"salmon", "rice", "nori", "beef_roll", "enoki", "napa"}

STORY = {
 "sushi": dict(
    history=[  # (supplier, every N days, first offset in days before today, items, overrides)
      ("baie_nord", 7, 5, ["salmon", "tuna", "tobiko"], {"salmon": {"price": 17.50}, "tuna": {"price": 34.00}, "tobiko": {"price": 21.50}}),
      ("asie_quebec", 14, 9, ["rice", "nori", "soy_sauce"], {"rice": {"price": 38.50, "pack": "20 kg"}, "nori": {"price": 4.50}, "soy_sauce": {"price": 44.00}}),
      ("marche_soleil", 7, 4, ["avocado", "cucumber", "mango"], {"avocado": {"price": 46.00}, "cucumber": {"price": 22.50}, "mango": {"price": 14.00}}),
    ],
    today=[
      ("1_fish", "baie_nord", "fr", ["salmon", "tuna", "tobiko"],
       {"salmon": {"price": 21.00, "qty": 12.4}, "tuna": {"price": 34.00, "qty": 3.2}, "tobiko": {"price": 21.50, "qty": 2}},
       "Salmon is $21.00/kg after ten weeks at $17.50: +20%, $43.40 extra today."),
      ("2_dry", "asie_quebec", "fr", ["rice", "nori", "soy_sauce"],
       {"rice": {"price": 38.50, "pack": "18 kg", "qty": 4}, "nori": {"price": 4.50, "qty": 10, "bad_total": 54.00},
        "soy_sauce": {"price": 44.00, "qty": 1}},
       "Rice bag shrank from 20 kg to 18 kg at the same price (hidden +11.1%). Nori line says 10 x 4.50 = 54.00, should be 45.00."),
      ("3_clean", "marche_soleil", "fr", ["avocado", "cucumber", "mango"],
       {"avocado": {"price": 46.00, "qty": 2}, "cucumber": {"price": 22.50, "qty": 2}, "mango": {"price": 14.00, "qty": 3}},
       "Nothing wrong: shows the quiet path, one tap to save."),
    ],
    counts={-3: {"salmon": 22, "rice": 70, "avocado": 2.5, "nori": 14}, -1: {"salmon": 9, "rice": 46, "avocado": 2, "nori": 9}}),
 "hotpot": dict(
    history=[
      ("hong_yun", 4, 4, ["beef_roll", "lamb_roll", "fish_ball"], {"beef_roll": {"price": 6.80}, "lamb_roll": {"price": 8.20}, "fish_ball": {"price": 36.00}}),
      ("xin_xian", 4, 5, ["napa", "enoki", "tofu"], {"napa": {"price": 26.00, "pack": "50磅"}, "enoki": {"price": 18.00, "pack": "25 x 200g"}, "tofu": {"price": 19.00}}),
      ("long_ji", 14, 8, ["soup_base", "wide_noodle", "oil"], {"soup_base": {"price": 78.00}, "wide_noodle": {"price": 34.00}, "oil": {"price": 46.00}}),
    ],
    today=[
      ("1_meat", "hong_yun", "zh", ["beef_roll", "lamb_roll", "fish_ball"],
       {"beef_roll": {"price": 7.90, "qty": 40.0}, "lamb_roll": {"price": 8.20, "qty": 20.0}, "fish_ball": {"price": 36.00, "qty": 2}},
       "Beef rolls are $7.90/lb after weeks at $6.80: +16.2%, $44.00 extra today."),
      ("2_veg", "xin_xian", "zh", ["napa", "enoki", "tofu"],
       {"napa": {"price": 26.00, "pack": "50磅", "qty": 2, "bad_total": 62.00},
        "enoki": {"price": 18.00, "pack": "25 x 150g", "qty": 3}, "tofu": {"price": 19.00, "qty": 2}},
       "Enoki went from 25 x 200g to 25 x 150g at the same price (hidden +33.3%). Napa line says 2 x 26.00 = 62.00, should be 52.00."),
      ("3_clean", "long_ji", "zh", ["soup_base", "wide_noodle", "oil"],
       {"soup_base": {"price": 78.00, "qty": 2}, "wide_noodle": {"price": 34.00, "qty": 1}, "oil": {"price": 46.00, "qty": 1}},
       "Nothing wrong: shows the quiet path, one tap to save."),
    ],
    counts={-3: {"beef_roll": 25, "napa": 30, "enoki": 8, "soup_base": 14}, -1: {"beef_roll": 12, "napa": 14, "enoki": 6, "soup_base": 11}}),
}


def build(profile: str, today: date, weeks: int = 10, out: Path | None = None) -> dict:
    out = out or ROOT / "demo" / profile
    if out.exists():
        shutil.rmtree(out)
    (out / "history").mkdir(parents=True)
    rng = random.Random(f"{profile}-{today.isoformat()}")
    story = STORY[profile]
    n = 0
    for sid, every, first, items, ov in story["history"]:
        d = today - timedelta(days=first)
        while d >= today - timedelta(days=weeks * 7):
            # the items the story is about keep a flat price so the alert reads cleanly on stage
            wob = {k: v if k in HERO else {**v, "price": round(v["price"] * rng.uniform(0.98, 1.02) / 0.05) * 0.05}
                   for k, v in ov.items()}
            label, _, _ = make_invoice(rng, sid, profile, d, lang=None, only=items, overrides=wob, clean_print=True)
            (out / "history" / f"{d.isoformat()}_{sid}.json").write_text(
                json.dumps(label, ensure_ascii=False, indent=1), encoding="utf-8")
            n += 1
            d -= timedelta(days=every)
    notes = {}
    for stem, sid, lang, items, ov, note in story["today"]:
        label, pr, meta = make_invoice(rng, sid, profile, today, lang=lang, only=items, overrides=ov, clean_print=True)
        write(label, pr, meta, out, f"{profile}_{stem}", rng, photo=True, strength=0.55, keep_clean=True)
        notes[f"{profile}_{stem}.jpg"] = note
    (out / "counts.json").write_text(json.dumps(story["counts"]), encoding="utf-8")
    (out / "NOTES.json").write_text(json.dumps({"today": today.isoformat(), "planted": notes}, indent=1), encoding="utf-8")
    return {"history": n, "today": list(notes)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="all")
    ap.add_argument("--today", default=date.today().isoformat())
    a = ap.parse_args()
    for p in (STORY if a.profile == "all" else [a.profile]):
        print(p, build(p, date.fromisoformat(a.today)))
