"""The network price comparison: how does this shop's latest price for an item
sit against other shops' prices?

Every confirmed invoice already yields a cost per kg per item. Pooled across
shops, that is a local price index. With two demo restaurants there is no real
network yet, so network/demo_prices.json holds SIMULATED quartiles, and every
answer built from it says so. Only medians and quartiles are ever shared,
never one shop's price.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_network() -> dict:
    path = Path(os.environ.get("LOBSTA_NETWORK", ROOT / "network" / "demo_prices.json"))
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"prices": {}, "shops": 0, "simulated": True}


def compare(cfg: dict, store, item_key: str | None = None) -> dict:
    net = load_network()
    rows = []
    for it in cfg.get("items", []):
        if item_key and it["key"] != item_key:
            continue
        ref = net["prices"].get(it["key"])
        hist = store.price_history(it["key"], limit=1)
        if not ref or not hist or hist[0]["cost_per"] != ref["per"]:
            continue
        mine = hist[0]["unit_cost"]
        pct = round((mine / ref["median"] - 1) * 100, 1)
        band = "high" if mine > ref["p75"] else "low" if mine < ref["p25"] else "typical"
        rows.append({"item_key": it["key"], "mine": round(mine, 2), "median": ref["median"], "per": ref["per"],
                     "pct": pct, "band": band, "date": hist[0]["date"]})
    rows.sort(key=lambda r: -r["pct"])
    return {"shops": net.get("shops", 0), "simulated": bool(net.get("simulated")), "area": net.get("area", ""),
            "rows": rows}
