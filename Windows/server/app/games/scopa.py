"""Scopa (and Escoba) card game engine for TableVerse."""
import random
import uuid
from itertools import combinations
from typing import List, Tuple, Dict, Optional, Any

SUITS = ["Diamonds", "Hearts", "Spades", "Clubs"]
SUIT_MAP = {
    "Diamonds": "Diamonds",
    "Hearts": "Hearts",
    "Spades": "Spades",
    "Clubs": "Clubs",
    "دايموند": "Diamonds",
    "هارت": "Hearts",
    "سبيد": "Spades",
    "كلاب": "Clubs",
}
PRIMIERA_VALUES = {7: 21, 6: 18, 1: 16, 5: 15, 4: 14, 3: 13, 2: 12, 8: 10, 9: 10, 10: 10}

def card_display_name(card: Dict[str, Any]) -> str:
    """Return the English user-facing card name used by server event narration."""
    suit = SUIT_MAP.get(str(card.get("suit", "")), str(card.get("suit", ""))).capitalize()
    value = card.get("value", 0)
    rank = {
        1: "Ace",
        11: "Jack",
        12: "Queen",
        13: "King",
    }.get(value, str(value))
    return f"{rank} of {suit}"

class ScopaGame:
    def __init__(
        self,
        players: List[Tuple[int, str]],
        target_score: int = 11,
        rules: Optional[Dict[str, Any]] = None,
    ):
        if len(players) < 2:
            raise ValueError("لعبة إسكوبا تتطلب لاعبين على الأقل.")
        if len(players) > 6:
            raise ValueError("لعبة إسكوبا تدعم من لاعبين إلى ستة لاعبين فقط.")
        requested_mode = str((rules or {}).get("scopa_mode", "classic")).strip().lower()
        if requested_mode == "scopone" and len(players) != 4:
            raise ValueError("وضع سكوبوني يتطلب أربعة لاعبين بالضبط.")
        self.players = players
        self.player_ids = [p[0] for p in players]
        self.player_names = {p[0]: p[1] for p in players}
        self.target_score = target_score
        self.rules = rules or {}
        self.game_mode = self.rules.get("scopa_mode", "classic")  # classic, escoba_15, asso_piglia_tutto, scopone, inverted

        # Team setup: 4 or 6 players are 2 teams (Team 0 and Team 1)
        self.is_team_game = len(self.players) in (4, 6)
        self.teams: Dict[int, int] = {}
        for idx, (uid, _) in enumerate(self.players):
            self.teams[uid] = (idx % 2) if self.is_team_game else uid

        # Persistent match state
        self.scores: Dict[int, int] = {p[0]: 0 for p in self.players}
        self.team_scores: Dict[int, int] = {0: 0, 1: 0} if self.is_team_game else {}
        self.round_number: int = 0
        self.winner_id: Optional[int] = None
        self.winning_team: Optional[int] = None

        # Round state
        self.active: bool = False
        self.deck: List[Dict[str, Any]] = []
        self.table_cards: List[Dict[str, Any]] = []
        self.hands: Dict[int, List[Dict[str, Any]]] = {p[0]: [] for p in self.players}
        self.captured_cards: Dict[int, List[Dict[str, Any]]] = {p[0]: [] for p in self.players}
        self.scopa_count: Dict[int, int] = {p[0]: 0 for p in self.players}

        self.dealer_index: int = -1
        self.last_capture_id: Optional[int] = None
        self.last_player_id: Optional[int] = None
        self.current_turn_index: int = 0
        self.pending_choice: Optional[Dict[str, Any]] = None

        # Event narration & sound cues
        self.event_id: int = 0
        self.last_action: str = ""
        self.event_type: str = ""
        self.sound_cue: str = ""
        self.final_play_event_type: str = ""
        self.round_summary: str = ""
        self.pending_deal_batch: bool = False

    @property
    def match_finished(self) -> bool:
        return bool(self.winner_id is not None or self.winning_team is not None)

    @property
    def winner_name(self) -> str:
        if self.is_team_game and self.winning_team is not None:
            return f"فريق {self.winning_team + 1}"
        if self.winner_id is not None:
            return self.player_names.get(self.winner_id, "الفائز")
        return ""

    @property
    def winner_label(self) -> str:
        return self.winner_name

    def start_match(self):
        self.scores = {p[0]: 0 for p in self.players}
        if self.is_team_game:
            self.team_scores = {0: 0, 1: 0}
        self.round_number = 0
        self.winner_id = None
        self.winning_team = None
        self.start_new_round()

    def start_new_round(self):
        self.round_number += 1
        self.active = True
        self.pending_choice = None
        self.round_summary = ""
        self.final_play_event_type = ""
        self.pending_deal_batch = False

        # Build 40-card deck
        self.deck = []
        for suit in SUITS:
            for val in range(1, 11):
                self.deck.append({"id": uuid.uuid4().hex[:8], "suit": suit, "value": val})
        random.shuffle(self.deck)

        self.table_cards = []
        self.hands = {p[0]: [] for p in self.players}
        self.captured_cards = {p[0]: [] for p in self.players}
        self.scopa_count = {p[0]: 0 for p in self.players}
        self.last_capture_id = None

        self.dealer_index = (self.dealer_index + 1) % len(self.players)
        self.current_turn_index = (self.dealer_index + 1) % len(self.players)

        is_scopone = bool(self.rules.get("scopone") or self.game_mode == "scopone")
        if is_scopone:
            cards_per = 40 // len(self.players)
            for uid, _ in self.players:
                self.hands[uid] = [self.deck.pop() for _ in range(cards_per)]
            self.table_cards = [self.deck.pop() for _ in range(len(self.deck))]
        else:
            table_init = 5 if len(self.players) == 5 else 4
            for uid, _ in self.players:
                self.hands[uid] = [self.deck.pop() for _ in range(3)]
            self.table_cards = [self.deck.pop() for _ in range(table_init)]

        dealer_name = self.players[self.dealer_index][1]
        first_name = self.players[self.current_turn_index][1]
        self._set_event(
            f"الجولة {self.round_number}! الموزع {dealer_name}، والدور عند {first_name}.",
            "ROUND_START",
            "SCOPA_DEAL"
        )

    def _deal_next_batch(self):
        if not self.deck:
            self._finalize_round()
            return

        num_players = len(self.players)
        if num_players == 0 or len(self.deck) < num_players:
            self._finalize_round()
            return

        count = 4 if num_players == 5 and len(self.deck) == 20 else 3
        count = min(count, len(self.deck) // num_players)
        if count <= 0:
            self._finalize_round()
            return

        for uid, _ in self.players:
            self.hands[uid] = [self.deck.pop() for _ in range(count)]

        self.current_turn_index = (self.dealer_index + 1) % num_players

        self._set_event("", "DEAL_BATCH", "SCOPA_DEAL")

    def current_player_id(self) -> int:
        return self.players[self.current_turn_index][0]

    def current_player_name(self) -> str:
        return self.players[self.current_turn_index][1]

    def get_combinations(self, card_value: int) -> List[List[Dict[str, Any]]]:
        if not self.table_cards:
            return []

        is_asso = bool(self.rules.get("asso_piglia_tutto") or self.game_mode == "asso_piglia_tutto")
        if is_asso and card_value == 1:
            return [list(self.table_cards)]

        is_escoba = bool(self.rules.get("escoba_15") or self.game_mode == "escoba_15")
        if is_escoba:
            target = 15 - card_value
            result = []
            for r in range(1, len(self.table_cards) + 1):
                for combo in combinations(self.table_cards, r):
                    if sum(c["value"] for c in combo) == target:
                        result.append(list(combo))
            return self._remove_duplicate_combos(result)

        # Classic Scopa
        exact_matches = [c for c in self.table_cards if c["value"] == card_value]
        if exact_matches:
            return [[c] for c in exact_matches]

        result = []
        for r in range(2, len(self.table_cards) + 1):
            for combo in combinations(self.table_cards, r):
                if sum(c["value"] for c in combo) == card_value:
                    result.append(list(combo))

        return self._remove_duplicate_combos(result)

    def _remove_duplicate_combos(self, combos: List[List[Dict[str, Any]]]) -> List[List[Dict[str, Any]]]:
        unique = []
        seen = set()
        for c in combos:
            sig = tuple(sorted(item["id"] for item in c))
            if sig not in seen:
                seen.add(sig)
                unique.append(c)
        return unique

    def play_card(self, user_id: int, card_index: int, capture_choice: Optional[int] = None) -> Dict[str, Any]:
        if not self.active:
            raise ValueError("المباراة غير نشطة حالياً.")
        if user_id != self.current_player_id():
            raise ValueError("ليس دورك للعب الآن.")
        self.last_player_id = user_id

        hand = self.hands.get(user_id, [])
        if card_index < 0 or card_index >= len(hand):
            raise ValueError("رقم الورقة غير صالح.")

        card = hand[card_index]

        combos = self.get_combinations(card["value"])
        if not combos:
            # Play onto table
            played = self.hands[user_id].pop(card_index)
            self.table_cards.append(played)
            pname = self.current_player_name()
            self._set_event(
                f"لعب {pname} {card_display_name(played)}.",
                "CARD_PLAYED",
                "SCOPA_CARD_THROW"
            )
            self._advance_turn()
            return {"status": "played", "card": played}
        else:
            if capture_choice is not None and isinstance(capture_choice, int) and 0 <= capture_choice < len(combos):
                chosen_combo = combos[capture_choice]
            else:
                chosen_combo = self._pick_best_combo(combos)
            return self._execute_capture(user_id, card_index, chosen_combo)

    def _pick_best_combo(self, combos: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        # Single card match rule (applies in Classic Italian Scopa, not in Escoba 15)
        if self.game_mode != "escoba_15":
            single_matches = [c for c in combos if len(c) == 1]
            if single_matches:
                return single_matches[0]

        is_inverted = (self.game_mode == "inverted")
        best_combo = combos[0]
        best_val = -9999 if not is_inverted else 9999

        for combo in combos:
            val = len(combo) * 2
            for c in combo:
                if c["suit"] == "Diamonds":
                    val += 4
                if c["suit"] == "Diamonds" and c["value"] == 7:
                    val += 20
                if c["value"] in (7, 6, 1):
                    val += 3
            if not is_inverted:
                if val > best_val:
                    best_val = val
                    best_combo = combo
            else:
                if val < best_val:
                    best_val = val
                    best_combo = combo

        return best_combo

    def _execute_capture(self, user_id: int, card_index: int, captured_combo: List[Dict[str, Any]]) -> Dict[str, Any]:
        played_card = self.hands[user_id].pop(card_index)
        captured_ids = {c["id"] for c in captured_combo}
        self.table_cards = [c for c in self.table_cards if c["id"] not in captured_ids]

        self.captured_cards[user_id].append(played_card)
        self.captured_cards[user_id].extend(captured_combo)
        self.last_capture_id = user_id

        # Check Scopa sweep. The played card has already been removed above, so
        # this correctly identifies the final play of the final deal.
        is_last_play = (not self.deck) and all(len(h) == 0 for h in self.hands.values())
        is_asso = bool(self.rules.get("asso_piglia_tutto") or self.game_mode == "asso_piglia_tutto")
        is_asso_sweep = is_asso and played_card.get("value") == 1 and not (len(captured_combo) == 1 and captured_combo[0].get("value") == 1)
        is_scopa = (not self.table_cards) and (not is_last_play) and (not is_asso_sweep)
        pname = self.current_player_name()
        cap_str = " و ".join(card_display_name(c) for c in captured_combo)

        is_inverted = bool(self.rules.get("inverted") or self.game_mode == "inverted")
        if is_scopa:
            self.scopa_count[user_id] += 1
            if is_inverted:
                if self.is_team_game:
                    my_tid = self.teams[user_id]
                    for other_tid in self.team_scores:
                        if other_tid != my_tid:
                            self.team_scores[other_tid] += 1
                else:
                    for other_uid in self.scores:
                        if other_uid != user_id:
                            self.scores[other_uid] += 1
                self._set_event(
                    f"لعب {pname} {card_display_name(played_card)} وأكل بها ({cap_str}) ... إسكوبااااا! 🧹✨ (+1 نقطة للمنافس)",
                    "SCOPA_SWEEP",
                    "SCOPA_SWEEP"
                )
            else:
                if self.is_team_game:
                    tid = self.teams[user_id]
                    self.team_scores[tid] += 1
                else:
                    self.scores[user_id] += 1

                self._set_event(
                    f"لعب {pname} {card_display_name(played_card)} وأكل بها ({cap_str}) ... إسكوبااااا! 🧹✨ (+1 نقطة فوري)",
                    "SCOPA_SWEEP",
                    "SCOPA_SWEEP"
                )
        else:
            self._set_event(
                f"لعب {pname} {card_display_name(played_card)} وأكل بها: {cap_str}.",
                "CARD_CAPTURED",
                "SCOPA_CAPTURE"
            )

        self._advance_turn()
        return {"status": "captured", "card": played_card, "is_scopa": is_scopa}

    def _advance_turn(self):
        if all(len(h) == 0 for h in self.hands.values()):
            if self.deck:
                self.pending_deal_batch = True
            else:
                self._finalize_round()
            return

        self.current_turn_index = (self.current_turn_index + 1) % len(self.players)
        while len(self.hands[self.players[self.current_turn_index][0]]) == 0:
            self.current_turn_index = (self.current_turn_index + 1) % len(self.players)

    def _finalize_round(self):
        # The last play ends the deal synchronously. Preserve its semantic
        # event because _calculate_round_scores will replace it with the round
        # summary before the client receives a snapshot.
        if self.event_type in ("CARD_PLAYED", "CARD_CAPTURED", "SCOPA_SWEEP"):
            self.final_play_event_type = self.event_type
        else:
            self.final_play_event_type = ""
        table_clear_note = ""
        # Remaining table cards go to last capture player
        if self.table_cards and self.last_capture_id:
            last_pname = self.player_names.get(self.last_capture_id, "اللاعب")
            self.captured_cards[self.last_capture_id].extend(self.table_cards)
            rem_str = " و ".join(card_display_name(c) for c in self.table_cards)
            self.table_cards = []
            table_clear_note = f"أخذ {last_pname} باقي الطاولة ({rem_str}). "

        self._calculate_round_scores(table_clear_note=table_clear_note)

    def _calculate_round_scores(self, table_clear_note: str = ""):
        stats = {
            uid: {
                "cards": 0,
                "diamonds": 0,
                "sette_bello": 0,
                "primiera_cards": {"Diamonds": 0, "Hearts": 0, "Spades": 0, "Clubs": 0},
                "scopas": self.scopa_count[uid],
            }
            for uid in self.player_ids
        }

        for uid, cards in self.captured_cards.items():
            stats[uid]["cards"] = len(cards)
            for c in cards:
                s = SUIT_MAP.get(c.get("suit", ""), c.get("suit", ""))
                if s == "Diamonds":
                    stats[uid]["diamonds"] += 1
                if s == "Diamonds" and c.get("value") == 7:
                    stats[uid]["sette_bello"] = 1
                pval = PRIMIERA_VALUES.get(c.get("value"), 0)
                if pval > stats[uid]["primiera_cards"].get(s, 0):
                    stats[uid]["primiera_cards"][s] = pval

        team_stats: Dict[int, Dict[str, Any]] = {}
        for uid, st in stats.items():
            tid = self.teams[uid]
            if tid not in team_stats:
                team_stats[tid] = {"cards": 0, "diamonds": 0, "sette_bello": 0, "primiera": 0, "scopas": 0}
            team_stats[tid]["cards"] += st["cards"]
            team_stats[tid]["diamonds"] += st["diamonds"]
            team_stats[tid]["sette_bello"] += st["sette_bello"]
            team_stats[tid]["scopas"] += st["scopas"]

        # Merge Primiera per team
        team_prim_best: Dict[int, Dict[str, int]] = {}
        for uid, st in stats.items():
            tid = self.teams[uid]
            if tid not in team_prim_best:
                team_prim_best[tid] = {"Diamonds": 0, "Hearts": 0, "Spades": 0, "Clubs": 0}
            for suit in SUITS:
                if st["primiera_cards"].get(suit, 0) > team_prim_best[tid].get(suit, 0):
                    team_prim_best[tid][suit] = st["primiera_cards"][suit]

        for tid in team_prim_best:
            suits_count = sum(1 for s in SUITS if team_prim_best[tid].get(s, 0) > 0)
            team_stats[tid]["primiera_suits"] = suits_count
            team_stats[tid]["primiera"] = sum(team_prim_best[tid].values())

        max_cards = max(st["cards"] for st in team_stats.values())
        max_diamonds = max(st["diamonds"] for st in team_stats.values())
        max_suits = max((st["primiera_suits"] for st in team_stats.values()), default=0)
        qualifying_primiera = {
            tid: st["primiera"] for tid, st in team_stats.items()
            if st["primiera_suits"] == max_suits and st["primiera_suits"] > 0
        }
        max_primiera = max(qualifying_primiera.values()) if qualifying_primiera else 0

        teams_max_cards = [tid for tid, st in team_stats.items() if st["cards"] == max_cards]
        teams_max_diamonds = [tid for tid, st in team_stats.items() if st["diamonds"] == max_diamonds]
        teams_max_prim = [tid for tid, pval in qualifying_primiera.items() if pval == max_primiera] if max_primiera > 0 else []

        is_inverted = bool(self.rules.get("inverted") or self.game_mode == "inverted")
        win_lose_phrase = "وخسر نقطة" if is_inverted else "ونال نقطة"

        round_end_points = {tid: 0 for tid in team_stats}
        details = []

        # 1. Cards point
        if len(teams_max_cards) == 1:
            round_end_points[teams_max_cards[0]] += 1
            lbl = self._team_label(teams_max_cards[0])
            details.append(f"{lbl} الأكثر كروتاً ({max_cards} كارت) {win_lose_phrase}")
        else:
            details.append(f"تعادل في الكروت ({max_cards} كارت)")

        # 2. Diamonds point
        if len(teams_max_diamonds) == 1:
            round_end_points[teams_max_diamonds[0]] += 1
            lbl = self._team_label(teams_max_diamonds[0])
            details.append(f"{lbl} الأكثر من أوراق Diamonds ({max_diamonds} ورقة) {win_lose_phrase}")
        else:
            details.append("تعادل في أوراق Diamonds")

        # 3. 7 of Diamonds (Sette Bello)
        for tid, st in team_stats.items():
            if st["sette_bello"]:
                round_end_points[tid] += 1
                lbl = self._team_label(tid)
                details.append(f"{lbl} صاحب 7 of Diamonds {win_lose_phrase}")

        # 4. Primiera
        if len(teams_max_prim) == 1:
            round_end_points[teams_max_prim[0]] += 1
            lbl = self._team_label(teams_max_prim[0])
            details.append(f"{lbl} صاحب البريميرا {win_lose_phrase}")
        else:
            details.append("تعادل في البريميرا")

        # 5. Scopas during the round
        for tid, st in team_stats.items():
            if st["scopas"] > 0:
                lbl = self._team_label(tid)
                sc_word = "إسكوبا" if st["scopas"] == 1 else f"{st['scopas']} إسكوبا"
                if is_inverted:
                    sc_pts_word = "نقطة" if st["scopas"] == 1 else f"{st['scopas']} نقطة"
                    details.append(f"{lbl} حقق {sc_word} وخسر {sc_pts_word}")
                else:
                    details.append(f"{lbl} حقق {sc_word} (+{st['scopas']} نقطة)")

        # Inverted mode
        if is_inverted:
            inv_pts = {tid: 0 for tid in team_stats}
            if len(team_stats) == 2:
                for tid, pts in round_end_points.items():
                    others = [o for o in team_stats if o != tid]
                    for o in others:
                        inv_pts[o] += pts
            else:
                # 3+ players inverted mode: single point awarded to unique lowest count without duplication
                min_cards = min(st["cards"] for st in team_stats.values())
                min_diamonds = min(st["diamonds"] for st in team_stats.values())
                teams_min_cards = [tid for tid, st in team_stats.items() if st["cards"] == min_cards]
                teams_min_diamonds = [tid for tid, st in team_stats.items() if st["diamonds"] == min_diamonds]
                if len(teams_min_cards) == 1:
                    inv_pts[teams_min_cards[0]] += 1
                if len(teams_min_diamonds) == 1:
                    inv_pts[teams_min_diamonds[0]] += 1
            round_end_points = inv_pts

        # Accumulate round-end points (scopas already added in real-time)
        if self.is_team_game:
            for tid, pts in round_end_points.items():
                self.team_scores[tid] += pts
        else:
            for tid, pts in round_end_points.items():
                uid = next((u for u, t in self.teams.items() if t == tid), None)
                if uid is not None and uid in self.scores:
                    self.scores[uid] += pts

        # Total points earned in this round (end points + real-time scopas)
        total_round_pts = {tid: round_end_points[tid] + team_stats[tid]["scopas"] for tid in team_stats}

        pts_parts = []
        for tid, pts in total_round_pts.items():
            label = self._team_label(tid)
            pts_parts.append(f"{label} {pts} نقطة")

        tot_parts = []
        if self.is_team_game:
            for tid, sc in self.team_scores.items():
                tot_parts.append(f"{self._team_label(tid)} {sc}")
        else:
            for uid, name in self.players:
                tot_parts.append(f"{name} {self.scores[uid]}")

        details_str = "، ".join(details)
        pts_str = "، ".join(pts_parts)
        tot_str = "، ".join(tot_parts)

        self.round_summary = f"{table_clear_note}نهاية الجولة {self.round_number}: {details_str}. نقاط الجولة ({pts_str}). النتيجة الكلية: {tot_str}، الهدف {self.target_score}."
        self.active = False

        # Match win condition
        if self.is_team_game:
            max_tot = max(self.team_scores.values())
            min_tot = min(self.team_scores.values()) if len(self.team_scores) > 1 else 0
            if max_tot >= self.target_score and (max_tot - min_tot) >= 2:
                self.winning_team = max(self.team_scores, key=self.team_scores.get)
                wname = self._team_label(self.winning_team)
                self._set_event(
                    f"نهاية المباراة! الفائز: {wname}. النتائج: {tot_str}",
                    "MATCH_FINISHED",
                    "MATCH_WIN"
                )
                return
        else:
            max_tot = max(self.scores.values())
            sorted_scores = sorted(self.scores.values(), reverse=True)
            second_max = sorted_scores[1] if len(sorted_scores) > 1 else 0
            if max_tot >= self.target_score and (max_tot - second_max) >= 2:
                self.winner_id = max(self.scores, key=self.scores.get)
                wname = self.player_names.get(self.winner_id, "الفائز")
                self._set_event(
                    f"نهاية المباراة! الفائز: {wname}. النتائج: {tot_str}",
                    "MATCH_FINISHED",
                    "MATCH_WIN"
                )
                return

        self._set_event(self.round_summary, "ROUND_FINISHED", "ROUND_END")

    def _team_label(self, tid: int) -> str:
        if self.is_team_game:
            members = [name for uid, name in self.players if self.teams[uid] == tid]
            return f"فريق {tid + 1} ({' و '.join(members)})"
        return self.player_names.get(tid, f"لاعب {tid}")

    def _set_event(self, text: str, event_type: str, sound_cue: str = ""):
        self.event_id += 1
        self.last_action = text
        self.event_type = event_type
        self.sound_cue = sound_cue

    def public_state(self, viewer_id: Optional[int] = None) -> Dict[str, Any]:
        return {
            "active": self.active,
            "game_mode": self.game_mode,
            "target_score": self.target_score,
            "round_number": self.round_number,
            "current_turn_id": self.current_player_id() if self.active else None,
            "current_turn_name": self.current_player_name() if self.active else "",
            "table_cards": [c for c in self.table_cards],
            "deck_count": len(self.deck),
            "hands_count": {str(uid): len(self.hands.get(uid, [])) for uid in self.player_ids},
            "my_hand": self.hands.get(viewer_id, []) if viewer_id is not None else [],
            "my_captured_count": len(self.captured_cards.get(viewer_id, [])) if viewer_id is not None else 0,
            "scores": {str(k): v for k, v in self.scores.items()} if not self.is_team_game else {str(k): v for k, v in self.team_scores.items()},
            "is_team_game": self.is_team_game,
            "teams": {str(uid): tid for uid, tid in self.teams.items()},
            "winner_id": self.winner_id,
            "pending_choice": self.pending_choice if (self.pending_choice and self.pending_choice.get("user_id") == viewer_id) else None,
            "last_action": self.last_action,
            "last_player_id": getattr(self, "last_player_id", None),
            "event_id": self.event_id,
            "event_type": self.event_type,
            "sound_cue": self.sound_cue,
            "final_play_event_type": self.final_play_event_type,
            "players": [
                {"id": uid, "user_id": uid, "name": name, "score": self.scores.get(uid, 0)}
                for uid, name in self.players
            ],
            "round_summary": self.round_summary,
        }

    def remove_player(self, user_id: int):
        if user_id not in self.player_ids:
            return
        self.player_ids.remove(user_id)
        self.players = [p for p in self.players if p[0] != user_id]
        self.player_names.pop(user_id, None)
        if hasattr(self, "teams"):
            self.teams.pop(user_id, None)
        self.scores.pop(user_id, None)
        self.hands.pop(user_id, None)
        self.captured_cards.pop(user_id, None)
        self.scopa_count.pop(user_id, None)
        if self.last_capture_id == user_id:
            self.last_capture_id = None
        if self.last_player_id == user_id:
            self.last_player_id = None

        if len(self.player_ids) < 2 or (self.is_team_game and len(self.player_ids) < 4):
            self.active = False
            return

        if self.current_turn_index >= len(self.players):
            self.current_turn_index = 0
        if self.dealer_index >= len(self.players):
            self.dealer_index = 0
