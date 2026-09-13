"""Room and Match lifecycle manager."""
import asyncio
import logging
import random
import threading
import copy
from datetime import datetime, timezone
from uuid import uuid4
from typing import Dict, List, Optional
from server.app.games.uno.game import UnoGame
from server.app.games.thief_hunt import ThiefHuntGame
from server.app.games.farkle import FarkleGame
from server.app.games.domino import DominoGame
from server.app.games.american_domino import AmericanDominoGame
from server.app.games.snakes_and_ladders import SnakesAndLaddersGame
from server.app.games.scopa import ScopaGame
from server.app.games.tennis import TennisGame

logger = logging.getLogger("tableverse.room_manager")

# Thief Hunt bots are normal investigators. They answer with human-like
# uncertainty instead of receiving the correct floor automatically.
THIEF_BOT_ACCURACY = 0.80
SUPPORTED_GAMES = {"UNO", "THIEF_HUNT", "FARKLE", "DOMINO", "AMERICAN_DOMINO", "SNAKES_LADDERS", "SCOPA", "TENNIS", "NINETY_NINE"}

class Room:
    def __init__(self, room_id: str, host_id: int, host_name: str, game: str = "UNO", target_score: int | None = None, rules: dict | None = None):
        self.room_id = room_id
        self.host_id = host_id
        self.host_name = host_name
        self.game = game
        self.target_score = target_score
        self.rules = dict(rules or {})
        self._round_transition_task = None
        now = datetime.now(timezone.utc).isoformat()
        self.table_created_at = now
        self.table_started_at = None
        self.round_started_at = None
        self.match_key = None
        self.player_joined_at: Dict[int, str] = {host_id: now}
        self._bot_task = None
        self._deal_batch_task = None
        self._mutation_lock = asyncio.Lock()
        self.players: List[int] = [host_id]
        self.player_names: Dict[int, str] = {host_id: host_name}
        self.scores: Dict[int, int] = {host_id: 0}
        self.banned_players: set[int] = set()
        self.voice_banned: set[int] = set()
        self.voice_muted: set[int] = set()
        self.voice_mode: str = "all"  # "all", "listen_only", "owner_only"
        self.co_host_id: Optional[int] = None
        self.spectators: List[int] = []
        self.pending_spectators: set[int] = set()
        self.status = "waiting"  # "waiting", "playing", "match_finished"
        self.uno_game: Optional[UnoGame] = None
        self.thief_game: Optional[ThiefHuntGame] = None
        self.farkle_game: Optional[FarkleGame] = None
        self.ninety_nine_game = None
        self.domino_game: Optional[DominoGame] = None
        self.american_domino_game: Optional[AmericanDominoGame] = None
        self.snakes_game: Optional[SnakesAndLaddersGame] = None
        self.scopa_game: Optional[ScopaGame] = None
        self.tennis_game: Optional[TennisGame] = None
        self._next_bot_id = -1
        self._bot_names = [
            "Alex", "Emma", "Lucas", "Sophia", "Oliver", "Maya", "Liam", "Ava", "Noah", "Isabella",
            "Ethan", "Mia", "James", "Charlotte", "Benjamin", "Amelia", "William", "Harper", "Elijah", "Evelyn",
            "Daniel", "Luna", "Henry", "Ella", "Alexander", "Scarlett", "Jackson", "Grace", "Sebastian", "Chloe",
            "Jack", "Lily", "Samuel", "Emily", "David", "Aria", "Matthew", "Zoe", "Joseph", "Penelope",
            "Carter", "Riley", "Owen", "Layla", "Wyatt", "Nora", "John", "Hazel", "Leo", "Aurora",
            "Gabriel", "Ellie", "Julian", "Stella", "Anthony", "Victoria", "Isaac", "Hannah", "Thomas", "Nathalie"
        ]
        self._bot_name_index = 0

    def add_player(self, user_id: int, name: str):
        if user_id in self.banned_players:
            raise ValueError("تم حظر هذا اللاعب من الطاولة.")
        if user_id not in self.players:
            self.players.append(user_id)
            self.player_names[user_id] = name
            self.player_joined_at[user_id] = datetime.now(timezone.utc).isoformat()
            if user_id not in self.scores:
                self.scores[user_id] = 0

    def add_spectator(self, user_id: int, name: str):
        if user_id in self.banned_players:
            raise ValueError("تم حظر هذا اللاعب من الطاولة.")
        if user_id not in self.spectators:
            self.spectators.append(user_id)
            self.player_names[user_id] = name
            self.player_joined_at[user_id] = datetime.now(timezone.utc).isoformat()

    def remove_player(self, user_id: int):
        if self.co_host_id == user_id:
            self.co_host_id = None
        if user_id in self.players:
            # Keep every live engine's private identity state aligned with the
            # roster before removing the public room membership.
            for engine in (self.uno_game, self.thief_game, self.farkle_game,
                           self.domino_game, self.american_domino_game,
                           self.snakes_game, self.scopa_game,
                           self.tennis_game, self.ninety_nine_game):
                remover = getattr(engine, "remove_player", None)
                if remover:
                    try:
                        remover(user_id)
                    except Exception:
                        logger.exception("Engine player cleanup failed for room %s", self.room_id)
            self.players.remove(user_id)
            self.player_names.pop(user_id, None)
            self.player_joined_at.pop(user_id, None)
            self.scores.pop(user_id, None)
            if self.game == "SCOPA" and self.scopa_game is not None and not self.scopa_game.active:
                self.cancel_background_tasks()
                self.scopa_game = None
                self.status = "waiting"
        if user_id in self.spectators:
            self.spectators.remove(user_id)
            self.player_names.pop(user_id, None)
            self.player_joined_at.pop(user_id, None)

    def add_bot(self) -> str:
        bot_id = self._next_bot_id
        self._next_bot_id -= 1
        # Give each bot a unique English name selected randomly from the pool
        used_names = {str(name) for name in self.player_names.values()}
        available_names = [name for name in self._bot_names if name not in used_names]
        if available_names:
            bot_name = random.choice(available_names)
        else:
            # Fallback only when the predefined pool is exhausted.
            bot_name = f"Bot {abs(bot_id)}"
        self.add_player(bot_id, bot_name)
        return bot_name

    def apply_pending_spectators(self) -> List[int]:
        moved = []
        for uid in list(self.pending_spectators):
            if uid in self.players:
                self.players.remove(uid)
                if uid not in self.spectators:
                    self.spectators.append(uid)
                moved.append(uid)
        self.pending_spectators.clear()
        return moved

    def remove_bot(self) -> Optional[str]:
        bot_ids = [uid for uid in self.players if uid < 0]
        if not bot_ids:
            return None
        last_bot_id = bot_ids[-1]
        bot_name = self.player_names.get(last_bot_id, "Bot")
        self.remove_player(last_bot_id)
        self.scores.pop(last_bot_id, None)
        return bot_name

    def cancel_background_tasks(self):
        """Cancel all room-owned asyncio tasks when the room is destroyed/stopped."""
        try:
            from server.app.main import cancel_room_disconnect_grace_timers
            cancel_room_disconnect_grace_timers(self.room_id)
        except Exception:
            pass
        try:
            current = asyncio.current_task()
        except RuntimeError:
            current = None
        for attr in ("_bot_task", "_round_transition_task", "_deal_batch_task"):
            task = getattr(self, attr, None)
            if task is not None and not task.done() and task is not current:
                task.cancel()
            setattr(self, attr, None)

    def cancel_bot_task(self):
        """Safely cancel any active bot runner task before spawning a new one."""
        try:
            current = asyncio.current_task()
        except RuntimeError:
            current = None
        task = getattr(self, "_bot_task", None)
        if task is not None and not task.done() and task is not current:
            task.cancel()
        self._bot_task = None

    def get_voice_participants(self) -> list[int]:
        try:
            from server.app.hub.ws_manager import ws_manager
            return ws_manager.get_voice_user_ids(self.room_id)
        except Exception:
            return []

    def public_dict(self, viewer_id: Optional[int] = None) -> dict:
        from server.app.games.registry import get_plugin
        plugin = get_plugin(self.game)
        game_label = plugin.display_name if plugin else self.game
        return {
            "id": self.room_id,
            "is_pending_spectator": viewer_id in self.pending_spectators if viewer_id is not None else False,
            "pending_spectators": list(self.pending_spectators),
            "room_id": self.room_id,
            "game": self.game,
            "status": self.status,
            "host_id": self.host_id,
            "host_name": self.host_name,
            "is_host": viewer_id == self.host_id,
            "co_host_id": self.co_host_id,
            "is_co_host": viewer_id == self.co_host_id if self.co_host_id is not None else False,
            "target_score": self.target_score,
            "rules": copy.deepcopy(self.rules),
            "game_label": game_label,
            "players": list(self.players),
            "player_names": [self.player_names[uid] for uid in self.players],
            "players_dict": {str(uid): self.player_names.get(uid, "لاعب") for uid in set(self.players) | set(self.spectators)},
            "scores": {str(k): v for k, v in self.scores.items()},
            "spectators": list(self.spectators),
            "voice_banned": [int(uid) for uid in self.voice_banned],
            "voice_muted": [int(uid) for uid in self.voice_muted],
            "voice_mode": getattr(self, "voice_mode", "all"),
            "voice_participants": self.get_voice_participants(),
            "role": "captain" if viewer_id == self.host_id else "co_host" if (self.co_host_id is not None and viewer_id == self.co_host_id) else "player" if viewer_id in self.players else "spectator",
            "table_created_at": self.table_created_at,
            "table_started_at": self.table_started_at,
            "round_started_at": self.round_started_at,
            "viewer_joined_at": self.player_joined_at.get(viewer_id) if viewer_id is not None else None,
        }

