"""Accessible floor-chase game: Thief and Investigators."""
from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class HuntPlayer:
    user_id: int
    name: str
    is_bot: bool = False
    wins: int = 0
    active: bool = True


class ThiefHuntGame:
    """Authoritative Thief Hunt engine.

    Normal mode uses a *virtual thief*: the thief is a hidden game role and is
    not one of the room's bot/player seats. Bots are ordinary investigators,
    exactly like human investigators, and their answers are decided by the bot
    runner using a probability of error.

    If ``allow_human_thief`` is enabled, one human room player can be selected
    as the thief for a round. Bots are never promoted to the thief role.
    """

    DIRECTIONS_START = 3
    VIRTUAL_THIEF_NAME = "اللص"

    def __init__(self, players, total_rounds=5, allow_human_thief=False, elimination_mode=False):
        self.players: List[HuntPlayer] = [
            HuntPlayer(uid, name, uid < 0) for uid, name in players
        ]
        self.total_rounds = max(1, min(100, int(total_rounds)))
        self.allow_human_thief = bool(allow_human_thief)
        self.elimination_mode = bool(elimination_mode)
        self.sudden_death = False
        self.round_number = 0
        self.phase = "waiting"
        self.active = False
        # None means the thief is the virtual role. A real user id is used
        # only when the optional human-thief setting is enabled.
        self.thief_id: Optional[int] = None
        self.start_floor: Optional[int] = None
        self.current_floor: Optional[int] = None
        self.directions: List[str] = []
        self.direction_duration = 0
        self.answers: Dict[int, int] = {}
        self.round_winners: List[int] = []
        self.round_winner_type = ""
        self.round_winner_id: Optional[int] = None
        self.round_winner_name = ""
        self.virtual_thief_wins = 0
        self.event_id = 0
        self.event_type = ""
        self.last_action = ""
        self.match_winner_id: Optional[int] = None
        self.match_winner_name = ""
        self.match_winner_type = ""
        self.match_finished = False
        self._round_resolved = False
        self._used_human_thief_ids: set[int] = set()
        self.answer_deadline: Optional[float] = None
        self.escape_deadline: Optional[float] = None

    @property
    def active_players(self):
        return [p for p in self.players if p.active]

    @property
    def investigators(self):
        return [p for p in self.active_players if p.user_id != self.thief_id]

    @property
    def virtual_thief(self) -> bool:
        return self.thief_id is None

    def stop(self):
        """Stop the match immediately and invalidate all pending phases."""
        self.active = False
        self.answer_deadline = None
        self.escape_deadline = None
        self.phase = "waiting"
        self.answers.clear()
        self._round_resolved = True

    def remove_player(self, user_id: int) -> bool:
        """Remove a room player without changing room membership."""
        player = next((p for p in self.players if p.user_id == user_id), None)
        if player is None:
            return False
        player.active = False
        self.answers.pop(user_id, None)
        if user_id == self.thief_id:
            self.stop()
            self._set_event("غادر اللص الطاولة. توقفت المباراة.", "GAME_STOPPED")
            return True
        if len(self.active_players) < 2 and self.active:
            self.stop()
            self._set_event("لم يعد هناك عدد كافٍ من اللاعبين. توقفت المباراة.", "GAME_STOPPED")
        return True

    def _find(self, uid: int) -> HuntPlayer:
        for p in self.players:
            if p.user_id == uid:
                return p
        raise ValueError("اللاعب غير موجود.")

    def _set_event(self, text: str, event_type: str):
        self.last_action = text
        self.event_type = event_type
        self.event_id += 1

    def _select_thief(self):
        """Select the hidden role without turning ordinary bots into thieves."""
        if not self.allow_human_thief:
            self.thief_id = None
            return

        # The optional role can only be assigned to a real human player.
        candidates = [p for p in self.active_players if not p.is_bot]
        if not candidates:
            raise ValueError("يجب وجود لاعب بشري واحد على الأقل لتفعيل دور اللص البشري.")

        unused = [p for p in candidates if p.user_id not in self._used_human_thief_ids]
        if not unused:
            self._used_human_thief_ids.clear()
            unused = candidates
        thief = random.choice(unused)
        self._used_human_thief_ids.add(thief.user_id)
        self.thief_id = thief.user_id

    def _generate_directions(self, floor: int):
        count = self.DIRECTIONS_START + (self.round_number - 1)
        result = []
        current = floor
        for _ in range(count):
            if current <= 1:
                direction = "أعلى"
            elif current >= 10:
                direction = "أسفل"
            else:
                direction = random.choice(("أعلى", "أسفل"))
            result.append(direction)
            current = min(10, current + 1) if direction == "أعلى" else max(1, current - 1)
        self.directions = result
        self.current_floor = current

    def start(self):
        if len(self.active_players) < 2:
            raise ValueError("يجب وجود لاعبين اثنين على الأقل.")
        if self.allow_human_thief and not any(not p.is_bot for p in self.active_players):
            raise ValueError("لا يوجد لاعب بشري يمكنه تولي دور اللص.")
        self.active = True
        self.match_finished = False
        self.round_number = 1
        self._begin_round()

    def _begin_round(self):
        self._round_resolved = False
        self.answers.clear()
        self.round_winners = []
        self.round_winner_type = ""
        self.round_winner_id = None
        self.round_winner_name = ""
        self.start_floor = None
        self.current_floor = None
        self.directions = []
        self.direction_duration = 0
        self.answer_deadline = None
        self.escape_deadline = None
        self._select_thief()

        if self.virtual_thief:
            # The virtual thief acts entirely inside the game engine. No bot
            # seat is consumed and no client action is required from a thief.
            self._choose_floor(random.randint(1, 10))
            return

        thief = self._find(self.thief_id)
        self.phase = "choose_floor"
        self._set_event("اللص يختار الطابق سرًا.", "THIEF_CHOOSE_FLOOR")

    def _choose_floor(self, floor: int):
        if not 1 <= int(floor) <= 10:
            raise ValueError("اختر طابقًا من 1 إلى 10.")
        self.start_floor = int(floor)
        self._generate_directions(self.start_floor)
        self.phase = "escape"
        self.answer_deadline = None
        self.escape_deadline = time.monotonic() + 4.2 + len(self.directions) * 0.65
        self._set_event(f"الجولة {self.round_number}. اللص في الطابق {self.start_floor}.", "ESCAPE_START")

    def _begin_answering(self):
        if self.phase == "answering":
            return
        if self.phase != "escape":
            raise ValueError("لا يمكن بدء الإجابة الآن.")
        self.phase = "answering"
        self.escape_deadline = None
        self.answer_deadline = time.monotonic() + 8.0
        self._set_event("اكتب رقم الطابق.", "ANSWER_START")

    def tick(self):
        if (self.active and self.phase == "escape" and self.escape_deadline is not None
                and time.monotonic() >= self.escape_deadline):
            self._begin_answering()
        if (
            self.active
            and self.phase == "answering"
            and not self._round_resolved
            and self.answer_deadline is not None
            and time.monotonic() >= self.answer_deadline
        ):
            self._resolve_if_ready(force=True)

    def action(self, uid: int, action: str, value: str = ""):
        if not self.active:
            raise ValueError("اللعبة ليست جارية.")
        player = self._find(uid)
        if not player.active:
            raise ValueError("أنت خارج المنافسة.")
        self.tick()

        if action == "choose_floor":
            if self.phase != "choose_floor" or uid != self.thief_id:
                raise ValueError("لا يمكنك اختيار الطابق الآن.")
            self._choose_floor(int(value))
            return self.state_for(uid)

        if action == "begin_answering":
            if uid not in {p.user_id for p in self.investigators}:
                raise ValueError("لا يمكن بدء الإجابة الآن.")
            if self.phase == "answering":
                return self.state_for(uid)
            if self.escape_deadline is not None and time.monotonic() < self.escape_deadline:
                raise ValueError("لم ينته سرد الاتجاهات بعد.")
            self._begin_answering()
            return self.state_for(uid)

        if action == "answer":
            if self.phase != "answering" or uid == self.thief_id:
                raise ValueError("الإجابة غير متاحة الآن.")
            if uid in self.answers:
                raise ValueError("تم اعتماد إجابتك بالفعل.")
            try:
                floor = int(value)
            except Exception:
                raise ValueError("اكتب رقم طابق من 1 إلى 10.")
            if not 1 <= floor <= 10:
                raise ValueError("اكتب رقم طابق من 1 إلى 10.")
            self.answers[uid] = floor
            self._resolve_if_ready()
            return self.state_for(uid)

        raise ValueError("الأمر غير معروف.")

    @staticmethod
    def _floor_ordinal(floor: Optional[int]) -> str:
        names = {
            1: "الأول", 2: "الثاني", 3: "الثالث", 4: "الرابع", 5: "الخامس",
            6: "السادس", 7: "السابع", 8: "الثامن", 9: "التاسع", 10: "العاشر",
        }
        return names.get(int(floor or 0), str(floor or "غير معروف"))

    def _resolve_if_ready(self, force: bool = False):
        if self._round_resolved or self.phase != "answering":
            return
        investigators = self.investigators
        if not investigators:
            return
        if not self.answers and not force:
            return

        # Every investigator gets the full authoritative eight-second window.
        # A correct answer from one investigator must never resolve the round
        # while another investigator still has time to answer. The round can
        # resolve early only after every investigator has submitted an answer;
        # otherwise it resolves when the server deadline expires.
        correct_uids = [
            uid
            for uid, floor in self.answers.items()
            if floor == self.current_floor
            and any(p.user_id == uid for p in investigators)
        ]
        if len(self.answers) < len(investigators) and not force:
            return

        # Resolve strictly from correctness, never from response speed.
        # Every investigator must have submitted an answer (or the full
        # authoritative 8-second window must have expired) before deciding.
        # If exactly one investigator is correct, that investigator wins.
        # If everybody is wrong, the thief wins. If two or more investigators
        # are correct, the round is a tie: nobody receives a round win.
        correct_uid = correct_uids[0] if len(correct_uids) == 1 else None
        multiple_correct = len(correct_uids) > 1
        self.answer_deadline = None
        self._round_resolved = True

        floor_name = self._floor_ordinal(self.current_floor)
        if multiple_correct:
            self.round_winners = list(correct_uids)
            self.round_winner_type = "tie"
            self.round_winner_id = None
            self.round_winner_name = "تعادل"
            self.last_action = (
                f"انتهت الجولة بالتعادل. اللص كان في الطابق {floor_name}."
            )
            self.event_type = "ROUND_TIE"
        elif correct_uid is not None:
            self.round_winners = [correct_uid]
            self._find(correct_uid).wins += 1
            self.round_winner_type = "investigator"
            self.round_winner_id = correct_uid
            self.round_winner_name = self._find(correct_uid).name
            self.last_action = f"الفائز {self.round_winner_name}، اللص كان في الطابق {floor_name}."
            self.event_type = "ROUND_WIN"
        else:
            self.round_winner_type = "thief"
            self.round_winner_id = self.thief_id
            self.round_winner_name = (
                self._find(self.thief_id).name
                if self.thief_id is not None
                else self.VIRTUAL_THIEF_NAME
            )
            if self.virtual_thief:
                self.virtual_thief_wins += 1
            else:
                self._find(self.thief_id).wins += 1
            self.last_action = f"اللص كان في الطابق {floor_name}."
            self.event_type = "THIEF_WIN"
        self.event_id += 1
        self._advance_match_or_round()

    def _advance_match_or_round(self):
        if self.round_number < self.total_rounds:
            self.phase = "round_result"
            return

        # The configured number is the normal phase. A tie at that point must
        # never produce a draw: continue with mandatory sudden-death rounds
        # until there is a unique winner. In elimination mode, remove a unique
        # lowest scorer and continue with the remaining players.
        if self.elimination_mode:
            if self._eliminate_lowest_if_possible():
                if len(self.active_players) <= 1:
                    self._resolve_match()
                    return
                self.sudden_death = False
                self.phase = "round_result"
                return
            # In elimination mode a tied lowest score is itself a tie-break
            # situation. Do not declare the highest scorer the winner yet;
            # play mandatory rounds until one lowest scorer can be eliminated.
            self.sudden_death = True
            self.phase = "round_result"
            return

        if self._has_unique_match_winner():
            self._resolve_match()
            return

        self.sudden_death = True
        self.phase = "round_result"

    def continue_after_round(self):
        if not self.active or self.phase != "round_result":
            return self.state()
        if len(self.active_players) < 2:
            self._resolve_match()
            return self.state()
        self.round_number += 1
        self._begin_round()
        return self.state()

    def _competition_scores(self):
        scores = [(p.user_id, p.wins) for p in self.active_players]
        if self.virtual_thief:
            scores.append((None, self.virtual_thief_wins))
        return scores

    def _has_unique_match_winner(self):
        scores = self._competition_scores()
        if not scores:
            return False
        top = max(score for _, score in scores)
        return sum(1 for _, score in scores if score == top) == 1

    def _eliminate_lowest_if_possible(self):
        """Eliminate one unique lowest-scoring room player in elimination mode."""
        players = self.active_players
        if len(players) <= 1:
            return False
        lowest = min(p.wins for p in players)
        candidates = [p for p in players if p.wins == lowest]
        if len(candidates) != 1:
            # No player can be eliminated safely while the bottom score is tied.
            # Continue mandatory rounds until the lowest score becomes unique.
            return False
        player = candidates[0]
        player.active = False
        self.answers.pop(player.user_id, None)
        self._set_event(
            f"تم إقصاء {player.name}. تستمر المباراة باللاعبين المتبقين.",
            "PLAYER_ELIMINATED",
        )
        return True

    def _resolve_match(self):
        active_players = self.active_players
        if not active_players and not self.virtual_thief:
            self.stop()
            return

        if self.elimination_mode and len(active_players) == 1:
            winner = active_players[0]
            self.match_winner_id = winner.user_id
            self.match_winner_name = winner.name
            self.match_winner_type = "player"
            self.match_finished = True
            self.active = False
            self.phase = "match_finished"
            score_parts = [f"{p.name} {p.wins} جولات" for p in self.players if p.wins or p.active]
            if self.virtual_thief_wins:
                score_parts.append(f"{self.VIRTUAL_THIEF_NAME} {self.virtual_thief_wins} جولات")
            score_text = "، ".join(score_parts)
            winner_text = f"الفائز: {winner.name}."
            self._set_event(
                f"{winner_text} {score_text}. عدد الجولات {self.round_number}.",
                "MATCH_WIN",
            )
            return

        scores = self._competition_scores()
        if not scores:
            self.stop()
            return
        top = max(score for _, score in scores)
        leaders = [uid for uid, score in scores if score == top]

        # This method is only reached when the game has a unique winner.
        # Keep a defensive fallback so a race cannot publish a draw.
        if len(leaders) != 1:
            self.sudden_death = True
            self.phase = "round_result"
            self.match_finished = False
            self.active = True
            return

        winner_id = leaders[0]
        if winner_id is None:
            self.match_winner_id = None
            self.match_winner_name = self.VIRTUAL_THIEF_NAME
            self.match_winner_type = "virtual_thief"
        else:
            winner = self._find(winner_id)
            self.match_winner_id = winner.user_id
            self.match_winner_name = winner.name
            self.match_winner_type = "player"

        self.match_finished = True
        self.active = False
        self.phase = "match_finished"
        score_parts = [f"{p.name} {p.wins} جولات" for p in self.players if p.wins or p.active]
        if self.virtual_thief_wins:
            score_parts.append(f"{self.VIRTUAL_THIEF_NAME} {self.virtual_thief_wins} جولات")
        score_text = "، ".join(score_parts)
        if winner_id is None:
            winner_text = "الفائز: اللص."
        else:
            winner_text = f"الفائز: {self.match_winner_name}."
        self._set_event(
            f"{winner_text} {score_text}. عدد الجولات {self.round_number}.",
            "MATCH_WIN",
        )

    def state_for(self, viewer_id: int):
        self.tick()
        is_thief = viewer_id == self.thief_id and self.thief_id is not None
        revealed = self.phase in ("round_result", "match_finished")
        thief_name = ""
        if revealed or is_thief:
            thief_name = (
                self._find(self.thief_id).name
                if self.thief_id is not None
                else self.VIRTUAL_THIEF_NAME
            )

        # During the answering window, each investigator may see only their own
        # submitted answer. Revealing other investigators' answers would allow
        # later players to copy them and changes the game's information model.
        if revealed:
            visible_answers = [
                {"user_id": uid, "name": self._find(uid).name, "floor": floor}
                for uid, floor in self.answers.items()
            ]
        elif viewer_id in self.answers:
            visible_answers = [{
                "user_id": viewer_id,
                "name": self._find(viewer_id).name,
                "floor": self.answers[viewer_id],
            }]
        else:
            visible_answers = []

        round_scores = {str(p.user_id): p.wins for p in self.players}
        if self.virtual_thief:
            round_scores["virtual_thief"] = self.virtual_thief_wins
        data = {
            "game": "THIEF_HUNT",
            "active": self.active,
            "phase": self.phase,
            "round_number": self.round_number,
            "total_rounds": self.total_rounds,
            "played_rounds": self.round_number,
            "sudden_death": self.sudden_death,
            "elimination_mode": self.elimination_mode,
            "round_scores": round_scores,
            "rounds_won_total": sum(round_scores.values()),
            "direction_duration": self.direction_duration,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "last_action": self.last_action,
            "thief_name": thief_name,
            "thief_id": self.thief_id if (revealed or is_thief) else None,
            "thief_virtual": self.virtual_thief,
            "is_thief": is_thief,
            "start_floor": self.start_floor if (is_thief or self.phase in ("escape", "answering", "round_result", "match_finished")) else None,
            "directions": list(self.directions) if self.phase in ("escape", "answering", "round_result", "match_finished") else [],
            "final_floor": self.current_floor if self.phase in ("round_result", "match_finished") else None,
            "answer_seconds_remaining": max(0, int(self.answer_deadline - time.monotonic() + 0.999)) if self.phase == "answering" and self.answer_deadline is not None else 0,
            "answers": visible_answers,
            "round_winners": list(self.round_winners),
            "round_winner_type": self.round_winner_type,
            "round_winner_id": self.round_winner_id,
            "round_winner_name": self.round_winner_name,
            "virtual_thief_wins": self.virtual_thief_wins,
            "match_winner_id": self.match_winner_id,
            "match_winner_name": self.match_winner_name,
            "match_winner_type": self.match_winner_type,
            "players": [
                {
                    "user_id": p.user_id,
                    "name": p.name,
                    "wins": p.wins,
                    "active": p.active,
                    "eliminated": not p.active,
                    # Never mark a bot as the thief in virtual-thief mode.
                    "is_thief": (p.user_id == self.thief_id) if (revealed or is_thief) else False,
                }
                for p in self.players
            ],
        }
        return data

    def state(self):
        if not self.active_players:
            return {"game": "THIEF_HUNT", "active": False, "phase": "waiting", "players": []}
        return self.state_for(self.active_players[0].user_id)
