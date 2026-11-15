"""Load the demo history into the store so today's invoices have something to
be compared against. Run once before the demo (and again to reset it).

  python -m scripts.seed_demo --profile sushi            # uses today's date
  python -m scripts.seed_demo --profile hotpot --today 2026-11-15
"""
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from lobsta import config, pipeline
from lobsta.store import Store
from scripts.make_demo import ROOT, build


def seed(profile: str, today: date, db: str | None = None, rebuild: bool = True, store: Store | None = None) -> dict:
    demo = ROOT / "demo" / profile
    notes = demo / "NOTES.json"
    stale = not notes.exists() or json.loads(notes.read_text())["today"] != today.isoformat()
    if rebuild or stale:
        try:
            build(profile, today)
        except Exception as e:      # e.g. fonts missing on this machine
            if stale:
                raise
            print(f"could not redraw the demo invoices ({e}); keeping the ones already in demo/")
    cfg = config.load(profile)
    store = store or Store(db or f"lobsta_{profile}.db")
    store.reset()
    n = 0
    for f in sorted((demo / "history").glob("*.json")):
        res = pipeline.process(str(f), cfg, store, raw=json.loads(f.read_text(encoding="utf-8")))
        assert res["ok"], (f.name, res["errors"])
        keys = {ln["n"]: ln["item_key"] for ln in res["invoice"]["lines"]}
        pipeline.confirm(res["id"], cfg, store, keys)
        n += 1
    for off, counts in json.loads((demo / "counts.json").read_text()).items():
        for key, qty in counts.items():
            store.add_count(key, qty, (today + timedelta(days=int(off))).isoformat())
    return {"profile": profile, "history_invoices": n, "db": store.path}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="sushi")
    ap.add_argument("--today", default=date.today().isoformat())
    ap.add_argument("--db")
    ap.add_argument("--rebuild", action="store_true", help="redraw the demo invoices even if they match today's date")
    a = ap.parse_args()
    print(seed(a.profile, date.fromisoformat(a.today), a.db, rebuild=a.rebuild))
