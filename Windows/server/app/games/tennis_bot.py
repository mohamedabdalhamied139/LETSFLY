from __future__ import annotations

import asyncio
from server.app.hub.ws_manager import ws_manager
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from server.app.hub.room_manager import Room
async def run_tennis_bots(room: "Room"):
    import time
    import random
    import logging
    logger = logging.getLogger("tableverse.tennis.bot")
    from server.app.hub.room_manager import room_manager
    from server.app.games.tennis_lifecycle import finalize_tennis_match
    """
    Exact port of Unity Update() loop from scify/LeapGame-tennis.

    Runs at 50Hz (every 20ms). Calls game.tick(now) which returns
    a list of events to broadcast â€” floor_hit, net_pass, racket/boundary,
    wall bounce â€” all timed exactly as the original C# physics timeline.

    Timeline per ball trip (T = 1.0 / speed seconds):
        t = 0.0T  â†’ launch
        t = 0.3T  â†’ floor_hit  (bounce.wav)
        t = 0.5T  â†’ net_pass   (bounce_b.wav)
        t = 1.0T  â†’ reach: racket/boundary (player) or wall (bot)
    """
    if not room.tennis_game:
        return

    has_bots = any(uid < 0 for uid in room.players)
    logger.info(
        f"Tennis loop started â€” room={room.room_id} bots={has_bots}"
    )

    while room.tennis_game and room.tennis_game.state != "FINISHED":
        await asyncio.sleep(0.02)
        
        async with room._mutation_lock:
            if not room.tennis_game or room.tennis_game.state == "FINISHED":
                break
            
            now    = time.time()
            game   = room.tennis_game
            events = game.tick(now)

        # Broadcast outside the lock to avoid P1-2 blocking
        for evt in events:
            ws_manager.broadcast_room(room.room_id, {
                "room_id": room.room_id,
                **evt,
            })

    if room.tennis_game and room.tennis_game.state == "FINISHED":
        # Check if match is already finalized to prevent duplicate calls
        if room.status != "waiting":
            await finalize_tennis_match(room)

    logger.info(f"Tennis loop ended â€” room={room.room_id}")

