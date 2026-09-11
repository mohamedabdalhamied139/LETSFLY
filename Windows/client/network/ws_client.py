"""Threaded WebSocket client with safe restart and outgoing chat support."""
import json
import logging
import threading
import time
from typing import Callable, Optional
import websocket

logger = logging.getLogger("tableverse.ws_client")


class WebSocketClient:
    def __init__(self):
        self.ws_url = ""
        self.callback: Optional[Callable[[dict], None]] = None
        self._ws = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._send_lock = threading.Lock()
        self._generation = 0
        self._auth_token = ""
        self._ping_lock = threading.Lock()
        self._connected_event = threading.Event()
        self._pending_ping_id = None
        self._pending_ping_at = None

    def start(self, on_message: Callable[[dict], None], ws_url: str, token: Optional[str] = None):
        self.stop()
        with self._lock:
            self._generation += 1
            generation = self._generation
            self.callback = on_message
            self._auth_token = token or ""
            self.ws_url = ws_url
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            args=(generation, on_message, ws_url, self._auth_token),
            daemon=True,
            name="TableVerse-WebSocket",
        )
        self._thread.start()

    def stop(self):
        self._stop.set()
        with self._lock:
            self._generation += 1
            ws = self._ws
            self._ws = None
            self._connected_event.clear()
        if ws:
            try:
                ws.close()
            except Exception:
                logger.debug("WebSocket close failed", exc_info=True)

    def _is_current(self, generation: int) -> bool:
        with self._lock:
            return generation == self._generation

    def send_bytes(self, payload: bytes) -> bool:
        """Send a bounded binary frame on the current WebSocket."""
        if not isinstance(payload, (bytes, bytearray)) or len(payload) > 4096:
            return False
        with self._lock:
            ws = self._ws
        if not ws:
            return False
        try:
            ws.send_binary(bytes(payload))
            return True
        except Exception:
            logger.debug("WebSocket binary send failed", exc_info=True)
            return False

    def is_connected(self) -> bool:
        """Return whether a live WebSocket is currently registered."""
        return self._connected_event.is_set() and self._ws is not None

    def ping(self, wait_timeout: float = 1.5) -> str:
        """Send one measured application-level ping over the current socket.

        Returns ``sent``, ``busy`` when another F3 measurement is pending, or
        ``offline`` when no WebSocket becomes available within wait_timeout.
        Waiting briefly avoids a false "offline" result when F3 is pressed
        immediately after entering a table while the async socket handshake is
        still completing.
        """
        import time
        import uuid
        if not self._connected_event.wait(max(0.0, float(wait_timeout))):
            return "offline"
        with self._lock:
            ws = self._ws
        if not ws:
            return "offline"
        ping_id = uuid.uuid4().hex
        with self._ping_lock:
            # Only one UI-requested measurement may be outstanding. Automatic
            # heartbeat pings never use this slot and therefore cannot steal or
            # corrupt the F3 measurement.
            if self._pending_ping_id is not None:
                return "busy"
            self._pending_ping_id = ping_id
            self._pending_ping_at = time.perf_counter()
        try:
            with self._send_lock:
                ws.send(json.dumps({"type": "ping", "ping_id": ping_id}))
            return "sent"
        except Exception:
            with self._ping_lock:
                self._pending_ping_id = None
                self._pending_ping_at = None
            return False

    def send_json(self, payload: dict) -> bool:
        with self._lock:
            ws = self._ws
        if not ws:
            return False
        try:
            with self._send_lock:
                ws.send(json.dumps(payload, ensure_ascii=False))
            return True
        except Exception:
            logger.debug("WebSocket send failed", exc_info=True)
            return False

    def _emit(self, callback: Callable[[dict], None], generation: int, data: dict):
        if self._stop.is_set() or not self._is_current(generation):
            return
        try:
            callback(data)
        except Exception:
            # Never let a consumer callback terminate the networking thread.
            logger.exception("WebSocket callback failed")

    def _loop(self, generation: int, callback: Callable[[dict], None], ws_url: str, token: str):
        retry_delay = 1
        while not self._stop.is_set() and self._is_current(generation):
            ws = None
            try:
                headers = [f"Authorization: Bearer {token}"] if token else []
                ws = websocket.create_connection(ws_url, timeout=5, header=headers)
                ws.settimeout(2)
                with self._lock:
                    current = generation == self._generation
                    if not current:
                        ws.close()
                        return
                    self._ws = ws
                    self._connected_event.set()
                self._emit(callback, generation, {"type": "ws_connected"})
                connected_at = last_ping = time.monotonic()
                while not self._stop.is_set() and self._is_current(generation):
                    try:
                        now = time.monotonic()
                        if now - connected_at >= 15:
                            retry_delay = 1
                        if now - last_ping >= 15:
                            try:
                                ws.send(json.dumps({"type": "ping"}))
                            except Exception:
                                break
                            last_ping = now
                        raw = ws.recv()
                        if not raw:
                            break
                        if isinstance(raw, (bytes, bytearray)):
                            # Binary frames are reserved for the table voice channel.
                            self._emit(callback, generation, {"type": "voice_packet", "data": bytes(raw)})
                            continue
                        data = json.loads(raw)
                        if isinstance(data, dict):
                            if data.get("type") == "pong":
                                ping_id = data.get("ping_id")
                                with self._ping_lock:
                                    if ping_id != self._pending_ping_id:
                                        # This is an automatic heartbeat pong, not
                                        # the F3 measurement.
                                        continue
                                    started = self._pending_ping_at
                                    self._pending_ping_id = None
                                    self._pending_ping_at = None
                                if started is not None:
                                    self._emit(callback, generation, {"type": "ws_ping", "rtt_ms": round((time.perf_counter() - started) * 1000, 1)})
                                continue
                            self._emit(callback, generation, data)
                    except websocket.WebSocketTimeoutException:
                        continue
                try:
                    ws.close()
                except Exception:
                    logger.debug("WebSocket close failed", exc_info=True)
                if not self._stop.is_set() and self._is_current(generation):
                    self._emit(callback, generation, {"type": "ws_disconnected"})
            except Exception:
                if not self._stop.is_set() and self._is_current(generation):
                    logger.warning("WebSocket connection failed; retrying in %ss", retry_delay, exc_info=True)
                else:
                    break
            finally:
                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        logger.debug("WebSocket close failed", exc_info=True)
                with self._ping_lock:
                    self._pending_ping_id = None
                    self._pending_ping_at = None
                with self._lock:
                    if self._ws is ws:
                        self._ws = None
                        self._connected_event.clear()
            if self._stop.is_set() or not self._is_current(generation):
                break
            if self._stop.wait(retry_delay):
                break
            self._emit(callback, generation, {"type": "ws_connecting"})
            retry_delay = min(retry_delay * 2, 5)
