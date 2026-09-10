import asyncio
import logging
import time
import threading
from collections import defaultdict
"""Room and game endpoints."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import update
from core_shared.protocol import CreateRoomRequest, StartGameRequest, RoomActionRequest, TargetUserRequest
from server.app.db.database import User, CoinTransaction, ChallengeInvitation, SessionLocal, get_db
from server.app.api.users import get_current_user
from server.app.hub.room_manager import room_manager
from server.app.hub.ws_manager import ws_manager
from server.app.activity import create_event

router = APIRouter(prefix="/api/rooms", tags=["rooms"])
logger = logging.getLogger("tableverse.rooms_api")

CREATE_ROOM_COST = 2
BOT_COST = 1
_MAX_ROOMS_GLOBAL = 500
_MAX_ROOMS_PER_HOST = 10
_ROOM_CREATE_WINDOW_SECONDS = 15 * 60
_ROOM_CREATE_MAX_PER_USER = 10
_ROOM_CREATE_MAX_TRACKED_USERS = 10_000
_room_create_times = defaultdict(list)
def _record_activity(recipient_ids, category, text, event_type, actor_id=None, room_id=None):
    """Persist one central activity event for each recipient and push it live."""
    ids = sorted({int(uid) for uid in recipient_ids if uid is not None and int(uid) > 0})
    if not ids:
        return
    db = SessionLocal()
    events = {}
    try:
        for uid in ids:
            event = create_event(
                db, uid, category, text, event_type=event_type, actor_id=actor_id, room_id=room_id
            )
            # Capture the scalar id while the ORM instance is still attached to
            # the live session. Session.close() expires ORM state, so reading
            # event.id after close can raise DetachedInstanceError.
            events[uid] = int(event.id) if event.id is not None else None
        db.commit()
    finally:
        db.close()
    for uid in ids:
        event_id = events.get(uid)
        ws_manager.broadcast_user(uid, {
            "type": "activity_event", "id": event_id,
            "category": category, "event_type": event_type,
            "text": text, "actor_id": actor_id, "room_id": room_id,
        })

_room_create_lock = asyncio.Lock()
_SUGGESTION_WINDOW_SECONDS = 15 * 60
_SUGGESTION_MAX_PER_USER = 5
_SUGGESTION_MAX_TRACKED_USERS = 10_000
_suggestion_times = defaultdict(list)
_suggestion_lock = threading.Lock()


def _require_room_member(room, user: User) -> None:
    if (user.id not in room.players and user.id not in room.spectators) or user.id in room.banned_players:
        raise HTTPException(403, "أنت لست عضوًا في هذه الطاولة.")


def _spend_coins(db: Session, user: User, amount: int, reason: str, *, commit: bool = True) -> int:
    """Debit coins with a database-level balance guard.

    When ``commit=False`` the debit and transaction remain in the caller's transaction so an in-memory room mutation can be committed atomically
    with the wallet debit.
    """
    if amount <= 0:
        raise ValueError("Coin amount must be positive")
    result = db.execute(
        update(User)
        .where(User.id == user.id)
        .where(User.coins >= amount)
        .values(coins=User.coins - amount)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(400, f"رصيدك غير كافٍ. تحتاج إلى {amount} عملة.")
    db.add(CoinTransaction(user_id=user.id, amount=-amount, reason=reason))
    if commit:
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
    db.refresh(user)
    return int(user.coins or 0)


def _refund_coins(db: Session, user: User, amount: int, reason: str) -> int:
    if amount <= 0:
        raise ValueError("Coin amount must be positive")
    db.execute(update(User).where(User.id == user.id).values(coins=User.coins + amount))
    db.add(CoinTransaction(user_id=user.id, amount=amount, reason=reason))
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(user)
    return int(user.coins or 0)


@router.get("")
async def list_rooms(user: User = Depends(get_current_user)):
    return await room_manager.list_rooms_consistent(user.id)

async def _check_room_create_rate_limit(user_id: int) -> None:
    now = time.monotonic()
    async with _room_create_lock:
        if user_id not in _room_create_times and len(_room_create_times) >= _ROOM_CREATE_MAX_TRACKED_USERS:
            oldest = min(_room_create_times, key=lambda uid: _room_create_times[uid][-1] if _room_create_times[uid] else 0)
            _room_create_times.pop(oldest, None)
        recent = [t for t in _room_create_times.get(user_id, []) if now - t < _ROOM_CREATE_WINDOW_SECONDS]
        if len(recent) >= _ROOM_CREATE_MAX_PER_USER:
            _room_create_times[user_id] = recent
            raise HTTPException(429, "أنشأت عددًا كبيرًا من الطاولات مؤخرًا. حاول مرة أخرى لاحقًا.", headers={"Retry-After": str(_ROOM_CREATE_WINDOW_SECONDS)})
        recent.append(now)
        _room_create_times[user_id] = recent

@router.post("")
async def create_room(req: CreateRoomRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    await _check_room_create_rate_limit(user.id)
    # Validate and build the room object first without publishing to the active rooms map.
    # The room is registered in memory strictly after the database transaction commits.
    room = None
    try:
        room = room_manager.build_room(
            host_id=user.id,
            host_name=user.display_name,
            game=req.game,
        )
        _spend_coins(db, user, CREATE_ROOM_COST, "فتح طاولة", commit=False)
        db.commit()
        room_manager.register_room(room)
    except HTTPException:
        db.rollback()
        raise
    except (ValueError, RuntimeError) as exc:
        db.rollback()
        raise HTTPException(400 if isinstance(exc, ValueError) else 429, str(exc))
    except Exception:
        db.rollback()
        logger.exception("Unexpected room creation failure for user %s", user.id)
        raise HTTPException(500, "حدث خطأ داخلي أثناء إنشاء الطاولة.")
    ws_manager.broadcast_lobby({"type": "room_created", "room_id": room.room_id})
    result = room.public_dict(user.id)
    try:
        db.refresh(user)
        result["coins"] = user.coins
    except Exception:
        # The wallet/room transaction already committed. Never delete a valid
        # room or attempt a second refund because a post-commit refresh failed.
        result["coins"] = None
        logger.warning("Room %s created but wallet refresh failed for user %s", room.room_id, user.id, exc_info=True)
    return result

@router.get("/{room_id}")
async def get_room(room_id: str, user: User = Depends(get_current_user)):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(404, "الطاولة غير موجودة.")
    async with room._mutation_lock:
        current = room_manager.get_room(room_id)
        if current is None:
            raise HTTPException(404, "الطاولة غير موجودة.")
        return current.public_dict(user.id)

@router.post("/{room_id}/invite/{user_id}")
async def invite_user_to_room(room_id: str, user_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Invite a user to the sender's current table. No new table is created."""
    if user_id == user.id:
        raise HTTPException(400, "لا يمكنك دعوة نفسك.")
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(404, "الطاولة غير موجودة.")
    if user.id not in room.players or user.id in room.banned_players:
        raise HTTPException(403, "يجب أن تكون داخل الطاولة لإرسال الدعوة.")
    # Invitations remain available for the lifetime of the table, including
    # while the match is already playing. Joining an active match remains
    # governed by the room/game lifecycle separately.
    if len(room.players) >= 10:
        raise HTTPException(409, "الطاولة مكتملة.")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(404, "المستخدم غير موجود.")
    from server.app.social_services import friend_ids, is_blocked, mute_flags, GAME_LABELS
    if user_id not in friend_ids(db, user.id):
        raise HTTPException(403, "دعوة الطاولة متاحة للأصدقاء فقط.")
    if is_blocked(db, user.id, user_id):
        raise HTTPException(403, "لا يمكن إرسال دعوة لهذا اللاعب.")
    if room_manager.user_in_any_room(user_id):
        raise HTTPException(409, "اللاعب موجود حاليًا في طاولة.")
    if target.invite_policy == "nobody":
        raise HTTPException(403, "هذا اللاعب لا يستقبل دعوات اللعب.")
    if target.invite_policy == "friends" and user_id not in friend_ids(db, user.id):
        raise HTTPException(403, "دعوات اللعب لهذا اللاعب متاحة للأصدقاء فقط.")
    existing = db.query(ChallengeInvitation).filter(
        ChallengeInvitation.sender_id == user.id,
        ChallengeInvitation.recipient_id == user_id,
        ChallengeInvitation.room_id == room.room_id,
        ChallengeInvitation.status == "pending",
    ).first()
    if existing:
        raise HTTPException(409, "تم إرسال دعوة لهذا اللاعب بالفعل.")
    result = db.execute(update(User).where(User.id == user.id).where(User.coins >= 1).values(coins=User.coins - 1))
    if result.rowcount != 1:
        raise HTTPException(400, "رصيدك غير كافٍ. تحتاج إلى 1 عملة.")
    db.add(CoinTransaction(user_id=user.id, amount=-1, reason="challenge:invite"))
    inv = ChallengeInvitation(sender_id=user.id, recipient_id=user_id, status="pending", room_id=room.room_id, game=room.game)
    db.add(inv); db.flush()
    text_msg = f"{user.display_name} دعاك للانضمام إلى طاولة {GAME_LABELS.get(room.game, room.game)}."
    event = create_event(db, user_id, "INVITATIONS", text_msg, event_type="CHALLENGE_INVITATION", actor_id=user.id, room_id=room.room_id, payload={"invitation_id": inv.id, "room_id": room.room_id, "game": room.game})
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    try:
        flags = mute_flags(db, user_id, user.id)
        ws_manager.broadcast_user(user_id, {
            "type": "activity_event",
            "id": int(event.id) if event.id is not None else None,
            "category": "INVITATIONS",
            "event_type": "CHALLENGE_INVITATION",
            "text": text_msg,
            "actor_id": user.id,
            "room_id": room.room_id,
            "payload": {"invitation_id": inv.id, "room_id": room.room_id, "game": room.game, "sender_id": user.id, "sender": user.display_name},
            "notification_muted": bool(flags["all"] or flags["invitations"])
        })
    except Exception:
        # The invitation is already persisted; notification delivery is best effort.
        logger.warning("Invitation notification failed for invitation %s", inv.id, exc_info=True)
    return {"ok": True, "id": inv.id, "room_id": room.room_id, "game": room.game, "coins_charged": 1}

