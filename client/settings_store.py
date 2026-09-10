"""Persistent general settings store for Let's Fly v2.0."""
import json
import os
import threading
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

APP_DIR = Path(os.getenv("APPDATA") or (Path.home() / ".letsfly")) / "LetsFly"
SETTINGS_FILE = APP_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "general": {
        "language": "system",
        "auto_login": True,
        "keep_credentials": True,
    },
    "audio": {
        "mute_all": False,
        "voice_auto_join": False,
        "speaker": "default",
        "volumes": {
            "effects": 1.0,
            "game": 1.0
        }
    },
    "speech": {
        "mute_all": False,
        "modes": {
            "friends": "speech",
            "invitations": "speech_and_sound",
            "table_chat": "speech",
            "private_messages": "speech_and_sound",
            "game_events": "speech_and_sound"
        }
    },
    "privacy": {
        "pm_policy": "everyone",       # everyone, friends, nobody
        "invite_policy": "everyone",   # everyone, friends, nobody
        "join_policy": "everyone"      # everyone, friends, nobody
    }
}

_cached_settings: Optional[Dict[str, Any]] = None
_save_lock = threading.Lock()

def clear_cache() -> None:
    global _cached_settings
    with _save_lock:
        _cached_settings = None

def load_settings(force_reload: bool = False) -> Dict[str, Any]:
    global _cached_settings
    if _cached_settings is not None and not force_reload:
        return _cached_settings
    try:
        if SETTINGS_FILE.exists():
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            _cached_settings = _merge_defaults(DEFAULT_SETTINGS, data)
            return _cached_settings
    except Exception:
        pass
    _cached_settings = _merge_defaults(DEFAULT_SETTINGS, {})
    return _cached_settings

def save_settings(settings: Dict[str, Any]) -> None:
    global _cached_settings
    with _save_lock:
        _cached_settings = settings
        APP_DIR.mkdir(parents=True, exist_ok=True)
        tmp = SETTINGS_FILE.parent / f"{SETTINGS_FILE.name}.{uuid.uuid4().hex[:8]}.tmp"
        try:
            tmp.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
            for _ in range(5):
                try:
                    tmp.replace(SETTINGS_FILE)
                    break
                except (PermissionError, FileNotFoundError):
                    import time
                    time.sleep(0.05)
            else:
                try:
                    if tmp.exists():
                        SETTINGS_FILE.write_text(tmp.read_text(encoding="utf-8"), encoding="utf-8")
                except Exception:
                    pass
        finally:
            try:
                if tmp.exists():
                    tmp.unlink(missing_ok=True)
            except Exception:
                pass

save = save_settings

def update_setting(category: str, key: str, value: Any) -> None:
    settings = load_settings()
    if category in settings:
        settings[category][key] = value
        save_settings(settings)

def update_nested_setting(category: str, subcategory: str, key: str, value: Any) -> None:
    settings = load_settings()
    if category in settings and subcategory in settings[category]:
        settings[category][subcategory][key] = value
        save_settings(settings)

def _merge_defaults(default: dict, loaded: dict) -> dict:
    merged = {}
    if not isinstance(loaded, dict):
        loaded = {}
    for k, v in default.items():
        if isinstance(v, dict):
            val = loaded.get(k)
            merged[k] = _merge_defaults(v, val if isinstance(val, dict) else {})
        else:
            merged[k] = loaded.get(k, v)
    return merged
