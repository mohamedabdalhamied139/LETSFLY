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
            record_match(db, "DOMINO", room.room_id, room.players, list(winners))
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    await asyncio.to_thread(save)
async def check_and_finalize_domino_round(room: Room):
    import logging
    logger = logging.getLogger("tableverse.domino.lifecycle")
    from server.app.hub.room_manager import room_manager
    if room.status == "round_finished":
        return
    game = room.domino_game
    if not game or game.active:
        return
    wid = game.round_winner_id
    wname = room.player_names.get(wid, "لاعب") if wid else ""
    points = game.round_points_won or 0
    target_score = int(room.target_score or 100)

    match_over = game.winner_id is not None or any(s >= target_score for s in game.scores.values())
    if match_over:
        room.status = "match_finished"
        final_winner_id = game.winner_id or min(game.scores.items(), key=lambda x: x[1])[0]
        final_winner_name = room.player_names.get(final_winner_id, "الفائز")
        ws_manager.broadcast_room(room.room_id, {
            "type": "domino_match_finished",
            "room_id": room.room_id,
            "winner_id": final_winner_id,
            "winner_name": final_winner_name,
            "scores": {str(k): v for k, v in game.scores.items()},
            "target_score": target_score,
        })
        await _persist_match(room, [final_winner_id])
        if room._bot_task and not room._bot_task.done():
            current = asyncio.current_task()
            if room._bot_task is not current:
                room._bot_task.cancel()
        room._bot_task = None
        room.domino_game = None
        room.status = "waiting"
        room.round_started_at = None
        room.target_score = None
        room.rules = {}
        room.scores = {uid: 0 for uid in room.players}
        ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})
        ws_manager.broadcast_room(room.room_id, {
            "type": "game_finished", "room_id": room.room_id, "game": "DOMINO"
        })
        return

    # Round finished, advance to next round after delay
    room.status = "round_finished"
    ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})
    ws_manager.broadcast_room(room.room_id, {
        "type": "domino_round_finished",
        "winner_name": wname,
        "winner_id": wid,
        "round_score": points,
        "total": room.scores.get(wid, 0) if wid else 0,
        "target_score": target_score,
        "delay_seconds": 5,
        "scores": {str(uid): room.scores.get(uid, 0) for uid in room.players},
    })
    if room._round_transition_task is None or room._round_transition_task.done():
        room._round_transition_task = asyncio.create_task(_start_next_domino_round_after_delay(room))

async def _start_next_domino_round_after_delay(room: Room):
    import logging
    logger = logging.getLogger("tableverse.domino.lifecycle")
    from server.app.hub.room_manager import room_manager
    from server.app.games.domino import DominoGame
    from server.app.games.domino_bot import run_domino_bots
    try:
        await asyncio.sleep(5)
        # Serialize the transition with player actions/Stop. The state check and
        # round creation must happen while holding the same room mutation lock.
        async with room._mutation_lock:
            if room.status != "round_finished" or not room.players or not room.domino_game:
                return
            room._bot_task = None
            room.domino_game.start_new_round()
            room.status = "playing"
            room.round_started_at = datetime.now(timezone.utc).isoformat()
        ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})
        ws_manager.broadcast_room(room.room_id, {
            "type": "domino_state_changed",
            "room_id": room.room_id,
            "round_started": True
        })
        if room._bot_task is None or room._bot_task.done():
            room._bot_task = asyncio.create_task(run_domino_bots(room))
    except asyncio.CancelledError:
        raise
    finally:
        current = asyncio.current_task()
        if room._round_transition_task is current:
            room._round_transition_task = None