@router.post("/{room_id}/join")
async def join_room(room_id: str, as_spectator: bool = False, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(404, "الطاولة غير موجودة.")
    if user.id in room.banned_players:
        raise HTTPException(403, "أنت محظور من هذه الطاولة.")
        
    # Join Policy Check & Block Check
    host = db.query(User).filter(User.id == room.host_id).first()
    if host and host.id != user.id:
        from server.app.social_services import is_blocked, friend_ids
        if is_blocked(db, host.id, user.id):
            raise HTTPException(403, "لا يمكنك الانضمام لطاولة هذا المستخدم.")
        if host.join_policy == "nobody":
            raise HTTPException(403, "هذه الطاولة مغلقة بواسطة صاحبها.")
        elif host.join_policy == "friends":
            if user.id not in friend_ids(db, host.id):
                raise HTTPException(403, "هذه الطاولة للأصدقاء فقط.")

    if as_spectator:
        joined = room_manager.add_spectator_exclusive(room, user.id, user.display_name)
        if not joined:
            raise HTTPException(409, "أنت داخل طاولة أخرى حاليًا.")
        ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})
        ws_manager.broadcast_room(room.room_id, {
            "type": "spectator_changed",
            "user_id": user.id,
            "name": user.display_name,
            "is_spectator": True,
            "spectators": list(room.spectators),
            "players": list(room.players),
            "player_names": [room.player_names[uid] for uid in room.players if uid in room.player_names],
            "players_dict": {str(uid): room.player_names.get(uid, "لاعب") for uid in set(room.players) | set(room.spectators)},
        })
        return room.public_dict(user.id)

    if room.status != "waiting":
        raise HTTPException(400, "لا يمكن الانضمام إلى هذه الطاولة الآن.")
    if len(room.players) >= 10:
        raise HTTPException(409, "تغيرت حالة الطاولة. حاول مرة أخرى.")
    joined = room_manager.add_player_exclusive(room, user.id, user.display_name)
    if not joined:
        raise HTTPException(409, "أنت داخل طاولة حاليًا.")
    ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})
    ws_manager.broadcast_room(room.room_id, {"type": "player_joined", "user_id": user.id, "name": user.display_name})
    return room.public_dict(user.id)

