"""Turn folders of (image, answer.json) pairs into the JSONL the trainer reads.

  python -m train.prepare_dataset --src data/synth data/real_labeled --out data/ds --val 0.05 --repeat-real 5

Every row: {"image": "<path>", "answer": "<compact JSON>"}. Real invoices are
few, so --repeat-real oversamples anything not under a 'synth' folder.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

KEYS = ["supplier", "invoice_number", "date", "language", "currency", "lines", "subtotal", "taxes", "total"]
LINE_KEYS = ["code", "description", "quantity", "unit", "pack", "unit_price", "line_total"]


def canonical(label: dict) -> str:
    """One fixed key order and spacing, so the model learns one output format."""
    out = {k: label.get(k, "" if k not in ("lines", "taxes") else []) for k in KEYS}
    out["lines"] = [{k: str(ln.get(k) or "") for k in LINE_KEYS} for ln in label.get("lines") or []]
    out["taxes"] = [{"name": str(t.get("name") or ""), "amount": str(t.get("amount") or "")} for t in label.get("taxes") or []]
    for k in ("subtotal", "total", "supplier", "invoice_number", "date", "language", "currency"):
        out[k] = str(out[k] or "")
    return json.dumps(out, ensure_ascii=False, separators=(", ", ": "))


def pairs(folder: Path):
    for img in sorted(folder.rglob("*")):
        if img.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp") or img.stem.endswith("_print"):
            continue
        ans = img.with_suffix(".json")
        if ans.exists():
            yield img, json.loads(ans.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", nargs="+", required=True)
    ap.add_argument("--out", default="data/ds")
    ap.add_argument("--val", type=float, default=0.05)
    ap.add_argument("--repeat-real", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    train, val = [], []
    for src in a.src:
        rows = [{"image": str(img.resolve()), "answer": canonical(lab)} for img, lab in pairs(Path(src))]
        rng.shuffle(rows)
        k = max(1, int(len(rows) * a.val)) if len(rows) > 10 else 0
        val += rows[:k]
        reps = 1 if "synth" in src else a.repeat_real
        train += rows[k:] * reps
        print(f"{src}: {len(rows)} invoices ({k} held out, x{reps} in train)")
    rng.shuffle(train)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in (("train", train), ("val", val)):
        with open(out / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"train {len(train)} rows, val {len(val)} rows -> {out}")


if __name__ == "__main__":
    main()
