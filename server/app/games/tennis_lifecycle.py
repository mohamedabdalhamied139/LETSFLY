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
            record_match(db, "TENNIS", room.room_id, room.players, list(winners), match_key=room.match_key)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    await asyncio.to_thread(save)
async def finalize_tennis_match(room: "Room"):
    import logging
    logger = logging.getLogger("tableverse.tennis.lifecycle")
    from server.app.hub.room_manager import room_manager
    game = room.tennis_game
    if not game:
        return
    winner_idx = getattr(game, "winner_idx", 0)
    winner_dict = game.players[winner_idx] if winner_idx < len(game.players) else (game.players[0] if game.players else {})
    winner_id = int(winner_dict.get("id", 0))
    winner_name = winner_dict.get("name", room.player_names.get(winner_id, "الفائز"))
    score_snapshot = game.score.snapshot()
    await _persist_match(room, [winner_id])
    ws_manager.broadcast_room(room.room_id, {
        "type": "tennis_match_finished",
        "room_id": room.room_id,
        "winner_id": winner_id,
        "winner_name": winner_name,
        "score": score_snapshot,
    })
    if room._bot_task and not room._bot_task.done():
        current = asyncio.current_task()
        if room._bot_task is not current:
            room._bot_task.cancel()
    room._bot_task = None
    room.tennis_game = None
    room.status = "waiting"
    room.round_started_at = None
    room.rules = {}
    room.target_score = None
    room.scores = {uid: 0 for uid in room.players}
    ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})
    ws_manager.broadcast_room(room.room_id, {
        "type": "game_finished", "room_id": room.room_id, "game": "TENNIS"
    })

