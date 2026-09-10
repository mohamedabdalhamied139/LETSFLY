"""Intelligent UnoBot player."""
from __future__ import annotations
from typing import Optional
from core_shared.constants import COLORS, DARK_COLORS
from core_shared.uno_rules import is_card_playable
from server.app.games.uno.game import UnoGame
from server.app.games.uno.deck import Card

class UnoBot:
    def __init__(self, user_id: int, name: str):
        self.user_id = user_id
        self.name = name

    def choose_color(self, hand: list[Card], dark_side: bool = False) -> str:
        palette = DARK_COLORS if dark_side else COLORS
        counts = {c: 0 for c in palette}
        for card in hand:
            if card.color in counts:
                counts[card.color] += 1
        return max(palette, key=lambda c: counts[c])

    def choose_card(self, game: UnoGame) -> Optional[Card]:
        player = game._find_player(self.user_id)
        top = game.discard[-1]
        playable = [
            c for c in player.hand
            if game._is_playable_for_player(c, top, player)
        ]
        if not playable:
            return None
        # Heuristic: play high value number cards first, then action cards, then wilds
        def priority(c: Card):
            if c.card_type == "number":
                return (1, c.value or 0)
            if c.card_type in ("skip", "reverse", "draw_two"):
                return (2, 20)
            return (3, 50)
        return max(playable, key=priority)



