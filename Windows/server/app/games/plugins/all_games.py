from server.app.games.registry import ServerGamePlugin, register_plugin
from fastapi import HTTPException
import asyncio
from uuid import uuid4

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
from server.app.games.scopa_lifecycle import check_and_finalize_scopa_round, broadcast_scopa_state
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
        record_match(db, game_name, room.room_id, room.players, list(winners), match_key=room.match_key)
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
    recipients = [uid for uid in room.players if int(uid) > 0]
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
    moved = room.apply_pending_spectators()
    if moved:
        for uid in moved:
            ws_manager.broadcast_room(room.room_id, {
                "type": "spectator_changed",
                "user_id": uid,
                "name": room.player_names.get(uid, "لاعب"),
                "is_spectator": True,
                "spectators": list(room.spectators),
                "players": list(room.players),
                "player_names": [room.player_names[p] for p in room.players if p in room.player_names],
                "players_dict": {str(p): room.player_names.get(p, "لاعب") for p in set(room.players) | set(room.spectators)},
            })

def generic_bot_replace(room, user_id, bot_id, bot_name, plugin):
    game = plugin.get_engine(room)
    if not game: return
    if bot_id in getattr(game, "player_ids", ()) and bot_id != user_id:
        raise ValueError("Replacement id already exists in the game")
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
    if room.game == "TENNIS" and hasattr(game, "players") and len(game.players) == 2:
        bot_index = next((i for i, player in enumerate(game.players)
                          if str(player.get("id")) == str(bot_id)), None)
        if bot_index == 0:
            game.players[0], game.players[1] = game.players[1], game.players[0]
            if hasattr(game, "player_pos"):
                game.player_pos[0], game.player_pos[1] = game.player_pos[1], game.player_pos[0]
            if hasattr(game, "score"):
                for score_map in (game.score.points, game.score.games, game.score.sets, game.score.tiebreak_points):
                    score_map[0], score_map[1] = score_map[1], score_map[0]
                game.score.server_idx = 1 - game.score.server_idx
                if game.score.in_tiebreak:
                    game.score.tiebreak_server_start = 1 - game.score.tiebreak_server_start
    if hasattr(game, "player_names") and user_id in game.player_names:
        game.player_names[bot_id] = bot_name
        game.player_names.pop(user_id, None)
    
    for attr in ["scores", "hands", "tokens", "positions", "turn_start_positions", "frozen_players", "shielded_players", "teams", "captured_cards", "scopa_count", "answers"]:
        if hasattr(game, attr):
            obj = getattr(game, attr)
            if isinstance(obj, dict) and user_id in obj:
                obj[bot_id] = obj.pop(user_id)
    for attr in ("drawn_card", "pending_score_adjustments"):
        obj = getattr(game, attr, None)
        if isinstance(obj, dict) and user_id in obj:
            obj[bot_id] = obj.pop(user_id)
    for attr in ("pending_uno", "buzzer_pending"):
        obj = getattr(game, attr, None)
        if isinstance(obj, set) and user_id in obj:
            obj.remove(user_id)
            obj.add(bot_id)
    if hasattr(game, "buzzer_order"):
        game.buzzer_order = [bot_id if uid == user_id else uid for uid in game.buzzer_order]
    if getattr(game, "pending_exchange_user", None) == user_id:
        game.pending_exchange_user = bot_id
    pending = getattr(game, "pending_bluff", None)
    if isinstance(pending, dict):
        for key in ("target_id", "bluffer_id"):
            if pending.get(key) == user_id:
                pending[key] = bot_id
                
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

