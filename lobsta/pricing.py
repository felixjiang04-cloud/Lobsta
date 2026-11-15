"""Price memory. All arithmetic, no AI: the model only ever phrases the result."""
from __future__ import annotations

from statistics import median

from .parse import norm_unit, unit_kg


def alerts_for(inv: dict, cfg: dict, store) -> list[dict]:
    jump = cfg["alerts"]["price_jump_pct"] / 100
    shrink = cfg["alerts"]["shrink_pct"] / 100
    out = []
    for ln in inv["lines"]:
        key = ln.get("item_key")
        if not key or ln.get("unit_cost") is None:
            continue
        hist = [h for h in store.price_history(key, before=inv.get("date"), limit=6)
                if h["cost_per"] == ln["cost_per"]]
        if not hist:
            continue
        usual = median(h["unit_cost"] for h in hist[:4])
        if usual > 0:
            pct = ln["unit_cost"] / usual - 1
            extra = round((ln["unit_cost"] - usual) * (ln.get("base_qty") or 0), 2)
            # show prices in the unit printed on the invoice (lb stays lb)
            k = unit_kg(ln["unit"]) if ln["cost_per"] == "kg" else None
            shown = {"now_shown": round(ln["unit_cost"] * (k or 1), 2), "usual_shown": round(usual * (k or 1), 2),
                     "per_shown": norm_unit(ln["unit"]) if k else ln["cost_per"]}
            if pct >= jump:
                out.append({"code": "price_jump", "line": ln["n"], "item_key": key,
                            "now": ln["unit_cost"], "usual": round(usual, 2), "per": ln["cost_per"],
                            "pct": round(pct * 100, 1), "extra": extra, "n_prior": len(hist[:4]), **shown})
            elif pct <= -jump:
                out.append({"code": "price_drop", "line": ln["n"], "item_key": key,
                            "now": ln["unit_cost"], "usual": round(usual, 2), "per": ln["cost_per"],
                            "pct": round(pct * 100, 1), "extra": extra, **shown})
        # Same case price, smaller case: a hidden increase.
        pk = (ln.get("pack") or {}).get("kg")
        last = next((h for h in hist if h["supplier"] == inv["supplier"] and h["pack_kg"]), None)
        if pk and last and ln["unit"] == last["unit"] and last["pack_kg"] > 0:
            smaller = 1 - pk / last["pack_kg"]
            if smaller >= shrink and ln["unit_price"] >= last["unit_price"] * 0.98:
                out.append({"code": "shrink", "line": ln["n"], "item_key": key,
                            "pack_before": round(last["pack_kg"], 2), "pack_now": round(pk, 2),
                            "case_price": ln["unit_price"],
                            # what the missing weight is worth at the old price per kg
                            "extra": round(ln["unit_price"] * (ln["quantity"] or 0) * smaller, 2),
                            "pct": round((last["pack_kg"] / pk - 1) * 100, 1)})
    # one alert per line: shrink explains a jump better than "price went up"
    shrunk = {a["line"] for a in out if a["code"] == "shrink"}
    return [a for a in out if not (a["code"] == "price_jump" and a["line"] in shrunk)]
