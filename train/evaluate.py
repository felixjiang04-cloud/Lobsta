"""Score readers against invoices with known answers. This produces the number
for the slide: "our model on one gaming GPU vs the big API model".

  python -m train.evaluate --data data/mum/val --backends anthropic local
  python -m train.evaluate --data data/synth_val --backends local --local-url http://localhost:8000/v1
  python -m train.evaluate --data data/synth_val --backends mock noisy      # offline sanity check

Backends: anthropic | local (LOBSTA_LOCAL_URL) | local:<url> | mock | noisy (mock + random digit
errors, to show what the math check catches). Outputs are cached per backend in <data>/.eval/.

What is measured, per backend:
  numbers   share of numeric fields (qty, unit price, line total, subtotal, total) read exactly
  lines     share of lines with every number right
  invoices  share of invoices with every number right
  text      average similarity of descriptions (1.0 = identical)
  caught    of the invoices read wrong, how many the math check flagged
  silent    invoices read wrong AND passing the math check (the dangerous kind)
"""
from __future__ import annotations

import argparse
import difflib
import json
import random
import time
from pathlib import Path

from lobsta import checks, reader
from lobsta.parse import norm_unit
from train.prepare_dataset import pairs


def noisy(label: dict, rng: random.Random, p: float = 0.5) -> dict:
    """Simulate an imperfect reader: change one digit in one number, half the time."""
    out = json.loads(json.dumps(label))
    if rng.random() < p and out["lines"]:
        ln = rng.choice(out["lines"])
        field = rng.choice(["quantity", "unit_price", "line_total"])
        digits = [i for i, c in enumerate(ln[field]) if c.isdigit()]
        if digits:
            i = rng.choice(digits)
            new = rng.choice([c for c in "0123456789" if c != ln[field][i]])
            ln[field] = ln[field][:i] + new + ln[field][i + 1:]
    return out


def run_backend(name: str, img: Path, label: dict, rng: random.Random) -> dict:
    if name == "mock":
        return label
    if name == "noisy":
        return noisy(label, rng)
    if name.startswith("local:"):
        return reader.read_local(str(img), base_url=name.split(":", 1)[1])
    return reader.read_invoice(str(img), name)


def score(pred_raw: dict | None, gold_raw: dict) -> dict:
    gold = checks.normalize(gold_raw)
    s = {"num_ok": 0, "num_n": 0, "line_ok": 0, "line_n": len(gold["lines"]), "text": [], "unit_ok": 0,
         "header_ok": 0, "header_n": 3, "all_ok": False, "flagged": True, "parsed": pred_raw is not None}
    for k in ("subtotal", "total"):
        s["num_n"] += gold[k] is not None
    s["num_n"] += 3 * len(gold["lines"])
    if pred_raw is None:
        return s
    pred = checks.normalize(pred_raw)
    s["flagged"] = bool(checks.check(pred))
    eq = lambda a, b: a is not None and b is not None and abs(a - b) < 0.006
    for k in ("subtotal", "total"):
        if gold[k] is not None:
            s["num_ok"] += eq(pred[k], gold[k])
    for i, g in enumerate(gold["lines"]):
        p = pred["lines"][i] if i < len(pred["lines"]) else None
        if not p:
            continue
        oks = [eq(p[f], g[f]) for f in ("quantity", "unit_price", "line_total")]
        s["num_ok"] += sum(oks)
        s["line_ok"] += all(oks)
        s["unit_ok"] += norm_unit(p["unit"]) == norm_unit(g["unit"])
        s["text"].append(difflib.SequenceMatcher(None, p["description"].lower(), g["description"].lower()).ratio())
    s["header_ok"] = sum([pred["supplier"].lower() == gold["supplier"].lower(),
                          pred["invoice_number"] == gold["invoice_number"], pred["date"] == gold["date"]])
    s["all_ok"] = s["num_ok"] == s["num_n"] and len(pred["lines"]) == len(gold["lines"])
    return s


