"""Advanced Grandmaster bot player for American Dominoes (All Fives)."""
from __future__ import annotations
from typing import Dict, Any, List, Tuple
from server.app.games.american_domino import AmericanDominoGame


class AmericanDominoBot:
    """Master-level American Domino Bot that:
    - Actively hunts and maximizes multiple-of-5 scoring combinations (5, 10, 15, 20).
    - Double management (5/5 = 10 points, 6/6 = 12 on the end).
    - Defensive end play: avoids leaving sum combinations that opponents can easily score on.
    - Hand synergy and pip dump on non-scoring turns.
    """

    @staticmethod
    def choose_action(game: AmericanDominoGame, bot_id: int) -> Dict[str, Any]:
        if not game.active or bot_id != game.current_player_id():
            return {}

        valid_moves = game.get_valid_moves(bot_id)
        if valid_moves:
            hand: List[Tuple[int, int]] = game.hands.get(bot_id, [])
            best_move = None
            best_score = -999999.0

            for m in valid_moves:
                idx = m["tile_index"]
                tile = m["tile"]
                a, b = tile
                is_double = (a == b)
                pip_sum = a + b
                sides = m["sides"]
                remaining_tiles = [t for i, t in enumerate(hand) if i != idx]

                for side in sides:
                    # Calculate resulting board ends
                    if not game.board:
                        sim_sum = a + b
                        new_left = a
                        new_right = b
                    else:
                        if len(game.board) == 1 and game.board[0][0] == game.board[0][1]:
                            opp_val = game.board[0][0] + game.board[0][1]
                            opp_end = game.board[0][0]
                        elif side == "left":
                            opp_val = (game.board[-1][0] + game.board[-1][1]) if game.board[-1][0] == game.board[-1][1] else game.board[-1][1]
                            opp_end = game.right_end
                        else:
                            opp_val = (game.board[0][0] + game.board[0][1]) if game.board[0][0] == game.board[0][1] else game.board[0][0]
                            opp_end = game.left_end

                        if side == "left":
                            new_left = a if b == game.left_end else b
                            my_val = (a + b) if is_double else new_left
                            new_right = opp_end
                            sim_sum = my_val + opp_val
                        else:
                            new_right = b if a == game.right_end else a
                            my_val = (a + b) if is_double else new_right
                            new_left = opp_end
                            sim_sum = opp_val + my_val

                    score = 0.0

                    # 1. Primary Objective: Direct Multiple of 5 Scoring
                    if sim_sum > 0 and sim_sum % 5 == 0:
                        score += 300.0 + (sim_sum * 15.0)  # Massive weight for scoring points!

                    # 2. Doubles priority
                    if is_double:
                        score += 30.0 + pip_sum * 2.0
                    else:
                        score += pip_sum * 1.5

                    # 3. Synergy for next turns: does remaining hand match new ends?
                    matching_ends = sum(1 for rt in remaining_tiles if new_left in rt or new_right in rt)
                    score += matching_ends * 15.0

                    # 4. Defensive board safety: avoid leaving ends that easily sum to 5 (e.g. 0 and 5)
                    if (new_left + new_right) % 5 == 0 and sim_sum % 5 != 0:
                        score -= 25.0

                    if score > best_score:
                        best_score = score
                        best_move = {
                            "action": "play",
                            "tile_index": idx,
                            "side": side,
                        }

            if best_move:
                return best_move

        if game.can_draw(bot_id):
            return {"action": "draw"}

        if game.can_pass(bot_id):
            return {"action": "pass"}

        return {}



import asyncio
from server.app.hub.ws_manager import ws_manager
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from server.app.hub.room_manager import Room
async def run_american_domino_bots(room: Room):
    import random
    import logging
    logger = logging.getLogger("letsfly.american_domino.bot")
    from server.app.hub.room_manager import room_manager
    from server.app.games.american_domino_lifecycle import check_and_finalize_american_domino_round
    game = room.american_domino_game
    if not game or not game.active:
        return
    bot_ids = {uid for uid in room.players if uid < 0}
    while game.active:
        if not game.active:
            break
        curr_id = game.current_player_id()
        if curr_id not in bot_ids:
            break
        await asyncio.sleep(1.2)
        if not game.active or game.current_player_id() != curr_id:
            continue
        action = AmericanDominoBot.choose_action(game, curr_id)
        if not action:
            break
        act = action.get("action")
        try:
            async with room._mutation_lock:
                if not game.active or game.current_player_id() != curr_id:
                    continue
                if act == "play":
                    game.play_tile(curr_id, action["tile_index"], action.get("side", "auto"))
                elif act == "draw":
                    game.draw_tile(curr_id)
                elif act == "pass":
                    game.pass_turn(curr_id)
                room.scores = dict(game.scores)
                ws_manager.broadcast_room(room.room_id, {"type": "american_domino_state_changed", "room_id": room.room_id})
                if not game.active:
                    await check_and_finalize_american_domino_round(room)
                    break
        except ValueError as exc:
            logger.warning("American Domino bot action rejected for %s: %s", curr_id, exc)
            break
        except Exception:
            logger.exception("Unexpected American Domino bot failure for %s", curr_id)
            break

