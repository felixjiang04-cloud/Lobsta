"""Turn the strings the reader transcribed into numbers. No AI in here.

The reader is asked to copy numbers exactly as printed ("17,50 $", "1 234,56",
"$1,234.56"). Everything that turns those into floats, kilograms and $/kg lives
in this file so it can be unit-tested.
"""
from __future__ import annotations

import re
from typing import Optional

LB_TO_KG = 0.45359237

# unit spelling -> (canonical unit, kg per unit or None, litres per unit or None)
_UNITS = {
    "kg": ("kg", 1.0, None), "kgs": ("kg", 1.0, None), "kilo": ("kg", 1.0, None),
    "kilos": ("kg", 1.0, None), "公斤": ("kg", 1.0, None), "千克": ("kg", 1.0, None),
    "g": ("g", 0.001, None), "gr": ("g", 0.001, None), "克": ("g", 0.001, None),
    "lb": ("lb", LB_TO_KG, None), "lbs": ("lb", LB_TO_KG, None), "#": ("lb", LB_TO_KG, None),
    "livre": ("lb", LB_TO_KG, None), "livres": ("lb", LB_TO_KG, None), "磅": ("lb", LB_TO_KG, None),
    "oz": ("oz", LB_TO_KG / 16, None),
    "斤": ("jin", 0.5, None),
    "l": ("l", None, 1.0), "litre": ("l", None, 1.0), "litres": ("l", None, 1.0), "升": ("l", None, 1.0),
    "ml": ("ml", None, 0.001), "毫升": ("ml", None, 0.001),
}
_COUNT_UNITS = {
    "case": "case", "cases": "case", "cs": "case", "caisse": "case", "caisses": "case",
    "cse": "case", "bte": "case", "boite": "case", "boîte": "case", "carton": "case", "箱": "case",
    "ea": "ea", "each": "ea", "un": "ea", "unité": "ea", "unite": "ea", "pc": "ea", "pcs": "ea",
    "个": "ea", "個": "ea", "件": "ea",
    "bag": "bag", "bags": "bag", "sac": "bag", "sacs": "bag", "袋": "bag", "包": "bag",
    "btl": "ea", "bouteille": "ea", "瓶": "ea",
}


def parse_number(raw, decimal_hint: Optional[str] = None) -> Optional[float]:
    """'17,50 $' -> 17.5 ; '1 234,56' -> 1234.56 ; '$1,234.56' -> 1234.56.

    decimal_hint is ',' for French-style invoices and '.' for English/Chinese
    ones. It only matters for the ambiguous case of a lone comma followed by
    exactly three digits ("1,234").
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip()
    if not s:
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = re.sub(r"[^\d,.\-]", "", s.replace("−", "-"))
    if s.startswith("-"):
        neg, s = True, s[1:]
    s = s.replace("-", "")
    if not re.search(r"\d", s):
        return None
    if "," in s and "." in s:
        dec = "," if s.rfind(",") > s.rfind(".") else "."
        thou = "." if dec == "," else ","
        s = s.replace(thou, "").replace(dec, ".")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        if s.count(",") > 1:
            s = s.replace(",", "")
        elif len(tail) == 3 and decimal_hint != "," and head not in ("", "0"):
            s = head + tail            # 1,234 -> thousands
        else:
            s = head + "." + tail      # 17,50 -> decimal
    elif s.count(".") > 1:
        head, _, tail = s.rpartition(".")
        s = head.replace(".", "") + "." + tail
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def norm_unit(raw: Optional[str]) -> Optional[str]:
    """'KG' -> 'kg', 'caisse' -> 'case', '箱' -> 'case'. Unknown -> lowercased."""
    if not raw:
        return None
    u = str(raw).strip().lower().rstrip(".").lstrip("/")
    if u in _UNITS:
        return _UNITS[u][0]
    return _COUNT_UNITS.get(u, u)


def unit_kg(unit: Optional[str]) -> Optional[float]:
    """kg in one of this unit, or None if it isn't a weight unit."""
    u = norm_unit(unit)
    for canon, kg, _ in _UNITS.values():
        if canon == u:
            return kg
    return None


_UNIT_ALT = "|".join(sorted((re.escape(k) for k in _UNITS), key=len, reverse=True))
_NUM = r"\d+(?:[.,]\d+)?"
# "4 x 5 kg", "4×5kg", "12/500 g", "6*2.5L"
_MULTI = re.compile(rf"({_NUM})\s*(?:x|×|\*|/)\s*({_NUM})\s*({_UNIT_ALT})(?![a-z])", re.I)
# "25 lb", "10kg", "20斤", "25#"
_SINGLE = re.compile(rf"({_NUM})\s*({_UNIT_ALT})(?![a-z])", re.I)


def parse_pack(text: Optional[str]) -> Optional[dict]:
    """Find the pack size hidden in a description.

    'Tomates Roma 25 lb'  -> {'kg': 11.34, 'text': '25 lb'}
    'Riz Calrose 4 x 5 kg' -> {'kg': 20.0, 'text': '4 x 5 kg'}
    'Sauce soya 6 x 1.8 L' -> {'l': 10.8, 'text': '6 x 1.8 L'}
    Returns None when no size is printed (the owner fills it in once).
    """
    if not text:
        return None
    t = str(text)
    m = _MULTI.search(t)
    if m:
        n, each, unit = parse_number(m.group(1), ","), parse_number(m.group(2), ","), m.group(3).lower()
    else:
        m = _SINGLE.search(t)
        if not m:
            return None
        n, each, unit = 1.0, parse_number(m.group(1), ","), m.group(2).lower()
    _, kg, litres = _UNITS[unit]
    out = {"text": m.group(0).strip()}
    if kg is not None:
        out["kg"] = round(n * each * kg, 4)
    else:
        out["l"] = round(n * each * litres, 4)
    return out


def price_per_kg(unit_price: Optional[float], unit: Optional[str], pack: Optional[dict]) -> Optional[float]:
    """$/kg for a line, or None when it can't be known from the invoice alone.

    Sold by weight -> convert the unit. Sold by the case -> divide by the pack.
    """
    if unit_price is None:
        return None
    kg = unit_kg(unit)
    if kg:
        return round(unit_price / kg, 4)
    if pack and pack.get("kg"):
        return round(unit_price / pack["kg"], 4)
    return None


def unit_cost(unit_price: Optional[float], unit: Optional[str], pack: Optional[dict]):
    """(cost, per) with per in {'kg', 'l', <count unit>}. Comparable across invoices."""
    if unit_price is None:
        return None, None
    per_kg = price_per_kg(unit_price, unit, pack)
    if per_kg is not None:
        return per_kg, "kg"
    u = norm_unit(unit)
    for canon, _, litres in _UNITS.values():
        if canon == u and litres:
            return round(unit_price / litres, 4), "l"
    if pack and pack.get("l"):
        return round(unit_price / pack["l"], 4), "l"
    return round(unit_price, 4), u or "ea"


def base_quantity(quantity: Optional[float], unit: Optional[str], pack: Optional[dict]) -> Optional[float]:
    """What arrived, in the same unit as unit_cost's 'per' (kg, l, or a count)."""
    if quantity is None:
        return None
    kg = unit_kg(unit)
    if kg:
        return round(quantity * kg, 3)
    if pack and pack.get("kg"):
        return round(quantity * pack["kg"], 3)
    u = norm_unit(unit)
    for canon, _, litres in _UNITS.values():
        if canon == u and litres:
            return round(quantity * litres, 3)
    if pack and pack.get("l"):
        return round(quantity * pack["l"], 3)
    return quantity
