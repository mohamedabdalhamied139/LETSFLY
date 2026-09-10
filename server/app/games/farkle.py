"""Authoritative Farkle game engine for Let's Fly.

Rules are based strictly on the supplied Farkle rules:
- six dice
- scoring combinations are evaluated from a single roll only
- turn points are lost on a farkle
- hot dice resets the player to six dice
- default minimum bank is 30; first bank from zero requires 50
- default match target is 1500
"""
from __future__ import annotations
import random
from itertools import combinations
from typing import Optional


COMBO_NAMES = {
    "single_5": "خمسة واحدة",
    "single_1": "واحد واحد",
    "three_kind": "ثلاثة من نفس الرقم",
    "three_ones": "ثلاثة واحد",
    "four_kind": "أربعة من نفس الرقم",
    "five_kind": "خمسة من نفس الرقم",
    "six_kind": "ستة من نفس الرقم",
    "small_straight": "تتابع صغير",
    "large_straight": "تتابع كبير",
    "three_pairs": "ثلاثة أزواج",
    "full_house": "منزل كامل",
    "two_triplets": "مجموعتان من ثلاثة",
}


class FarkleGame:
    def __init__(self, players, target_score: int = 1500, rules: dict | None = None):
        self.players = list(players)
        self.target_score = int(target_score or 1500)
        rules = dict(rules or {})
        self.min_bank = int(rules.get("min_bank", 30))
        self.first_bank_min = int(rules.get("first_bank_min", 50))
        self.active = False
        self.winner_id = None
        self.current_index = 0
        self.dice: list[int] = []
        self.used_indices: set[int] = set()
        self.selected_indices: list[int] = []
        self.turn_score = 0
        self.scores = {p[0]: 0 for p in self.players}
        self.last_roll: list[int] = []
        self.event_id = 0
        self.event_type = ""
        self.last_action = ""
        self._rolled = False

    @property
    def current_player(self):
        return self.players[self.current_index] if self.players else None

    def _set_event(self, text: str, event_type: str):
        self.event_id += 1
        self.last_action = text
        self.event_type = event_type

    def start(self):
        if len(self.players) < 2:
            raise ValueError("تحتاج لعبة فاركل إلى لاعبين اثنين على الأقل.")
        self.active = True
        self.winner_id = None
        self.current_index = 0
        self.dice = []
        self.used_indices = set()
        self.selected_indices = []
        self.turn_score = 0
        self.scores = {p[0]: 0 for p in self.players}
        self.last_roll = []
        self._rolled = False
        self._set_event("بدأت اللعبة.", "GAME_STARTED")

    def _score_combo(self, vals: tuple[int, ...]) -> tuple[str, int] | None:
        n = len(vals)
        counts = {x: vals.count(x) for x in set(vals)}
        if n == 1:
            if vals[0] == 1:
                return "single_1", 10
            if vals[0] == 5:
                return "single_5", 5
            return None

        if n == 3:
            x = vals[0]
            if len(counts) == 1:
                if x == 1:
                    return "three_ones", 75
                if 2 <= x <= 6:
                    return "three_kind", x * 10
            return None

        if n == 4 and len(counts) == 1:
            x = vals[0]
            return "four_kind", 110 + (x - 1) * 10

        if n == 5 and len(counts) == 1:
            x = vals[0]
            return "five_kind", 160 + (x - 1) * 10

        if n == 6 and len(counts) == 1:
            x = vals[0]
            return "six_kind", 210 + (x - 1) * 10

        if n == 6:
            if sorted(vals) == [1, 2, 3, 4, 5, 6]:
                return "large_straight", 200
            if len(counts) == 3 and all(c == 2 for c in counts.values()):
                return "three_pairs", 150
            if len(counts) == 2 and set(counts.values()) == {2, 4}:
                return "full_house", 250
            if len(counts) == 2 and set(counts.values()) == {3, 3}:
                return "two_triplets", 250

        if n == 5:
            s = sorted(vals)
            if s in ([1, 2, 3, 4, 5], [2, 3, 4, 5, 6]):
                return "small_straight", 100

        return None

    def _combo_label_ar(self, combo_type: str, vals: tuple[int, ...], points: int) -> str:
        pts_word = "نقاط" if 3 <= points <= 10 else "نقطة"
        if combo_type == "single_1":
            return f"1 فردي مقابل {points} {pts_word}"
        if combo_type == "single_5":
            return f"5 فردي مقابل {points} {pts_word}"
        if combo_type == "three_ones":
            return f"ثلاثة 1 مقابل {points} {pts_word}"
        if combo_type == "three_kind":
            val = vals[0] if vals else 0
            return f"ثلاثة {val} مقابل {points} {pts_word}"
        if combo_type == "four_kind":
            val = vals[0] if vals else 0
            return f"أربعة {val} مقابل {points} {pts_word}"
        if combo_type == "five_kind":
            val = vals[0] if vals else 0
            return f"خمسة {val} مقابل {points} {pts_word}"
        if combo_type == "six_kind":
            val = vals[0] if vals else 0
            return f"ستة {val} مقابل {points} {pts_word}"
        if combo_type == "small_straight":
            return f"تتابع صغير مقابل {points} {pts_word}"
        if combo_type == "large_straight":
            return f"تتابع كبير مقابل {points} {pts_word}"
        if combo_type == "three_pairs":
            return f"ثلاثة أزواج مقابل {points} {pts_word}"
        if combo_type == "full_house":
            return f"منزل كامل مقابل {points} {pts_word}"
        if combo_type == "two_triplets":
            return f"مجموعتان من ثلاثة مقابل {points} {pts_word}"
        return f"{COMBO_NAMES.get(combo_type, combo_type)} مقابل {points} {pts_word}"

    def _combo_label_en(self, combo_type: str, vals: tuple[int, ...], points: int) -> str:
        pts_word = "point" if points == 1 else "points"
        if combo_type == "single_1":
            return f"Single 1 for {points} {pts_word}"
        if combo_type == "single_5":
            return f"Single 5 for {points} {pts_word}"
        if combo_type == "three_ones":
            return f"Three 1 for {points} {pts_word}"
        if combo_type == "three_kind":
            val = vals[0] if vals else 0
            return f"Three {val} for {points} {pts_word}"
        if combo_type == "four_kind":
            val = vals[0] if vals else 0
            return f"Four {val} for {points} {pts_word}"
        if combo_type == "five_kind":
            val = vals[0] if vals else 0
            return f"Five {val} for {points} {pts_word}"
        if combo_type == "six_kind":
            val = vals[0] if vals else 0
            return f"Six {val} for {points} {pts_word}"
        if combo_type == "small_straight":
            return f"Small straight for {points} {pts_word}"
        if combo_type == "large_straight":
            return f"Large straight for {points} {pts_word}"
        if combo_type == "three_pairs":
            return f"Three pairs for {points} {pts_word}"
        if combo_type == "full_house":
            return f"Full house for {points} {pts_word}"
        if combo_type == "two_triplets":
            return f"Two triplets for {points} {pts_word}"
        return f"{combo_type} for {points} {pts_word}"

    def _combo_label(self, combo_type: str, vals: tuple[int, ...], points: int) -> str:
        return self._combo_label_ar(combo_type, vals, points)

    def get_available_combinations(self) -> list[dict]:
        """Return distinct legal atomic scoring combinations available from the current un-scored dice."""
        if not self.dice or not self._rolled:
            return []
        n = len(self.dice)
        combos = []
        seen_keys = set()

        def add_combo(ctype: str, indices: list[int], vals: tuple[int, ...], pts: int):
            key = (ctype, pts, tuple(sorted(vals)))
            if key in seen_keys:
                return
            seen_keys.add(key)
            combos.append({
                "type": ctype,
                "points": pts,
                "label": self._combo_label_ar(ctype, vals, pts),
                "label_en": self._combo_label_en(ctype, vals, pts),
                "indices": indices,
                "values": list(vals),
            })

        # Check multi-dice atomic combinations from largest to smallest
        # 1. Six dice combinations
        if n == 6:
            full_indices = list(range(6))
            full_vals = tuple(self.dice)
            res = self._score_combo(full_vals)
            if res:
                add_combo(res[0], full_indices, full_vals, res[1])

        # 2. Five dice combinations
        if n >= 5:
            for c_idx in combinations(range(n), 5):
                c_vals = tuple(self.dice[i] for i in c_idx)
                res = self._score_combo(c_vals)
                if res and res[0] in ("five_kind", "small_straight"):
                    add_combo(res[0], list(c_idx), c_vals, res[1])

        # 3. Four dice combinations
        if n >= 4:
            for c_idx in combinations(range(n), 4):
                c_vals = tuple(self.dice[i] for i in c_idx)
                res = self._score_combo(c_vals)
                if res and res[0] == "four_kind":
                    add_combo(res[0], list(c_idx), c_vals, res[1])

        # 4. Three dice combinations
        if n >= 3:
            for c_idx in combinations(range(n), 3):
                c_vals = tuple(self.dice[i] for i in c_idx)
                res = self._score_combo(c_vals)
                if res and res[0] in ("three_ones", "three_kind"):
                    add_combo(res[0], list(c_idx), c_vals, res[1])

        # 5. Single scoring dice (1s and 5s)
        for i, val in enumerate(self.dice):
            if val == 1:
                add_combo("single_1", [i], (1,), 10)
                break
        for i, val in enumerate(self.dice):
            if val == 5:
                add_combo("single_5", [i], (5,), 5)
                break

        combos.sort(key=lambda c: (c["points"], len(c["indices"])), reverse=True)
        return combos

    def _best_partition(self, indices: tuple[int, ...]) -> tuple[int, list[tuple[str, tuple[int, ...]]]] | None:
        """Partition selected dice into one or more legal combinations, maximizing points."""
        if not indices:
            return (0, [])
        best = None
        idx_set = tuple(indices)
        first = idx_set[0]
        for size in range(1, len(idx_set) + 1):
            for combo_indices in combinations(idx_set, size):
                if first not in combo_indices:
                    continue
                vals = tuple(self.dice[i] for i in combo_indices)
                combo = self._score_combo(vals)
                if not combo:
                    continue
                remaining = tuple(i for i in idx_set if i not in combo_indices)
                tail = self._best_partition(remaining)
                if tail is None:
                    continue
                score = combo[1] + tail[0]
                candidate = (score, [(combo[0], combo_indices)] + tail[1])
                if best is None or score > best[0]:
                    best = candidate
        return best

    def _all_roll_has_score(self) -> bool:
        """Return True when the roll contains at least one legal scoring combo."""
        remaining = tuple(i for i in range(len(self.dice)) if i not in self.used_indices)
        if not remaining:
            return False
        for size in range(1, len(remaining) + 1):
            for combo_indices in combinations(remaining, size):
                if self._score_combo(tuple(self.dice[i] for i in combo_indices)):
                    return True
        return False

    def _advance_turn(self):
        self.current_index = (self.current_index + 1) % len(self.players)
        self.dice = []
        self.used_indices = set()
        self.selected_indices = []
        self.turn_score = 0
        self.last_roll = []
        self._rolled = False

    def action(self, user_id: int, action: str, value=None):
        if not self.active:
            raise ValueError("اللعبة غير نشطة.")
        if self.current_player is None or int(user_id) != int(self.current_player[0]):
            raise ValueError("ليس دورك الآن.")

        action = str(action or "").lower()
        if action == "roll":
            if self.selected_indices:
                raise ValueError("ثبّت المجموعة المختارة أولًا.")
            if self._rolled and self.event_type == "DICE_ROLLED":
                raise ValueError("يجب اختيار وتثبيت مجموعة رابحة أولًا قبل الرمي مجددًا.")
            available_count = len(self.dice) if self.dice else 6
            if available_count <= 0:
                self.used_indices = set()
                available_count = 6
            self.dice = sorted([random.randint(1, 6) for _ in range(available_count)])
            self.used_indices = set()
            self.last_roll = list(self.dice)
            self._rolled = True
            if not self._all_roll_has_score():
                lost = self.turn_score
                name = self.current_player[1]
                self._set_event(
                    f"فاركل! {name} خسر {lost} نقطة في هذا الدور.",
                    "FARKLE",
                )
                self._advance_turn()
            else:
                self._set_event(
                    f"{self.current_player[1]} رمى النرد: " + " ".join(map(str, sorted(self.dice))),
                    "DICE_ROLLED",
                )
            return

        if action == "score":
            if not self._rolled:
                raise ValueError("ارمِ النرد أولًا.")
            raw = value if isinstance(value, list) else []
            try:
                selected = sorted({int(x) for x in raw})
            except Exception:
                raise ValueError("اختيار النرد غير صالح.")
            available = [i for i in range(len(self.dice)) if i not in self.used_indices]
            if not selected or any(i not in available for i in selected):
                raise ValueError("اختر نردًا متاحًا لتكوين مجموعة رابحة.")
            result = self._best_partition(tuple(selected))
            if result is None:
                raise ValueError("الاختيار لا يمثل مجموعة رابحة كاملة.")
            points, combos = result
            scored_values = tuple(self.dice[i] for i in selected)
            self.turn_score += points
            remaining_dice = [v for i, v in enumerate(self.dice) if i not in selected]
            self.dice = remaining_dice
            self.used_indices = set()
            self.selected_indices = []

            # Determine combo name for announcement
            combo_type = None
            direct_combo = self._score_combo(scored_values)
            if direct_combo:
                combo_type = direct_combo[0]
            elif combos and len(combos) == 1:
                combo_type = combos[0][0]

            if combo_type:
                combo_name_ar = self._combo_label_ar(combo_type, scored_values, points)
            else:
                pts_word = "نقاط" if 3 <= points <= 10 else "نقطة"
                combo_name_ar = f"{points} {pts_word}"

            name = self.current_player[1]
            if not self.dice:
                self._rolled = False
                self._set_event(
                    f"{name} أخذ {combo_name_ar}، نرد ساخن!",
                    "HOT_DICE",
                )
            else:
                self._set_event(
                    f"{name} أخذ {combo_name_ar}.",
                    "COMBINATION_SCORED",
                )
            return

        if action == "bank":
            if self.turn_score < self.min_bank:
                raise ValueError(f"لا يمكنك تثبيت النقاط قبل الوصول إلى {self.min_bank} نقطة في الدور.")
            uid = self.current_player[0]
            if self.scores[uid] == 0 and self.turn_score < self.first_bank_min:
                raise ValueError(f"أول تثبيت يجب أن يصل إلى {self.first_bank_min} نقطة على الأقل.")
            banked = self.turn_score
            self.scores[uid] += banked
            name = self.current_player[1]
            if self.scores[uid] >= self.target_score:
                self.winner_id = uid
                self.active = False
                scores_summary = "، ".join(f"{p[1]}: {self.scores.get(p[0], 0)}" for p in self.players)
                self._set_event(
                    f"نهاية المباراة! الفائز: {name}. النتائج: {scores_summary}",
                    "MATCH_FINISHED",
                )
                return
            else:
                self._set_event(
                    f"{name} ثبّت {banked} نقطة. رصيده الآن {self.scores[uid]}.",
                    "TURN_BANKED",
                )
                self._advance_turn()
                return

        raise ValueError("أمر فاركل غير معروف.")

    def state_for(self, viewer_id: int) -> dict:
        available = [i for i in range(len(self.dice)) if i not in self.used_indices]
        current = self.current_player
        combos = self.get_available_combinations() if self.active and self._rolled and self.dice else []
        return {
            "active": self.active,
            "winner_id": self.winner_id,
            "target_score": self.target_score,
            "min_bank": self.min_bank,
            "first_bank_min": self.first_bank_min,
            "current_player_id": current[0] if current else None,
            "current_player_name": current[1] if current else "",
            "scores": {str(k): v for k, v in self.scores.items()},
            "player_names": {str(k): n for k, n in self.players},
            "dice": list(self.dice),
            "available_indices": available,
            "available_combinations": combos,
            "turn_score": self.turn_score,
            "last_roll": list(self.last_roll),
            "event_id": self.event_id,
            "event_type": self.event_type,
            "last_action": self.last_action,
            "is_my_turn": bool(current and int(current[0]) == int(viewer_id)),
            "can_roll": bool((not self._rolled) or (self._rolled and bool(self.dice) and not self.selected_indices and self.event_type in ("COMBINATION_SCORED", "HOT_DICE"))),
            "must_score_before_roll": bool(self._rolled and len(self.used_indices) == 0 and len(self.dice) > 0 and self.event_type == "DICE_ROLLED"),
        }

    def stop(self):
        self.active = False
        self._set_event("توقفت اللعبة.", "GAME_STOPPED")
