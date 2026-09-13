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
        target = int(game.target_score or 1500)

        req_min = first_min if my_score == 0 else min_bank
        if turn_score < req_min:
            return False

        # 1. Instant Victory: if banking reaches or exceeds target score, bank immediately!
        if my_score + turn_score >= target:
            return True

        # Opponent threat assessment
        other_scores = [s for uid, s in game.scores.items() if uid != self.user_id]
        max_opponent = max(other_scores) if other_scores else 0
        opponent_close_to_win = (max_opponent >= target - 300)
        trailing_significantly = (my_score < max_opponent - 250)
        comfortable_lead = (my_score > max_opponent + 300)

        num_remaining = len(game.dice)

        # Hot dice (0 remaining dice / all scored -> next roll is with 6 dice, ~97.7% survival)
        if num_remaining == 0:
            # Rolling 6 dice has only a 2.3% chance to Farkle!
            # Only bank if turn score is already massive AND we have a comfortable lead
            if turn_score >= 1200 and comfortable_lead:
                return True
            return False

        # 1 die remaining (66.7% chance to Farkle)
        # Highly dangerous; bank unless desperate and points are too low
        if num_remaining == 1:
            if opponent_close_to_win and trailing_significantly and turn_score < req_min + 20:
                return False
            return True

        # 2 dice remaining (44.4% chance to Farkle)
        # Moderate-to-high risk. Bank if we meet minimum or accumulated good turn score
        if num_remaining == 2:
            if opponent_close_to_win and trailing_significantly and turn_score < 100:
                return False
            if turn_score >= req_min + 15 or turn_score >= 50:
                return True
            return my_score == 0 and turn_score >= first_min

        # 3 dice remaining (27.8% chance to Farkle)
        # Balanced risk. Bank if we have solid points or lead
        if num_remaining == 3:
            if comfortable_lead and turn_score >= 150:
                return True
            if turn_score >= 250:
                return True
            return False

        # 4 dice remaining (15.7% chance to Farkle)
        # Low risk. Keep rolling unless accumulated points are high
        if num_remaining == 4:
            if comfortable_lead and turn_score >= 300:
                return True
            if turn_score >= 450:
                return True
            return False

        # 5 dice remaining (7.7% chance to Farkle)
        # Very low risk. Almost always roll unless turn score is already huge
        if num_remaining == 5:
            if turn_score >= 600:
                return True
            return False

        return False

    def choose_scoring_indices(self, game) -> list[int]:
        """Choose the best scoring combination from current dice.
        Prioritize higher point combos first (large combinations), then single 1s (10 pts) and 5s (5 pts).
        """
        combos = game.get_available_combinations()
        if not combos:
            return []

        # Separate multi-dice combos vs single 1s/5s
        multi_combos = [c for c in combos if len(c.get("indices", [])) > 1]
        if multi_combos:
            # Sort by highest points first, then largest dice count to clear dice towards Hot Dice
            multi_combos.sort(key=lambda c: (c.get("points", 0), len(c.get("indices", []))), reverse=True)
            return multi_combos[0]["indices"]

        # Single dice: prefer single 1 (10 pts) over single 5 (5 pts)
        ones = [c for c in combos if c.get("type") == "single_1"]
        if ones:
            return ones[0]["indices"]
        fives = [c for c in combos if c.get("type") == "single_5"]
        if fives:
            return fives[0]["indices"]

        combos.sort(key=lambda c: c.get("points", 0), reverse=True)
        return combos[0]["indices"]

    def should_take_additional_combo(self, game) -> bool:
        """Determine if taking another available combo from remaining dice is beneficial.
        If taking the combo leaves 0 dice (Hot Dice!), always take it.
        If taking a low-value 5 (5 pts) leaves 1 or 2 dice, it might be better to keep them to roll,
        UNLESS we plan to bank anyway.
        """
        combos = game.get_available_combinations()
        if not combos:
            return False

        dice_left = len(game.dice)
        best_combo = combos[0]
        combo_len = len(best_combo.get("indices", []))

        # If taking this combo achieves Hot Dice (clears all remaining dice), always take it!
        if combo_len == dice_left:
            return True

        # If we already decided to bank or want to bank, take all available points before banking
        if self.should_bank(game):
            return True

        # If taking this combo would leave only 1 die remaining, and it's just a single 5 (5 pts),
        # don't take it if rolling 2 dice gives better odds than rolling 1 die!
        if dice_left == 2 and combo_len == 1 and best_combo.get("type") == "single_5":
            return False

        return True



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