def generic_bot_add_midgame(room, bot_id: int, bot_name: str, plugin):
    """Integrate a newly added bot into an actively running match without resetting the game."""
    game = plugin.get_engine(room)
    if not game:
        return
    # 1. Update player list/identities
    if hasattr(game, "player_ids") and bot_id not in game.player_ids:
        game.player_ids.append(bot_id)
    if hasattr(game, "players"):
        exists = False
        for p in game.players:
            pid = int(p[0] if isinstance(p, tuple) else p.get("id") if isinstance(p, dict) else p.user_id)
            if pid == bot_id:
                exists = True
                break
        if not exists:
            if isinstance(game.players, list) and game.players and isinstance(game.players[0], tuple):
                game.players.append((bot_id, bot_name))
            elif isinstance(game.players, list) and game.players and isinstance(game.players[0], dict):
                game.players.append({"id": str(bot_id), "name": bot_name})
            elif hasattr(game, "players") and hasattr(game, "_find_player"): # UnoGame
                from server.app.games.uno.game import Player as UnoPlayer
                new_p = UnoPlayer(bot_id, bot_name)
                # Deal starting cards (7 cards) from deck
                for _ in range(7):
                    c = game._draw_card()
                    if c:
                        new_p.hand.append(c)
                game.players.append(new_p)

    if hasattr(game, "player_names"):
        game.player_names[bot_id] = bot_name

    # 2. Initialize game state structures
    if hasattr(game, "scores") and isinstance(game.scores, dict) and bot_id not in game.scores:
        game.scores[bot_id] = 0
    if hasattr(game, "tokens") and isinstance(game.tokens, dict) and bot_id not in game.tokens:
        game.tokens[bot_id] = getattr(game, "starting_tokens", 11)
    if hasattr(game, "positions") and isinstance(game.positions, dict) and bot_id not in game.positions:
        game.positions[bot_id] = 0
    if hasattr(game, "turn_start_positions") and isinstance(game.turn_start_positions, dict) and bot_id not in game.turn_start_positions:
        game.turn_start_positions[bot_id] = 0
    if hasattr(game, "hands") and isinstance(game.hands, dict) and bot_id not in game.hands:
        game.hands[bot_id] = []
        if room.game in ("DOMINO", "AMERICAN_DOMINO") and hasattr(game, "boneyard"):
            count = min(getattr(game, "hand_size", 7), len(game.boneyard))
            for _ in range(count):
                if game.boneyard:
                    game.hands[bot_id].append(game.boneyard.pop())

    # 3. Ensure bot runner is active
    if plugin.bot_runner:
        if room._bot_task is None or room._bot_task.done():
            room._bot_task = asyncio.create_task(plugin.bot_runner(room))

def generic_bot_remove_midgame(room, bot_id: int, plugin):
    """Safely remove a bot from an actively running match."""
    game = plugin.get_engine(room)
    if not game:
        return
    # If the game has a custom remove_player method, use it
    if hasattr(game, "remove_player"):
        try:
            game.remove_player(bot_id)
        except Exception:
            pass
    else:
        if hasattr(game, "player_ids") and bot_id in game.player_ids:
            game.player_ids.remove(bot_id)
        if hasattr(game, "players"):
            game.players = [
                p for p in game.players
                if int(p[0] if isinstance(p, tuple) else p.get("id") if isinstance(p, dict) else p.user_id) != bot_id
            ]
        if hasattr(game, "player_names"):
            game.player_names.pop(bot_id, None)
        for attr in ("scores", "hands", "tokens", "positions", "turn_start_positions", "frozen_players", "shielded_players"):
            obj = getattr(game, attr, None)
            if isinstance(obj, dict):
                obj.pop(bot_id, None)

        if hasattr(game, "current_turn_index") and hasattr(game, "players") and game.players:
            game.current_turn_index = game.current_turn_index % len(game.players)

    # Wake bot runner if turn shifted to another bot
    if plugin.bot_runner:
        if room._bot_task is None or room._bot_task.done():
            room._bot_task = asyncio.create_task(plugin.bot_runner(room))

def generic_player_swap(room, outgoing_id, replacement_id, replacement_name, plugin):
    game = plugin.get_engine(room)
    if not game:
        return
    if hasattr(game, "player_ids"):
        if replacement_id not in game.player_ids:
            return generic_bot_replace(room, outgoing_id, replacement_id, replacement_name, plugin)
        first, second = game.player_ids.index(outgoing_id), game.player_ids.index(replacement_id)
        game.player_ids[first], game.player_ids[second] = game.player_ids[second], game.player_ids[first]
        return
    if hasattr(game, "players"):
        def ident(player):
            return int(player[0] if isinstance(player, tuple) else player.get("id") if isinstance(player, dict) else player.user_id)
        ids = [ident(player) for player in game.players]
        if replacement_id not in ids:
            return generic_bot_replace(room, outgoing_id, replacement_id, replacement_name, plugin)
        first, second = ids.index(outgoing_id), ids.index(replacement_id)
        game.players[first], game.players[second] = game.players[second], game.players[first]

