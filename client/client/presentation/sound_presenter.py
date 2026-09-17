"""Thin sound-cue presentation helper for client code.

The helper deliberately delegates to the existing SoundEngine. It adds duplicate
cue suppression for callers that want it, without changing any registry or asset
mapping behavior.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger("tableverse.sound_presenter")


class SoundPresenter:
    def __init__(self, sound_engine):
        self.sound_engine = sound_engine
        self._last_event_key: Optional[tuple[Any, Any]] = None

    def play_event(self, cue: str) -> bool:
        if not cue:
            return False
        try:
            self.sound_engine.play_event(str(cue))
            return True
        except Exception:
            logger.debug("Failed to play sound cue %s", cue, exc_info=True)
            return False

    def play_state_sound(self, state: dict, *, dedupe: bool = True) -> bool:
        if not isinstance(state, dict):
            return False
        cue = state.get("sound_cue") or ""
        event_id = state.get("event_id")
        key = (event_id, cue)
        if dedupe and key == self._last_event_key:
            return False
        self._last_event_key = key
        return self.play_event(cue)
