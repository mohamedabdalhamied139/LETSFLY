"""Scopa AI Bot for TableVerse."""
from __future__ import annotations
from typing import Dict, Any, Optional
from server.app.games.scopa import ScopaGame

class ScopaBot:
    @staticmethod
    def choose_action(game: ScopaGame, bot_id: int) -> Optional[Dict[str, Any]]:
        if not game.active or game.current_player_id() != bot_id:
            return None

        hand = game.hands.get(bot_id, [])
        if not hand:
            return None

        is_inverted = bool(game.rules.get("inverted") or game.game_mode == "inverted")

        # If a pending choice is waiting for this bot
        if game.pending_choice and game.pending_choice["user_id"] == bot_id:
            choices = game.pending_choice["choices"]
            best_idx = 0
            best_val = -9999 if not is_inverted else 9999
            for c_idx, combo in enumerate(choices):
                val = len(combo) * 2
                for c in combo:
                    if c["suit"] in ("Diamonds", "دايموند"):
                        val += 4
                    if c["suit"] in ("Diamonds", "دايموند") and c["value"] == 7:
                        val += 20
                    if c["value"] in (7, 6, 1):
                        val += 3
                if not is_inverted:
                    if val > best_val:
                        best_val = val
                        best_idx = c_idx
                else:
                    if val < best_val:
                        best_val = val
                        best_idx = c_idx
            return {
                "action": "play",
                "card_index": game.pending_choice["card_index"],
                "capture_choice": best_idx,
            }

        best_card_idx = 0
        best_combo_idx = None
        best_score = -99999

        for idx, card in enumerate(hand):
            combos = game.get_combinations(card["value"])
            if not combos:
                # Discard heuristic
                if not is_inverted:
                    score = -10
                    if card["suit"] in ("Diamonds", "دايموند"):
                        score -= 10
                    if card["value"] == 7:
                        score -= 20
                    if card["value"] == 6:
                        score -= 8
                    if card["value"] == 1:
                        score -= 6
                else:
                    score = 10
                    if card["suit"] in ("Diamonds", "دايموند"):
                        score += 10
                    if card["value"] == 7:
                        score += 20
                if score > best_score:
                    best_score = score
                    best_card_idx = idx
                    best_combo_idx = None
            else:
                for c_idx, combo in enumerate(combos):
                    if not is_inverted:
                        score = len(combo) * 2
                        for c in combo:
                            if c["suit"] in ("Diamonds", "دايموند"):
                                score += 5
                            if c["suit"] in ("Diamonds", "دايموند") and c["value"] == 7:
                                score += 25
                            if c["value"] == 7:
                                score += 10
                            if c["value"] == 6:
                                score += 6
                            if c["value"] == 1:
                                score += 5

                        # Scopa sweep bonus!
                        if len(combo) == len(game.table_cards):
                            score += 40
                    else:
                        score = -len(combo) * 3
                        for c in combo:
                            if c["suit"] in ("Diamonds", "دايموند"):
                                score -= 8
                            if c["suit"] in ("Diamonds", "دايموند") and c["value"] == 7:
                                score -= 30
                            if c["value"] == 7:
                                score -= 12

                    if score > best_score:
                        best_score = score
                        best_card_idx = idx
                        best_combo_idx = c_idx if len(combos) > 1 else None

        return {
            "action": "play",
            "card_index": best_card_idx,
            "capture_choice": best_combo_idx,
        }



import asyncio
from server.app.hub.ws_manager import ws_manager
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from server.app.hub.room_manager import Room
async def run_scopa_bots(room: Room):
    import random
    import logging
    logger = logging.getLogger("tableverse.scopa.bot")
    from server.app.hub.room_manager import room_manager
    from server.app.games.scopa_lifecycle import check_and_finalize_scopa_round
    game = room.scopa_game
    if not game or not game.active:
        return
    bot_ids = {uid for uid in room.players if uid < 0}
    while game.active:
        curr_id = game.current_player_id()
        if curr_id not in bot_ids:
            break
        await asyncio.sleep(1.2)
        if not game.active or game.current_player_id() != curr_id:
            break
        action = ScopaBot.choose_action(game, curr_id)
        if not action:
            break
        try:
            async with room._mutation_lock:
                if not game.active or game.current_player_id() != curr_id:
                    break
                game.play_card(curr_id, action["card_index"], action.get("capture_choice"))
                room.scores = dict(game.team_scores if game.is_team_game else game.scores)
                state = game.public_state()
                ws_manager.broadcast_room(room.room_id, {
                    "type": "scopa_state_changed",
                    "room_id": room.room_id,
                    "state": state
                })
                if getattr(game, "pending_deal_batch", False):
                    game.pending_deal_batch = False
                    await asyncio.sleep(2.2)
                    if game.active:
                        game._deal_next_batch()
                        ws_manager.broadcast_room(room.room_id, {
                            "type": "scopa_state_changed",
                            "room_id": room.room_id,
                            "state": game.public_state()
                        })
                if not game.active:
                    await check_and_finalize_scopa_round(room)
                    break
        except ValueError as exc:
            logger.warning("Scopa bot action rejected for %s: %s", curr_id, exc)
            break
        except Exception:
            logger.exception("Unexpected Scopa bot failure for %s", curr_id)
            break

