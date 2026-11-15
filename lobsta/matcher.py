"""Which of the owner's items is this invoice line?

Order of trust: (1) a match the owner already confirmed -> plain lookup,
(2) keyword score against the config, (3) optional LLM suggestion.
(2) and (3) are only suggestions until the owner taps OK once.
"""
from __future__ import annotations

import difflib
import re
import unicodedata


def norm_desc(text: str) -> str:
    """'SAUMON ATL. FRAIS 12,4 KG' -> 'saumon atl frais'. Stable lookup key."""
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"\d+(?:[.,]\d+)?\s*(?:x|×|\*|/)?\s*", " ", t)
    t = re.sub(r"\b(kg|kgs|g|gr|lb|lbs|oz|l|ml|cs|cse|ea|un)\b", " ", t)
    t = re.sub(r"[公斤千克磅斤升箱袋包]", " ", t)
    t = re.sub(r"[^\w一-鿿]+", " ", t)
    return " ".join(t.split())


def suggest(description: str, cfg: dict) -> tuple[str | None, float]:
    d = norm_desc(description)
    if not d:
        return None, 0.0
    best, score = None, 0.0
    words = d.split()
    for it in cfg.get("items", []):
        s = 0.0
        for kw in it.get("keywords", []):
            k = norm_desc(kw)
            if not k:
                continue
            if k in d:
                s = max(s, 0.6 + min(0.4, len(k) / 12))
            else:
                r = max((difflib.SequenceMatcher(None, k, w).ratio() for w in words), default=0)
                if r >= 0.8:
                    s = max(s, r * 0.7)
        if s > score:
            best, score = it["key"], s
    return (best, round(score, 2)) if score >= 0.5 else (None, round(score, 2))


def match_lines(inv: dict, cfg: dict, store) -> None:
    """Adds item_key / match ('confirmed' | 'suggested' | 'unknown') to each line."""
    for ln in inv["lines"]:
        known = store.get_alias(inv["supplier"], norm_desc(ln["description"]))
        if known:
            ln["item_key"], ln["match"] = known["item_key"], "confirmed"
            if not ln.get("pack") and known.get("pack_kg"):
                ln["pack"] = {"kg": known["pack_kg"], "text": "saved"}
            continue
        key, score = suggest(ln["description"], cfg)
        ln["item_key"], ln["match"], ln["match_score"] = key, ("suggested" if key else "unknown"), score