@router.post("/{room_id}/leave")
async def leave_room_internal(room_id: str, user_id: int, user_display_name: str):
    room = room_manager.get_room(room_id)
    if not room:
        return {"ok": True}
    try:
        from server.app.main import cancel_disconnect_grace_timer
        cancel_disconnect_grace_timer(room_id, user_id)
    except Exception:
        pass
    was_host = user_id == room.host_id
    
    bot_id = -user_id
    while bot_id in room.players:
        bot_id -= 1
    bot_name = f"Bot_{user_display_name}"
    
    async with room._mutation_lock:
        if room.status in ("playing", "round_finished", "match_finished"):
            if room.game == "FARKLE" and user_id in room.spectators:
                room.spectators.remove(user_id)
            else:
                if bot_id not in room.players:
                    room.add_player(bot_id, bot_name)
                from server.app.games.registry import get_plugin
                plugin = get_plugin(room.game)
                if plugin and plugin.bot_replace_handler:
                    plugin.bot_replace_handler(room, user_id, bot_id, bot_name, plugin)
                room.players = [uid for uid in room.players if uid != user_id]
                room.player_names.pop(user_id, None)
                room.scores.pop(user_id, None)
                if user_id == room.co_host_id:
                    room.co_host_id = None
                if user_id in room.spectators:
                    room.spectators.remove(user_id)
        else:
            room.remove_player(user_id)

    await ws_manager.disconnect_user_from_room(room_id, user_id)

    if not room.players:
        room_manager.delete_room(room_id)
        ws_manager.broadcast_lobby({"type": "room_deleted", "room_id": room_id})
        return {"ok": True}

    if was_host:
        human_players = [uid for uid in room.players if uid > 0]
        if not human_players:
            room_manager.delete_room(room_id)
            ws_manager.broadcast_lobby({"type": "room_deleted", "room_id": room_id})
            return {"ok": True}
        new_host = human_players[0]
        room.host_id = new_host
        room.host_name = room.player_names[new_host]
        ws_manager.broadcast_room(room_id, {"type": "captain_changed", "user_id": new_host, "name": room.host_name})

    ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room_id})
    ws_manager.broadcast_room(room_id, {"type": "player_left", "user_id": user_id, "name": user_display_name})
    
    if room.status in ("playing", "round_finished", "match_finished"):
        if room.game != "FARKLE" or user_id not in room.spectators:
            ws_manager.broadcast_room(room_id, {"type": "bot_added", "user_id": bot_id, "name": bot_name})
            ws_manager.broadcast_room(room_id, {"type": "game_state_changed", "room_id": room_id})
            
    return {"ok": True}

@router.post("/{room_id}/leave")
async def leave_room(room_id: str, user: User = Depends(get_current_user)):
    # Cancel any pending disconnect grace timer since player is explicitly leaving
    from server.app.main import cancel_disconnect_grace_timer
    cancel_disconnect_grace_timer(room_id, user.id)
    return await leave_room_internal(room_id, user.id, user.display_name)

@router.post("/{room_id}/bot")
async def add_bot(room_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(404, "الطاولة غير موجودة.")
    if user.id != room.host_id:
        raise HTTPException(403, "إضافة بوت متاح لمضيف الطاولة فقط.")
    if room.status != "waiting":
        raise HTTPException(400, "لا يمكن إضافة بوت بعد بدء المباراة.")
    if len(room.players) >= 10:
        raise HTTPException(400, "الطاولة مكتملة.")

    # Keep the wallet debit and bot insertion in one request transaction.
    # The bot is not broadcast until the database commit succeeds.
    bot_id = None
    name = None
    async with room._mutation_lock:
        uid_int = int(user.id)
        is_member = (uid_int in room.players or uid_int in room.spectators)
        if uid_int != int(room.host_id) or not is_member or uid_int in room.banned_players:
            raise HTTPException(403, "لم تعد مخولًا لإضافة بوت إلى هذه الطاولة.")
        if room.status != "waiting" or len(room.players) >= 10:
            raise HTTPException(409, "تغيرت حالة الطاولة. حاول مرة أخرى.")
        bot_id = room._next_bot_id
        try:
            _spend_coins(db, user, BOT_COST, "إضافة بوت", commit=False)
            name = room.add_bot()
            db.commit()
        except HTTPException:
            db.rollback()
            if bot_id in room.players:
                room.remove_player(bot_id)
            room._next_bot_id = bot_id
            raise
        except Exception:
            db.rollback()
            if bot_id in room.players:
                room.remove_player(bot_id)
            room._next_bot_id = bot_id
            logger.exception("Failed to atomically add bot for user %s", user.id)
            raise HTTPException(500, "تعذر إضافة البوت وإتمام العملية بأمان.")

    ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room_id})
    ws_manager.broadcast_room(room_id, {
        "type": "bot_added",
        "user_id": bot_id,
        "name": name,
        "players": list(room.players),
        "player_names": [room.player_names[uid] for uid in room.players if uid in room.player_names],
        "players_dict": {str(uid): room.player_names.get(uid, "لاعب") for uid in set(room.players) | set(room.spectators)},
    })
    result = room.public_dict(user.id)
    try:
        db.refresh(user)
        result["coins"] = user.coins
    except Exception:
        result["coins"] = None
        logger.warning("Bot added to room %s but wallet refresh failed for user %s", room.room_id, user.id, exc_info=True)
    return result

