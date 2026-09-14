"""User-facing error presentation helpers for the desktop client.

This module intentionally contains no navigation or gameplay logic.  It keeps
error cleanup, invalid-action cues and screen-reader announcement formatting in
one small place while preserving the existing client behavior.
"""
from __future__ import annotations

from typing import Iterable


DEFAULT_INVALID_MARKERS: tuple[str, ...] = (
    "ليس دورك", "غير صالح", "غير مناسب", "لا يمكنك السحب",
    "الكارت المحدد", "لا يمكن الاعتراض", "كارت الاعتراض",
    "غير كاف", "رصيدك",
)


class ErrorPresenter:
    def __init__(self, reader, sound_engine, translator, invalid_markers: Iterable[str] = DEFAULT_INVALID_MARKERS):
        self.reader = reader
        self.sound_engine = sound_engine
        self.tr = translator
        self.invalid_markers = tuple(invalid_markers)

    @staticmethod
    def clean_message(message: object) -> str:
        text = str(message or "").strip()
        for prefix in ("400: ", "403: ", "404: ", "409: "):
            if text.startswith(prefix):
                return text[len(prefix):].strip()
        return text

    def is_invalid_action(self, text: str) -> bool:
        return any(marker in text for marker in self.invalid_markers)

    def show_error(self, message: object) -> str:
        text = self.clean_message(message)
        if self.is_invalid_action(text):
            self.sound_engine.play_event("INVALID_ACTION")
        self.reader.speak(self.tr("تنبيه: {text}", text=text), interrupt=True)
        return text
