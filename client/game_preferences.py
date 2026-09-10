"""Persistent per-game preferences for the lobby settings screen."""
import json
from pathlib import Path
import os

APP_DIR = Path(os.getenv("APPDATA") or (Path.home() / ".letsfly")) / "LetsFly"
FILE = APP_DIR / "game_preferences.json"

def load_all():
    try:
        data = json.loads(FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def load(game_type, default_target, default_rules):
    data = load_all().get(str(game_type).upper(), {})
    try:
        target = int(data.get("target_score", default_target))
    except (TypeError, ValueError):
        target = int(default_target)
    rules = dict(default_rules or {})
    if isinstance(data.get("rules"), dict):
        rules.update(data["rules"])
    return target, rules

def save(game_type, target, rules):
    data = load_all()
    data[str(game_type).upper()] = {"target_score": int(target), "rules": dict(rules or {})}
    APP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(FILE)