@router.post("/{room_id}/bot/remove")
@router.delete("/{room_id}/bot")
async def remove_bot(room_id: str, user: User = Depends(get_current_user)):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(404, "الطاولة غير موجودة.")
    if int(user.id) != int(room.host_id):
        raise HTTPException(403, "إزالة بوت متاح للمضيف فقط.")
    if room.status != "waiting":
        raise HTTPException(400, "لا يمكن إزالة بوت بعد بدء المباراة.")
    async with room._mutation_lock:
        uid_int = int(user.id)
        is_member = (uid_int in room.players or uid_int in room.spectators)
        if uid_int != int(room.host_id) or not is_member or uid_int in room.banned_players:
            raise HTTPException(403, "لم تعد مخولًا لإزالة بوت من هذه الطاولة.")
        if room.status != "waiting":
            raise HTTPException(409, "تغيرت حالة الطاولة. حاول مرة أخرى.")
        name = room.remove_bot()
        if not name:
            raise HTTPException(400, "لا يوجد بوت في الطاولة.")
    ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room_id})
    ws_manager.broadcast_room(room_id, {
        "type": "bot_removed",
        "name": name,
        "players": list(room.players),
        "player_names": [room.player_names[uid] for uid in room.players if uid in room.player_names],
        "players_dict": {str(uid): room.player_names.get(uid, "لاعب") for uid in set(room.players) | set(room.spectators)},
    })
    return {"ok": True, "name": name, "room": room.public_dict(user.id)}

def _validate_game_configuration(game: str, target_score: int, rules: dict) -> tuple[int, dict]:
    """Strict server-side validation for game settings supplied by clients.

    The client settings UI is not a trust boundary. Each game receives only
    the rule keys and value types it actually supports, with bounded numeric
    values. Unknown keys are rejected instead of being silently passed into
    the game engines.
    """
    game = str(game or "").upper()
    rules = dict(rules or {})
    specs = {
        "UNO": ({k: "bool" for k, _, _ in __import__("core_shared.rules_config", fromlist=["RULE_DEFINITIONS"]).RULE_DEFINITIONS}, (1, 9999)),
        "THIEF_HUNT": ({"rounds": ("int", 1, 10), "allow_human_thief": "bool", "elimination_mode": "bool"}, (1, 1)),
        "FARKLE": ({"min_bank": ("int", 30, 10000), "first_bank_min": ("int", 50, 10000)}, (1, 100000)),
        "DOMINO": ({"mode": ("choice", {"draw", "block"}), "hand_size": ("int", 1, 7)}, (1, 10000)),
        "AMERICAN_DOMINO": ({"hand_size": ("int", 1, 7), "scoring_mode": ("choice", {"standard", "unit"})}, (1, 10000)),
        "SNAKES_LADDERS": ({"knockout": "bool", "mystery_tiles": "bool"}, (100, 100)),
        "SCOPA": ({"scopa_mode": ("choice", {"classic", "escoba_15", "asso_piglia_tutto", "scopone"}), "classic": "bool", "escoba_15": "bool", "asso_piglia_tutto": "bool", "scopone": "bool", "inverted": "bool"}, (1, 1000)),
        "TENNIS": ({"bot_difficulty": ("choice", {"EASY", "NORMAL", "HARD", "EXPERT"})}, (1, 5)),
        "NINETY_NINE": ({"starting_tokens": ("int", 1, 99)}, (1, 99)),
    }
    allowed, target_bounds = specs.get(game, ({}, (1, 9999)))
    unknown = sorted(set(rules) - set(allowed))
    if unknown:
        raise HTTPException(400, f"إعدادات غير مسموحة للعبة: {', '.join(unknown)}")
    for key, value in rules.items():
        spec = allowed[key]
        if spec == "bool":
            if type(value) is not bool:
                raise HTTPException(400, f"قيمة الإعداد {key} يجب أن تكون منطقية.")
        elif isinstance(spec, tuple) and spec[0] == "int":
            if type(value) is not int or not (spec[1] <= value <= spec[2]):
                raise HTTPException(400, f"قيمة الإعداد {key} خارج النطاق المسموح.")
        elif isinstance(spec, tuple) and spec[0] == "choice":
            if type(value) is not str or value not in spec[1]:
                raise HTTPException(400, f"قيمة الإعداد {key} غير صالحة.")
    target = int(target_score)
    if not (target_bounds[0] <= target <= target_bounds[1]):
        raise HTTPException(400, "قيمة الهدف خارج النطاق المسموح لهذه اللعبة.")
    # Keep game-specific settings internally consistent.
    if game == "UNO":
        from core_shared.rules_config import NO_MERCY_CHILDREN
        if rules.get("uno_flip") and rules.get("no_mercy"):
            raise HTTPException(400, "لا يمكن تفعيل UNO Flip وNo Mercy معًا.")
        if not rules.get("no_mercy") and any(rules.get(k) for k in NO_MERCY_CHILDREN):
            raise HTTPException(400, "قواعد No Mercy الفرعية تتطلب تفعيل No Mercy.")
    if game == "SCOPA":
        base_modes = [rules.get("classic"), rules.get("escoba_15"), rules.get("asso_piglia_tutto"), rules.get("scopone")]
        if sum(bool(x) for x in base_modes) > 1:
            raise HTTPException(400, "يجب اختيار وضع أساسي واحد فقط في إسكوبا.")
        if rules.get("scopa_mode") == "scopone" and rules.get("scopone") is not True:
            raise HTTPException(400, "إعداد وضع إسكوبوني غير متسق.")
    return target, rules