import asyncio
from server.app.hub.ws_manager import ws_manager
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from server.app.hub.room_manager import Room
async def run_uno_bots(room: Room):
    import random
    import logging
    logger = logging.getLogger("tableverse.uno.bot")
    from server.app.hub.room_manager import room_manager, _apply_game_score_adjustments
    from server.app.games.uno.lifecycle import check_and_finalize_uno_round
    game = room.uno_game
    if not game or not game.active:
        return
    bot_ids = {uid for uid in room.players if uid < 0}
    for _ in range(60):
        if not game.active:
            break

        # Global buzzer phase: every bot must press B, regardless of whose
        # normal turn it is. Human players can press B from the client.
        if game.buzzer_pending:
            pending_bots = [uid for uid in game.buzzer_pending if uid in bot_ids and uid not in game.buzzer_order]
            for bot_id in pending_bots:
                await asyncio.sleep(0.35)
                try:
                    async with room._mutation_lock:
                        if not game.active or bot_id not in game.buzzer_pending or bot_id in game.buzzer_order:
                            continue
                        game.action(bot_id, "buzzer")
                        _apply_game_score_adjustments(room)
                    ws_manager.broadcast_room(room.room_id, {"type": "uno_state_changed", "room_id": room.room_id})
                except ValueError as exc:
                    logger.warning("UNO bot buzzer action rejected for %s: %s", bot_id, exc)
                except Exception:
                    logger.exception("Unexpected UNO bot buzzer failure for %s", bot_id)
            if game.buzzer_pending:
                # Wait for the human player(s) to press B. A later human action
                # will wake the bot runner again if necessary.
                break
            continue

        # Bluff challenge is also a mandatory decision window. If the target
        # is a bot, it can either challenge or draw; we choose challenge when
        # the +4 was demonstrably a bluff, otherwise accept the penalty.
        if game.pending_bluff:
            target_id = game.pending_bluff["target_id"]
            if target_id not in bot_ids:
                break
            await asyncio.sleep(2.0)
            try:
                async with room._mutation_lock:
                    if not game.active or not game.pending_bluff or game.pending_bluff.get("target_id") != target_id:
                        continue
                    if game.pending_bluff.get("had_matching_color"):
                        game.action(target_id, "challenge_bluff")
                    else:
                        game.action(target_id, "draw")
                    _apply_game_score_adjustments(room)
                ws_manager.broadcast_room(room.room_id, {"type": "uno_state_changed", "room_id": room.room_id})
            except ValueError as exc:
                logger.warning("UNO bot bluff action rejected for %s: %s", target_id, exc)
                break
            except Exception:
                logger.exception("Unexpected UNO bot bluff failure for %s", target_id)
                break
            continue

        # A 7 exchange is a mandatory decision for the player who played the
        # seven. If that player is a bot, choose another active player.
        if game.pending_exchange_user is not None:
            exchange_user = game.pending_exchange_user
            if exchange_user not in bot_ids:
                break
            await asyncio.sleep(2.0)
            try:
                async with room._mutation_lock:
                    if not game.active or game.pending_exchange_user != exchange_user:
                        continue
                    targets = [p for p in game.active_players if p.user_id != exchange_user]
                    if targets:
                        target = random.choice(targets)
                        game.action(exchange_user, "exchange_hand", str(target.user_id))
                        _apply_game_score_adjustments(room)
                if targets:
                    ws_manager.broadcast_room(room.room_id, {"type": "uno_state_changed", "room_id": room.room_id})
                else:
                    break
            except ValueError as exc:
                logger.warning("UNO bot exchange action rejected for %s: %s", exchange_user, exc)
                break
            except Exception:
                logger.exception("Unexpected UNO bot exchange failure for %s", exchange_user)
                break
            continue

        if game.current_player.user_id not in bot_ids:
            break
        bot_id = game.current_player.user_id
        bot = UnoBot(bot_id, game.current_player.name)
        await asyncio.sleep(2.0)

        try:
            bot_needs_call = False
            async with room._mutation_lock:
                if not game.active or game.current_player.user_id != bot_id:
                    break

                # Catch an uncalled UNO before making the bot's normal move.
                if game.pending_uno:
                    other = [u for u in game.pending_uno if u != bot_id]
                    if other:
                        try:
                            game.action(bot_id, "catch_uno", str(other[0]))
                            _apply_game_score_adjustments(room)
                            ws_manager.broadcast_room(room.room_id, {"type": "uno_state_changed", "room_id": room.room_id})
                        except Exception:
                            logger.exception("Unexpected UNO bot catch-UNO failure for %s", bot_id)

                card = bot.choose_card(game)
                bot_player = game._find_player(bot_id)
                if card:
                    chosen = bot.choose_color(bot_player.hand, dark_side=game.dark_side) if card.is_wild else ""
                    game.action(bot_id, "play", card.card_id, chosen)
                    _apply_game_score_adjustments(room)
                    bot_needs_call = len(bot_player.hand) == 1 and bot_id in game.pending_uno
                else:
                    game.action(bot_id, "draw")
                    _apply_game_score_adjustments(room)
                    if bot_id in game.drawn_card:
                        drawn = game.drawn_card[bot_id]
                        top = game.discard[-1]
                        if game._is_playable_for_player(drawn, top, bot_player):
                            chosen = bot.choose_color(bot_player.hand, dark_side=game.dark_side) if drawn.is_wild else ""
                            game.action(bot_id, "play", drawn.card_id, chosen)
                            _apply_game_score_adjustments(room)
                            bot_needs_call = len(bot_player.hand) == 1 and bot_id in game.pending_uno

            ws_manager.broadcast_room(room.room_id, {"type": "uno_state_changed", "room_id": room.room_id})

            if bot_needs_call:
                await asyncio.sleep(0.45)
                async with room._mutation_lock:
                    if (
                        room_manager.get_room(room.room_id) is room
                        and room.uno_game is game
                        and game.active
                        and any(p.user_id == bot_id for p in game.players)
                        and bot_id in game.pending_uno
                        and len(game._find_player(bot_id).hand) == 1
                    ):
                        try:
                            game.action(bot_id, "call_uno")
                            _apply_game_score_adjustments(room)
                            ws_manager.broadcast_room(room.room_id, {"type": "uno_state_changed", "room_id": room.room_id})
                        except Exception:
                            logger.exception("Unexpected UNO bot call-uno failure for %s", bot_id)

            if not game.active:
                await check_and_finalize_uno_round(room)
                break
        except Exception:
            logger.exception("Unexpected UNO bot loop failure for room %s", room.room_id)
            break

        if not game.active:
            await check_and_finalize_uno_round(room)
            break

    # If the 60-iteration budget finishes while a bot action is still required,
    # safely reschedule the bot runner to keep long bot matches running smoothly.
    if (
        room_manager.get_room(room.room_id) is room
        and room.uno_game is game
        and game.active
        and (
            game.current_player.user_id in bot_ids
            or (game.buzzer_pending and any(b in game.buzzer_pending and b not in game.buzzer_order for b in bot_ids))
            or (game.pending_bluff and game.pending_bluff.get("target_id") in bot_ids)
            or (game.pending_exchange_user is not None and game.pending_exchange_user in bot_ids)
        )
    ):
        if room._bot_task is None or room._bot_task.done() or room._bot_task is asyncio.current_task():
            room._bot_task = asyncio.create_task(run_uno_bots(room))

