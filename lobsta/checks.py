"""Arithmetic checks. If the reader misread a digit, or the supplier made a
mistake, the numbers stop adding up and we say so instead of saving it."""
from __future__ import annotations

from .parse import base_quantity, norm_unit, parse_number, parse_pack, unit_cost

CENT = 0.011


def _close(a: float, b: float, rel: float = 0.001) -> bool:
    """Two cents, or 0.1% for big totals (suppliers round weights differently).
    Tight on purpose: a loose tolerance lets a misread cent slip through."""
    return abs(a - b) <= max(2 * CENT, rel * max(abs(a), abs(b)))


def normalize(raw: dict) -> dict:
    """Reader output (strings as printed) -> numbers, units, packs, $/kg."""
    lang = (raw.get("language") or "en").lower()[:2]
    hint = "," if lang == "fr" else "."
    num = lambda v: parse_number(v, hint)
    lines = []
    for i, ln in enumerate(raw.get("lines") or []):
        desc = (ln.get("description") or "").strip()
        unit = norm_unit(ln.get("unit"))
        pack = parse_pack(ln.get("pack")) or parse_pack(desc)
        up, qty = num(ln.get("unit_price")), num(ln.get("quantity"))
        cost, per = unit_cost(up, unit, pack)
        lines.append({
            "n": i + 1, "description": desc, "code": ln.get("code") or None,
            "quantity": qty, "unit": unit, "pack": pack,
            "unit_price": up, "line_total": num(ln.get("line_total")),
            "unit_cost": cost, "cost_per": per, "base_qty": base_quantity(qty, unit, pack),
        })
    taxes = [{"name": t.get("name") or "tax", "amount": num(t.get("amount")) or 0.0}
             for t in (raw.get("taxes") or [])]
    return {
        "supplier": (raw.get("supplier") or "").strip(),
        "invoice_number": str(raw.get("invoice_number") or "").strip(),
        "date": raw.get("date"), "language": lang, "currency": raw.get("currency") or "CAD",
        "lines": lines, "subtotal": num(raw.get("subtotal")), "taxes": taxes,
        "total": num(raw.get("total")),
    }


def check(inv: dict) -> list[dict]:
    """Returns flags: {code, line, expected, printed, diff}. Empty list = clean."""
    flags = []
    for ln in inv["lines"]:
        q, p, t = ln["quantity"], ln["unit_price"], ln["line_total"]
        if q is None or p is None or t is None:
            flags.append({"code": "missing_number", "line": ln["n"]})
            continue
        want = round(q * p, 2)
        if not _close(want, t):
            flags.append({"code": "line_math", "line": ln["n"], "expected": want,
                          "printed": t, "diff": round(t - want, 2)})
    totals = [ln["line_total"] for ln in inv["lines"] if ln["line_total"] is not None]
    if inv["subtotal"] is not None and totals and len(totals) == len(inv["lines"]):
        want = round(sum(totals), 2)
        if not _close(want, inv["subtotal"]):
            flags.append({"code": "subtotal_math", "line": None, "expected": want,
                          "printed": inv["subtotal"], "diff": round(inv["subtotal"] - want, 2)})
    if inv["total"] is not None:
        base = inv["subtotal"] if inv["subtotal"] is not None else (round(sum(totals), 2) if totals else None)
        if base is not None:
            want = round(base + sum(t["amount"] for t in inv["taxes"]), 2)
            if not _close(want, inv["total"]):
                flags.append({"code": "total_math", "line": None, "expected": want,
                              "printed": inv["total"], "diff": round(inv["total"] - want, 2)})
    if not inv["lines"]:
        flags.append({"code": "no_lines", "line": None})
    return flags


def is_clean(raw: dict) -> bool:
    """Used as the free label checker when auto-labeling real invoices."""
    inv = normalize(raw)
    return bool(inv["lines"]) and inv["total"] is not None and not check(inv)