@router.post("/{room_id}/start")
async def start_game(room_id: str, req: StartGameRequest, user: User = Depends(get_current_user)):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(404, "Room not found.")
    is_authorized = (user.id == room.host_id or (room.co_host_id is not None and user.id == room.co_host_id))
    if not is_authorized:
        raise HTTPException(403, "بدء اللعبة متاح للقائد أو نائب القائد فقط.")

    from server.app.games.registry import get_plugin
    plugin = get_plugin(room.game)
    if not plugin:
        raise HTTPException(400, "Unknown game.")

    async with room._mutation_lock:
        is_member = (user.id in room.players or user.id in room.spectators)
        if (user.id != room.host_id and user.id != room.co_host_id) or not is_member or user.id in room.banned_players:
            raise HTTPException(403, "Access denied.")
        if room.status != "waiting":
            raise HTTPException(400, "Game already started.")
        
        # Farkle filters out spectators. The other games don't explicitly do it here, but Farkle did it in its block.
        if room.game == "FARKLE":
            players_tuples = [(uid, room.player_names[uid]) for uid in room.players if uid not in room.spectators]
        else:
            players_tuples = [(uid, room.player_names[uid]) for uid in room.players]

        # Enforce each game's supported player cardinality at the API boundary.
        # Individual engines keep their own validation too, but this prevents
        # malformed room starts from reaching engines with incompatible deal
        # or turn structures.
        player_count = len(players_tuples)
        limits = {
            "UNO": (2, 10),
            "THIEF_HUNT": (2, 10),
            "FARKLE": (2, 10),
            "DOMINO": (2, 5),
            "AMERICAN_DOMINO": (2, 5),
            "SNAKES_LADDERS": (2, 10),
            "SCOPA": (2, 6),
            "TENNIS": (2, 2),
            "NINETY_NINE": (2, 10),
        }
        min_players, max_players = limits.get(room.game, (1, 10))
        if not (min_players <= player_count <= max_players):
            raise HTTPException(400, f"هذه اللعبة تتطلب من {min_players} إلى {max_players} لاعبين.")
        if room.game == "SCOPA" and (req.rules or {}).get("scopa_mode") == "scopone" and player_count != 4:
            raise HTTPException(400, "وضع سكوبوني يتطلب أربعة لاعبين بالضبط.")

        # The API accepts an omitted target and resolves the authoritative default
        # here, so every game receives its own documented target instead of the
        # old global UNO/Farkle-incompatible default of 500.
        default_targets = {
            "UNO": 500, "THIEF_HUNT": 1, "FARKLE": 1500, "DOMINO": 100,
            "AMERICAN_DOMINO": 150, "SNAKES_LADDERS": 100, "SCOPA": 11,
            "TENNIS": 1, "NINETY_NINE": 11,
        }
        target_score = req.target_score if req.target_score is not None else default_targets.get(room.game, 1)
        target_score, validated_rules = _validate_game_configuration(room.game, target_score, req.rules or {})
        try:
            res = await plugin.start_handler(room, target_score, validated_rules, players_tuples)
            if res:
                pass
            now = datetime.now(timezone.utc).isoformat()
            room.table_started_at = room.table_started_at or now
            room.round_started_at = now
        except ValueError as e:
            raise HTTPException(400, str(e))

    ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room_id})
    ws_manager.broadcast_room(room_id, {"type": "game_state_changed", "room_id": room_id})
    _record_activity([uid for uid in room.players if uid > 0], "GAMEPLAY", f"بدأت لعبة {room.game}", "GAME_STARTED", user.id, room_id)
    return room.public_dict(user.id)

@router.get("/{room_id}/game/state")
async def game_state(room_id: str, user: User = Depends(get_current_user)):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(404, "Room not found.")
    async with room._mutation_lock:
        _require_room_member(room, user)
        from server.app.games.registry import get_plugin
        plugin = get_plugin(room.game)
        if not plugin or not plugin.get_engine(room):
            raise HTTPException(409, "Game not active.")
        try:
            return plugin.get_state_handler(plugin.get_engine(room), user.id)
        except ValueError as e:
            raise HTTPException(400, str(e))

@router.post("/{room_id}/game/action")
async def game_action(room_id: str, req: RoomActionRequest, user: User = Depends(get_current_user)):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(404, "Room not found.")
    _require_room_member(room, user)
    async with room._mutation_lock:
        _require_room_member(room, user)
        from server.app.games.registry import get_plugin
        plugin = get_plugin(room.game)
        if not plugin or not plugin.get_engine(room):
            raise HTTPException(409, "Game not active.")
        try:
            return await plugin.action_handler(room, user.id, req)
        except ValueError as e:
            raise HTTPException(400, str(e))

