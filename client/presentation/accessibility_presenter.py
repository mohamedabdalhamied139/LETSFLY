"""Screen-reader presentation helper for reusable announcements."""
from __future__ import annotations


class AccessibilityPresenter:
    def __init__(self, reader, translator):
        self.reader = reader
        self.tr = translator

    def announce(self, message: object, *, interrupt: bool = False, translate: bool = True, **kwargs) -> str:
        text = str(message or "")
        spoken = self.tr(text, **kwargs) if translate else text
        self.reader.speak(spoken, interrupt=interrupt)
        return spoken
