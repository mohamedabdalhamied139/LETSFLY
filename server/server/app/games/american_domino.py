"""American Dominoes (All Fives / Muggins) Game Engine."""
import random
from typing import List, Tuple, Dict, Optional, Any

def tile_display_name(tile: Tuple[int, int]) -> str:
    """Format a domino tile with slash numbers (e.g., 6/6, 6/4, 5/0, 0/0)."""
    a, b = tile
    return f"{max(a, b)}/{min(a, b)}"


def create_double_six_deck() -> List[Tuple[int, int]]:
    """Generate all 28 tiles in standard double-six dominoes."""
    tiles = []
    for a in range(7):
        for b in range(a, 7):
            tiles.append((a, b))
    return tiles


class AmericanDominoGame:
    """American Dominoes / All Fives: players score multiples of 5 during play and upon domino."""

    def __init__(
        self,
        players: List[Tuple[int, str]],
        target_score: int = 150,
        rules: Optional[Dict[str, Any]] = None,
    ):
        if len(players) < 2:
            raise ValueError("لعبة الدومينو تتطلب لاعبين على الأقل.")
        if len(players) > 5:
            raise ValueError("لعبة الدومينو الأمريكاني تدعم من لاعبين إلى خمسة لاعبين فقط.")
        self.players = players
        self.player_ids = [p[0] for p in players]
        self.player_names = {p[0]: p[1] for p in players}
        self.target_score = target_score
        self.rules = rules or {"hand_size": 7, "scoring_mode": "standard"}
        self.hand_size = int(self.rules.get("hand_size", 7))
        self.scoring_mode = str(self.rules.get("scoring_mode", "standard"))
        if len(self.players) >= 3 and self.hand_size > 5:
            self.hand_size = 5

        self.scores: Dict[int, int] = {p[0]: 0 for p in players}
        self.hands: Dict[int, List[Tuple[int, int]]] = {p[0]: [] for p in players}
        self.boneyard: List[Tuple[int, int]] = []
        self.board: List[Tuple[int, int]] = []
        self.left_end: Optional[int] = None
        self.right_end: Optional[int] = None
        self.current_turn_index: int = 0
        self.active: bool = False
        self.round_number: int = 0
        self.consecutive_passes: int = 0
        self.winner_id: Optional[int] = None
        self.round_winner_id: Optional[int] = None
        self.round_points_won: int = 0
        self.event_id: int = 0
        self.last_action: str = ""
        self.event_type: str = ""
        self.sound_cue: str = ""

    def start_match(self):
        self.scores = {p[0]: 0 for p in self.players}
        self.round_number = 0
        self.winner_id = None
        self.start_new_round()

    def _is_hand_unbalanced(self, hand: List[Tuple[int, int]]) -> bool:
        """Return True if a hand holds 5+ of the same number or 5+ doubles."""
        pip_counts = {i: 0 for i in range(7)}
        double_count = 0
        for a, b in hand:
            pip_counts[a] += 1
            if a != b:
                pip_counts[b] += 1
            else:
                double_count += 1
        return any(count >= 5 for count in pip_counts.values()) or double_count >= 5

    def start_new_round(self):
        self.round_number += 1
        prev_winner = self.round_winner_id
        self.round_winner_id = None
        self.round_points_won = 0
        self.consecutive_passes = 0
        self.board.clear()
        self.left_end = None
        self.right_end = None
        self.active = True

        # Deal tiles with fairness guard: reshuffle if any player holds >= 5 of the same number or >= 5 doubles
        deck = create_double_six_deck()
        for _ in range(100):
            random.shuffle(deck)
            deck_copy = list(deck)
            test_hands = {}
            unbalanced = False
            for uid in self.player_ids:
                h = [deck_copy.pop() for _ in range(self.hand_size)]
                if self._is_hand_unbalanced(h):
                    unbalanced = True
                    break
                test_hands[uid] = h
            if not unbalanced:
                for uid in self.player_ids:
                    self.hands[uid] = test_hands[uid]
                    self.hands[uid].sort(key=lambda t: (t[0] + t[1], max(t)), reverse=True)
                self.boneyard = deck_copy
                break
        else:
            for uid in self.player_ids:
                self.hands[uid] = test_hands.get(uid, [])
            self.boneyard = deck_copy

        if self.round_number == 1 or not prev_winner:
            starter_idx = self._find_highest_double_holder()
            self.current_turn_index = starter_idx
        else:
            if prev_winner in self.player_ids:
                self.current_turn_index = self.player_ids.index(prev_winner)

        current_uid = self.player_ids[self.current_turn_index]
        current_name = self.player_names[current_uid]

        self.event_id += 1
        self.event_type = "ROUND_STARTED"
        self.sound_cue = "DOMINO_SHUFFLE"
        self.last_action = f"بدأت الجولة {self.round_number}. دور {current_name} لافتتاح الطاولة."

    def _find_highest_double_holder(self) -> int:
        for double_val in range(6, -1, -1):
            for idx, uid in enumerate(self.player_ids):
                if (double_val, double_val) in self.hands[uid]:
                    return idx
        highest_pips = -1
        starter = 0
        for idx, uid in enumerate(self.player_ids):
            for t in self.hands[uid]:
                if t[0] + t[1] > highest_pips:
                    highest_pips = t[0] + t[1]
                    starter = idx
        return starter

    def current_player_id(self) -> int:
        return self.player_ids[self.current_turn_index]

    def current_player_name(self) -> str:
        return self.player_names[self.current_player_id()]

    def get_valid_moves(self, user_id: int) -> List[Dict[str, Any]]:
        if not self.active or user_id != self.current_player_id():
            return []
        hand = self.hands.get(user_id, [])
        if not self.board:
            return [
                {
                    "tile_index": i,
                    "tile": t,
                    "sides": ["left", "right"],
                    "label": tile_display_name(t),
                }
                for i, t in enumerate(hand)
            ]

        valid = []
        for i, t in enumerate(hand):
            a, b = t
            sides = []
            if a == self.left_end or b == self.left_end:
                sides.append("left")
            if a == self.right_end or b == self.right_end:
                sides.append("right")
            if sides:
                valid.append(
                    {
                        "tile_index": i,
                        "tile": t,
                        "sides": sides,
                        "label": tile_display_name(t),
                    }
                )
        return valid

    def calculate_open_ends_sum(self) -> int:
        """Calculate the sum of all exposed open ends on the board."""
        if not self.board:
            return 0
        if len(self.board) == 1:
            first_tile = self.board[0]
            if first_tile[0] == first_tile[1]:
                return first_tile[0] + first_tile[1]
            return first_tile[0] + first_tile[1]

        left_tile = self.board[0]
        right_tile = self.board[-1]

        left_val = (left_tile[0] + left_tile[1]) if left_tile[0] == left_tile[1] else left_tile[0]
        right_val = (right_tile[0] + right_tile[1]) if right_tile[0] == right_tile[1] else right_tile[1]

        return left_val + right_val

    def can_draw(self, user_id: int) -> bool:
        if not self.active or user_id != self.current_player_id():
            return False
        if not self.boneyard:
            return False
        valid = self.get_valid_moves(user_id)
        return len(valid) == 0

    def can_pass(self, user_id: int) -> bool:
        if not self.active or user_id != self.current_player_id():
            return False
        valid = self.get_valid_moves(user_id)
        if valid:
            return False
        return len(self.boneyard) == 0

    def play_tile(
        self, user_id: int, tile_index: int, side: str = "auto"
    ) -> Dict[str, Any]:
        if not self.active:
            raise ValueError("المباراة غير نشطة.")
        if user_id != self.current_player_id():
            raise ValueError("ليس دورك الآن.")

        hand = self.hands.get(user_id, [])
        if tile_index < 0 or tile_index >= len(hand):
            raise ValueError("القطعة المحددة غير موجودة.")

        tile = hand[tile_index]
        a, b = tile
        player_name = self.player_names[user_id]

        if not self.board:
            hand.pop(tile_index)
            placed_tile = (a, b)
            self.board.append(placed_tile)
            self.left_end = a
            self.right_end = b
            self.consecutive_passes = 0
            self.event_id += 1
            self.event_type = "TILE_PLACED"
            self.sound_cue = "DOMINO_PLACE"
            self.last_action = f"{player_name} افتتح الطاولة بـ {tile_display_name(tile)}."

            ends_sum = self.calculate_open_ends_sum()
            if ends_sum > 0 and ends_sum % 5 == 0:
                pts, label = self._format_points(ends_sum)
                self.scores[user_id] += pts
                self.last_action += f" ({label}!)"

            self._check_match_winner()
            if self.active:
                self._check_round_end(user_id)
            if self.active:
                self._advance_turn()
            return self.get_state(user_id)

        valid_sides = []
        if a == self.left_end or b == self.left_end:
            valid_sides.append("left")
        if a == self.right_end or b == self.right_end:
            valid_sides.append("right")

        if not valid_sides:
            raise ValueError("هذه القطعة لا يمكن لعبها على أي طرف حالياً.")

        target_side = side.lower()
        if target_side not in ("left", "right"):
            if len(valid_sides) == 1:
                target_side = valid_sides[0]
            else:
                target_side = "right"

        if target_side not in valid_sides:
            side_name = "الأيسر" if target_side == "left" else "الأيمن"
            raise ValueError(f"لا يمكن وضع القطعة على الطرف {side_name}.")

        hand.pop(tile_index)

        if target_side == "left":
            if b == self.left_end:
                placed_tile = (a, b)
                self.left_end = a
            else:
                placed_tile = (b, a)
                self.left_end = b
            self.board.insert(0, placed_tile)
        else:
            if a == self.right_end:
                placed_tile = (a, b)
                self.right_end = b
            else:
                placed_tile = (b, a)
                self.right_end = a
            self.board.append(placed_tile)

        self.consecutive_passes = 0
        self.event_id += 1
        self.event_type = "TILE_PLACED"
        self.sound_cue = "DOMINO_PLACE"
        side_ar = "اليسار" if target_side == "left" else "اليمين"
        self.last_action = f"{player_name} لعب {tile_display_name(tile)} على {side_ar}."

        ends_sum = self.calculate_open_ends_sum()
        if ends_sum > 0 and ends_sum % 5 == 0:
            pts, label = self._format_points(ends_sum)
            self.scores[user_id] += pts
            self.last_action += f" ({label}!)"

        self._check_match_winner()
        if self.active:
            self._check_round_end(user_id)
        if self.active:
            self._advance_turn()

        return self.get_state(user_id)

    def draw_tile(self, user_id: int) -> Dict[str, Any]:
        if not self.active:
            raise ValueError("المباراة غير نشطة.")
        if user_id != self.current_player_id():
            raise ValueError("ليس دورك الآن.")
        if not self.boneyard:
            raise ValueError("بنك السحب فارغ.")
        if self.get_valid_moves(user_id):
            raise ValueError("لديك قطعة صالحة للعب، لا يمكنك السحب.")

        draw_idx = random.randrange(len(self.boneyard))
        tile = self.boneyard.pop(draw_idx)
        self.hands[user_id].append(tile)
        self.hands[user_id].sort(key=lambda t: (t[0] + t[1], max(t)), reverse=True)

        player_name = self.player_names[user_id]
        self.event_id += 1
        self.event_type = "TILE_DRAWN"
        self.sound_cue = "DOMINO_DRAW"
        self.last_action = f"{player_name} سحب قطعة."

        return self.get_state(user_id)

    def pass_turn(self, user_id: int) -> Dict[str, Any]:
        if not self.active:
            raise ValueError("المباراة غير نشطة.")
        if user_id != self.current_player_id():
            raise ValueError("ليس دورك الآن.")
        if not self.can_pass(user_id):
            if self.boneyard:
                raise ValueError("يجب عليك السحب أولاً قبل التمرير.")
            raise ValueError("لديك حركة صالحة، لا يمكنك التمرير.")

        player_name = self.player_names[user_id]
        self.consecutive_passes += 1
        self.event_id += 1
        self.event_type = "PLAYER_PASSED"
        self.sound_cue = "DOMINO_PASS"
        self.last_action = f"{player_name} باص."

        if self.consecutive_passes >= len(self.player_ids):
            self._resolve_blocked_game()
        else:
            self._advance_turn()

        return self.get_state(user_id)

    def _advance_turn(self):
        self.current_turn_index = (self.current_turn_index + 1) % len(self.player_ids)

    def _format_points(self, raw_points: int) -> Tuple[int, str]:
        """Convert a multiple of 5 into scored points and Arabic label based on scoring_mode."""
        if self.scoring_mode == "unit":
            pts = raw_points // 5
            if pts == 1:
                label = "وحدة واحدة"
            elif pts == 2:
                label = "وحدتان"
            elif 3 <= pts <= 10:
                label = f"{pts} وحدات"
            else:
                label = f"{pts} وحدة"
            return pts, label
        else:
            pts = raw_points
            if pts == 1:
                label = "نقطة واحدة"
            elif pts == 2:
                label = "نقطتان"
            elif 3 <= pts <= 10:
                label = f"{pts} نقاط"
            else:
                label = f"{pts} نقطة"
            return pts, label

    def _format_round_end_points(self, pips_difference: int) -> Tuple[int, str]:
        """Calculate end-of-round points from pips difference rounded to nearest multiple of 5."""
        if self.scoring_mode == "unit":
            pts = int(round(pips_difference / 5.0))
            if pts == 1:
                label = "وحدة واحدة"
            elif pts == 2:
                label = "وحدتان"
            elif 3 <= pts <= 10:
                label = f"{pts} وحدات"
            else:
                label = f"{pts} وحدة"
            return pts, label
        else:
            pts = int(round(pips_difference / 5.0) * 5)
            if pts == 1:
                label = "نقطة واحدة"
            elif pts == 2:
                label = "نقطتان"
            elif 3 <= pts <= 10:
                label = f"{pts} نقاط"
            else:
                label = f"{pts} نقطة"
            return pts, label

    def _check_match_winner(self) -> bool:
        for uid, s in self.scores.items():
            if s >= self.target_score:
                self.winner_id = uid
                self.active = False
                winner_name = self.player_names[uid]
                unit_label = "وحدة" if self.scoring_mode == "unit" else "نقطة"
                self.event_type = "MATCH_WON"
                self.sound_cue = "DOMINO_WIN"
                self.last_action = f"فاز {winner_name} بالمباراة برصيد ({s}) {unit_label}!"
                return True
        return False

    def _check_round_end(self, player_id: int):
        if len(self.hands[player_id]) == 0:
            player_name = self.player_names[player_id]
            opp_pips = sum(sum(t[0] + t[1] for t in self.hands[uid]) for uid in self.player_ids if uid != player_id)
            round_pts, label = self._format_round_end_points(opp_pips)
            self.scores[player_id] += round_pts

            self.round_winner_id = player_id
            self.round_points_won = round_pts
            self.active = False

            self.event_id += 1
            self.event_type = "DOMINO_WIN"
            self.sound_cue = "DOMINO_WIN"

            unit_label = "وحدة" if self.scoring_mode == "unit" else "نقطة"
            if self.scores[player_id] >= self.target_score:
                self.winner_id = player_id
                self.event_type = "MATCH_WON"
                self.last_action = f"دومينو! فاز {player_name} بالمباراة برصيد ({self.scores[player_id]}) {unit_label}!"
            else:
                self.last_action = f"دومينو! {player_name} أنهى قطعه (+{label})."

    def _resolve_blocked_game(self):
        pip_sums = {uid: sum(t[0] + t[1] for t in hand) for uid, hand in self.hands.items()}
        min_pips = min(pip_sums.values())
        lowest_players = [uid for uid, pips in pip_sums.items() if pips == min_pips]

        self.active = False
        self.event_id += 1
        self.sound_cue = "DOMINO_BLOCKED"

        if len(lowest_players) == 1:
            winner_id = lowest_players[0]
            winner_name = self.player_names[winner_id]
            opp_pips = sum(pips for uid, pips in pip_sums.items() if uid != winner_id)
            diff = opp_pips - min_pips
            round_pts, label = self._format_round_end_points(diff)
            self.scores[winner_id] += round_pts
            self.round_winner_id = winner_id
            self.round_points_won = round_pts

            unit_label = "وحدة" if self.scoring_mode == "unit" else "نقطة"
            if self.scores[winner_id] >= self.target_score:
                self.winner_id = winner_id
                self.event_type = "MATCH_WON"
                self.last_action = f"قفلت الطاولة! فاز {winner_name} بالمباراة برصيد ({self.scores[winner_id]}) {unit_label}!"
            else:
                self.event_type = "ROUND_BLOCKED"
                self.last_action = f"قفلت الطاولة! فاز {winner_name} بأقل نقاط يد (+{label})."
        else:
            self.round_winner_id = None
            self.round_points_won = 0
            self.event_type = "ROUND_TIED"
            self.last_action = "قفلت الطاولة بتعادل النقاط بين اللاعبين!"

    def get_state(self, viewer_id: Optional[int] = None) -> Dict[str, Any]:
        viewer_id = viewer_id or self.current_player_id()
        hand = self.hands.get(viewer_id, [])
        valid_moves = self.get_valid_moves(viewer_id)
        valid_indices = {m["tile_index"] for m in valid_moves}

        formatted_hand = []
        for i, t in enumerate(hand):
            vm = next((m for m in valid_moves if m["tile_index"] == i), None)
            formatted_hand.append({
                "index": i,
                "tile": list(t),
                "label": tile_display_name(t),
                "is_valid": i in valid_indices,
                "valid_sides": vm["sides"] if vm else []
            })

        return {
            "active": self.active,
            "round_number": self.round_number,
            "target_score": self.target_score,
            "scores": {str(k): v for k, v in self.scores.items()},
            "player_names": {str(k): v for k, v in self.player_names.items()},
            "players": [
                {
                    "user_id": uid,
                    "name": self.player_names[uid],
                    "tile_count": len(self.hands.get(uid, [])),
                    "score": self.scores.get(uid, 0)
                } for uid in self.player_ids
            ],
            "current_player_id": self.current_player_id(),
            "current_player_name": self.current_player_name(),
            "is_my_turn": viewer_id == self.current_player_id(),
            "left_end": self.left_end,
            "right_end": self.right_end,
            "open_ends_sum": self.calculate_open_ends_sum(),
            "board": [list(t) for t in self.board],
            "board_count": len(self.board),
            "boneyard_count": len(self.boneyard),
            "hand": formatted_hand,
            "can_draw": self.can_draw(viewer_id),
            "can_pass": self.can_pass(viewer_id),
            "winner_id": self.winner_id,
            "round_winner_id": self.round_winner_id,
            "round_points_won": self.round_points_won,
            "scoring_mode": self.scoring_mode,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "sound_cue": self.sound_cue,
            "last_action": self.last_action
        }