@router.post("/{room_id}/stop")
async def stop_game(room_id: str, user: User = Depends(get_current_user)):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(404, "Room not found.")
    if user.id != room.host_id:
        raise HTTPException(403, "Only the captain can stop the game.")

    async with room._mutation_lock:
        is_member = (user.id in room.players or user.id in room.spectators)
        if user.id != room.host_id or not is_member or user.id in room.banned_players:
            raise HTTPException(403, "Access denied.")
        if room.status not in ("playing", "round_finished", "match_finished"):
            raise HTTPException(400, "Game is not playing.")
            
        from server.app.games.registry import get_plugin
        plugin = get_plugin(room.game)
        if plugin:
            plugin.stop_handler(room, plugin)

        room.status = "waiting"
        room.target_score = None
        room.rules = {}
        room.scores = {uid: 0 for uid in room.players}
        room.round_started_at = None

    ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room_id})
    ws_manager.broadcast_room(room_id, {"type": "game_stopped", "room_id": room_id})
    _record_activity([uid for uid in room.players if uid > 0], "GAMEPLAY", f"توقفت لعبة {room.game}", "GAME_STOPPED", user.id, room_id)
    return room.public_dict(user.id)

@router.post("/{room_id}/kick")
async def kick_player(room_id: str, req: TargetUserRequest, user: User = Depends(get_current_user)):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(404, "الطاولة غير موجودة.")
    is_authorized = (user.id == room.host_id or (room.co_host_id is not None and user.id == room.co_host_id))
    if not is_authorized:
        raise HTTPException(403, "طرد اللاعبين متاح للقائد أو نائب القائد فقط.")
    if room.status != "waiting":
        raise HTTPException(400, "لا يمكن طرد لاعب أثناء اللعب.")
    target_id = req.target_user_id
    if target_id == room.host_id:
        raise HTTPException(400, "لا يمكن طرد قائد الطاولة.")
    if user.id == room.co_host_id and target_id == room.co_host_id:
        raise HTTPException(400, "لا يمكن لنائب القائد طرد نفسه بهذا الإجراء.")
    target_name = room.player_names.get(target_id, "لاعب")
    if target_id < 0:
        async with room._mutation_lock:
            room.remove_player(target_id)
            room.scores.pop(target_id, None)
        ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room_id})
        ws_manager.broadcast_room(room_id, {
            "type": "bot_removed",
            "name": target_name,
            "players": list(room.players),
            "player_names": [room.player_names[uid] for uid in room.players if uid in room.player_names],
            "players_dict": {str(uid): room.player_names.get(uid, "لاعب") for uid in set(room.players) | set(room.spectators)},
        })
        return {"ok": True}
    await leave_room_internal(room_id, target_id, target_name)
    actor_label = "القائد" if user.id == room.host_id else "نائب القائد"
    ws_manager.broadcast_user(target_id, {"type": "kicked_from_room", "room_id": room_id, "message": f"تم طردك من الطاولة بواسطة {actor_label}."})
    ws_manager.broadcast_room(room_id, {"type": "player_kicked", "user_id": target_id, "name": target_name, "actor_id": user.id, "actor_label": actor_label})
    return {"ok": True}

@router.post("/{room_id}/ban")
async def ban_player(room_id: str, req: TargetUserRequest, user: User = Depends(get_current_user)):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(404, "الطاولة غير موجودة.")
    is_authorized = (user.id == room.host_id or (room.co_host_id is not None and user.id == room.co_host_id))
    if not is_authorized:
        raise HTTPException(403, "حظر اللاعبين متاح للقائد أو نائب القائد فقط.")
    if room.status != "waiting":
        raise HTTPException(400, "لا يمكن حظر لاعب أثناء اللعب.")
    target_id = req.target_user_id
    if target_id == room.host_id:
        raise HTTPException(400, "لا يمكن حظر قائد الطاولة.")
    if user.id == room.co_host_id and target_id == room.co_host_id:
        raise HTTPException(400, "لا يمكن لنائب القائد حظر نفسه.")
    target_name = room.player_names.get(target_id, "لاعب")
    if target_id < 0:
        async with room._mutation_lock:
            room.remove_player(target_id)
            room.scores.pop(target_id, None)
        ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room_id})
        ws_manager.broadcast_room(room_id, {
            "type": "bot_removed",
            "name": target_name,
            "players": list(room.players),
            "player_names": [room.player_names[uid] for uid in room.players if uid in room.player_names],
            "players_dict": {str(uid): room.player_names.get(uid, "لاعب") for uid in set(room.players) | set(room.spectators)},
        })
        return {"ok": True}
    room.banned_players.add(target_id)
    await leave_room_internal(room_id, target_id, target_name)
    actor_label = "القائد" if user.id == room.host_id else "نائب القائد"
    ws_manager.broadcast_user(target_id, {"type": "banned_from_room", "room_id": room_id, "message": f"تم حظرك من هذه الطاولة بواسطة {actor_label}."})
    ws_manager.broadcast_room(room_id, {"type": "player_banned", "user_id": target_id, "name": target_name, "actor_id": user.id, "actor_label": actor_label})
    return {"ok": True}

@router.post("/{room_id}/voice/mute")
async def voice_mute_player(room_id: str, req: TargetUserRequest, user: User = Depends(get_current_user)):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(404, "الطاولة غير موجودة.")
    if user.id != room.host_id:
        raise HTTPException(403, "كتم ميكروفون اللاعبين متاح للقائد فقط.")
    target_id = req.target_user_id
    if target_id in room.voice_muted:
        room.voice_muted.remove(target_id)
        action = "unmuted"
    else:
        room.voice_muted.add(target_id)
        action = "muted"
    target_name = room.player_names.get(target_id, "لاعب")
    ws_manager.broadcast_room(room_id, {
        "type": "voice_mute_changed",
        "user_id": target_id,
        "name": target_name,
        "is_muted": target_id in room.voice_muted
    })
    return {"ok": True, "action": action, "is_muted": target_id in room.voice_muted}