def evaluate(data: Path, backends: list[str], limit: int | None = None, seed: int = 0) -> dict:
    items = list(pairs(data))[:limit]
    if not items:
        raise SystemExit(f"no (image, .json) pairs in {data}")
    results = {}
    for b in backends:
        cache = data / ".eval" / b.replace("/", "_").replace(":", "_")
        cache.mkdir(parents=True, exist_ok=True)
        rng = random.Random(seed)
        tot = {"n": 0, "num_ok": 0, "num_n": 0, "line_ok": 0, "line_n": 0, "text": [], "unit_ok": 0, "header_ok": 0,
               "header_n": 0, "inv_ok": 0, "wrong": 0, "caught": 0, "silent": 0, "unparsed": 0, "secs": []}
        for img, gold in items:
            cf = cache / (img.stem + ".json")
            if cf.exists() and b not in ("mock", "noisy"):
                rec = json.loads(cf.read_text(encoding="utf-8"))
            else:
                t0 = time.time()
                try:
                    pred = run_backend(b, img, gold, rng)
                except Exception as e:
                    print(f"  [{b}] {img.name}: {e}")
                    pred = None
                rec = {"pred": pred, "seconds": round(time.time() - t0, 2)}
                cf.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
            s = score(rec["pred"], gold)
            tot["n"] += 1
            for k in ("num_ok", "num_n", "line_ok", "line_n", "unit_ok", "header_ok", "header_n"):
                tot[k] += s[k]
            tot["text"] += s["text"]
            tot["inv_ok"] += s["all_ok"]
            tot["unparsed"] += not s["parsed"]
            tot["secs"].append(rec["seconds"])
            if not s["all_ok"]:
                tot["wrong"] += 1
                tot["caught" if s["flagged"] else "silent"] += 1
        pct = lambda a, n: round(100 * a / n, 1) if n else None
        results[b] = {
            "invoices_scored": tot["n"], "numbers_pct": pct(tot["num_ok"], tot["num_n"]),
            "lines_pct": pct(tot["line_ok"], tot["line_n"]), "invoices_pct": pct(tot["inv_ok"], tot["n"]),
            "text_similarity": round(sum(tot["text"]) / len(tot["text"]), 3) if tot["text"] else None,
            "units_pct": pct(tot["unit_ok"], tot["line_n"]), "header_pct": pct(tot["header_ok"], tot["header_n"]),
            "wrong": tot["wrong"], "caught_by_math": tot["caught"], "silent": tot["silent"],
            "unparsed": tot["unparsed"], "median_seconds": sorted(tot["secs"])[len(tot["secs"]) // 2]}
    return results


def table(results: dict) -> str:
    cols = [("numbers_pct", "Numbers %"), ("lines_pct", "Lines %"), ("invoices_pct", "Invoices %"),
            ("text_similarity", "Text sim"), ("wrong", "Read wrong"), ("caught_by_math", "Caught by math"),
            ("silent", "Silent"), ("median_seconds", "Sec/invoice")]
    out = ["| Reader | " + " | ".join(c[1] for c in cols) + " |", "|---|" + "---|" * len(cols)]
    for b, r in results.items():
        out.append(f"| {b} | " + " | ".join(str(r[c[0]]) for c in cols) + " |")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True)
    ap.add_argument("--backends", nargs="+", default=["anthropic", "local"])
    ap.add_argument("--local-url")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.local_url:
        import os
        os.environ["LOBSTA_LOCAL_URL"] = a.local_url
    res = evaluate(Path(a.data), a.backends, a.limit)
    n = next(iter(res.values()))["invoices_scored"]
    print(f"\n{n} invoices from {a.data}\n")
    print(table(res))
    out = Path(a.out or Path(a.data) / "eval_results.json")
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("\nsaved", out)


if __name__ == "__main__":
    main()
