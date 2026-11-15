"""Synthetic invoices with known answers.

  python -m gen.generate --n 3000 --out data/synth            # training set
  python -m gen.generate --n 200 --out data/synth_val --seed 7 # held-out set

Each invoice is img_XXXXX.jpg (looks like a phone photo) plus img_XXXXX.json
(the exact answer, in the reader's output format). 3% of invoices contain a
deliberately wrong line total so the model learns to copy, not to correct.
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

from .augment import phone_photo
from .catalog import CUSTOMERS, PROFILE_SUPPLIERS, SUPPLIERS
from .render import render

MONTHS_FR = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fmt(v: float, lang: str, places: int = 2) -> str:
    s = f"{v:,.{places}f}"
    if lang == "fr":
        s = s.replace(",", " ").replace(".", ",").replace(" ", " ")
    return s


def date_text(d: date, lang: str, rng: random.Random) -> str:
    if lang == "zh":
        return rng.choice([f"{d.year}年{d.month}月{d.day}日", d.isoformat(), f"{d.year}/{d.month:02d}/{d.day:02d}"])
    if lang == "fr":
        return rng.choice([d.isoformat(), f"{d.day:02d}/{d.month:02d}/{d.year}",
                           f"{d.day} {MONTHS_FR[d.month - 1]} {d.year}"])
    return rng.choice([d.isoformat(), f"{MONTHS_EN[d.month - 1]} {d.day}, {d.year}", f"{d.month:02d}/{d.day:02d}/{d.year}"])


CASE_WORD = {"fr": ["caisse", "cs", "cse"], "en": ["case", "cs"], "zh": ["箱"]}
EACH_WORD = {"fr": ["un", "un."], "en": ["ea", "each"], "zh": ["个", "包"]}


def make_invoice(rng: random.Random, supplier_id: str, profile: str, day: date, lang: str | None = None,
                 only: list[str] | None = None, overrides: dict | None = None, n_lines: int | None = None,
                 error_rate: float = 0.0, number: str | None = None, clean_print: bool = False):
    """Returns (label, print_details, meta). overrides: {item_key: {price, pack, qty, unit, bad_total}}."""
    sup = SUPPLIERS[supplier_id]
    lang = lang or rng.choice(sup["langs"])
    overrides = overrides or {}
    prods = [p for p in sup["products"] if lang in p["names"] or "fr" in p["names"] or "zh" in p["names"]]
    if only:
        prods = [next(p for p in sup["products"] if p["key"] == k) for k in only]
    else:
        rng.shuffle(prods)
        prods = prods[: n_lines or rng.randint(2, min(len(prods), 9))]
    upper = (not clean_print) and rng.random() < 0.3
    tight = (not clean_print) and rng.random() < 0.25
    lines, meta_lines, taxable = [], [], 0.0
    for p in prods:
        o = overrides.get(p["key"], {})
        name = p["names"].get(lang) or next(iter(p["names"].values()))
        pack = o.get("pack", p["packs"][0] if clean_print or rng.random() < 0.85 else rng.choice(p["packs"]))
        if lang != "fr":
            pack = pack.replace(",", ".")
        if tight and pack:
            pack = pack.replace(" kg", "kg").replace(" lb", "lb").replace(" g", "g")
        price = o.get("price", round(p["price"] * rng.uniform(0.94, 1.06) / 0.05) * 0.05 if not clean_print else p["price"])
        if p["mode"] == "w":
            unit = o.get("unit", p["unit"])
            if unit == "kg" and lang != "zh" and not clean_print and rng.random() < 0.2:
                unit, price = "lb", price / 2.20462
            qty = o.get("qty", round(rng.uniform(*p["qty"]), rng.choice([1, 2])))
            qty_s = fmt(qty, lang, 2 if round(qty, 1) != qty else 1)
        else:
            unit = o.get("unit", p["unit"] or rng.choice((CASE_WORD if p["mode"] == "c" else EACH_WORD)[lang]))
            qty = o.get("qty", rng.randint(*p["qty"]))
            qty_s = str(int(qty))
        price = round(price, 2)
        total = round(qty * price, 2)
        bad = o.get("bad_total")
        if bad is None and rng.random() < error_rate:
            bad = round(total + rng.choice([-1, 1]) * rng.choice([1, 2, 5, 9, 10, 0.9, 0.1]), 2)
        printed = bad if bad is not None else total
        desc = f"{name} {pack}".strip()
        if upper:
            desc = desc.upper().replace(" X ", " x ")
            pack = pack.upper().replace(" X ", " x ")
        lines.append({"code": p["code"], "description": desc, "quantity": qty_s, "unit": unit, "pack": pack,
                      "unit_price": fmt(price, lang), "line_total": fmt(printed, lang)})
        meta_lines.append({"item_key": p["key"], "true_total": total, "printed_total": printed})
        if p["taxable"]:
            taxable += printed
    subtotal = round(sum(m["printed_total"] for m in meta_lines), 2)
    gst, qst = round(taxable * 0.05, 2), round(taxable * 0.09975, 2)
    names = {"fr": rng.choice([("TPS", "TVQ"), ("TPS 5 %", "TVQ 9,975 %")]),
             "en": rng.choice([("GST", "QST"), ("GST 5%", "QST 9.975%")]),
             "zh": ("GST", "QST")}[lang]
    taxes = [{"name": names[0], "amount": fmt(gst, lang)}, {"name": names[1], "amount": fmt(qst, lang)}]
    if taxable == 0 and not clean_print and rng.random() < 0.3:
        taxes = []
    total = round(subtotal + gst + qst, 2)
    number = number or (rng.choice([sup["prefix"] + "-", sup["prefix"], ""]) + str(rng.randint(10000, 999999)))
    show_code = clean_print or rng.random() < 0.8
    label = {"supplier": sup["name"], "invoice_number": number, "date": day.isoformat(), "language": lang,
             "currency": "CAD",
             "lines": [{**ln, "code": ln["code"] if show_code else ""} for ln in lines],
             "subtotal": fmt(subtotal, lang), "taxes": taxes, "total": fmt(total, lang)}
    cur = {"fr": [("", " $"), ("", "")], "en": [("$", ""), ("", "")], "zh": [("", ""), ("$", "")]}[lang]
    pre, suf = cur[0] if clean_print else rng.choice(cur)
    pr = {"style": sup["style"], "lang": lang, "date_text": day.isoformat() if clean_print else date_text(day, lang, rng),
          "address": sup["address"], "phone": sup["phone"], "customer": CUSTOMERS[profile],
          "cur_prefix": pre, "cur_suffix": suf, "show_code": show_code,
          "stamp": (None if clean_print or rng.random() > 0.25 else {"fr": "REÇU", "en": "RECEIVED", "zh": "已收货"}[lang])}
    meta = {"supplier_id": supplier_id, "profile": profile, "lines": meta_lines}
    return label, pr, meta


def random_invoice(rng: random.Random, error_rate: float = 0.03):
    profile = rng.choice(["sushi", "hotpot"])
    sid = rng.choice(PROFILE_SUPPLIERS[profile])
    day = date(2026, 11, 14) - timedelta(days=rng.randint(0, 400))
    return make_invoice(rng, sid, profile, day, error_rate=error_rate)


def write(label, pr, meta, out: Path, stem: str, rng: random.Random, photo: bool = True, strength: float = 1.0,
          keep_clean: bool = False) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    img = render(label, pr, rng)
    if keep_clean:
        img.save(out / f"{stem}_print.png")
    if photo:
        img = phone_photo(img, rng, strength)
    path = out / f"{stem}.jpg"
    img.save(path, "JPEG", quality=90)
    (out / f"{stem}.json").write_text(json.dumps(label, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / f"{stem}.meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return path


def _one(args):
    i, seed, out, error_rate, clean = args
    rng = random.Random(f"{seed}-{i}")        # per-invoice seed: same output with any number of workers
    label, pr, meta = random_invoice(rng, error_rate)
    write(label, pr, meta, Path(out), f"img_{i:05d}", rng, photo=not clean, strength=rng.uniform(0.5, 1.3))
    return i


def main():
    import os
    from concurrent.futures import ProcessPoolExecutor
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=3000)
    ap.add_argument("--out", default="data/synth")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--error-rate", type=float, default=0.03)
    ap.add_argument("--clean", action="store_true", help="no phone-photo effects")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    a = ap.parse_args()
    jobs = [(i, a.seed, a.out, a.error_rate, a.clean) for i in range(a.n)]
    with ProcessPoolExecutor(a.workers) as ex:
        for done, _ in enumerate(ex.map(_one, jobs, chunksize=8), 1):
            if done % 200 == 0:
                print(f"{done}/{a.n}")
    print("wrote", a.n, "invoices to", a.out)


if __name__ == "__main__":
    main()