@router.post("/{room_id}/voice/kick")
async def voice_kick_player(room_id: str, req: TargetUserRequest, user: User = Depends(get_current_user)):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(404, "الطاولة غير موجودة.")
    if user.id != room.host_id:
        raise HTTPException(403, "إزالة اللاعبين من المحادثة الصوتية متاح للقائد فقط.")
    target_id = req.target_user_id
    with ws_manager._state_lock:
        sockets = [ws for ws in ws_manager.voice_connections.get(room_id, set()) if ws_manager.connection_users.get(ws) == target_id]
    for ws in sockets:
        ws_manager.leave_voice(room_id, ws)
    target_name = room.player_names.get(target_id, "لاعب")
    ws_manager.broadcast_user(target_id, {"type": "voice_kicked", "room_id": room_id, "message": "تم إخراجك من المحادثة الصوتية بواسطة القائد."})
    ws_manager.broadcast_room(room_id, {"type": "voice_user_kicked", "user_id": target_id, "name": target_name})
    return {"ok": True}

@router.post("/{room_id}/voice/ban")
async def voice_ban_player(room_id: str, req: TargetUserRequest, user: User = Depends(get_current_user)):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(404, "الطاولة غير موجودة.")
    if user.id != room.host_id:
        raise HTTPException(403, "حظر اللاعبين من المحادثة الصوتية متاح للقائد فقط.")
    target_id = req.target_user_id
    room.voice_banned.add(target_id)
    with ws_manager._state_lock:
        sockets = [ws for ws in ws_manager.voice_connections.get(room_id, set()) if ws_manager.connection_users.get(ws) == target_id]
    for ws in sockets:
        ws_manager.leave_voice(room_id, ws)
    target_name = room.player_names.get(target_id, "لاعب")
    ws_manager.broadcast_user(target_id, {"type": "voice_banned", "room_id": room_id, "message": "تم حظرك من المحادثة الصوتية في هذه الطاولة."})
    ws_manager.broadcast_room(room_id, {"type": "voice_user_banned", "user_id": target_id, "name": target_name})
    return {"ok": True}

@router.post("/{room_id}/spectator")
async def toggle_spectator(room_id: str, req: Optional[TargetUserRequest] = None, user: User = Depends(get_current_user)):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(404, "الطاولة غير موجودة.")
    target_id = (req.target_user_id if req and req.target_user_id is not None else user.id)
    if target_id != user.id and user.id != room.host_id:
        raise HTTPException(403, "تحويل لاعب آخر لمتفرج متاح للقائد فقط.")
    if room.status != "waiting":
        raise HTTPException(400, "لا يمكن تغيير وضع المتفرج أثناء اللعب.")

    async with room._mutation_lock:
        if target_id in room.spectators:
            room.spectators.remove(target_id)
            if target_id not in room.players:
                room.players.append(target_id)
            is_spectator = False
        else:
            if target_id == room.host_id and len(room.players) <= 1:
                # Allow host to be spectator as well if they wish
                pass
            room.spectators.append(target_id)
            if target_id in room.players:
                room.players.remove(target_id)
            is_spectator = True

    target_name = room.player_names.get(target_id, "لاعب")
    ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room_id})
    ws_manager.broadcast_room(room_id, {
        "type": "spectator_changed",
        "user_id": target_id,
        "name": target_name,
        "is_spectator": is_spectator,
        "spectators": list(room.spectators),
        "players": list(room.players),
        "player_names": [room.player_names[uid] for uid in room.players if uid in room.player_names],
        "players_dict": {str(uid): room.player_names.get(uid, "لاعب") for uid in set(room.players) | set(room.spectators)},
    })
    return {"ok": True, "is_spectator": is_spectator, "room": room.public_dict(user.id)}

@router.post("/{room_id}/transfer_host")
async def transfer_host(room_id: str, req: TargetUserRequest, user: User = Depends(get_current_user)):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(404, "الطاولة غير موجودة.")
    if user.id != room.host_id:
        raise HTTPException(403, "نقل القيادة متاح للقائد فقط.")
    target_id = req.target_user_id
    if not target_id or target_id <= 0:
        raise HTTPException(400, "يجب تحديد لاعب لنقل القيادة إليه.")
    if target_id == room.host_id:
        raise HTTPException(400, "أنت قائد الطاولة بالفعل.")
    if target_id not in room.players:
        raise HTTPException(400, "اللاعب غير موجود في الطاولة.")

    target_name = room.player_names.get(target_id, "لاعب")
    async with room._mutation_lock:
        room.host_id = target_id
        room.host_name = target_name
        if room.co_host_id == target_id:
            room.co_host_id = None

    ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room_id})
    ws_manager.broadcast_room(room_id, {
        "type": "captain_changed",
        "user_id": target_id,
        "name": target_name,
        "co_host_id": room.co_host_id,
    })
    return {"ok": True, "host_id": target_id, "host_name": target_name}

@router.post("/{room_id}/set_co_host")
async def set_co_host(room_id: str, req: TargetUserRequest, user: User = Depends(get_current_user)):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(404, "الطاولة غير موجودة.")
    if user.id != room.host_id:
        raise HTTPException(403, "تعيين نائب القائد متاح للقائد فقط.")
    target_id = req.target_user_id
    if not target_id or target_id <= 0:
        raise HTTPException(400, "يجب تحديد لاعب.")
    if target_id == room.host_id:
        raise HTTPException(400, "لا يمكن تعيين القائد كنائب للقائد.")
    if target_id not in room.players:
        raise HTTPException(400, "اللاعب غير موجود في الطاولة.")

    target_name = room.player_names.get(target_id, "لاعب")
    async with room._mutation_lock:
        if room.co_host_id == target_id:
            room.co_host_id = None
            is_co_host = False
        else:
            room.co_host_id = target_id
            is_co_host = True

    ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room_id})
    ws_manager.broadcast_room(room_id, {
        "type": "co_captain_changed",
        "user_id": target_id if is_co_host else None,
        "name": target_name if is_co_host else "",
        "co_host_id": room.co_host_id,
        "is_co_host": is_co_host,
    })
    return {"ok": True, "co_host_id": room.co_host_id, "is_co_host": is_co_host}

