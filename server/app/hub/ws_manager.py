"""Authenticated WebSocket connection hub for lobby, rooms and chat."""
import asyncio
import logging
import threading
from typing import Dict, Set, Optional
from fastapi import WebSocket

logger = logging.getLogger("tableverse.ws_manager")


class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.room_connections: Dict[str, Set[WebSocket]] = {}
        self.voice_connections: Dict[str, Set[WebSocket]] = {}
        self.connection_users: Dict[WebSocket, int] = {}
        self.connection_rooms: Dict[WebSocket, str] = {}
        self._ws_locks: Dict[WebSocket, asyncio.Lock] = {}
        self._connection_times: Dict[WebSocket, float] = {}
        self.send_timeout = 2.0
        self.max_connections_per_user = 5
        self.max_total_connections = 1000
        self._connect_lock = asyncio.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._broadcast_slots = asyncio.BoundedSemaphore(256)
        # Protect the connection registries themselves.  WebSocket lifecycle
        # callbacks and broadcast cleanup can run concurrently with connect/
        # disconnect operations; the async admission lock alone does not cover
        # synchronous cleanup paths.
        self._state_lock = threading.RLock()

    def can_connect(self, user_id: int) -> bool:
        """Bound authenticated socket fan-out to prevent connection exhaustion."""
        with self._state_lock:
            if len(self.connection_users) >= self.max_total_connections:
                return False
            user_count = sum(1 for uid in self.connection_users.values() if uid == user_id)
            return user_count < self.max_connections_per_user

    def _notify_friend_presence(self, user_id: int, online: bool):
        threading.Thread(
            target=self._notify_friend_presence_sync,
            args=(int(user_id), bool(online)),
            daemon=True,
            name=f"PresenceSync-{user_id}"
        ).start()

    def _notify_friend_presence_sync(self, user_id: int, online: bool):
        try:
            from datetime import datetime, timezone
            from server.app.db.database import SessionLocal, User, Friendship
            from server.app.activity import create_event
            from server.app.social_services import mute_flags
            db = SessionLocal()
            try:
                me = db.query(User).filter(User.id == int(user_id)).first()
                if not me:
                    return
                friend_rows = db.query(Friendship).filter((Friendship.user_id == user_id) | (Friendship.friend_id == user_id)).all()
                friend_ids = [r.friend_id if r.user_id == user_id else r.user_id for r in friend_rows]
                events_for_friend = {}
                for fid in friend_ids:
                    # Muting suppresses audible/foreground notification only;
                    # the event must remain visible in the activity log.
                    text = f"{me.display_name} متصل الآن." if online else f"{me.display_name} غير متصل الآن."
                    events_for_friend[int(fid)] = create_event(db, fid, "FRIENDS", text, event_type="FRIEND_ONLINE" if online else "FRIEND_OFFLINE", actor_id=user_id)
                if not online and not any(uid == int(user_id) for uid in self.connection_users.values()):
                    me.last_seen_at = datetime.now(timezone.utc)
                db.commit()
                for fid in friend_ids:
                    flags = mute_flags(db, fid, user_id)
                    text = f"{me.display_name} متصل الآن." if online else f"{me.display_name} غير متصل الآن."
                    self.broadcast_user(fid, {
                        "type": "activity_event",
                        "id": int(events_for_friend[int(fid)].id) if events_for_friend[int(fid)].id is not None else None,
                        "category": "FRIENDS",
                        "event_type": "FRIEND_ONLINE" if online else "FRIEND_OFFLINE",
                        "text": text,
                        "notification_muted": bool(flags["all"] or flags["presence"])
                    })
            finally:
                db.close()
        except Exception:
            logger.exception("Presence event update failed for user %s", user_id)

    async def connect(self, ws: WebSocket, user_id: int, room_id: str = ""):
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
        # Serialize the admission check with the accept/register operation so
        # concurrent connection attempts cannot race past the configured caps.
        async with self._connect_lock:
            if not self.can_connect(user_id):
                await ws.close(code=1013, reason="Too many active connections")
                return False
            await ws.accept()
            with self._state_lock:
                was_online = any(uid == int(user_id) for uid in self.connection_users.values())
                # Re-check after the await: another lifecycle callback may have
                # changed the registry while the socket was being accepted.
                if not self.can_connect(user_id):
                    try:
                        await ws.close(code=1013, reason="Too many active connections")
                    except Exception:
                        logger.debug("Failed to close late-rejected WebSocket", exc_info=True)
                    return False
                self.connection_users[ws] = user_id
                self._ws_locks[ws] = asyncio.Lock()
                self._connection_times[ws] = __import__("time").monotonic()
                if room_id:
                    self.room_connections.setdefault(room_id, set()).add(ws)
                    self.connection_rooms[ws] = room_id
                else:
                    self.active_connections.add(ws)
            if not was_online:
                self._notify_friend_presence(int(user_id), True)
            return True

    def room_user_connected(self, room_id: str, user_id: int) -> bool:
        with self._state_lock:
            return any(self.connection_users.get(ws) == user_id for ws in self.room_connections.get(room_id, set()))

    def disconnect(self, ws: WebSocket, room_id: str = ""):
        user_id = None
        became_offline = False
        with self._state_lock:
            user_id = self.connection_users.get(ws)
            self.active_connections.discard(ws)
            actual_room = self.connection_rooms.pop(ws, None) or room_id
            if actual_room and actual_room in self.room_connections:
                self.room_connections[actual_room].discard(ws)
                if not self.room_connections[actual_room]:
                    self.room_connections.pop(actual_room, None)
            if actual_room and actual_room in self.voice_connections:
                self.voice_connections[actual_room].discard(ws)
                if not self.voice_connections[actual_room]:
                    self.voice_connections.pop(actual_room, None)
            self.connection_users.pop(ws, None)
            self._ws_locks.pop(ws, None)
            self._connection_times.pop(ws, None)
            if user_id is not None:
                became_offline = not any(uid == user_id for uid in self.connection_users.values())
        if became_offline and user_id is not None:
            self._notify_friend_presence(int(user_id), False)

    def online_user_ids(self):
        """Return unique authenticated users with at least one live socket."""
        with self._state_lock:
            return sorted({int(uid) for uid in self.connection_users.values()})

    def is_user_online(self, user_id: int) -> bool:
        """Return whether the user currently has at least one live WebSocket."""
        with self._state_lock:
            return any(int(uid) == int(user_id) for uid in self.connection_users.values())

    def online_users_with_connection_times(self):
        """Return unique online users with the oldest live connection timestamp.

        Connection timestamps are monotonic and are only used for relative
        oldest/newest sorting in the lobby UI.
        """
        with self._state_lock:
            first = {}
            for ws, uid in self.connection_users.items():
                stamp = self._connection_times.get(ws, 0.0)
                uid = int(uid)
                first[uid] = min(first.get(uid, stamp), stamp)
            return first

    def user_id(self, ws: WebSocket) -> Optional[int]:
        with self._state_lock:
            return self.connection_users.get(ws)

    async def disconnect_user(self, user_id: int, reason: str = "Authentication state changed"):
        """Close every active WebSocket for a user after logout/password change/revocation."""
        with self._state_lock:
            sockets = [ws for ws, uid in list(self.connection_users.items()) if uid == user_id]
        for ws in sockets:
            room_id = self.connection_rooms.get(ws, "")
            try:
                await asyncio.wait_for(ws.close(code=1008, reason=reason), timeout=self.send_timeout)
            except Exception:
                logger.debug("Failed to close revoked socket for user %s", user_id, exc_info=True)
            self.disconnect(ws, room_id)

    async def disconnect_user_from_room(self, room_id: str, user_id: int):
        with self._state_lock:
            sockets = [
                ws for ws in self.room_connections.get(room_id, set())
                if self.connection_users.get(ws) == user_id
            ]
        for ws in sockets:
            try:
                await asyncio.wait_for(ws.close(code=1000, reason="Room membership ended"), timeout=self.send_timeout)
            except Exception:
                logger.debug("Failed to close room socket for user %s", user_id, exc_info=True)
            self.disconnect(ws, room_id)

    async def _broadcast(self, sockets, message: dict, room_id: str = ""):
        if not sockets:
            return

        async def send_one(ws):
            lock = self._ws_locks.get(ws)
            if not lock:
                return ws
            try:
                async with lock:
                    await asyncio.wait_for(ws.send_json(message), timeout=self.send_timeout)
                return None
            except Exception:
                return ws

        dead = [ws for ws in await asyncio.gather(*(send_one(ws) for ws in sockets)) if ws is not None]
        for ws in dead:
            self.disconnect(ws, room_id)

    async def send_json(self, ws: WebSocket, message: dict, room_id: str = "") -> bool:
        """Serialize every outbound JSON frame for one socket."""
        lock = self._ws_locks.get(ws)
        if lock is None:
            return False
        try:
            async with lock:
                await asyncio.wait_for(ws.send_json(message), timeout=self.send_timeout)
            return True
        except Exception:
            self.disconnect(ws, room_id)
            return False

    def _schedule_broadcast(self, coro):
        """Schedule a broadcast coroutine safely from any thread or event loop."""
        try:
            current_loop = None
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

            if current_loop is not None and current_loop.is_running():
                if self._loop is None or not self._loop.is_running():
                    self._loop = current_loop
                async def bounded():
                    if self._broadcast_slots.locked():
                        coro.close()
                        return
                    async with self._broadcast_slots:
                        await coro
                self._loop.create_task(bounded())
            elif self._loop is not None and self._loop.is_running():
                async def bounded_threadsafe():
                    if self._broadcast_slots.locked():
                        coro.close()
                        return
                    async with self._broadcast_slots:
                        await coro
                asyncio.run_coroutine_threadsafe(bounded_threadsafe(), self._loop)
            else:
                logger.debug("No active running event loop to schedule broadcast")
                try:
                    coro.close()
                except Exception:
                    pass
        except Exception:
            logger.debug("Failed to schedule WebSocket broadcast", exc_info=True)
            try:
                coro.close()
            except Exception:
                pass

    def broadcast_user(self, user_id: int, message: dict):
        """Send a lobby/activity event only to sockets authenticated as user_id."""
        with self._state_lock:
            sockets = [ws for ws, uid in self.connection_users.items() if uid == int(user_id)]
        if sockets:
            self._schedule_broadcast(self._broadcast(sockets, message))

    def join_voice(self, room_id: str, ws: WebSocket) -> bool:
        with self._state_lock:
            if ws not in self.room_connections.get(room_id, set()):
                return False
            uid = self.connection_users.get(ws)
            sockets = self.voice_connections.setdefault(room_id, set())
            # One voice stream per authenticated user/table prevents duplicate
            # microphone streams during reconnect races or multi-socket retries.
            for other in list(sockets):
                if other is not ws and self.connection_users.get(other) == uid:
                    sockets.discard(other)
            sockets.add(ws)
            return True

    def leave_voice(self, room_id: str, ws: WebSocket):
        with self._state_lock:
            sockets = self.voice_connections.get(room_id)
            if sockets is not None:
                sockets.discard(ws)
                if not sockets:
                    self.voice_connections.pop(room_id, None)

    def get_voice_user_ids(self, room_id: str) -> list[int]:
        with self._state_lock:
            sockets = self.voice_connections.get(room_id, set())
            return [self.connection_users[s] for s in sockets if s in self.connection_users and self.connection_users[s] is not None]

    def broadcast_room_bytes(self, room_id: str, payload: bytes, exclude: WebSocket | None = None):
        """Broadcast an opaque binary frame only to sockets subscribed to one room."""
        if not isinstance(payload, (bytes, bytearray)) or len(payload) > 4096:
            return
        with self._state_lock:
            sockets = [ws for ws in self.voice_connections.get(room_id, set()) if ws is not exclude]
        if sockets:
            self._schedule_broadcast_bytes(sockets, bytes(payload), room_id)

    async def _broadcast_bytes(self, sockets, payload: bytes, room_id: str = ""):
        async def send_one(ws):
            lock = self._ws_locks.get(ws)
            if not lock:
                return ws
            try:
                async with lock:
                    await asyncio.wait_for(ws.send_bytes(payload), timeout=self.send_timeout)
                return None
            except Exception:
                return ws
        dead = [ws for ws in await asyncio.gather(*(send_one(ws) for ws in sockets)) if ws is not None]
        for ws in dead:
            self.disconnect(ws, room_id)

    def _schedule_broadcast_bytes(self, sockets, payload: bytes, room_id: str):
        self._schedule_broadcast(self._broadcast_bytes(sockets, payload, room_id))

    def broadcast_lobby(self, message: dict):
        with self._state_lock:
            sockets = list(self.active_connections)
        if sockets:
            self._schedule_broadcast(self._broadcast(sockets, message))

    def broadcast_room(self, room_id: str, message: dict):
        with self._state_lock:
            sockets = list(self.room_connections.get(room_id, set()))
        if sockets:
            self._schedule_broadcast(self._broadcast(sockets, message, room_id))


ws_manager = ConnectionManager()
