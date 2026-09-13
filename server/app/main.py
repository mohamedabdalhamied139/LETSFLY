import server.app.games.plugins.all_games
"""FastAPI Application Entry Point."""
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import os
import logging
import json
import time
import struct
from collections import deque
from contextlib import asynccontextmanager, suppress
from server.app.api.auth import router as auth_router
from server.app.api.users import router as users_router
from server.app.api.rooms import router as rooms_router
from server.app.api.activity import router as activity_router
from server.app.api.social import router as social_router
from server.app.core.security import decode_access_token
from server.app.hub.ws_manager import ws_manager
from server.app.hub.room_manager import room_manager
from server.app.db.database import SessionLocal, User
from server.app.activity import create_event
from core_shared.version import BUILD
from core_shared.protocol import RoomActionRequest
@asynccontextmanager
async def lifespan(app):
    app.state.chat_persist_queue = asyncio.Queue(maxsize=500)
    worker = asyncio.create_task(_chat_persist_worker(app.state.chat_persist_queue))
    try:
        yield
    finally:
        try:
            await asyncio.wait_for(app.state.chat_persist_queue.join(), timeout=10)
        except asyncio.TimeoutError:
            logger.warning("Chat persistence queue did not drain before shutdown")
        finally:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker

app = FastAPI(title="TableVerse Server v2", version="2.0.0", lifespan=lifespan)

_MAX_HTTP_BODY_BYTES = 64 * 1024
_environment = os.getenv("TABLEVERSE_ENV", "development").strip().lower()
_REQUIRE_HTTPS = os.getenv("TABLEVERSE_REQUIRE_HTTPS", "true" if _environment in {"production", "prod"} else "false").strip().lower() in {"1", "true", "yes", "on"}

_allowed_hosts_raw = os.getenv("TABLEVERSE_ALLOWED_HOSTS") or os.getenv("LETSFLY_ALLOWED_HOSTS")
if _environment in {"production", "prod"} and not _allowed_hosts_raw:
    raise RuntimeError("TABLEVERSE_ALLOWED_HOSTS must be explicitly configured in production.")
if not _allowed_hosts_raw:
    _allowed_hosts_raw = "127.0.0.1,localhost,testserver,letsfly.onrender.com,tableverse.onrender.com"
_allowed_hosts = [x.strip() for x in _allowed_hosts_raw.split(",") if x.strip()]
if "*" in _allowed_hosts:
    raise RuntimeError("TABLEVERSE_ALLOWED_HOSTS must not contain '*' in production.")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=_allowed_hosts)

def _request_host_is_allowed(request) -> bool:
    """Validate Host before constructing an HTTPS redirect target.

    The HTTPS redirect middleware runs outside TrustedHostMiddleware in the
    Starlette stack. Validate the host here as well so an attacker cannot use
    an untrusted Host header to manufacture an open redirect.
    """
    host = request.headers.get("host", "").strip().lower()
    if not host:
        return False
    hostname = host.split(":", 1)[0].strip("[]")
    return hostname in {item.lower().split(":", 1)[0].strip("[]") for item in _allowed_hosts}

@app.middleware("http")
async def security_headers_and_body_limit(request, call_next):
    request_started = time.perf_counter()
    if ws_manager._loop is None or not ws_manager._loop.is_running():
        try:
            ws_manager._loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
    if not _request_host_is_allowed(request):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Invalid Host header."}, status_code=400)
    if _REQUIRE_HTTPS and request.url.scheme != "https":
        from fastapi.responses import RedirectResponse
        target = request.url.replace(scheme="https")
        return RedirectResponse(str(target), status_code=307)

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared_length = int(content_length)
            if declared_length < 0:
                from fastapi.responses import JSONResponse
                return JSONResponse({"detail": "Content-Length غير صالح."}, status_code=400)
            if declared_length > _MAX_HTTP_BODY_BYTES:
                from fastapi.responses import JSONResponse
                return JSONResponse({"detail": "حجم الطلب كبير جدًا."}, status_code=413)
        except ValueError:
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Content-Length غير صالح."}, status_code=400)
    elif request.method in {"POST", "PUT", "PATCH"} and request.headers.get("content-type", "").lower().startswith("application/json"):
        # Do not call request.body() on an unbounded chunked request: Starlette
        # would buffer the entire payload before we could enforce the limit.
        # Consume at most MAX+1 bytes, then replay the bounded body to FastAPI.
        chunks = []
        total = 0
        original_receive = request._receive
        while True:
            message = await original_receive()
            if message.get("type") == "http.disconnect":
                break
            if message.get("type") != "http.request":
                continue
            chunk = message.get("body", b"")
            total += len(chunk)
            if total > _MAX_HTTP_BODY_BYTES:
                from fastapi.responses import JSONResponse
                return JSONResponse({"detail": "حجم الطلب كبير جدًا."}, status_code=413)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        request._body = body
        replayed = False
        async def receive_from_buffer():
            nonlocal replayed
            if replayed:
                return {"type": "http.request", "body": b"", "more_body": False}
            replayed = True
            return {"type": "http.request", "body": body, "more_body": False}
        request._receive = receive_from_buffer

    response = await call_next(request)
    response.headers.setdefault("X-TableVerse-Process-Time-Ms", f"{(time.perf_counter() - request_started) * 1000:.2f}")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path.startswith("/api/auth/"):
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("Pragma", "no-cache")
    if request.url.scheme == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response