@router.post("/{room_id}/substitute")
async def substitute_player(room_id: str, req: TargetUserRequest, user: User = Depends(get_current_user)):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(404, "الطاولة غير موجودة.")
    is_authorized = (user.id == room.host_id or (room.co_host_id is not None and user.id == room.co_host_id))
    if not is_authorized:
        raise HTTPException(403, "الاستبدال متاح للقائد أو نائب القائد فقط.")
    target_id = req.target_user_id
    if not target_id or target_id <= 0:
        raise HTTPException(400, "يجب تحديد لاعب للاستبدال.")
    if target_id == room.host_id:
        raise HTTPException(400, "لا يمكن استبدال قائد الطاولة.")
    if target_id not in room.players and target_id not in room.spectators:
        raise HTTPException(400, "اللاعب غير موجود في الطاولة.")

    target_name = room.player_names.get(target_id, "لاعب")
    actor_label = "القائد" if user.id == room.host_id else "نائب القائد"

    # Check replacement type: bot or another user
    rep_id = req.replacement_user_id
    is_bot_replacement = bool(req.is_bot) or (rep_id is None) or (rep_id <= 0)

    if not is_bot_replacement:
        if rep_id not in room.players and rep_id not in room.spectators:
            raise HTTPException(400, "اللاعب البديل غير موجود في الطاولة.")
        if rep_id == target_id:
            raise HTTPException(400, "لا يمكن استبدال اللاعب بنفسه.")
        rep_name = room.player_names.get(rep_id, "لاعب")

        async with room._mutation_lock:
            # If replacement is a spectator: promote replacement to player, demote target to spectator
            if rep_id in room.spectators:
                room.spectators.remove(rep_id)
                if rep_id not in room.players:
                    room.players.append(rep_id)
                if target_id in room.players:
                    room.players.remove(target_id)
                if target_id not in room.spectators:
                    room.spectators.append(target_id)
            elif rep_id in room.players and target_id in room.players:
                # Both are players: swap positions in room.players
                idx1 = room.players.index(target_id)
                idx2 = room.players.index(rep_id)
                room.players[idx1], room.players[idx2] = room.players[idx2], room.players[idx1]

            # In an active match: swap player in the game engine
            if room.status in ("playing", "round_finished", "match_finished"):
                from server.app.games.registry import get_plugin
                plugin = get_plugin(room.game)
                if plugin and plugin.bot_replace_handler:
                    plugin.bot_replace_handler(room, target_id, rep_id, rep_name, plugin)

        ws_manager.broadcast_user(target_id, {"type": "kicked_from_room", "room_id": room_id, "message": f"تم استبدالك بـ {rep_name} في الطاولة بواسطة {actor_label}."})
        ws_manager.broadcast_room(room_id, {
            "type": "player_substituted",
            "user_id": target_id,
            "name": target_name,
            "replacement_user_id": rep_id,
            "replacement_name": rep_name,
            "is_bot": False,
            "players": list(room.players),
            "spectators": list(room.spectators),
            "player_names": [room.player_names[uid] for uid in room.players if uid in room.player_names],
            "players_dict": {str(uid): room.player_names.get(uid, "لاعب") for uid in set(room.players) | set(room.spectators)},
        })
        if room.status in ("playing", "round_finished", "match_finished"):
            ws_manager.broadcast_room(room_id, {"type": "game_state_changed", "room_id": room_id})
        ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room_id})
        return {"ok": True, "target_user_id": target_id, "replacement_user_id": rep_id, "replacement_name": rep_name, "is_bot": False}

    # Bot replacement
    bot_name = None
    if room.status == "waiting":
        async with room._mutation_lock:
            room.remove_player(target_id)
            bot_name = room.add_bot()
        await ws_manager.disconnect_user_from_room(room_id, target_id)
        ws_manager.broadcast_user(target_id, {"type": "kicked_from_room", "room_id": room_id, "message": f"تم استبدالك ببوت في هذه الطاولة بواسطة {actor_label}."})
        ws_manager.broadcast_room(room_id, {
            "type": "player_substituted",
            "user_id": target_id,
            "name": target_name,
            "bot_name": bot_name,
            "is_bot": True,
            "players": list(room.players),
            "spectators": list(room.spectators),
            "player_names": [room.player_names[uid] for uid in room.players if uid in room.player_names],
            "players_dict": {str(uid): room.player_names.get(uid, "لاعب") for uid in set(room.players) | set(room.spectators)},
        })
        ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room_id})
    else:
        # In playing match: leave_room_internal replaces player with a bot in game state
        await leave_room_internal(room_id, target_id, target_name)
        ws_manager.broadcast_user(target_id, {"type": "kicked_from_room", "room_id": room_id, "message": f"تم استبدالك ببوت في هذه الطاولة بواسطة {actor_label}."})
        ws_manager.broadcast_room(room_id, {
            "type": "player_substituted",
            "user_id": target_id,
            "name": target_name,
            "is_bot": True,
            "players": list(room.players),
            "spectators": list(room.spectators),
            "player_names": [room.player_names[uid] for uid in room.players if uid in room.player_names],
            "players_dict": {str(uid): room.player_names.get(uid, "لاعب") for uid in set(room.players) | set(room.spectators)},
        })
    return {"ok": True, "target_user_id": target_id, "bot_name": bot_name, "is_bot": True}



