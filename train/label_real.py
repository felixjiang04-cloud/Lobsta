"""Label real invoice photos with the big API model, and keep only the labels
whose arithmetic checks out. The math check is the free label checker: a
misread digit almost always breaks qty x price = total or the sum of lines.

  export ANTHROPIC_API_KEY=...
  python -m train.label_real --photos data/mum --hold-out 10

Result:
  data/mum/labeled/        photo + .json, math-clean  -> training data
  data/mum/needs_review/   photo + .json, math failed -> fix by hand or skip
  data/mum/val/            the held-out photos        -> CHECK THESE BY HAND,
                           they are what you score the models against.
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path

from lobsta import checks, reader


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--photos", required=True)
    ap.add_argument("--hold-out", type=int, default=10)
    ap.add_argument("--backend", default="anthropic")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    root = Path(a.photos)
    photos = sorted(p for p in root.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".heic"))
    if any(p.suffix.lower() == ".heic" for p in photos):
        print("HEIC photos found: convert to JPG first (iPhone: Settings > Camera > Formats > Most Compatible).")
        photos = [p for p in photos if p.suffix.lower() != ".heic"]
    random.Random(a.seed).shuffle(photos)
    held = set(photos[: a.hold_out])
    for d in ("labeled", "needs_review", "val"):
        (root / d).mkdir(exist_ok=True)
    n = {"labeled": 0, "needs_review": 0, "val": 0, "failed": 0}
    for p in photos:
        try:
            raw = reader.read_invoice(str(p), a.backend)
        except Exception as e:
            print("failed", p.name, e)
            n["failed"] += 1
            continue
        dest = "val" if p in held else ("labeled" if checks.is_clean(raw) else "needs_review")
        shutil.copy(p, root / dest / p.name)
        (root / dest / p.with_suffix(".json").name).write_text(json.dumps(raw, ensure_ascii=False, indent=1),
                                                                encoding="utf-8")
        n[dest] += 1
        print(f"{p.name} -> {dest}")
    print(n)
    print(f"Now open every file in {root / 'val'} and correct the .json by hand against the photo.")


if __name__ == "__main__":
    main()
