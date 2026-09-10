"""Classic Double-Six Dominoes game engine."""
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


class DominoGame:
    def __init__(
        self,
        players: List[Tuple[int, str]],
        target_score: int = 100,
        rules: Optional[Dict[str, Any]] = None,
    ):
        if len(players) < 2:
            raise ValueError("لعبة الدومينو تتطلب لاعبين على الأقل.")
        if len(players) > 5:
            raise ValueError("لعبة الدومينو تدعم من لاعبين إلى خمسة لاعبين فقط.")
        self.players = players  # [(user_id, display_name), ...]
        self.player_ids = [p[0] for p in players]
        self.player_names = {p[0]: p[1] for p in players}
        self.target_score = target_score
        self.rules = rules or {"mode": "draw", "hand_size": 7}
        self.hand_size = int(self.rules.get("hand_size", 7))
        if len(self.players) >= 3 and self.hand_size > 5:
            self.hand_size = 5

        # Game state
        self.scores: Dict[int, int] = {p[0]: 0 for p in players}
        self.hands: Dict[int, List[Tuple[int, int]]] = {p[0]: [] for p in players}
        self.boneyard: List[Tuple[int, int]] = []
        self.board: List[Tuple[int, int]] = []  # Ordered list of tiles on table
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
            # Clean standard fallback deal
            deck_copy = create_double_six_deck()
            random.shuffle(deck_copy)
            for uid in self.player_ids:
                self.hands[uid] = [deck_copy.pop() for _ in range(self.hand_size)]
                self.hands[uid].sort(key=lambda t: (t[0] + t[1], max(t)), reverse=True)
            self.boneyard = deck_copy

        # First round: player with highest double opens. Subsequent rounds: previous winner opens.
        if self.round_number == 1 or not prev_winner:
            starter_idx = self._find_highest_double_holder()
            self.current_turn_index = starter_idx
        else:
            if prev_winner in self.player_ids:
                self.current_turn_index = self.player_ids.index(prev_winner)

        current_uid = self.player_ids[self.current_turn_index]
        current_name = self.player_names[current_uid]

        self.event_id += 1
        self.event_type = "ROUND_START"
        self.sound_cue = "DOMINO_SETUP"
        self.last_action = f"الجولة {self.round_number}. دور {current_name} لافتتاح الطاولة."

    def _find_highest_double_holder(self) -> int:
        for double_val in range(6, -1, -1):
            for idx, uid in enumerate(self.player_ids):
                if (double_val, double_val) in self.hands[uid]:
                    return idx
        # If no double held, find highest pip tile
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
        """Return list of playable tiles and their valid placement sides."""
        if not self.active or user_id != self.current_player_id():
            return []
        hand = self.hands.get(user_id, [])
        if not self.board:
            # First move on empty board: any tile in hand is playable
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

    def can_draw(self, user_id: int) -> bool:
        if not self.active or user_id != self.current_player_id():
            return False
        mode = str(self.rules.get("mode", "draw")).lower()
        if mode == "block":
            return False
        if not self.boneyard:
            return False
        # In Draw mode, player must draw if they have no valid move
        valid = self.get_valid_moves(user_id)
        return len(valid) == 0

    def can_pass(self, user_id: int) -> bool:
        if not self.active or user_id != self.current_player_id():
            return False
        valid = self.get_valid_moves(user_id)
        if valid:
            return False
        mode = str(self.rules.get("mode", "draw")).lower()
        if mode == "block":
            return True
        # In Draw mode, can pass only when no valid moves AND boneyard is empty
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
            raise ValueError("القطعة المحددة غير موجودة في يدك.")

        tile = hand[tile_index]
        a, b = tile
        player_name = self.player_names[user_id]

        if not self.board:
            # First tile on board
            hand.pop(tile_index)
            self.board.append(tile)
            self.left_end = a
            self.right_end = b
            self.consecutive_passes = 0
            self.event_id += 1
            self.event_type = "TILE_PLACED"
            self.sound_cue = "DOMINO_PLACE"
            self.last_action = f"{player_name} افتتح الطاولة بـ {tile_display_name(tile)}."
            self._check_round_end(user_id)
            if self.active:
                self._advance_turn()
            return self.get_state(user_id)

        # Determine valid sides for this tile
        valid_sides = []
        if a == self.left_end or b == self.left_end:
            valid_sides.append("left")
        if a == self.right_end or b == self.right_end:
            valid_sides.append("right")

        if not valid_sides:
            raise ValueError("هذه القطعة غير صالحة للعب على أطراف الطاولة الحالية.")

        target_side = side
        if target_side not in ("left", "right"):
            if len(valid_sides) == 1:
                target_side = valid_sides[0]
            else:
                target_side = "right"

        if target_side not in valid_sides:
            side_name = "الأيسر" if target_side == "left" else "الأيمن"
            raise ValueError(f"لا يمكن وضع القطعة على الطرف {side_name}.")

        hand.pop(tile_index)

        # Connect tile and update end
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

        self._check_round_end(user_id)
        if self.active:
            self._advance_turn()

        return self.get_state(user_id)

    def draw_tile(self, user_id: int) -> Dict[str, Any]:
        if not self.active:
            raise ValueError("المباراة غير نشطة.")
        if user_id != self.current_player_id():
            raise ValueError("ليس دورك الآن.")
        mode = str(self.rules.get("mode", "draw")).lower()
        if mode == "block":
            raise ValueError("في نمط القفل، لا يوجد سحب من البنك.")
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
            mode = str(self.rules.get("mode", "draw")).lower()
            if mode == "draw" and self.boneyard:
                raise ValueError("يجب عليك السحب أولاً قبل التمرير.")
            raise ValueError("لديك حركة صالحة، لا يمكنك التمرير.")

        player_name = self.player_names[user_id]
        self.consecutive_passes += 1
        self.event_id += 1
        self.event_type = "PLAYER_PASSED"
        self.sound_cue = "DOMINO_PASS"
        self.last_action = f"{player_name} باص."

        # If all players passed consecutively, the board is blocked!
        if self.consecutive_passes >= len(self.player_ids):
            self._resolve_blocked_game()
        else:
            self._advance_turn()

        return self.get_state(user_id)

    def _advance_turn(self):
        self.current_turn_index = (self.current_turn_index + 1) % len(self.player_ids)

    def _check_round_end(self, player_id: int):
        # Check if player emptied their hand (Domino!)
        if len(self.hands[player_id]) == 0:
            player_name = self.player_names[player_id]
            round_penalty = 0
            for uid, hand in self.hands.items():
                if uid != player_id:
                    p = sum(t[0] + t[1] for t in hand)
                    self.scores[uid] += p
                    round_penalty += p

            self.round_winner_id = player_id
            self.round_points_won = round_penalty
            self.active = False

            self.event_id += 1
            scores_summary = "، ".join(f"{self.player_names.get(uid, 'لاعب')}: {self.scores.get(uid, 0)}" for uid in self.player_ids)
            max_score = max(self.scores.values())
            if max_score >= self.target_score:
                min_score = min(self.scores.values())
                winner_candidates = [uid for uid, s in self.scores.items() if s == min_score]
                self.winner_id = winner_candidates[0]
                match_winner_name = self.player_names[self.winner_id]
                self.event_type = "MATCH_FINISHED"
                self.sound_cue = "MATCH_WIN"
                self.last_action = f"نهاية المباراة! الفائز: {match_winner_name}. النتائج: {scores_summary}"
            else:
                self.event_type = "ROUND_FINISHED"
                self.sound_cue = "ROUND_END"
                self.last_action = f"نهاية الجولة {self.round_number}. النتائج: {scores_summary}"

    def _resolve_blocked_game(self):
        # Board blocked: calculate pip total for each player
        pip_sums = {uid: sum(t[0] + t[1] for t in hand) for uid, hand in self.hands.items()}
        min_pips = min(pip_sums.values())
        lowest_players = [uid for uid, pips in pip_sums.items() if pips == min_pips]

        self.active = False
        self.event_id += 1

        if len(lowest_players) == 1:
            winner_id = lowest_players[0]
            winner_name = self.player_names[winner_id]

            round_penalty = 0
            # Winner gets 0, other players get their remaining pips added
            for uid, pips in pip_sums.items():
                if uid != winner_id:
                    self.scores[uid] += pips
                    round_penalty += pips

            self.round_winner_id = winner_id
            self.round_points_won = round_penalty

            scores_summary = "، ".join(f"{self.player_names.get(uid, 'لاعب')}: {self.scores.get(uid, 0)}" for uid in self.player_ids)
            max_score = max(self.scores.values())
            if max_score >= self.target_score:
                min_score = min(self.scores.values())
                winner_candidates = [uid for uid, s in self.scores.items() if s == min_score]
                self.winner_id = winner_candidates[0]
                match_winner_name = self.player_names[self.winner_id]
                self.event_type = "MATCH_FINISHED"
                self.sound_cue = "MATCH_WIN"
                self.last_action = f"نهاية المباراة! الفائز: {match_winner_name}. النتائج: {scores_summary}"
            else:
                self.event_type = "ROUND_FINISHED"
                self.sound_cue = "ROUND_END"
                self.last_action = f"نهاية الجولة {self.round_number}. النتائج: {scores_summary}"
        else:
            # Tie: lowest players get 0, others get their pips
            for uid, pips in pip_sums.items():
                if uid not in lowest_players:
                    self.scores[uid] += pips
            self.round_winner_id = None
            self.round_points_won = 0
            scores_summary = "، ".join(f"{self.player_names.get(uid, 'لاعب')}: {self.scores.get(uid, 0)}" for uid in self.player_ids)
            self.event_type = "ROUND_FINISHED"
            self.sound_cue = "ROUND_END"
            self.last_action = f"نهاية الجولة {self.round_number}. النتائج: {scores_summary}"

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
            "board": [list(t) for t in self.board],
            "board_count": len(self.board),
            "boneyard_count": len(self.boneyard),
            "hand": formatted_hand,
            "can_draw": self.can_draw(viewer_id),
            "can_pass": self.can_pass(viewer_id),
            "winner_id": self.winner_id,
            "round_winner_id": self.round_winner_id,
            "round_points_won": self.round_points_won,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "sound_cue": self.sound_cue,
            "last_action": self.last_action
        }