logger = logging.getLogger("tableverse.server")

def _persist_chat_activity(room_id: str, sender_id: int, sender: str, text: str, recipients: list[int]):
    """Persist chat activity without blocking the WebSocket event loop."""
    db = SessionLocal()
    try:
        for recipient_id in recipients:
            create_event(
                db, recipient_id, "TABLE_CHAT",
                f"{sender}: {text}", event_type="CHAT_MESSAGE",
                actor_id=sender_id, room_id=room_id,
            )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Chat activity persistence failed for room %s", room_id)
    finally:
        db.close()

async def _chat_persist_worker(queue):
    while True:
        args = await queue.get()
        try:
            await asyncio.to_thread(_persist_chat_activity, *args)
        except Exception:
            logger.exception("Chat persistence worker failed")
        finally:
            queue.task_done()

_WS_CHAT_WINDOW_SECONDS = 5.0
_WS_CHAT_MAX_MESSAGES = 10
_WS_MAX_JSON_BYTES = 4096
_WS_EVENTS_WINDOW_SECONDS = 5.0
_WS_EVENTS_MAX_MESSAGES = 30

# Keep the desktop/local deployment safe by default. Production deployments can
# explicitly provide a comma-separated allow-list without changing the shared
# room/table architecture.
_cors_raw = os.getenv("TABLEVERSE_CORS_ORIGINS")
if _environment in {"production", "prod"} and not _cors_raw:
    raise RuntimeError("TABLEVERSE_CORS_ORIGINS must be explicitly configured in production.")
if not _cors_raw:
    _cors_raw = "http://127.0.0.1:8000,http://localhost:8000"
_cors_origins = [x.strip() for x in _cors_raw.split(",") if x.strip()]
if "*" in _cors_origins:
    raise RuntimeError("TABLEVERSE_CORS_ORIGINS must not contain '*' when credentials are enabled.")
if _environment in {"production", "prod"} and any(not origin.lower().startswith("https://") for origin in _cors_origins):
    raise RuntimeError("Production CORS origins must use HTTPS.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(rooms_router)
app.include_router(activity_router)
app.include_router(social_router)

def _ws_user_id(websocket: WebSocket):
    authorization = websocket.headers.get("authorization", "")
    parts = authorization.strip().split(None, 1)
    token = parts[1].strip() if len(parts) == 2 and parts[0].lower() == "bearer" else ""
    if not token:
        token = websocket.query_params.get("token", "").strip()
    payload = decode_access_token(token) if token else None
    if not payload:
        return None
    try:
        user_id = int(payload.get("sub"))
        token_version = int(payload.get("ver"))
    except (TypeError, ValueError):
        return None
    if user_id <= 0 or payload.get("typ") != "access":
        return None
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or token_version != int(user.token_version or 0):
            return None
        return user_id
    finally:
        db.close()

@app.websocket("/ws/events")
async def ws_events(websocket: WebSocket):
    user_id = await asyncio.to_thread(_ws_user_id, websocket)
    if user_id is None:
        await websocket.close(code=1008, reason="Authentication required")
        return
    if not await ws_manager.connect(websocket, user_id):
        return
    try:
        event_times = deque()
        while True:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=45)
            if len(raw.encode("utf-8")) > _WS_MAX_JSON_BYTES:
                await websocket.close(code=1009, reason="Message too large")
                ws_manager.disconnect(websocket)
                return
            try:
                msg = json.loads(raw)
                if isinstance(msg, dict) and msg.get("type") == "ping":
                    ping_id = msg.get("ping_id")
                    response = {"type": "pong"}
                    if isinstance(ping_id, str) and len(ping_id) <= 64:
                        response["ping_id"] = ping_id
                    await ws_manager.send_json(websocket, response)
                    continue
            except Exception:
                pass
            now = time.monotonic()
            while event_times and now - event_times[0] >= _WS_EVENTS_WINDOW_SECONDS:
                event_times.popleft()
            if len(event_times) >= _WS_EVENTS_MAX_MESSAGES:
                await websocket.close(code=1008, reason="Message rate exceeded")
                ws_manager.disconnect(websocket)
                return
            event_times.append(now)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        logger.exception("Lobby WebSocket failed for user %s", user_id)
        ws_manager.disconnect(websocket)

