from __future__ import annotations

import asyncio
from server.app.hub.ws_manager import ws_manager
from server.app.social_services import record_match
from server.app.db.database import SessionLocal, User, CoinTransaction
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from server.app.hub.room_manager import Room


def _persist_snakes_match(room, winner_id, coin_rewards):
    db = SessionLocal()
    try:
        match_record = record_match(db, "SNAKES_LADDERS", room.room_id, room.players, [winner_id])
        match_id = match_record.id if match_record else 0
        for uid, amount in list(coin_rewards.items()):
            if isinstance(uid, int) and uid > 0 and amount > 0:
                reward_id = f"snakes_mystery_box:{room.room_id}:{uid}"
                from server.app.db.database import RewardRecord
                existing = db.query(RewardRecord).filter_by(reward_id=reward_id).first()
                if not existing:
                    from sqlalchemy import update
                    result = db.execute(update(User).where(User.id == uid).values(coins=User.coins + amount))
                    if result.rowcount <= 0:
                        raise RuntimeError(f"User {uid} not found for snakes coin reward update; rolling back.")
                    db.add(RewardRecord(reward_id=reward_id))
                    db.add(CoinTransaction(user_id=uid, amount=amount, reason=reward_id))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
async def finalize_snakes_match(room: Room):
    import logging
    logger = logging.getLogger("letsfly.snakes.lifecycle")
    from server.app.hub.room_manager import room_manager
    game = room.snakes_game
    if not game or game.winner_id is None:
        return
    winner_id = game.winner_id
    winner_name = room.player_names.get(winner_id, "الفائز")
    coin_rewards = dict(getattr(game, "coin_rewards", {}) or {})
    try:
        await asyncio.to_thread(_persist_snakes_match, room, winner_id, coin_rewards)
        game.coin_rewards = {}
    except Exception:
        logger.exception("Failed to persist snakes match rewards to database")
        raise
    ws_manager.broadcast_room(room.room_id, {
        "type": "snakes_match_finished",
        "room_id": room.room_id,
        "winner_id": winner_id,
        "winner_name": winner_name,
        "positions": {str(k): v for k, v in game.positions.items()},
        "coin_rewards": {str(k): v for k, v in coin_rewards.items() if isinstance(k, int) and k > 0},
    })
    if room._bot_task and not room._bot_task.done():
        current = asyncio.current_task()
        if room._bot_task is not current:
            room._bot_task.cancel()
    room._bot_task = None
    room.snakes_game = None
    room.status = "waiting"
    room.round_started_at = None
    room.rules = {}
    ws_manager.broadcast_lobby({"type": "room_updated", "room_id": room.room_id})
    ws_manager.broadcast_room(room.room_id, {
        "type": "game_finished", "room_id": room.room_id, "game": "SNAKES_LADDERS"
    })

