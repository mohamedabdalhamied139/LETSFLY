from server.app.games.registry import ServerGamePlugin, register_plugin
from fastapi import HTTPException
import asyncio

# Imports for games
from server.app.games.uno.game import UnoGame
from server.app.games.thief_hunt import ThiefHuntGame
from server.app.games.farkle import FarkleGame
from server.app.games.domino import DominoGame
from server.app.games.american_domino import AmericanDominoGame
from server.app.games.snakes_and_ladders import SnakesAndLaddersGame
from server.app.games.scopa import ScopaGame
from server.app.games.tennis import TennisGame
from server.app.games.ninety_nine import NinetyNineGame
from server.app.games.uno.bot import run_uno_bots
from server.app.games.uno.lifecycle import check_and_finalize_uno_round
from server.app.games.thief_hunt_bot import run_thief_bots
from server.app.games.thief_hunt_lifecycle import finalize_thief_match
from server.app.games.farkle_bot import run_farkle_bots
from server.app.games.farkle_lifecycle import finalize_farkle_match
from server.app.games.domino_bot import run_domino_bots
from server.app.games.domino_lifecycle import check_and_finalize_domino_round
from server.app.games.american_domino_bot import run_american_domino_bots
from server.app.games.american_domino_lifecycle import check_and_finalize_american_domino_round
from server.app.games.snakes_bot import run_snakes_bots
from server.app.games.snakes_lifecycle import finalize_snakes_match
from server.app.games.scopa_bot import run_scopa_bots
from server.app.games.scopa_lifecycle import check_and_finalize_scopa_round
from server.app.games.tennis_bot import run_tennis_bots
from server.app.games.tennis_lifecycle import finalize_tennis_match
from server.app.games.ninety_nine_bot import run_ninety_nine_bots

from server.app.hub.ws_manager import ws_manager
from server.app.db.database import SessionLocal
from server.app.social_services import record_match
from server.app.activity import create_event

def _record_match(room, game_name, winners):
    db = SessionLocal()
    try:
        record_match(db, game_name, room.room_id, room.players, list(winners))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def _prepare_gameplay_event(room, actor_id, engine, fallback="حدث في اللعبة"):
    """Snapshot non-authoritative activity data without touching the database."""
    text = str(getattr(engine, "last_action", "") or fallback).strip()
    if not text:
        return None
    event_id = getattr(engine, "event_id", None)
    marker = f"{room.game}:{event_id}:{text}"
    if getattr(room, "_last_activity_marker", None) == marker:
        return None
    room._last_activity_marker = marker
    recipients = [uid for uid in (set(room.players) | set(room.spectators)) if int(uid) > 0]
    if not recipients:
        return None
    return {
        "room_id": room.room_id,
        "game": room.game,
        "actor_id": actor_id,
        "text": text,
        "event_id": event_id,
        "event_type": str(getattr(engine, "event_type", "GAME_ACTION")),
        "recipients": list(recipients),
    }