# UNO
async def uno_start(room, target, rules, players_tuples):
    if rules.get("uno_flip") and rules.get("no_mercy"): raise HTTPException(400, "Cannot mix UNO Flip and UNO No Mercy.")
    game = UnoGame(players_tuples, target_score=target, rules=rules)
    game.start()
    room.target_score = target
    room.rules = rules
    room.uno_game = game
    room.status = "playing"
    room.match_key = uuid4().hex
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
    room.match_key = uuid4().hex
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
    room.match_key = uuid4().hex
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
    room.match_key = uuid4().hex
    if room._bot_task is None or room._bot_task.done(): room._bot_task = asyncio.create_task(run_domino_bots(room))

async def domino_action(room, user_id, req):
    side = getattr(req, "side", "") or (req.data.get("side") if getattr(req, "data", None) else None)
    if req.action == "play":
        if not str(req.card_id).isdigit():
            raise ValueError("فهرس قطعة الدومينو غير صالح.")
        tile_idx = int(req.card_id)
        state = room.domino_game.play_tile(user_id, tile_idx, side)
    elif req.action == "draw":
        state = room.domino_game.draw_tile(user_id)
    elif req.action == "pass":
        state = room.domino_game.pass_turn(user_id)
    else:
        raise ValueError("إجراء الدومينو غير معروف.")
    _queue_gameplay_event(room, user_id, room.domino_game)
    room.scores = dict(room.domino_game.scores)
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
    room.match_key = uuid4().hex
    if room._bot_task is None or room._bot_task.done(): room._bot_task = asyncio.create_task(run_american_domino_bots(room))

async def am_domino_action(room, user_id, req):
    side = getattr(req, "side", "") or (req.data.get("side") if getattr(req, "data", None) else None)
    if req.action == "play":
        if not str(req.card_id).isdigit():
            raise ValueError("فهرس قطعة الدومينو غير صالح.")
        tile_idx = int(req.card_id)
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
    room.target_score = 100
    room.snakes_game = game
    room.status = "playing"
    room.match_key = uuid4().hex
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
    room.match_key = uuid4().hex
    if room._bot_task is None or room._bot_task.done(): room._bot_task = asyncio.create_task(run_scopa_bots(room))

async def scopa_action(room, user_id, req):
    if req.action == "play":
        if not str(req.card_id).isdigit():
            raise ValueError("فهرس كارت إسكوبا غير صالح.")
        card_idx = int(req.card_id)
        choice = (req.data.get("choice_idx") if getattr(req, "data", None) else None)
        if choice is not None and str(choice).isdigit():
            choice = int(choice)
        state = room.scopa_game.play_card(user_id, card_idx, choice)
    else:
        raise ValueError("إجراء إسكوبا غير معروف.")
    game = room.scopa_game
    _queue_gameplay_event(room, user_id, game)
    room.scores = dict(game.team_scores if game.is_team_game else game.scores)
    broadcast_scopa_state(room, game)
    if getattr(game, "pending_deal_batch", False):
        game.pending_deal_batch = False
        if room.scopa_game and room.scopa_game.active:
            room.scopa_game._deal_next_batch()
            broadcast_scopa_state(room, room.scopa_game)

    if getattr(game, "pending_round_finalize", False):
        game.pending_round_finalize = False
        if room.scopa_game and room.scopa_game.active:
            room.scopa_game._finalize_round()
            final_state = game.public_state(user_id)
            await check_and_finalize_scopa_round(room)
            return final_state
        return game.public_state(user_id)

    # The match finalizer is allowed to detach ``room.scopa_game``.  Keep the
    # acting player's final snapshot before that happens so the final card is
    # acknowledged instead of being turned into an AttributeError.
    if not game.active:
        final_state = game.public_state(user_id)
        await check_and_finalize_scopa_round(room)
        return final_state
    else:
        if room._bot_task is None or room._bot_task.done(): room._bot_task = asyncio.create_task(run_scopa_bots(room))
        return room.scopa_game.public_state(user_id)

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
    room.match_key = uuid4().hex
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
    room.match_key = uuid4().hex
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
