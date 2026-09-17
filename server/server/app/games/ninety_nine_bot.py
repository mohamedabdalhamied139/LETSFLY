from __future__ import annotations
# -*- coding: utf-8 -*-
from typing import Dict, Any, Optional, List, Tuple

class NinetyNineBot:
    """Intelligent and strategic bot decision engine for 99 / Ninety-Nine.
    
    Operates strictly within legal authoritative rules without cheating or peeking
    at hidden opponent cards or future deck cards.
    """

    @staticmethod
    def evaluate_card_branches(game, uid: int, card: Dict[str, Any]) -> List[Tuple[Optional[int], int, int]]:
        """Returns candidate (choice_val, resulting_total, val) branches for the given card."""
        val = card["value"]
        pile = game.pile_value
        outcomes = []
        
        if val in (3, 4, 5, 6, 7, 8):
            outcomes.append((None, pile + val, val))
        elif val == 9:
            outcomes.append((None, pile, val))
        elif val in (11, 12, 13):
            outcomes.append((None, pile + 10, val))
        elif val == 10:
            outcomes.append((10, pile + 10, val))
            outcomes.append((-10, pile - 10, val))
        elif val == 1:
            outcomes.append((1, pile + 1, val))
            outcomes.append((11, pile + 11, val))
        elif val == 2:
            if pile % 2 == 0 and pile > 49:
                outcomes.append((None, pile // 2, val))
            else:
                outcomes.append((None, pile * 2, val))
                
        return outcomes

    @staticmethod
    def choose_play(game, uid: int) -> Optional[Dict[str, Any]]:
        """Evaluates all legal moves strategically based on current pile, life totals, and tactical card retention."""
        hand = game.hands.get(uid, [])
        if not hand:
            return None
            
        pile = game.pile_value
        active_players = game.active_players
        my_tokens = game.tokens.get(uid, 11)
        
        # Determine next player in turn order (public info)
        next_idx = (game.current_turn_index + game.direction) % len(game.player_ids)
        while game.player_ids[next_idx] in game.eliminated:
            next_idx = (next_idx + game.direction) % len(game.player_ids)
        next_player_id = game.player_ids[next_idx] if active_players else None
        next_player_tokens = game.tokens.get(next_player_id, 11) if next_player_id is not None else 11

        candidates = []
        
        for c in hand:
            evals = NinetyNineBot.evaluate_card_branches(game, uid, c)
            for choice_val, res_tot, val in evals:
                score = 0
                
                # 1. Instant Round Win
                if res_tot == 99:
                    score = 2500
                    
                # 2. Bust Moves (Exceeding 99)
                elif res_tot > 99:
                    # 2 doubling beyond 99 costs 3 tokens (severely penalized!)
                    if val == 2:
                        score = -3000
                    else:
                        score = -1500
                        
                # 3. Safe Legal Moves (res_tot <= 99)
                else:
                    score = 300
                    
                    # Penalties for crossing 33 or 66 upward
                    if pile < 33 and res_tot >= 33:
                        score -= 180  # Incurs 1 token loss to bot
                    elif pile < 66 and res_tot >= 66:
                        score -= 180  # Incurs 1 token loss to bot

                    # High Danger Zone (Pile >= 85)
                    if pile >= 85:
                        # Massive value in cooldown moves: Halving with 2 or subtracting with 10
                        if val == 2 and res_tot < pile:
                            score += 950  # Halving brings huge relief (e.g. 96 -> 48)
                        elif val == 10 and choice_val == -10:
                            score += 880  # Subtracting 10 cools the pile (e.g. 95 -> 85)
                        elif val == 9:
                            score += 750  # 9 passes without increasing pile
                        elif val == 1 and choice_val == 1:
                            score += 700  # Ace as +1 is a delicate safe increment
                            
                        # Pressuring the next player into dangerous totals (95-98)
                        if 95 <= res_tot <= 98:
                            score += 150
                            if next_player_tokens <= 2:
                                score += 100  # Extra pressure if next opponent is vulnerable
                                
                    # Mid-Game Zone (Pile < 85)
                    else:
                        # In low/mid game, prefer playing ordinary value cards (3-8, face cards)
                        # and preserve high-utility cards (9, 10, Ace, 2) for the 90+ endgame.
                        if val in (3, 5, 6, 7, 8):
                            score += 120
                        elif val in (12, 13):  # Queen, King (+10)
                            score += 100
                        elif val == 11:  # Jack (+10 and Skip)
                            score += 140
                            if len(active_players) == 2:
                                score += 80  # Playing again in 2-player match is advantageous
                        elif val == 4:  # 4 (+4 and Reverse)
                            score += 110
                            
                        # Slight preference to save utility cards for later when pile is low
                        if val == 9:
                            score -= 60  # Hold onto 9 for when pile reaches 90+
                        if val == 10 and choice_val == -10 and pile < 60:
                            score -= 40  # Don't waste -10 when pile is already low
                        if val == 1 and choice_val == 1 and pile < 70:
                            score -= 30  # Save Ace for versatile endgame play
                        if val == 2 and res_tot <= 85 and pile <= 42:
                            score += 90  # Safe doubling accelerates game smoothly
                            
                candidates.append({
                    "card_id": c["id"],
                    "value": val,
                    "choice_val": choice_val,
                    "result_total": res_tot,
                    "score": score
                })
                
        # Sort candidates by strategic score descending
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[0] if candidates else None



import asyncio
from datetime import datetime, timezone
from server.app.hub.ws_manager import ws_manager
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from server.app.hub.room_manager import Room
async def run_ninety_nine_bots(room: "Room"):
    import random
    import logging
    logger = logging.getLogger("tableverse.ninety_nine.bot")
    from server.app.hub.room_manager import room_manager
    from server.app.games.ninety_nine_lifecycle import _start_next_ninety_nine_round_after_delay
    game = room.ninety_nine_game
    if not game or not game.active:
        return
    import asyncio
    import random
    import time
    from server.app.hub.ws_manager import ws_manager
    from server.app.games.ninety_nine_bot import NinetyNineBot
    bot_ids = {uid for uid in room.players if uid < 0}
    while game.active:
        curr = game.player_ids[game.current_turn_index]
        if curr not in bot_ids:
            if not game.turn_timer:
                break
            # Human player's turn with an active timer: wait until timeout or player move
            elapsed = time.monotonic() - game.turn_started_at
            remain = game.turn_timer - elapsed
            if remain > 0:
                await asyncio.sleep(min(remain, 0.5))
                continue
            
            # Timer expired for human player
            async with room._mutation_lock:
                if not game.active or game.player_ids[game.current_turn_index] != curr:
                    continue
                if (time.monotonic() - game.turn_started_at) < game.turn_timer:
                    continue
                game.handle_timeout()
                room.scores = dict(game.tokens)
                ws_manager.broadcast_room(room.room_id, {"type": "game_state_changed", "room_id": room.room_id})
                if game.match_finished:
                    wid = game.winner_id
                    wname = room.player_names.get(wid, "لاعب")
                    room.status = "match_finished"
                    from server.app.db.database import SessionLocal
                    from server.app.social_services import record_match
                    def persist_match():
                        db = SessionLocal()
                        try:
                            record_match(db, "NINETY_NINE", room.room_id, room.players, [wid])
                            db.commit()
                        except Exception:
                            db.rollback()
                            raise
                        finally:
                            db.close()
                    await asyncio.to_thread(persist_match)
                    ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})
                    ws_manager.broadcast_room(room.room_id, {
                        "type": "match_finished",
                        "winner_name": wname,
                        "winner_id": wid,
                        "total": game.tokens.get(wid, 0),
                        "scores": {str(uid): game.tokens.get(uid, 0) for uid in room.players}
                    })
                    room.ninety_nine_game = None
                    room.status = "waiting"
                    room.round_started_at = None
                    room.rules = {}
                    ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})
                    ws_manager.broadcast_room(room.room_id, {"type": "game_finished", "game": "NINETY_NINE"})
                    break
                elif game.round_finished:
                    room.status = "round_finished"
                    ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})
                    ws_manager.broadcast_room(room.room_id, {
                        "type": "ninety_nine_round_finished",
                        "delay_seconds": 5,
                        "last_action": game.last_action,
                        "tokens": game.tokens
                    })
                    if room._round_transition_task is None or room._round_transition_task.done():
                        room._round_transition_task = asyncio.create_task(_start_next_ninety_nine_round_after_delay(room))
                    break
            continue
            
        # Realistic human-like thinking delay (1.3 to 1.7s) matching Uno and Scopa bots
        await asyncio.sleep(random.uniform(1.3, 1.7))
        
        async with room._mutation_lock:
            if not game.active or game.player_ids[game.current_turn_index] != curr:
                break
                
            if game.pending_choice and game.pending_choice.get("player_id") == curr:
                c_type = game.pending_choice.get("type")
                best_choice = 10
                if c_type == "10":
                    best_choice = 10 if game.pile_value + 10 <= 99 else -10
                elif c_type == "A":
                    best_choice = 11 if (game.pile_value + 11 == 99 or (game.pile_value + 11 <= 99 and game.pile_value < 85)) else 1
                try:
                    game.action(curr, "choose", best_choice)
                except ValueError as exc:
                    logger.warning("Ninety-Nine bot choice rejected for %s: %s", curr, exc)
                except Exception:
                    logger.exception("Unexpected Ninety-Nine bot choice failure for %s", curr)
                ws_manager.broadcast_room(room.room_id, {"type": "game_state_changed", "room_id": room.room_id})
            else:
                decision = NinetyNineBot.choose_play(game, curr)
                if decision:
                    try:
                        game.action(curr, "play", decision["card_id"])
                        
                        # If a choice is pending for this bot (10 or Ace), resolve with decision choice_val immediately
                        if game.active and game.pending_choice and game.pending_choice.get("player_id") == curr:
                            c_val = decision.get("choice_val")
                            if c_val is not None:
                                game.action(curr, "choose", c_val)
                                
                        ws_manager.broadcast_room(room.room_id, {"type": "game_state_changed", "room_id": room.room_id})
                    except ValueError as exc:
                        logger.warning("Ninety-Nine bot play rejected for %s: %s", curr, exc)
                    except Exception:
                        logger.exception("Unexpected Ninety-Nine bot play failure for %s", curr)
                        
            room.scores = dict(game.tokens)
            if game.match_finished:
                wid = game.winner_id
                wname = room.player_names.get(wid, "لاعب")
                room.status = "match_finished"
                from server.app.db.database import SessionLocal
                from server.app.social_services import record_match
                def persist_match():
                    db = SessionLocal()
                    try:
                        record_match(db, "NINETY_NINE", room.room_id, room.players, [wid])
                        db.commit()
                    except Exception:
                        db.rollback()
                        raise
                    finally:
                        db.close()
                await asyncio.to_thread(persist_match)
                ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})
                ws_manager.broadcast_room(room.room_id, {
                    "type": "match_finished",
                    "winner_name": wname,
                    "winner_id": wid,
                    "total": game.tokens.get(wid, 0),
                    "scores": {str(uid): game.tokens.get(uid, 0) for uid in room.players}
                })
                room.ninety_nine_game = None
                room.status = "waiting"
                room.round_started_at = None
                room.rules = {}
                ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})
                ws_manager.broadcast_room(room.room_id, {"type": "game_finished", "game": "NINETY_NINE"})
                break
            elif game.round_finished:
                room.status = "round_finished"
                ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})
                ws_manager.broadcast_room(room.room_id, {
                    "type": "ninety_nine_round_finished",
                    "delay_seconds": 5,
                    "last_action": game.last_action,
                    "tokens": game.tokens
                })
                if room._round_transition_task is None or room._round_transition_task.done():
                    room._round_transition_task = asyncio.create_task(_start_next_ninety_nine_round_after_delay(room))
                break

