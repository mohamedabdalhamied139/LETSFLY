from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from server.app.hub.ws_manager import ws_manager
from server.app.social_services import record_match
from server.app.db.database import SessionLocal
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from server.app.hub.room_manager import Room


async def _persist_match(room, winners):
    def save():
        db = SessionLocal()
        try:
            record_match(db, "UNO", room.room_id, room.players, list(winners))
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    await asyncio.to_thread(save)
async def check_and_finalize_uno_round(room: Room):
    import logging
    logger = logging.getLogger("letsfly.uno.lifecycle")
    from server.app.hub.room_manager import room_manager, _apply_game_score_adjustments
    from server.app.games.uno.game import UnoGame
    # Prevent duplicate finalization/broadcasts from the action path and bot path.
    if room.status == "round_finished":
        return
    game = room.uno_game
    if not game or game.active or game.winner_id is None:
        return
    _apply_game_score_adjustments(room)
    wid = game.winner_id
    wname = room.player_names.get(wid, "لاعب")
    points = game.round_score or 0
    if not getattr(game, "_score_awarded", False):
        game._score_awarded = True
        room.scores[wid] = room.scores.get(wid, 0) + points

    target_score = int(room.target_score or 500)
    if room.scores[wid] >= target_score:
        room.status = "match_finished"
        game.active = False
        scores_summary = "، ".join(f"{room.player_names.get(uid, 'لاعب')}: {room.scores.get(uid, 0)}" for uid in room.players)
        game._set_event(f"نهاية المباراة! الفائز: {wname}. النتائج: {scores_summary}", "MATCH_FINISHED", "MATCH_WIN")
        final_total = room.scores[wid]
        ws_manager.broadcast_room(room.room_id, {
            "type": "match_finished", "winner_name": wname, "winner_id": wid,
            "total": final_total, "target_score": target_score,
            "scores": {str(uid): room.scores.get(uid, 0) for uid in room.players}
        })
        await _persist_match(room, [wid])
        if room._bot_task and not room._bot_task.done():
            current = asyncio.current_task()
            if room._bot_task is not current:
                room._bot_task.cancel()
        room._bot_task = None
        room.uno_game = None
        room.status = "waiting"
        room.round_started_at = None
        room.target_score = None
        room.rules = {}
        room.scores = {uid: 0 for uid in room.players}
        ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})
        ws_manager.broadcast_room(room.room_id, {
            "type": "game_finished", "room_id": room.room_id, "game": "UNO"
        })
        return

    # Round is over but the match continues. Clear the old round immediately,
    # keep the accumulated score, and start the next round automatically after 5s.
    room.status = "round_finished"
    for player in game.players:
        player.hand.clear()
    game.drawn_card.clear()
    game.pending_uno.clear()
    game.discard.clear()
    game.deck.clear()
    game.active = False
    curr_round = getattr(game, "round_number", 1)
    scores_summary = "، ".join(f"{room.player_names.get(uid, 'لاعب')}: {room.scores.get(uid, 0)}" for uid in room.players)
    game.last_action = f"نهاية الجولة {curr_round}. النتائج: {scores_summary}"
    game.event_id += 1
    game.event_type = "ROUND_FINISHED"
    game.sound_cue = "ROUND_END"
    ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})
    ws_manager.broadcast_room(room.room_id, {
        "type": "round_finished",
        "winner_name": wname,
        "winner_id": wid,
        "round_score": points,
        "total": room.scores[wid],
        "target_score": target_score,
        "delay_seconds": 5,
        "scores": {str(uid): room.scores.get(uid, 0) for uid in room.players}
    })

    if room._round_transition_task is None or room._round_transition_task.done():
        room._round_transition_task = asyncio.create_task(_start_next_round_after_delay(room))

async def _start_next_round_after_delay(room: Room):
    import logging
    logger = logging.getLogger("letsfly.uno.lifecycle")
    from server.app.hub.room_manager import room_manager
    from server.app.games.uno.game import UnoGame
    from server.app.games.uno.bot import run_uno_bots
    try:
        await asyncio.sleep(5)
        # Stop/leave and the transition must be serialized against each other.
        async with room._mutation_lock:
            if room.status != "round_finished" or not room.players or not room.uno_game:
                return
            target_score = int(room.target_score or 500)
            players_tuples = [(uid, room.player_names[uid]) for uid in room.players if uid in room.player_names]
            if len(players_tuples) < 2:
                room.status = "waiting"
                room.uno_game = None
                ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})
                return
            room._bot_task = None
            next_round = getattr(room.uno_game, "round_number", 1) + 1
            room.uno_game = UnoGame(players_tuples, target_score=target_score, rules=room.rules, round_number=next_round)
            room.uno_game.start()
            room.status = "playing"
            room.round_started_at = datetime.now(timezone.utc).isoformat()
        ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})
        ws_manager.broadcast_room(room.room_id, {
            "type": "uno_state_changed",
            "room_id": room.room_id,
            "round_started": True
        })
        if room._bot_task is None or room._bot_task.done():
            room._bot_task = asyncio.create_task(run_uno_bots(room))
    except asyncio.CancelledError:
        raise
    finally:
        current = asyncio.current_task()
        if room._round_transition_task is current:
            room._round_transition_task = None

