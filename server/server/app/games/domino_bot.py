"""Advanced Grandmaster bot player for Classic Dominoes."""
from __future__ import annotations
from typing import Dict, Any, List, Tuple
from server.app.games.domino import DominoGame


class DominoBot:
    """Master-level Domino Bot that plays strategically:
    - Dominant Suit Control: steers ends towards numbers it holds the most.
    - Double Management: prioritizes dumping heavy doubles early before getting trapped.
    - Exhaustion Tracking: detects when suits are almost exhausted on the board.
    - Smart Blocking & Pip Control: if ahead in points/pips, forces a table block (قفلة).
    - Synergy Evaluation: plays sides that leave the board open for its remaining tiles.
    """

    @staticmethod
    def choose_action(game: DominoGame, bot_id: int) -> Dict[str, Any]:
        if not game.active or bot_id != game.current_player_id():
            return {}

        valid_moves = game.get_valid_moves(bot_id)
        if valid_moves:
            hand: List[Tuple[int, int]] = game.hands.get(bot_id, [])
            board = list(game.board)

            # 1. Calculate suit frequencies in bot's hand
            hand_pip_counts = {i: 0 for i in range(7)}
            for a, b in hand:
                hand_pip_counts[a] += 1
                if a != b:
                    hand_pip_counts[b] += 1

            # 2. Count played tiles on the board per suit
            played_pip_counts = {i: 0 for i in range(7)}
            for t in board:
                played_pip_counts[t[0]] += 1
                if t[0] != t[1]:
                    played_pip_counts[t[1]] += 1

            # 3. Calculate bot's total hand pips
            my_total_pips = sum(t[0] + t[1] for t in hand)

            best_move = None
            best_score = -999999.0

            for m in valid_moves:
                idx = m["tile_index"]
                tile = m["tile"]
                a, b = tile
                is_double = (a == b)
                pip_sum = a + b
                remaining_tiles = [t for i, t in enumerate(hand) if i != idx]

                for side in m["sides"]:
                    score = 0.0

                    # 1. Base value: dump heavy pips to reduce penalty in case of block
                    score += pip_sum * 2.5

                    # 2. Doubles priority: dump high doubles early (6/6, 5/5, 4/4)
                    if is_double:
                        score += 45.0 + (pip_sum * 4.0)

                    # 3. Determine what the new open end on this side will be
                    if not board:
                        new_left = a
                        new_right = b
                        resulting_end = a
                    else:
                        if side == "left":
                            resulting_end = b if a == game.left_end else a
                            new_left = resulting_end
                            new_right = game.right_end
                        else:
                            resulting_end = b if a == game.right_end else a
                            new_left = game.left_end
                            new_right = resulting_end

                    # 4. Synergy: how many remaining tiles in hand match this resulting end?
                    matching_remaining = sum(1 for rt in remaining_tiles if resulting_end in rt)
                    score += matching_remaining * 22.0

                    # Also check if the other end matches remaining hand
                    other_end = new_right if side == "left" else new_left
                    if other_end is not None:
                        matching_other = sum(1 for rt in remaining_tiles if other_end in rt)
                        score += matching_other * 12.0

                    # 5. Dominant suit preference: favor opening numbers we have a majority of
                    score += (hand_pip_counts.get(resulting_end, 0) * 15.0)

                    # 6. Dead suit / Exhaustion trap:
                    played_of_this = played_pip_counts.get(resulting_end, 0)
                    if played_of_this >= 5 and matching_remaining == 0:
                        score += 30.0  # Trap opponent

                    # 7. Strategic Block Decision:
                    if new_left == new_right and new_left is not None:
                        avg_pip_per_tile = (my_total_pips - pip_sum) / max(1, len(remaining_tiles))
                        if avg_pip_per_tile <= 3.5:
                            score += 60.0  # Encourage winning block
                        else:
                            score -= 40.0  # Avoid blocking when holding heavy tiles

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
async def run_domino_bots(room: Room):
    import random
    import logging
    logger = logging.getLogger("tableverse.domino.bot")
    from server.app.hub.room_manager import room_manager
    from server.app.games.domino_lifecycle import check_and_finalize_domino_round
    game = room.domino_game
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
        action = DominoBot.choose_action(game, curr_id)
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
                ws_manager.broadcast_room(room.room_id, {"type": "domino_state_changed", "room_id": room.room_id})
                if not game.active:
                    await check_and_finalize_domino_round(room)
                    break
        except Exception:
            logger.exception("Unexpected Domino bot failure for %s", curr_id)
            break

