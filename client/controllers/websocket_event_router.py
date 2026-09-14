"""Small WebSocket event routing facade for the desktop client.

The full event handling still lives in TableVerseApp for behavior stability. This
facade gives tests and future incremental refactors a single stable delegation
point without changing event names or protocol semantics.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("tableverse.ws_event_router")


class WebSocketEventRouter:
    def __init__(self, app: Any):
        self.app = app

    def route(self, event: dict) -> None:
        if not isinstance(event, dict):
            logger.debug("Ignoring non-dict WebSocket event: %r", event)
            return
        handler = getattr(self.app, "_handle_ws_event_impl", None)
        if handler is None:
            handler = getattr(self.app, "_handle_ws_event", None)
        if handler is None:
            logger.warning("No WebSocket event handler installed on app")
            return
        handler(event)
