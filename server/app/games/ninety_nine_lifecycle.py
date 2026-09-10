from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from server.app.hub.ws_manager import ws_manager
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from server.app.hub.room_manager import Room
async def _start_next_ninety_nine_round_after_delay(room: "Room"):
    import logging
    logger = logging.getLogger("letsfly.ninety_nine.lifecycle")
    from server.app.hub.room_manager import room_manager
    from server.app.games.ninety_nine import NinetyNineGame
    from server.app.games.ninety_nine_bot import run_ninety_nine_bots
    try:
        await asyncio.sleep(5)
        # Serialize the transition with player actions/Stop. The state check and
        # round creation must happen while holding the same room mutation lock.
        async with room._mutation_lock:
            if room.status != "round_finished" or not room.players or not room.ninety_nine_game:
                return
            room._bot_task = None
            room.ninety_nine_game.start_new_round()
            room.status = "playing"
            room.round_started_at = datetime.now(timezone.utc).isoformat()
        ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})
        ws_manager.broadcast_room(room.room_id, {
            "type": "game_state_changed",
            "room_id": room.room_id,
            "round_started": True
        })
        if room._bot_task is None or room._bot_task.done():
            room._bot_task = asyncio.create_task(run_ninety_nine_bots(room))
    except asyncio.CancelledError:
        raise
    finally:
        current = asyncio.current_task()
        if room._round_transition_task is current:
            room._round_transition_task = None

