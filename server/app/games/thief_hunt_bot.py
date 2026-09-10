from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from server.app.hub.ws_manager import ws_manager
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from server.app.hub.room_manager import Room
async def run_thief_bots(room: Room):
    import random
    import logging
    logger = logging.getLogger("letsfly.thief_hunt.bot")
    from server.app.hub.room_manager import room_manager, THIEF_BOT_ACCURACY
    from server.app.games.thief_hunt_lifecycle import finalize_thief_match
    game = room.thief_game
    if not game or not game.active:
        return
    bot_ids = {uid for uid in room.players if uid < 0}
    for _ in range(300):
        if not room.thief_game or not room.thief_game.active:
            break
        
        async with room._mutation_lock:
            if not game.active:
                break
            game.tick()
            match_finished = game.match_finished
        if match_finished:
            await finalize_thief_match(room)
            return
        if game.phase == "choose_floor":
            if game.thief_id in bot_ids:
                async with room._mutation_lock:
                    chosen = random.randint(1, 10)
                    game.action(game.thief_id, "choose_floor", str(chosen))
                    ws_manager.broadcast_room(room.room_id, {"type": "thief_state_changed", "room_id": room.room_id})
            continue
        if game.phase == "escape":
            # Human investigators signal narration completion from the client.
            # If every investigator is a bot, there is no client to do that, so
            # the bot runner uses the same speech-duration estimate and then
            # starts the authoritative eight-second answer window.
            investigators = game.investigators
            human_investigators = [p for p in investigators if not p.is_bot]
            if not human_investigators:
                estimated = 0.5 + (len(game.directions) * 0.65)
                await asyncio.sleep(estimated)
                try:
                    async with room._mutation_lock:
                        if game.phase == "escape" and investigators:
                            game.action(investigators[0].user_id, "begin_answering")
                            ws_manager.broadcast_room(room.room_id, {"type": "thief_state_changed", "room_id": room.room_id})
                except ValueError as exc:
                    logger.warning("Thief bot could not begin answering: %s", exc)
                except Exception:
                    logger.exception("Unexpected Thief bot escape-phase failure")
            else:
                await asyncio.sleep(0.15)
            continue
        if game.phase == "answering":
            pending = [p for p in game.investigators if p.user_id in bot_ids and p.user_id not in game.answers]
            for p in pending:
                # Bots are ordinary investigators. They do not know the answer
                # automatically: each answer has a human-like probability of
                # error, and a wrong answer is deliberately chosen from the
                # other floors. This keeps bots subject to the same game rules
                # and win/loss accounting as human investigators.
                await asyncio.sleep(random.uniform(0.35, 1.10))
                try:
                    if random.random() < THIEF_BOT_ACCURACY:
                        answer_floor = game.current_floor
                    else:
                        alternatives = [floor for floor in range(1, 11) if floor != game.current_floor]
                        answer_floor = random.choice(alternatives)
                    async with room._mutation_lock:
                        game.action(p.user_id, "answer", str(answer_floor))
                        if game.match_finished:
                            await finalize_thief_match(room)
                            return
                        ws_manager.broadcast_room(room.room_id, {"type": "thief_state_changed", "room_id": room.room_id})
                except ValueError as exc:
                    logger.warning("Thief bot answer rejected for %s: %s", p.user_id, exc)
                except Exception:
                    logger.exception("Unexpected Thief bot answer failure for %s", p.user_id)
                    break
            if game.phase == "round_result":
                await asyncio.sleep(5.0)
                async with room._mutation_lock:
                    game.continue_after_round()
                    if game.phase != "round_result" and game.active:
                        room.round_started_at = datetime.now(timezone.utc).isoformat()
                    ws_manager.broadcast_room(room.room_id, {"type": "thief_state_changed", "room_id": room.room_id})
            else:
                await asyncio.sleep(0.15)
            continue
        if game.phase == "round_result":
            await asyncio.sleep(5.0)
            async with room._mutation_lock:
                game.continue_after_round()
                if game.phase != "round_result" and game.active:
                    room.round_started_at = datetime.now(timezone.utc).isoformat()
                ws_manager.broadcast_room(room.room_id, {"type": "thief_state_changed", "room_id": room.room_id})
            continue
        await asyncio.sleep(0.2)