_disconnect_grace_tasks: dict[tuple[str, int], asyncio.Task] = {}

def cancel_disconnect_grace_timer(room_id: str, user_id: int):
    """Cancel pending disconnect timer if player rejoins or explicitly leaves."""
    task = _disconnect_grace_tasks.pop((str(room_id), int(user_id)), None)
    if task and not task.done():
        task.cancel()

def cancel_room_disconnect_grace_timers(room_id: str):
    """Cancel all pending disconnect timers for a room being deleted or stopped."""
    target_keys = [k for k in _disconnect_grace_tasks if k[0] == str(room_id)]
    for k in target_keys:
        task = _disconnect_grace_tasks.pop(k, None)
        if task and not task.done():
            task.cancel()

async def _disconnect_grace_timeout(room_id: str, user_id: int, player_name: str):
    """Wait 120 seconds before treating unexpected disconnection as room departure."""
    try:
        await asyncio.sleep(120)
        _disconnect_grace_tasks.pop((str(room_id), int(user_id)), None)
        room = room_manager.get_room(room_id)
        if room and user_id in room.players:
            from server.app.api.rooms import leave_room_internal
            await leave_room_internal(room_id, user_id, player_name)
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("Error in disconnect grace timeout for user %s in room %s", user_id, room_id)

@app.websocket("/ws/room/{room_id}")
async def ws_room(websocket: WebSocket, room_id: str):
    user_id = await asyncio.to_thread(_ws_user_id, websocket)
    room = room_manager.get_room(room_id)
    is_room_member = room is not None and (user_id in room.players or user_id in room.spectators)
    if user_id is None or room is None or not is_room_member or user_id in room.banned_players:
        await websocket.close(code=1008, reason="Room access denied")
        return
    if not await ws_manager.connect(websocket, user_id, room_id=room_id):
        return

    # If this user had a pending disconnect grace timer, cancel it and announce reconnection!
    had_grace = (str(room_id), int(user_id)) in _disconnect_grace_tasks
    cancel_disconnect_grace_timer(room_id, user_id)
    player_name = room.player_names.get(user_id, "لاعب")
    if had_grace:
        logger.info("[انقطاع] %s أعاد الاتصال مجددا بالطاولة %s (user_id=%s)", player_name, room_id, user_id)
        print(f"[انقطاع] {player_name} أعاد الاتصال مجددا بالطاولة {room_id} (user_id={user_id})")
        ws_manager.broadcast_room(room_id, {
            "type": "player_reconnected",
            "user_id": user_id,
            "name": player_name,
            "room_id": room_id
        })

    # Build the initial snapshot while holding the room mutation lock so a
    # concurrent leave/stop/action cannot produce a mixed-version snapshot.
    try:
        async with room._mutation_lock:
            current_room = room_manager.get_room(room_id)
            is_room_member = current_room is not None and (user_id in current_room.players or user_id in current_room.spectators)
            if current_room is None or not is_room_member or user_id in current_room.banned_players:
                await websocket.close(code=1008, reason="Room access denied")
                ws_manager.disconnect(websocket, room_id=room_id)
                return
            snapshot = {
                "type": "room_snapshot",
                "room": current_room.public_dict(user_id),
                "uno_state": current_room.uno_game.state_for(user_id) if current_room.uno_game else None,
                "thief_state": current_room.thief_game.state_for(user_id) if current_room.thief_game else None,
                "farkle_state": current_room.farkle_game.state_for(user_id) if current_room.farkle_game else None,
                "domino_state": current_room.domino_game.get_state(user_id) if current_room.domino_game else None,
                "american_domino_state": current_room.american_domino_game.get_state(user_id) if current_room.american_domino_game else None,
                "snakes_state": current_room.snakes_game.get_state(user_id) if current_room.snakes_game else None,
                "scopa_state": current_room.scopa_game.public_state(user_id) if current_room.scopa_game else None,
                "tennis_state": current_room.tennis_game.full_state() if current_room.tennis_game else None,
                "ninety_nine_state": current_room.ninety_nine_game.state_for(user_id) if current_room.ninety_nine_game else None,
            }
        await ws_manager.send_json(websocket, snapshot, room_id)
        chat_times = deque()
        voice_times = deque()
        game_action_times = deque()
        while True:
            current_room = room_manager.get_room(room_id)
            is_room_member = current_room is not None and (user_id in current_room.players or user_id in current_room.spectators)
            if current_room is None or not is_room_member or user_id in current_room.banned_players:
                await websocket.close(code=1008, reason="Room membership ended")
                ws_manager.disconnect(websocket, room_id=room_id)
                return

            message = await asyncio.wait_for(websocket.receive(), timeout=45)
            if message.get("type") == "websocket.disconnect":
                raise WebSocketDisconnect()
            raw_bytes = message.get("bytes")
            if raw_bytes is not None:
                # Voice is opaque binary data at the server: authentication,
                # room isolation and rate/size limits are enforced here; the
                # client owns the codec so the server never performs audio work.
                if len(raw_bytes) > 4096 or len(raw_bytes) < 9 or raw_bytes[:4] != b"LFV1":
                    continue
                with ws_manager._state_lock:
                    voice_members = ws_manager.voice_connections.get(room_id, set())
                    is_voice_member = websocket in voice_members
                if not is_voice_member:
                    continue
                if current_room and (user_id in current_room.voice_banned or user_id in current_room.voice_muted):
                    continue
                now = time.monotonic()
                while voice_times and now - voice_times[0] >= 1.0:
                    voice_times.popleft()
                if len(voice_times) >= 60:
                    continue
                voice_times.append(now)
                outbound = b"LFS1" + struct.pack("<I", int(user_id)) + bytes(raw_bytes)
                ws_manager.broadcast_room_bytes(room_id, outbound, exclude=websocket)
                continue

            raw = message.get("text")
            if raw is None:
                continue
            if len(raw.encode("utf-8")) > _WS_MAX_JSON_BYTES:
                await websocket.close(code=1009, reason="Message too large")
                ws_manager.disconnect(websocket, room_id=room_id)
                return
            try:
                data = json.loads(raw)
            except (TypeError, ValueError):
                continue
            if not isinstance(data, dict):
                continue
            if data.get("type") == "ping":
                ping_id = data.get("ping_id")
                response = {"type": "pong"}
                if isinstance(ping_id, str) and len(ping_id) <= 64:
                    response["ping_id"] = ping_id
                await ws_manager.send_json(websocket, response, room_id)
                continue
            if data.get("type") == "voice_join" and set(data.keys()) == {"type"}:
                if current_room and user_id in current_room.voice_banned:
                    await ws_manager.send_json(websocket, {"type": "voice_banned_notice", "room_id": room_id, "message": "أنت محظور من المحادثة الصوتية في هذه الطاولة."}, room_id)
                    continue
                if ws_manager.join_voice(room_id, websocket):
                    await ws_manager.send_json(websocket, {"type": "voice_joined", "room_id": room_id}, room_id)
                    user_disp = (current_room.player_names.get(user_id) if current_room else None) or "لاعب"
                    ws_manager.broadcast_room(room_id, {
                        "type": "voice_user_joined",
                        "user_id": user_id,
                        "name": user_disp,
                    })
                continue
            if data.get("type") == "voice_leave" and set(data.keys()) == {"type"}:
                ws_manager.leave_voice(room_id, websocket)
                continue
            # Gameplay actions can use the already-open room WebSocket. This
            # avoids a second HTTP round trip for every move while keeping the
            # existing REST endpoint as the compatibility/fallback path.
            if data.get("type") == "game_action":
                request_id = data.get("request_id")
                if not isinstance(request_id, str) or not request_id or len(request_id) > 64:
                    continue
                action_payload = data.get("payload")
                if not isinstance(action_payload, dict):
                    continue
                now = time.monotonic()
                while game_action_times and now - game_action_times[0] >= 1.0:
                    game_action_times.popleft()
                if len(game_action_times) >= 20:
                    await ws_manager.send_json(websocket, {"type": "game_action_result", "request_id": request_id, "ok": False, "error": "عدد كبير جدًا من حركات اللعبة."}, room_id)
                    continue
                game_action_times.append(now)
                try:
                    req = RoomActionRequest.model_validate(action_payload)
                except Exception:
                    await ws_manager.send_json(websocket, {"type": "game_action_result", "request_id": request_id, "ok": False, "error": "إجراء لعبة غير صالح."}, room_id)
                    continue
                async with current_room._mutation_lock:
                    current_room = room_manager.get_room(room_id)
                    if current_room is None or user_id not in current_room.players or user_id in current_room.banned_players:
                        await websocket.close(code=1008, reason="Room membership ended")
                        ws_manager.disconnect(websocket, room_id=room_id)
                        return
                    from server.app.games.registry import get_plugin
                    plugin = get_plugin(current_room.game)
                    if not plugin or not plugin.get_engine(current_room):
                        await ws_manager.send_json(websocket, {"type": "game_action_result", "request_id": request_id, "ok": False, "error": "اللعبة غير نشطة."}, room_id)
                        continue
                    try:
                        result = await plugin.action_handler(current_room, user_id, req)
                        await ws_manager.send_json(websocket, {"type": "game_action_result", "request_id": request_id, "ok": True, "state": result}, room_id)
                    except ValueError as exc:
                        await ws_manager.send_json(websocket, {"type": "game_action_result", "request_id": request_id, "ok": False, "error": str(exc)}, room_id)
                    except Exception:
                        logger.exception("WebSocket game action failed for user %s in room %s", user_id, room_id)
                        await ws_manager.send_json(websocket, {"type": "game_action_result", "request_id": request_id, "ok": False, "error": "تعذر تنفيذ الحركة."}, room_id)
                continue
            # The room socket accepts chat only. Game/state events are server-only.
            if set(data.keys()) - {"text"}:
                continue
            text = data.get("text")
            if not isinstance(text, str):
                continue
            text = text.strip()
            if len(text) > 500:
                continue
            if not text:
                continue

            now = time.monotonic()
            while chat_times and now - chat_times[0] >= _WS_CHAT_WINDOW_SECONDS:
                chat_times.popleft()
            if len(chat_times) >= _WS_CHAT_MAX_MESSAGES:
                # Ignore excess messages rather than disconnecting a legitimate
                # user for a temporary burst. This prevents room-wide broadcast DoS.
                continue
            chat_times.append(now)

            async with current_room._mutation_lock:
                if user_id not in current_room.players or user_id in current_room.banned_players:
                    await websocket.close(code=1008, reason="Room membership ended")
                    ws_manager.disconnect(websocket, room_id=room_id)
                    return
                sender = current_room.player_names.get(user_id, "لاعب")
                message = {
                    "type": "chat_message",
                    "text": text,
                    "sender": sender,
                    "user_id": user_id,
                }
                all_members = set(current_room.players) | set(getattr(current_room, "spectators", []))
                recipients = [uid for uid in all_members if isinstance(uid, int) and uid > 0]

            # Chat delivery is latency-sensitive. Broadcast immediately after
            # the room membership check, then persist the activity record off
            # the asyncio event loop. The old implementation held the room
            # mutation lock while doing synchronous DB writes/commit, allowing
            # chat persistence to stall gameplay actions in the same room.
            ws_manager.broadcast_room(room_id, message)
            try:
                websocket.app.state.chat_persist_queue.put_nowait(
                    (room_id, user_id, sender, text, recipients)
                )
            except asyncio.QueueFull:
                logger.warning("Dropping chat activity persistence because the queue is full")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, room_id=room_id)
        _handle_room_disconnect(room_id, user_id)
    except Exception:
        logger.exception("Room WebSocket failed for user %s in room %s", user_id, room_id)
        ws_manager.disconnect(websocket, room_id=room_id)
        _handle_room_disconnect(room_id, user_id)

def _handle_room_disconnect(room_id: str, user_id: int):
    """When a player socket drops, start grace period if user is still a room member."""
    if not room_id or not user_id:
        return
    # If the user still has another active connection to this room, do not trigger disconnect grace
    if ws_manager.room_user_connected(room_id, user_id):
        return
    room = room_manager.get_room(room_id)
    if room and user_id in room.players:
        player_name = room.player_names.get(user_id, "لاعب")
        logger.info("[انقطاع] %s فقد الاتصال بالطاولة %s (user_id=%s)", player_name, room_id, user_id)
        print(f"[انقطاع] {player_name} فقد الاتصال بالطاولة {room_id} (user_id={user_id})")
        ws_manager.broadcast_room(room_id, {
            "type": "player_connection_lost",
            "user_id": user_id,
            "name": player_name,
            "room_id": room_id
        })
        cancel_disconnect_grace_timer(room_id, user_id)
        task = asyncio.create_task(_disconnect_grace_timeout(room_id, user_id, player_name))
        _disconnect_grace_tasks[(str(room_id), int(user_id))] = task
