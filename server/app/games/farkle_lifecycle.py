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
            record_match(db, "FARKLE", room.room_id, room.players, list(winners))
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    await asyncio.to_thread(save)
async def finalize_farkle_match(room: Room):
    import logging
    logger = logging.getLogger("letsfly.farkle.lifecycle")
    from server.app.hub.room_manager import room_manager
    game = room.farkle_game
    if not game or game.active or game.winner_id is None:
        return
    winner_id = game.winner_id
    winner_name = room.player_names.get(winner_id, "الفائز")
    final_state = game.state_for(room.host_id)
    room.scores = dict(game.scores)
    await _persist_match(room, [winner_id])
    ws_manager.broadcast_room(room.room_id, {
        "type": "farkle_match_finished",
        "room_id": room.room_id,
        "winner_id": winner_id,
        "winner_name": winner_name,
        "scores": {str(k): v for k, v in game.scores.items()},
        "target_score": game.target_score,
        "state": final_state,
    })
    room.farkle_game = None
    room.status = "waiting"
    room.round_started_at = None
    room.target_score = None
    room.rules = {}
    room.scores = {uid: 0 for uid in room.players}
    ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})

