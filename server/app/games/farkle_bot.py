"""Strategic, probabilistic Farkle bot decision engine."""
from __future__ import annotations
import random


class FarkleBot:
    def __init__(self, user_id: int, name: str):
        self.user_id = user_id
        self.name = name

    def should_bank(self, game) -> bool:
        """Determine whether banking current turn points is mathematically optimal."""
        turn_score = int(game.turn_score or 0)
        min_bank = int(game.min_bank or 30)
        first_min = int(game.first_bank_min or 50)
        my_score = int(game.scores.get(self.user_id, 0) or 0)
        target = int(game.target_score or 1000)

        req_min = first_min if my_score == 0 else min_bank
        if turn_score < req_min:
            return False

        # 1. Instant Victory: if banking reaches or exceeds target score, bank immediately!
        if my_score + turn_score >= target:
            return True

        # Opponent threat assessment
        other_scores = [s for uid, s in game.scores.items() if uid != self.user_id]
        max_opponent = max(other_scores) if other_scores else 0
        desperate = (max_opponent >= target - 200) and (my_score < max_opponent - 150)
        comfortable_lead = (my_score > max_opponent + 250)

        num_remaining = len(game.dice)

        # Hot dice (0 remaining dice / all scored -> next roll is with 6 dice, ~97.7% survival)
        if num_remaining == 0:
            if turn_score >= 1000 and comfortable_lead:
                return True
            return False

        # 1 die remaining (66.7% chance to Farkle)
        if num_remaining == 1:
            if desperate and turn_score < 150:
                return False
            return True

        # 2 dice remaining (44.4% chance to Farkle)
        if num_remaining == 2:
            if desperate and turn_score < 250:
                return False
            if turn_score >= 50 or my_score == 0:
                return True
            return turn_score >= 40

        # 3 dice remaining (27.8% chance to Farkle)
        if num_remaining == 3:
            if comfortable_lead and turn_score >= 150:
                return True
            if turn_score >= 300:
                return True
            return False

        # 4 or 5 dice remaining (low Farkle chance <= 15.7%)
        if num_remaining in (4, 5):
            if turn_score >= 500:
                return True
            return False

        return False

    def choose_scoring_indices(self, game) -> list[int]:
        """Choose the next single atomic scoring combination from current dice."""
        combos = game.get_available_combinations()
        if not combos:
            return []

        # 1. Take individual 5s (5 pts) and 1s (10 pts) step by step
        fives = [c for c in combos if c.get("type") == "single_5"]
        ones = [c for c in combos if c.get("type") == "single_1"]
        if fives:
            return fives[0]["indices"]
        if ones:
            return ones[0]["indices"]

        # 2. Distinct multi-dice combos (taken one by one)
        combos.sort(key=lambda c: (len(c.get("indices", [])), c.get("points", 0)))
        return combos[0]["indices"]

    def should_take_additional_combo(self, game) -> bool:
        """Determine if taking another available combo from the remaining dice is beneficial."""
        return bool(game.get_available_combinations())



import asyncio
from server.app.hub.ws_manager import ws_manager
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from server.app.hub.room_manager import Room
async def run_farkle_bots(room: Room):
    import random
    import logging
    logger = logging.getLogger("tableverse.farkle.bot")
    from server.app.hub.room_manager import room_manager
    from server.app.games.farkle_lifecycle import finalize_farkle_match
    game = room.farkle_game
    if not game or not game.active:
        return
    bot_ids = {uid for uid in room.players if uid < 0}
    while game.active:
        if not game.active:
            break
        current = game.current_player
        if not current or current[0] not in bot_ids:
            break
        bot = FarkleBot(current[0], current[1])
        try:
            # 1. Roll if turn just started
            if not game._rolled:
                await asyncio.sleep(1.0)
                async with room._mutation_lock:
                    if game.active and game.current_player and game.current_player[0] == bot.user_id:
                        game.action(bot.user_id, "roll")
            elif game.event_type == "DICE_ROLLED":
                # 2. Must score first combination from the roll
                selected = bot.choose_scoring_indices(game)
                await asyncio.sleep(1.0)
                if selected:
                    async with room._mutation_lock:
                        if game.active and game.current_player and game.current_player[0] == bot.user_id:
                            game.action(bot.user_id, "score", selected)
            else:
                # 3. Combination scored. Check if bot wants to score another available combination:
                await asyncio.sleep(1.0)
                async with room._mutation_lock:
                    if game.active and game.current_player and game.current_player[0] == bot.user_id:
                        if bot.should_take_additional_combo(game):
                            more_selected = bot.choose_scoring_indices(game)
                            if more_selected:
                                game.action(bot.user_id, "score", more_selected)
                            elif bot.should_bank(game):
                                game.action(bot.user_id, "bank")
                            else:
                                game.action(bot.user_id, "roll")
                        elif bot.should_bank(game):
                            game.action(bot.user_id, "bank")
                        else:
                            game.action(bot.user_id, "roll")

            room.scores = dict(game.scores)
            if game.winner_id is not None:
                await finalize_farkle_match(room)
                return
            ws_manager.broadcast_room(room.room_id, {"type": "farkle_state_changed", "room_id": room.room_id})
        except ValueError as exc:
            logger.warning("Farkle bot action rejected for %s: %s", bot.user_id, exc)
            await asyncio.sleep(0.5)
        except Exception:
            logger.exception("Unexpected Farkle bot failure for %s", bot.user_id)
            break
    room._bot_task = None

