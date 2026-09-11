from __future__ import annotations

import asyncio
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
            record_match(db, "THIEF_HUNT", room.room_id, room.players, list(winners), match_key=room.match_key)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    await asyncio.to_thread(save)
async def finalize_thief_match(room: Room):
    import logging
    logger = logging.getLogger("tableverse.thief_hunt.lifecycle")
    from server.app.hub.room_manager import room_manager
    """Finalize a completed Thief Hunt match and return the room to waiting."""
    game = room.thief_game
    if not game or not game.match_finished:
        return
    final_state = None
    try:
        final_state = game.state_for(room.host_id)
    except ValueError as exc:
        logger.warning("Unable to build final Thief Hunt state: %s", exc)
    except Exception:
        logger.exception("Unexpected Thief Hunt final-state failure")
    scores = dict((final_state or {}).get("round_scores") or {})
    total_rounds = int(game.round_number)
    winner_id = game.match_winner_id
    winner_name = game.match_winner_name
    winner_type = game.match_winner_type
    await _persist_match(room, [winner_id])
    if room._bot_task and not room._bot_task.done():
        current = asyncio.current_task()
        if room._bot_task is not current:
            room._bot_task.cancel()
    room._bot_task = None
    ws_manager.broadcast_room(room.room_id, {
        "type": "thief_match_finished", "room_id": room.room_id,
        "winner_id": winner_id, "winner_name": winner_name,
        "winner_type": winner_type, "scores": scores,
        "total_rounds": total_rounds, "state": final_state,
    })
    room.thief_game = None
    room.status = "waiting"
    room.round_started_at = None
    room.target_score = None
    room.rules = {}
    room.scores = {uid: 0 for uid in room.players}
    ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})
    ws_manager.broadcast_room(room.room_id, {
        "type": "game_finished", "room_id": room.room_id, "game": "THIEF_HUNT"
    })

