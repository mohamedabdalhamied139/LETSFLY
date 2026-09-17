from __future__ import annotations

import asyncio
from server.app.hub.ws_manager import ws_manager
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from server.app.hub.room_manager import Room
async def run_snakes_bots(room: Room):
    import random
    import logging
    logger = logging.getLogger("tableverse.snakes.bot")
    from server.app.hub.room_manager import room_manager
    from server.app.games.snakes_lifecycle import finalize_snakes_match
    game = room.snakes_game
    if not game or not game.active:
        return
    bot_ids = {uid for uid in room.players if uid < 0}
    while game.active:
        current_id = game.current_player_id()
        is_frozen = game.frozen_players.get(current_id, False)
        if current_id not in bot_ids and not is_frozen:
            break
        # Calculate realistic audio duration: footsteps + cue + speech narration + thinking time
        prior_roll = game.last_roll or 1
        steps_time = 0.28 + (prior_roll * 0.32)
        cue = getattr(game, "sound_cue", "")
        extra_sound = 0.9 if cue and cue not in ("DICE_ROLL", "") else 0.0
        speech_text = getattr(game, "arrival_action", "") or getattr(game, "last_action", "")
        speech_time = min(2.5, max(1.0, len(speech_text.split()) * 0.16)) if speech_text else 1.0
        
        # Natural human-like turn delay (footsteps + sound effects + speech + pause)
        wait_time = max(1.8, steps_time + extra_sound + speech_time + 0.6)

        await asyncio.sleep(wait_time)
        if not game.active or game.current_player_id() != current_id:
            break
        try:
            async with room._mutation_lock:
                if not game.active or game.current_player_id() != current_id:
                    continue
                if is_frozen:
                    game.check_and_skip_frozen()
                else:
                    game.roll_dice(current_id)
                if game.winner_id is not None:
                    ws_manager.broadcast_room(room.room_id, {"type": "snakes_state_changed", "room_id": room.room_id})
                    await asyncio.sleep(2.5)
                    await finalize_snakes_match(room)
                    return
                ws_manager.broadcast_room(room.room_id, {"type": "snakes_state_changed", "room_id": room.room_id})
        except ValueError as exc:
            logger.warning("Snakes bot/frozen action rejected for %s: %s", current_id, exc)
            await asyncio.sleep(1.0)
            continue
        except Exception:
            logger.exception("Unexpected Snakes bot/frozen failure for %s", current_id)
            break
    room._bot_task = None

