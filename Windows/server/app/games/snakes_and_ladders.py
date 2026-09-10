"""Snakes and Ladders multiplayer game engine with full 100-square board,
ladders, snakes, bounce-back, knockout mode, mystery tiles, and screen reader accessibility."""
import random
import time
from typing import List, Tuple, Dict, Optional, Any

STANDARD_LADDERS: Dict[int, int] = {
    4: 14,
    9: 31,
    20: 38,
    28: 84,
    40: 59,
    51: 67,
    63: 81,
    71: 91,
}

STANDARD_SNAKES: Dict[int, int] = {
    17: 7,
    54: 34,
    62: 19,
    64: 60,
    87: 24,
    93: 73,
    95: 75,
    98: 79,
}

MYSTERY_TILES: Dict[int, Dict[str, Any]] = {
    12: {"type": "bonus", "steps": 5, "name": "صندوق الهدية (+5 خطوات)"},
    45: {"type": "freeze", "name": "فخ الجليد (تجميد لدور واحد)"},
    78: {"type": "bonus", "steps": 4, "name": "صندوق الطاقة (+4 خطوات)"},
    88: {"type": "swap", "name": "صندوق السحر (تبديل الموقع مع المتصدر!)"},
}


class SnakesAndLaddersGame:
    def __init__(
        self,
        players: List[Tuple[int, str]],
        rules: Optional[Dict[str, Any]] = None,
    ):
        if len(players) < 2:
            raise ValueError("لعبة السلم والثعبان تتطلب لاعبين على الأقل.")
        self.players = players
        self.player_ids = [p[0] for p in players]
        self.player_names = {p[0]: p[1] for p in players}
        self.rules = rules or {"knockout": False, "mystery_tiles": False}
        self.knockout_enabled = bool(self.rules.get("knockout", False))
        self.mystery_enabled = bool(self.rules.get("mystery_tiles", False))

        self.positions: Dict[int, int] = {p[0]: 0 for p in players}
        self.turn_start_positions: Dict[int, int] = {p[0]: 0 for p in players}
        self.frozen_players: Dict[int, bool] = {p[0]: False for p in players}
        self.shielded_players: Dict[int, bool] = {p[0]: False for p in players}
        self.mystery_tiles: set[int] = set()
        self.coin_rewards: Dict[int, int] = {}  # coins earned via mystery boxes
        self.current_turn_index: int = 0
        self.active: bool = False
        self.winner_id: Optional[int] = None
        self.last_roll: int = 0
        self.last_roll_time: float = 0.0
        self.consecutive_sixes: int = 0
        self.extra_roll: bool = False

        self.event_id: int = 0
        self.last_action: str = ""
        self.roll_action: str = ""
        self.arrival_action: str = ""
        self.event_type: str = ""
        self.sound_cue: str = ""
        self.sound_cues: List[str] = []

    def _spawn_mystery_tiles(self, count: int = 6):
        """Spawn random mystery boxes on free board tiles."""
        forbidden = set(STANDARD_LADDERS.keys()) | set(STANDARD_LADDERS.values()) | set(STANDARD_SNAKES.keys()) | set(STANDARD_SNAKES.values()) | set(self.positions.values()) | {0, 100}
        candidates = [t for t in range(5, 95) if t not in forbidden]
        chosen = random.sample(candidates, min(count, len(candidates)))
        self.mystery_tiles = set(chosen)

    def _spawn_single_mystery_tile(self):
        """Spawn a new mystery tile when an existing one is opened."""
        forbidden = set(STANDARD_LADDERS.keys()) | set(STANDARD_LADDERS.values()) | set(STANDARD_SNAKES.keys()) | set(STANDARD_SNAKES.values()) | set(self.positions.values()) | self.mystery_tiles | {0, 100}
        candidates = [t for t in range(5, 95) if t not in forbidden]
        if candidates:
            self.mystery_tiles.add(random.choice(candidates))

    def start_match(self):
        self.positions = {p[0]: 0 for p in self.players}
        self.turn_start_positions = {p[0]: 0 for p in self.players}
        self.frozen_players = {p[0]: False for p in self.players}
        self.shielded_players = {p[0]: False for p in self.players}
        self.coin_rewards = {}  # reset mystery-box coin rewards for this match
        if self.mystery_enabled:
            self._spawn_mystery_tiles(6)
        else:
            self.mystery_tiles = set()

        self.current_turn_index = 0
        self.active = True
        self.winner_id = None
        self.last_roll = 0
        self.last_roll_time = 0.0
        self.consecutive_sixes = 0
        self.extra_roll = False

        starter_name = self.current_player_name()
        self.round_number = 1
        self.event_id += 1
        self.event_type = "GAME_STARTED"
        self.sound_cue = ""
        self.last_action = f"اللعبة بدأت. دور {starter_name} لرمي النرد."
        self.roll_action = ""
        self.arrival_action = self.last_action

    def current_player_id(self) -> int:
        return self.player_ids[self.current_turn_index]

    def current_player_name(self) -> str:
        return self.player_names[self.current_player_id()]

    def _roll_dice_value(self, current_pos: int) -> int:
        """Roll a fair six-sided die.

        ``current_pos`` remains in the signature for compatibility with existing
        callers and tests; the outcome is intentionally independent of position
        and previous rolls.
        """
        return random.randint(1, 6)

    def check_and_skip_frozen(self) -> bool:
        """If current player is frozen, automatically unfreeze them and advance turn."""
        if not self.active:
            return False
        curr_id = self.current_player_id()
        if not self.frozen_players.get(curr_id, False):
            return False
        self.frozen_players[curr_id] = False
        player_name = self.player_names.get(curr_id, "لاعب")
        self.event_id += 1
        self.event_type = "PLAYER_FROZEN"
        self.sound_cues = ["FREEZE_TRAP"]
        self.sound_cue = "FREEZE_TRAP"
        self.last_action = f"{player_name} مجمد في قالب الجليد ولا يمكنه اللعب هذا الدور! تم فك التجميد وسيلعب الدور القادم."
        self.roll_action = ""
        self.arrival_action = self.last_action
        self.last_roll = 0
        self._advance_turn()
        return True

    def roll_dice(self, user_id: int) -> Dict[str, Any]:
        user_id = int(user_id)
        if not self.active:
            raise ValueError("المباراة غير نشطة.")
        if user_id != self.current_player_id():
            raise ValueError("ليس دورك الآن.")

        now = time.time()
        last_time = getattr(self, f"_last_roll_time_{user_id}", 0.0)
        global_bypass = getattr(self, "last_roll_time", None) == 0.0
        if user_id > 0 and not getattr(self, "extra_roll", False) and last_time > 0 and not global_bypass:
            steps_delay = 0.28 + (self.last_roll * 0.32) + 0.4
            if now - last_time < steps_delay:
                raise ValueError("انتظر حتى تنتهي خطوات التحرك.")
        setattr(self, f"_last_roll_time_{user_id}", now)
        self.last_roll_time = now

        player_name = self.player_names[user_id]

        # Check if player is frozen from mystery trap
        if self.frozen_players.get(user_id, False):
            self.check_and_skip_frozen()
            return self.get_state(user_id)

        old_pos = self.positions[user_id]
        if self.consecutive_sixes == 0:
            self.turn_start_positions[user_id] = old_pos

        self.extra_roll = False
        roll = self._roll_dice_value(old_pos)
        self.last_roll = roll
        target_pos = old_pos + roll

        roll_text = f"رمى {player_name} النرد وحصل على {roll}."
        self.roll_action = roll_text
        self.sound_cues = []

        # Check 3 Consecutive Sixes Rule: cancel all progress this turn and return to starting tile
        if roll == 6:
            self.consecutive_sixes += 1
            if self.consecutive_sixes >= 3:
                reset_pos = self.turn_start_positions.get(user_id, 0)
                self.positions[user_id] = reset_pos
                self.consecutive_sixes = 0
                self.extra_roll = False
                self.sound_cues = ["INVALID_ACTION"]
                self.sound_cue = "INVALID_ACTION"
                self.arrival_action = f"حصل {player_name} على 6 ثلاث مرات متتالية! تم إلغاء حركته بالكامل وأُرجع إلى المربع {reset_pos} وانتهى دوره."
                self.last_action = f"{roll_text} {self.arrival_action}"
                self._advance_turn()
                self.event_id += 1
                self.event_type = "CANNOT_MOVE"
                return self.get_state(user_id)
            else:
                self.extra_roll = True
        else:
            self.consecutive_sixes = 0

        # Exact finish logic (No bounce-back: must roll exact number to reach 100)
        if target_pos > 100:
            target_pos = old_pos
            self.positions[user_id] = target_pos
            self.sound_cue = "INVALID_ACTION"
            self.sound_cues = ["INVALID_ACTION"]
            self.arrival_action = "لا يمكن التحرك وتجاوز المربع 100."
            self.last_action = f"{roll_text} {self.arrival_action}"

            # An overshoot is an invalid move, even when the roll is 6.
            self.consecutive_sixes = 0
            self.extra_roll = False
            self._advance_turn()

            self.event_id += 1
            self.event_type = "CANNOT_MOVE"
            return self.get_state(user_id)

        arrival_desc = f"وصل {player_name} إلى المربع {target_pos}."
        self.sound_cue = "DICE_ROLL"

        # 1. Check ladders
        if target_pos in STANDARD_LADDERS:
            ladder_top = STANDARD_LADDERS[target_pos]
            arrival_desc = f"وصل {player_name} إلى المربع {target_pos} وصعد السلم إلى {ladder_top}!"
            target_pos = ladder_top
            self.sound_cues.append("LADDER_CLIMB")
            self.sound_cue = "LADDER_CLIMB"

        # 2. Check snakes (with Snake Shield protection)
        elif target_pos in STANDARD_SNAKES:
            if self.shielded_players.get(user_id, False):
                self.shielded_players[user_id] = False
                arrival_desc = f"وصل {player_name} إلى المربع {target_pos} وكاد يلدغه الثعبان، لكن درع الحماية حماه من السقوط!"
                self.sound_cues.append("BONUS_ROLL")
                self.sound_cue = "BONUS_ROLL"
            else:
                snake_tail = STANDARD_SNAKES[target_pos]
                arrival_desc = f"وصل {player_name} إلى المربع {target_pos} ولدغه الثعبان إلى {snake_tail}!"
                target_pos = snake_tail
                self.sound_cues.append("SNAKE_BITE")
                self.sound_cue = "SNAKE_BITE"

        # 3. Check dynamic random mystery tiles
        elif self.mystery_enabled and target_pos in self.mystery_tiles:
            self.mystery_tiles.remove(target_pos)
            self._spawn_single_mystery_tile()
            self.sound_cues.append("MYSTERY_BOX")
            self.sound_cue = "MYSTERY_BOX"
            m_type = random.choice(["freeze", "shield", "boost", "swap", "bonus", "wind", "coins"])
            
            if m_type == "freeze":
                self.frozen_players[user_id] = True
                self.consecutive_sixes = 0
                self.extra_roll = False
                self.sound_cues.append("FREEZE_TRAP")
                self.sound_cue = "FREEZE_TRAP"
                arrival_desc = f"وصل {player_name} إلى المربع {target_pos} وفتح صندوق مفاجآت ووقع في فخ الجليد! سيتجمد لدور كامل."
            elif m_type == "shield":
                self.shielded_players[user_id] = True
                arrival_desc = f"وصل {player_name} إلى المربع {target_pos} وفتح صندوق مفاجآت وحصل على درع الحماية من الثعابين!"
            elif m_type == "boost":
                boost = random.randint(3, 7)
                new_boosted_pos = min(100, target_pos + boost)
                arrival_desc = f"وصل {player_name} إلى المربع {target_pos} وفتح صندوق مفاجآت وحصل على دفعة صاروخية (+{boost}) إلى {new_boosted_pos}!"
                target_pos = new_boosted_pos
            elif m_type == "swap":
                leader_id = max(self.positions, key=lambda uid: self.positions[uid])
                if leader_id != user_id and self.positions[leader_id] > target_pos:
                    leader_pos = self.positions[leader_id]
                    self.positions[leader_id] = target_pos
                    leader_name = self.player_names[leader_id]
                    arrival_desc = f"وصل {player_name} إلى المربع {target_pos} وفتح صندوق مفاجآت وتبادل المواقع سحرياً مع {leader_name} إلى {leader_pos}!"
                    target_pos = leader_pos
                else:
                    prev_pos = target_pos
                    target_pos = min(100, target_pos + 4)
                    arrival_desc = f"وصل {player_name} إلى المربع {prev_pos} وفتح صندوق مفاجآت وتقدم إلى {target_pos}!"
            elif m_type == "bonus":
                self.extra_roll = True
                self.sound_cues.append("BONUS_ROLL")
                self.sound_cue = "BONUS_ROLL"
                arrival_desc = f"وصل {player_name} إلى المربع {target_pos} وفتح صندوق مفاجآت وحصل على النرد الذهبي! ارمِ النرد مرة أخرى!"
            elif m_type == "wind":
                wind = random.randint(2, 4)
                target_pos = max(1, target_pos - wind)
                arrival_desc = f"وصل {player_name} إلى المربع {target_pos + wind} وفتح صندوق مفاجآت وهبت عاصفة رياح أرجعته إلى {target_pos}!"
            elif m_type == "coins":
                coins_earned = random.randint(5, 25)
                if not hasattr(self, "coin_rewards"):
                    self.coin_rewards = {}
                self.coin_rewards[user_id] = self.coin_rewards.get(user_id, 0) + coins_earned
                arrival_desc = f"وصل {player_name} إلى المربع {target_pos} وفتح صندوق مفاجآت وحصل على {coins_earned} عملة!"

            # Secondary tile mechanics (ladders/snakes after mystery moves)
            if m_type in ("boost", "swap", "wind") and 0 < target_pos < 100:
                if target_pos in STANDARD_LADDERS:
                    ladder_top = STANDARD_LADDERS[target_pos]
                    arrival_desc += f" ووجد سلماً صعد به إلى {ladder_top}!"
                    target_pos = ladder_top
                    self.sound_cues.append("LADDER_CLIMB")
                    self.sound_cue = "LADDER_CLIMB"
                elif target_pos in STANDARD_SNAKES:
                    if self.shielded_players.get(user_id, False):
                        self.shielded_players[user_id] = False
                        arrival_desc += " وكاد يلدغه ثعبان، لكن درع الحماية حماه!"
                        self.sound_cues.append("BONUS_ROLL")
                    else:
                        snake_tail = STANDARD_SNAKES[target_pos]
                        arrival_desc += f" ولدغه ثعبان إلى {snake_tail}!"
                        target_pos = snake_tail
                        self.sound_cues.append("SNAKE_BITE")
                        self.sound_cue = "SNAKE_BITE"

        # 4. Check Knockout / Bumping
        if self.knockout_enabled and target_pos < 100 and target_pos > 0:
            for other_uid in list(self.player_ids):
                other_uid_int = int(other_uid)
                if other_uid_int != user_id and self.positions.get(other_uid_int, 0) == target_pos:
                    new_other_pos = max(0, target_pos - 10)
                    steps_back = target_pos - new_other_pos
                    self.positions[other_uid_int] = new_other_pos
                    other_name = self.player_names.get(other_uid_int, "لاعب")
                    if steps_back == 1:
                        steps_phrase = "خطوة واحدة"
                    elif steps_back == 2:
                        steps_phrase = "خطوتين"
                    else:
                        steps_phrase = f"{steps_back} خطوات"
                    arrival_desc += f" واصطدم بـ {other_name} وأرجعه {steps_phrase} للخلف إلى المربع {new_other_pos}!"
                    self.sound_cues.append("PLAYER_BUMP")
                    self.sound_cue = "PLAYER_BUMP"

        target_pos = min(100, target_pos)
        self.positions[user_id] = target_pos
        self.arrival_action = arrival_desc
        self.last_action = f"{roll_text} {arrival_desc}"

        if target_pos >= 100:
            self.positions[user_id] = 100
            self.active = False
            self.winner_id = user_id
            self.event_id += 1
            self.event_type = "MATCH_FINISHED"
            self.sound_cues = ["MATCH_WIN"]
            self.sound_cue = "MATCH_WIN"
            scores_summary = "، ".join(f"{self.player_names.get(uid, 'لاعب')}: {self.positions.get(uid, 0)}" for uid in self.player_ids)
            self.arrival_action = f"نهاية المباراة! الفائز: {player_name}. النتائج: {scores_summary}"
            self.last_action = self.arrival_action
            return self.get_state(user_id)

        # If extra roll granted (from Golden Dice or rolling a 6) and player is not frozen
        is_frozen = self.frozen_players.get(user_id, False)
        if self.extra_roll and not is_frozen:
            self.event_id += 1
            self.event_type = "BONUS_ROLL"
            if "BONUS_ROLL" not in self.sound_cues:
                self.sound_cues.append("BONUS_ROLL")
            self.sound_cue = "BONUS_ROLL"
            if not self.arrival_action.endswith("ارمِ النرد مرة أخرى!"):
                self.arrival_action += " ارمِ النرد مرة أخرى!"
            self.last_action = f"{roll_text} {self.arrival_action}"
            return self.get_state(user_id)

        # Advance Turn
        self.consecutive_sixes = 0
        self.extra_roll = False
        self._advance_turn()

        self.event_id += 1
        self.event_type = "DICE_ROLLED"
        if not self.sound_cues:
            self.sound_cues = ["DICE_ROLL"]
            self.sound_cue = "DICE_ROLL"
        return self.get_state(user_id)

    def _advance_turn(self):
        self.current_turn_index = (self.current_turn_index + 1) % len(self.player_ids)
        self.consecutive_sixes = 0
        self.extra_roll = False

    def get_radar_info(self, user_id: int) -> Dict[str, Any]:
        """Scan ahead and behind for nearest ladders, snakes, and mystery boxes."""
        pos = self.positions.get(user_id, 0)
        ladders_ahead = [(k, v, k - pos) for k, v in STANDARD_LADDERS.items() if k > pos]
        snakes_ahead = [(k, v, k - pos) for k, v in STANDARD_SNAKES.items() if k > pos]
        nearest_ladder = min(ladders_ahead, key=lambda x: x[2]) if ladders_ahead else None
        nearest_snake = min(snakes_ahead, key=lambda x: x[2]) if snakes_ahead else None

        return {
            "position": pos,
            "nearest_ladder": nearest_ladder,  # (base, top, distance)
            "nearest_snake": nearest_snake,    # (head, tail, distance)
            "distance_to_finish": 100 - pos,
        }

    def get_state(self, viewer_id: Optional[int] = None) -> Dict[str, Any]:
        viewer_id = viewer_id or self.current_player_id()
        radar = self.get_radar_info(viewer_id)

        players_list = []
        for uid in self.player_ids:
            players_list.append({
                "user_id": uid,
                "name": self.player_names[uid],
                "position": self.positions.get(uid, 0),
                "is_frozen": self.frozen_players.get(uid, False),
                "has_shield": self.shielded_players.get(uid, False),
                "distance_to_finish": 100 - self.positions.get(uid, 0),
            })

        # Sort players by position descending (leaders first)
        players_list.sort(key=lambda p: p["position"], reverse=True)

        return {
            "active": self.active,
            "rules": self.rules,
            "players": players_list,
            "positions": {str(k): v for k, v in self.positions.items()},
            "player_names": {str(k): v for k, v in self.player_names.items()},
            "current_player_id": self.current_player_id(),
            "current_player_name": self.current_player_name(),
            "is_my_turn": viewer_id == self.current_player_id(),
            "last_roll": self.last_roll,
            "extra_roll": self.extra_roll,
            "winner_id": self.winner_id,
            "radar": radar,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "sound_cue": self.sound_cue,
            "sound_cues": list(getattr(self, "sound_cues", [self.sound_cue])),
            "last_action": self.last_action,
            "roll_action": getattr(self, "roll_action", ""),
            "arrival_action": getattr(self, "arrival_action", ""),
        }