def _persist_gameplay_event(snapshot):
    """Persist a previously captured activity snapshot off the asyncio loop."""
    db = SessionLocal()
    event_ids = {}
    try:
        for uid in snapshot["recipients"]:
            event = create_event(
                db, uid, "GAMEPLAY", snapshot["text"],
                event_type=snapshot["event_type"],
                actor_id=snapshot["actor_id"], room_id=snapshot["room_id"],
                payload={"game_event_id": snapshot["event_id"]}
            )
            db.flush()
            event_ids[int(uid)] = int(event.id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    for uid in snapshot["recipients"]:
        ws_manager.broadcast_user(uid, {
            "type": "activity_event",
            "id": event_ids.get(int(uid)),
            "category": "GAMEPLAY",
            "event_type": snapshot["event_type"],
            "text": snapshot["text"],
            "actor_id": snapshot["actor_id"],
            "room_id": snapshot["room_id"],
            "game_event_id": snapshot["event_id"],
        })

def _queue_gameplay_event(room, actor_id, engine, fallback="حدث في اللعبة"):
    """Queue non-authoritative activity persistence so gameplay responses stay fast."""
    snapshot = _prepare_gameplay_event(room, actor_id, engine, fallback)
    if snapshot is not None:
        asyncio.create_task(asyncio.to_thread(_persist_gameplay_event, snapshot))

def generic_stop(room, plugin):
    # Stop/cancel every room-owned async operation before clearing the engine.
    # This prevents delayed round transitions from resurrecting a stopped game.
    room.cancel_background_tasks()
    engine = plugin.get_engine(room)
    if engine:
        if hasattr(engine, "active"): engine.active = False
        if hasattr(engine, "stop"): engine.stop()
        if hasattr(engine, "state") and isinstance(engine.state, str): engine.state = "FINISHED"
    plugin.set_engine(room, None)

def generic_bot_replace(room, user_id, bot_id, bot_name, plugin):
    game = plugin.get_engine(room)
    if not game: return
    # Replacement IDs must never collide with an existing bot/player ID.
    while bot_id in room.players or bot_id in getattr(game, "player_ids", []):
        bot_id -= 1
    if hasattr(game, "player_ids") and user_id in game.player_ids:
        idx = game.player_ids.index(user_id)
        game.player_ids[idx] = bot_id
    if hasattr(game, "players"):
        for i, p in enumerate(game.players):
            if isinstance(p, tuple) and p[0] == user_id:
                game.players[i] = (bot_id, bot_name)
            elif isinstance(p, dict) and str(p.get("id")) == str(user_id):
                p["id"] = str(bot_id)
                p["name"] = bot_name
            elif hasattr(p, "user_id") and p.user_id == user_id:
                p.user_id = bot_id
                p.name = bot_name
    if hasattr(game, "player_names") and user_id in game.player_names:
        game.player_names[bot_id] = bot_name
        game.player_names.pop(user_id, None)
    
    for attr in ["scores", "hands", "tokens", "positions", "turn_start_positions", "frozen_players", "shielded_players", "teams", "captured_cards", "scopa_count", "answers"]:
        if hasattr(game, attr):
            obj = getattr(game, attr)
            if isinstance(obj, dict) and user_id in obj:
                obj[bot_id] = obj.pop(user_id)
                
    if getattr(game, "last_capture_id", None) == user_id: game.last_capture_id = bot_id
    if getattr(game, "last_player_id", None) == user_id: game.last_player_id = bot_id
    if getattr(game, "thief_id", None) == user_id:
        if room.game == "THIEF_HUNT":
            game.stop()
            room.thief_game = None
            room.status = "waiting"
            room.rules = {}
            room.target_score = None
            return
        game.thief_id = bot_id
    
    if plugin.bot_runner:
        room.cancel_bot_task()
        room._bot_task = asyncio.create_task(plugin.bot_runner(room))

# UNO
async def uno_start(room, target, rules, players_tuples):
    if rules.get("uno_flip") and rules.get("no_mercy"): raise HTTPException(400, "Cannot mix UNO Flip and UNO No Mercy.")
    game = UnoGame(players_tuples, target_score=target, rules=rules)
    game.start()
    room.target_score = target
    room.rules = rules
    room.uno_game = game
    room.status = "playing"
    if room._bot_task is None or room._bot_task.done(): room._bot_task = asyncio.create_task(run_uno_bots(room))

async def uno_action(room, user_id, req):
    chosen_col = getattr(req, "chosen_color", "") or (req.data.get("chosen_color", "") if getattr(req, "data", None) else "")
    state = room.uno_game.action(user_id, req.action, req.card_id or "", chosen_col)
    _queue_gameplay_event(room, user_id, room.uno_game)
    ws_manager.broadcast_room(room.room_id, {"type": "game_state_changed", "room_id": room.room_id})
    if not room.uno_game.active and room.uno_game.winner_id is not None:
        await check_and_finalize_uno_round(room)
    else:
        if room._bot_task is None or room._bot_task.done(): room._bot_task = asyncio.create_task(run_uno_bots(room))
    return state

register_plugin(ServerGamePlugin("UNO", "أونو", "uno_game", uno_start, run_uno_bots, lambda eng, uid: eng.state_for(uid), uno_action, generic_bot_replace, generic_stop))

# Thief Hunt
async def thief_start(room, target, rules, players_tuples):
    rules = rules or {}
    total_rounds = rules.get("rounds", 5)
    allow_human = rules.get("allow_human_thief", False)
    elim = rules.get("elimination_mode", False)
    game = ThiefHuntGame(players_tuples, total_rounds=total_rounds, allow_human_thief=allow_human, elimination_mode=elim)
    game.start()
    room.target_score = target
    room.rules = rules
    room.thief_game = game
    room.status = "playing"
    if room._bot_task is None or room._bot_task.done(): room._bot_task = asyncio.create_task(run_thief_bots(room))

async def thief_action(room, user_id, req):
    state = room.thief_game.action(user_id, req.action, req.card_id or "")
    _queue_gameplay_event(room, user_id, room.thief_game)
    if room.thief_game.phase == "round_result":
        ws_manager.broadcast_room(room.room_id, {"type": "game_state_changed", "room_id": room.room_id})
        if room._bot_task is None or room._bot_task.done(): room._bot_task = asyncio.create_task(run_thief_bots(room))
    elif room.thief_game.match_finished:
        await finalize_thief_match(room)
        return state
    else:
        ws_manager.broadcast_room(room.room_id, {"type": "game_state_changed", "room_id": room.room_id})
    return state

register_plugin(ServerGamePlugin("THIEF_HUNT", "صيد اللص", "thief_game", thief_start, run_thief_bots, lambda eng, uid: eng.state_for(uid), thief_action, generic_bot_replace, generic_stop))

# Farkle
async def farkle_start(room, target, rules, players_tuples):
    pt = [(uid, room.player_names[uid]) for uid in room.players if uid not in room.spectators]
    if len(pt) < 2: raise HTTPException(400, "Need at least 2 players")
    game = FarkleGame(pt, target_score=target, rules=rules)
    game.start()
    room.target_score = target
    room.rules = rules
    room.farkle_game = game
    room.scores = dict(game.scores)
    room.status = "playing"
    if room._bot_task is None or room._bot_task.done(): room._bot_task = asyncio.create_task(run_farkle_bots(room))

async def farkle_action(room, user_id, req):
    val = getattr(req, "card_id", "") or (req.data.get("value") if getattr(req, "data", None) else None)
    if str(req.action).lower() == "score" and isinstance(val, str):
        raw = [part.strip() for part in val.split(",") if part.strip()]
        try:
            val = [int(part) for part in raw]
        except ValueError:
            raise ValueError("اختيار النرد غير صالح.")
    state = room.farkle_game.action(user_id, req.action, val)
    _queue_gameplay_event(room, user_id, room.farkle_game)
    room.scores = dict(room.farkle_game.scores)
    if not room.farkle_game.active and room.farkle_game.winner_id is not None:
        ws_manager.broadcast_room(room.room_id, {"type": "game_state_changed", "room_id": room.room_id})
        await finalize_farkle_match(room)
        return state
    else:
        ws_manager.broadcast_room(room.room_id, {"type": "game_state_changed", "room_id": room.room_id})
        if room._bot_task is None or room._bot_task.done(): room._bot_task = asyncio.create_task(run_farkle_bots(room))
        return state

register_plugin(ServerGamePlugin("FARKLE", "فاركل", "farkle_game", farkle_start, run_farkle_bots, lambda eng, uid: eng.state_for(uid), farkle_action, generic_bot_replace, generic_stop))

# Domino
async def domino_start(room, target, rules, players_tuples):
    game = DominoGame(players_tuples, target_score=target, rules=rules)
    game.start_match()
    room.target_score = target
    room.rules = rules
    room.domino_game = game
    room.scores = dict(game.scores)
    room.status = "playing"
    if room._bot_task is None or room._bot_task.done(): room._bot_task = asyncio.create_task(run_domino_bots(room))

async def domino_action(room, user_id, req):
    side = getattr(req, "side", "") or (req.data.get("side") if getattr(req, "data", None) else None)
    if req.action == "play":
        tile_idx = int(req.card_id) if str(req.card_id).isdigit() else 0
        state = room.domino_game.play_tile(user_id, tile_idx, side)
    elif req.action == "draw":
        state = room.domino_game.draw_tile(user_id)
    elif req.action == "pass":
        state = room.domino_game.pass_turn(user_id)
    else:
        raise ValueError("إجراء الدومينو غير معروف.")
    _queue_gameplay_event(room, user_id, room.domino_game)
    if not room.domino_game.active:
        ws_manager.broadcast_room(room.room_id, {"type": "game_state_changed", "room_id": room.room_id})
        await check_and_finalize_domino_round(room)
        return state
    else:
        ws_manager.broadcast_room(room.room_id, {"type": "game_state_changed", "room_id": room.room_id})
        if room._bot_task is None or room._bot_task.done(): room._bot_task = asyncio.create_task(run_domino_bots(room))
        return state

register_plugin(ServerGamePlugin("DOMINO", "دومينو", "domino_game", domino_start, run_domino_bots, lambda eng, uid: eng.get_state(uid), domino_action, generic_bot_replace, generic_stop))

# American Domino
async def am_domino_start(room, target, rules, players_tuples):
    game = AmericanDominoGame(players_tuples, target_score=target, rules=rules)
    game.start_match()
    room.target_score = target
    room.rules = rules
    room.american_domino_game = game
    room.scores = dict(game.scores)
    room.status = "playing"
    if room._bot_task is None or room._bot_task.done(): room._bot_task = asyncio.create_task(run_american_domino_bots(room))

async def am_domino_action(room, user_id, req):
    side = getattr(req, "side", "") or (req.data.get("side") if getattr(req, "data", None) else None)
    if req.action == "play":
        tile_idx = int(req.card_id) if str(req.card_id).isdigit() else 0
        state = room.american_domino_game.play_tile(user_id, tile_idx, side)
    elif req.action == "draw":
        state = room.american_domino_game.draw_tile(user_id)
    elif req.action == "pass":
        state = room.american_domino_game.pass_turn(user_id)
    else:
        raise ValueError("إجراء الدومينو الأمريكي غير معروف.")
    room.scores = dict(room.american_domino_game.scores)
    _queue_gameplay_event(room, user_id, room.american_domino_game)
    if not room.american_domino_game.active:
        ws_manager.broadcast_room(room.room_id, {"type": "game_state_changed", "room_id": room.room_id})
        await check_and_finalize_american_domino_round(room)
        return state
    else:
        ws_manager.broadcast_room(room.room_id, {"type": "game_state_changed", "room_id": room.room_id})
        if room._bot_task is None or room._bot_task.done(): room._bot_task = asyncio.create_task(run_american_domino_bots(room))
        return state

register_plugin(ServerGamePlugin("AMERICAN_DOMINO", "دومينو أمريكي", "american_domino_game", am_domino_start, run_american_domino_bots, lambda eng, uid: eng.get_state(uid), am_domino_action, generic_bot_replace, generic_stop))

# Snakes
async def snakes_start(room, target, rules, players_tuples):
    game = SnakesAndLaddersGame(players_tuples, rules=rules)
    game.start_match()
    room.rules = rules
    room.snakes_game = game
    room.status = "playing"
    if room._bot_task is None or room._bot_task.done(): room._bot_task = asyncio.create_task(run_snakes_bots(room))

async def snakes_action(room, user_id, req):
    if req.action == "roll":
        state = room.snakes_game.roll_dice(user_id)
    else:
        raise ValueError("إجراء السلم والثعبان غير معروف.")
    _queue_gameplay_event(room, user_id, room.snakes_game)
    if room.snakes_game.winner_id is not None:
        ws_manager.broadcast_room(room.room_id, {"type": "game_state_changed", "room_id": room.room_id})
        await finalize_snakes_match(room)
        return state
    else:
        ws_manager.broadcast_room(room.room_id, {"type": "game_state_changed", "room_id": room.room_id})
        if room._bot_task is None or room._bot_task.done(): room._bot_task = asyncio.create_task(run_snakes_bots(room))
        return state

register_plugin(ServerGamePlugin("SNAKES_LADDERS", "السلم والثعبان", "snakes_game", snakes_start, run_snakes_bots, lambda eng, uid: eng.get_state(uid), snakes_action, generic_bot_replace, generic_stop))

# Scopa
async def scopa_start(room, target, rules, players_tuples):
    target = target or 11
    if target <= 0: raise HTTPException(400, "Invalid target")
    rules = dict(rules or {})
    mode = str(rules.get("scopa_mode", "classic")).strip().lower()
    if mode == "scopone" and len(players_tuples) != 4:
        raise HTTPException(400, "وضع إسكوبوني يتطلب أربعة لاعبين بالضبط.")
    if len(players_tuples) > 6:
        raise HTTPException(400, "إسكوبا تدعم من لاعبين إلى ستة لاعبين فقط.")
    rules["scopa_mode"] = mode
    game = ScopaGame(players_tuples, target_score=target, rules=rules)
    game.start_match()
    room.target_score = target
    room.rules = rules
    room.scopa_game = game
    room.scores = dict(game.scores)
    room.status = "playing"
    if room._bot_task is None or room._bot_task.done(): room._bot_task = asyncio.create_task(run_scopa_bots(room))

async def scopa_action(room, user_id, req):
    if req.action == "play":
        card_idx = int(req.card_id) if str(req.card_id).isdigit() else 0
        choice = (req.data.get("choice_idx") if getattr(req, "data", None) else None)
        if choice is not None and str(choice).isdigit():
            choice = int(choice)
        state = room.scopa_game.play_card(user_id, card_idx, choice)
    else:
        raise ValueError("إجراء إسكوبا غير معروف.")
    _queue_gameplay_event(room, user_id, room.scopa_game)
    if not room.scopa_game.active:
        ws_manager.broadcast_room(room.room_id, {"type": "game_state_changed", "room_id": room.room_id})
        await check_and_finalize_scopa_round(room)
        return state
    else:
        ws_manager.broadcast_room(room.room_id, {"type": "game_state_changed", "room_id": room.room_id})
        if room._bot_task is None or room._bot_task.done(): room._bot_task = asyncio.create_task(run_scopa_bots(room))
        return state

register_plugin(ServerGamePlugin("SCOPA", "إسكوبا", "scopa_game", scopa_start, run_scopa_bots, lambda eng, uid: eng.public_state(uid), scopa_action, generic_bot_replace, generic_stop))

# Tennis
async def tennis_start(room, target, rules, players_tuples):
    if len(players_tuples) != 2:
        raise HTTPException(400, "لعبة التنس تتطلب لاعبين اثنين بالضبط.")
    game = TennisGame(room)
    players_dicts = [{"id": str(uid), "name": name} for uid, name in players_tuples]
    game.start_game(players_dicts)
    room.target_score = target or 1
    room.rules = rules
    room.tennis_game = game
    room.scores = {uid: 0 for uid in room.players}
    room.status = "playing"
    if room._bot_task is None or room._bot_task.done(): room._bot_task = asyncio.create_task(run_tennis_bots(room))
    # Note: tennis historically broadcast state immediately on start. We'll do it in rooms.py

async def tennis_action(room, user_id, req):
    t_data = getattr(req, "data", {}) or {}
    act = req.action
    if act == "tennis_action":
        act = t_data.get("type", "position")
    state = room.tennis_game.handle_action(str(user_id), act, t_data)
    
    _queue_gameplay_event(room, user_id, room.tennis_game)
    if getattr(room.tennis_game, "state", None) == "FINISHED":
        await finalize_tennis_match(room)
        return state
    else:
        if act != "position":
            ws_manager.broadcast_room(room.room_id, {"type": "game_state_changed", "room_id": room.room_id, "state": room.tennis_game.full_state()})
        if isinstance(state, dict):
            if state.get("type") == "tennis_action_result" or "ball" in state or "trajectory" in state:
                ws_manager.broadcast_room(room.room_id, {
                    "type": "tennis_action_result",
                    "room_id": room.room_id,
                    "sender": user_id,
                    "result": state,
                    **state
                })
            elif state.get("sound"):
                ws_manager.broadcast_room(room.room_id, {"type": "tennis_sound", "sound": state["sound"], "sender": user_id})
        return state

register_plugin(ServerGamePlugin("TENNIS", "تنس", "tennis_game", tennis_start, run_tennis_bots, lambda eng, uid: eng.full_state(), tennis_action, generic_bot_replace, generic_stop))

# Ninety-Nine
async def ninety_nine_start(room, target, rules, players_tuples):
    game = NinetyNineGame(players_tuples, target_score=target, rules=rules)
    room.target_score = game.starting_tokens
    room.rules = dict(rules or {})
    room.ninety_nine_game = game
    room.scores = dict(game.tokens)
    room.status = "playing"
    if room._bot_task is None or room._bot_task.done(): room._bot_task = asyncio.create_task(run_ninety_nine_bots(room))

async def ninety_nine_action(room, user_id, req):
    val = None
    if req.action == "choose":
        val = int(req.card_id) if req.card_id.lstrip('-').isdigit() else None
        state = room.ninety_nine_game.action(user_id, req.action, val)
    else:
        target_pid = getattr(req, "target_player_id", "")
        if target_pid:
            state = room.ninety_nine_game.action(user_id, req.action, {"card_id": req.card_id, "target_player_id": int(target_pid)})
        else:
            state = room.ninety_nine_game.action(user_id, req.action, req.card_id)
            
    game = room.ninety_nine_game
    if state is None and game is not None:
        state = game.state_for(user_id)
    # Persist the gameplay activity while the authoritative engine still exists.
    # Match finalization clears room.ninety_nine_game below; queueing after that
    # point used to pass None and lose the final gameplay event.
    _queue_gameplay_event(room, user_id, game)
    room.scores = dict(game.tokens)
    if game.match_finished:
        wid = game.winner_id
        wname = room.player_names.get(wid, "لاعب")
        room.status = "match_finished"
        await asyncio.to_thread(_record_match, room, "NINETY_NINE", [wid])
        ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})
        ws_manager.broadcast_room(room.room_id, {
            "type": "match_finished",
            "winner_name": wname,
            "winner_id": wid,
            "total": game.tokens.get(wid, 0),
            "scores": {str(uid): game.tokens.get(uid, 0) for uid in room.players}
        })
        if room._bot_task and not room._bot_task.done():
            room._bot_task.cancel()
        room._bot_task = None
        room.ninety_nine_game = None
        room.status = "waiting"
        room.rules = {}
        ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})
        ws_manager.broadcast_room(room.room_id, {"type": "game_finished", "game": "NINETY_NINE"})
    elif game.round_finished:
        from server.app.games.ninety_nine_lifecycle import _start_next_ninety_nine_round_after_delay
        room.status = "round_finished"
        ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})
        ws_manager.broadcast_room(room.room_id, {
            "type": "ninety_nine_round_finished",
            "delay_seconds": 5,
            "last_action": game.last_action,
            "tokens": game.tokens
        })
        if room._round_transition_task is None or room._round_transition_task.done():
            room._round_transition_task = asyncio.create_task(_start_next_ninety_nine_round_after_delay(room))
    else:
        ws_manager.broadcast_room(room.room_id, {"type": "game_state_changed", "room_id": room.room_id})
        if room._bot_task is None or room._bot_task.done():
            room._bot_task = asyncio.create_task(run_ninety_nine_bots(room))
    return state

register_plugin(ServerGamePlugin("NINETY_NINE", "تسعة وتسعون", "ninety_nine_game", ninety_nine_start, run_ninety_nine_bots, lambda eng, uid: eng.state_for(uid), ninety_nine_action, generic_bot_replace, generic_stop))
