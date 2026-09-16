from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from server.app.hub.ws_manager import ws_manager
from server.app.social_services import record_match
from server.app.db.database import SessionLocal
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from server.app.hub.room_manager import Room


async def _persist_match(room, winners):
    def save():
        db = SessionLocal()
        try:
            record_match(db, "SCOPA", room.room_id, room.players, list(winners), match_key=room.match_key)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    await asyncio.to_thread(save)


def broadcast_scopa_state(room: Room, game=None, extra: dict | None = None):
    """Broadcast a private, viewer-correct Scopa snapshot to each attendee."""
    game = game or getattr(room, "scopa_game", None)
    if not game:
        return
    extra = extra or {}
    notified_users = set()
    for user_id in getattr(room, "players", []):
        if user_id > 0:
            payload = {
                "type": "scopa_state_changed",
                "room_id": room.room_id,
                "state": game.public_state(user_id),
            }
            payload.update(extra)
            ws_manager.broadcast_user(user_id, payload)
            notified_users.add(user_id)
    for spectator_id in getattr(room, "spectators", []):
        if spectator_id > 0 and spectator_id not in notified_users:
            payload = {
                "type": "scopa_state_changed",
                "room_id": room.room_id,
                "state": game.public_state(None),
            }
            payload.update(extra)
            ws_manager.broadcast_user(spectator_id, payload)
            notified_users.add(spectator_id)
async def check_and_finalize_scopa_round(room: Room):
    import logging
    logger = logging.getLogger("tableverse.scopa.lifecycle")
    from server.app.hub.room_manager import room_manager
    if room.status == "round_finished":
        return
    game = room.scopa_game
    if not game or game.active:
        return
    target_score = int(room.target_score or 11)

    if game.winner_id is not None or game.winning_team is not None:
        room.status = "match_finished"
        if game.is_team_game:
            winning_ids=[uid for uid,tid in game.teams.items() if tid == game.winning_team]
            winner_label = getattr(game, "winner_label", f"الفريق {game.winning_team}")
            try:
                await _persist_match(room, winning_ids)
            except Exception:
                logger.exception("Failed to persist scopa match to database")
            ws_manager.broadcast_room(room.room_id, {
                "type": "scopa_match_finished",
                "room_id": room.room_id,
                "winner_label": winner_label,
                "winning_team": game.winning_team,
                "scores": {str(k): v for k, v in game.team_scores.items()},
                "target_score": target_score,
                "event_id": game.event_id,
                "final_play_event_type": game.final_play_event_type,
                "final_play_action": game.final_play_action,
                "final_play_event_id": game.final_play_event_id,
            })
        else:
            final_winner_id = game.winner_id
            try:
                await _persist_match(room, [final_winner_id])
            except Exception:
                logger.exception("Failed to persist scopa match to database")
            final_winner_name = room.player_names.get(final_winner_id, "الفائز")
            ws_manager.broadcast_room(room.room_id, {
                "type": "scopa_match_finished",
                "room_id": room.room_id,
                "winner_id": final_winner_id,
                "winner_name": final_winner_name,
                "scores": {str(k): v for k, v in game.scores.items()},
                "target_score": target_score,
                "event_id": game.event_id,
                "final_play_event_type": game.final_play_event_type,
                "final_play_action": game.final_play_action,
                "final_play_event_id": game.final_play_event_id,
            })

        if room._bot_task and not room._bot_task.done():
            current = asyncio.current_task()
            if room._bot_task is not current:
                room._bot_task.cancel()
        room._bot_task = None
        room.scopa_game = None
        room.status = "waiting"
        room.round_started_at = None
        room.target_score = None
        room.rules = {}
        room.scores = {uid: 0 for uid in room.players}
        ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})
        ws_manager.broadcast_room(room.room_id, {
            "type": "game_finished", "room_id": room.room_id, "game": "SCOPA"
        })
        return

    # Advance to next round
    room.status = "round_finished"
    ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})
    ws_manager.broadcast_room(room.room_id, {
        "type": "scopa_round_finished",
        "round_summary": game.round_summary,
        "target_score": target_score,
        "delay_seconds": 5,
        "scores": {str(k): v for k, v in (game.team_scores if game.is_team_game else game.scores).items()},
        "event_id": game.event_id,
        "final_play_event_type": game.final_play_event_type,
        "final_play_action": game.final_play_action,
        "final_play_event_id": game.final_play_event_id,
    })
    if room._round_transition_task is None or room._round_transition_task.done():
        room._round_transition_task = asyncio.create_task(_start_next_scopa_round_after_delay(room))

async def _start_next_scopa_round_after_delay(room: Room):
    import logging
    logger = logging.getLogger("tableverse.scopa.lifecycle")
    from server.app.hub.room_manager import room_manager
    from server.app.games.scopa import ScopaGame
    from server.app.games.scopa_bot import run_scopa_bots
    try:
        await asyncio.sleep(5)
        # Serialize the transition with player actions/Stop. The state check and
        # round creation must happen while holding the same room mutation lock.
        async with room._mutation_lock:
            if room.status != "round_finished" or not room.players or not room.scopa_game:
                return
            room._bot_task = None
            room.scopa_game.start_new_round()
            room.status = "playing"
            room.round_started_at = datetime.now(timezone.utc).isoformat()
        ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})
        broadcast_scopa_state(room, room.scopa_game, extra={"round_started": True})
        if room._bot_task is None or room._bot_task.done():
            room._bot_task = asyncio.create_task(run_scopa_bots(room))
    except asyncio.CancelledError:
        raise
    finally:
        current = asyncio.current_task()
        if room._round_transition_task is current:
            room._round_transition_task = None


def schedule_scopa_deal_batch(room: Room, delay_seconds: float = 0.4):
    """Schedule dealing the next batch of cards after a delay, allowing last card speech to finish."""
    if getattr(room, "_deal_batch_task", None) is None or room._deal_batch_task.done():
        room._deal_batch_task = asyncio.create_task(_deal_next_batch_after_delay(room, delay_seconds))


async def _deal_next_batch_after_delay(room: Room, delay_seconds: float):
    from server.app.games.scopa_bot import run_scopa_bots
    try:
        await asyncio.sleep(delay_seconds)
        async with room._mutation_lock:
            if not room.scopa_game or not room.scopa_game.active:
                return
            room.scopa_game._deal_next_batch()
            broadcast_scopa_state(room, room.scopa_game)
        if room._bot_task is None or room._bot_task.done():
            room._bot_task = asyncio.create_task(run_scopa_bots(room))
    except asyncio.CancelledError:
        raise
    finally:
        current = asyncio.current_task()
        if getattr(room, "_deal_batch_task", None) is current:
            room._deal_batch_task = None