class RoomManager:
    MAX_ROOMS_GLOBAL = 500
    MAX_ROOMS_PER_HOST = 10

    def __init__(self):
        self.rooms: Dict[str, Room] = {}
        self._lock = threading.RLock()

    def build_room(self, host_id: int, host_name: str, game: str = "UNO") -> Room:
        game = str(game or "UNO").upper()
        if game not in SUPPORTED_GAMES:
            raise ValueError(f"اللعبة غير مدعومة: {game}")
        with self._lock:
            if len(self.rooms) >= self.MAX_ROOMS_GLOBAL:
                raise RuntimeError("وصل عدد الطاولات إلى الحد الأقصى.")
            if sum(1 for r in self.rooms.values() if r.host_id == host_id) >= self.MAX_ROOMS_PER_HOST:
                raise RuntimeError("وصلت إلى الحد الأقصى للطاولات المفتوحة.")
            room_id = uuid4().hex[:6].upper()
            while room_id in self.rooms:
                room_id = uuid4().hex[:6].upper()
            return Room(room_id, host_id, host_name, game, None)

    def register_room(self, room: Room) -> Room:
        with self._lock:
            if len(self.rooms) >= self.MAX_ROOMS_GLOBAL:
                raise RuntimeError("وصل عدد الطاولات إلى الحد الأقصى.")
            if sum(1 for r in self.rooms.values() if r.host_id == room.host_id) >= self.MAX_ROOMS_PER_HOST:
                raise RuntimeError("وصلت إلى الحد الأقصى للطاولات المفتوحة.")
            self.rooms[room.room_id] = room
            return room

    def create_room(self, host_id: int, host_name: str, game: str = "UNO") -> Room:
        room = self.build_room(host_id, host_name, game)
        return self.register_room(room)

    def get_room(self, room_id: str) -> Optional[Room]:
        with self._lock:
            return self.rooms.get(room_id)

    def user_in_any_room(self, user_id: int) -> bool:
        with self._lock:
            return any((int(user_id) in r.players or int(user_id) in r.spectators) for r in self.rooms.values())

    def add_player_exclusive(self, room: Room, user_id: int, name: str) -> bool:
        """Atomically enforce one-table-per-user within this server process."""
        with self._lock:
            if any(int(user_id) in r.players or int(user_id) in r.spectators for r in self.rooms.values()):
                return int(user_id) in room.players and int(user_id) not in room.spectators
            room.add_player(int(user_id), name)
            return True

    def add_spectator_exclusive(self, room: Room, user_id: int, name: str) -> bool:
        """Atomically enforce adding a spectator to a room."""
        with self._lock:
            if any((int(user_id) in r.players or int(user_id) in r.spectators)
                   and r.room_id != room.room_id for r in self.rooms.values()):
                return False
            if int(user_id) in room.players:
                return False
            room.add_spectator(int(user_id), name)
            return True

    def list_rooms(self, viewer_id: Optional[int] = None) -> List[dict]:
        # Backward-compatible synchronous snapshot for non-async callers.
        # API handlers use list_rooms_consistent() below so each Room snapshot
        # is serialized against its mutation lock.
        with self._lock:
            rooms = list(self.rooms.values())
        return [r.public_dict(viewer_id) for r in rooms]

    async def list_rooms_consistent(self, viewer_id: Optional[int] = None) -> List[dict]:
        with self._lock:
            rooms = list(self.rooms.values())
        snapshots = []
        for room in rooms:
            async with room._mutation_lock:
                snapshots.append(room.public_dict(viewer_id))
        return snapshots

    def delete_room(self, room_id: str):
        with self._lock:
            room = self.rooms.pop(room_id, None)
        if room is not None:
            room.cancel_background_tasks()


room_manager = RoomManager()

def _apply_game_score_adjustments(room: Room):
    """Apply one-time score changes produced by the authoritative game engine."""
    game = room.uno_game
    if not game:
        return
    adjustments = getattr(game, "pending_score_adjustments", None)
    if not adjustments:
        return
    for uid, points in list(adjustments.items()):
        room.scores[uid] = max(0, room.scores.get(uid, 0) + int(points))
    adjustments.clear()

