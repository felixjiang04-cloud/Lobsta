"""One JSON file per restaurant. This is the 'forward deployed' part: a new
customer is a new config file, not a new codebase."""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(profile: str | None = None) -> dict:
    profile = profile or os.environ.get("LOBSTA_PROFILE", "sushi")
    path = Path(profile) if profile.endswith(".json") else ROOT / "configs" / f"{profile}.json"
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg.setdefault("profile", path.stem)
    cfg.setdefault("owner_language", "en")
    cfg.setdefault("alerts", {})
    cfg["alerts"].setdefault("price_jump_pct", 8)
    cfg["alerts"].setdefault("shrink_pct", 3)
    cfg["items_by_key"] = {it["key"]: it for it in cfg.get("items", [])}
    return cfg


def item_name(cfg: dict, key: str | None, lang: str | None = None) -> str:
    it = cfg["items_by_key"].get(key or "")
    if not it:
        return key or "?"
    names = it.get("name", {})
    return names.get(lang or cfg["owner_language"]) or names.get("en") or key
