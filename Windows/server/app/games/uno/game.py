"""Authoritative configurable UNO game engine.

The selectable variants are based on the rules document supplied with the project.
"""
import random
from typing import List, Dict, Optional, Set, Tuple
from core_shared.constants import COLORS, DARK_COLORS, ALL_COLORS, COLOR_NAMES_AR, UNO_PENALTY_CARDS, CARD_SCORES
from core_shared.uno_rules import is_card_playable, WILD_TYPES
from server.app.games.uno.deck import Card, create_uno_deck

class Player:
    def __init__(self, user_id: int, name: str):
        self.user_id = user_id
        self.name = name
        self.hand: List[Card] = []
        self.eliminated = False

class UnoGame:
    def __init__(self, players_info: List[Tuple[int, str]], target_score: int = 500, rules: Optional[dict] = None, round_number: int = 1):
        if not (2 <= len(players_info) <= 10):
            raise ValueError("UNO requires between 2 and 10 players.")
        self.players = [Player(uid, name) for uid, name in players_info]
        self.target_score = target_score
        self.rules = dict(rules or {})
        self.round_number = int(round_number)
        self.deck: List[Card] = create_uno_deck(self.rules)
        self.discard: List[Card] = []
        self.turn_index = 0
        self.direction = 1
        self.current_color = ""
        self.dark_side = False
        self.active = False
        self.winner_id: Optional[int] = None
        self.drawn_card: Dict[int, Card] = {}
        self.pending_uno: Set[int] = set()
        self.last_action = ""
        self.round_score = 0
        self.event_id = 0
        self.event_type = ""
        self.sound_cue = ""
        self.pending_draw_count = 0
        self.pending_draw_type = ""
        self.buzzer_pending: Set[int] = set()
        self.buzzer_order: List[int] = []
        self.pending_exchange_user: Optional[int] = None
        self.pending_bluff: Optional[dict] = None
        # Score penalties earned during a round (for example elimination).
        # The room manager consumes these adjustments exactly once.
        self.pending_score_adjustments: Dict[int, int] = {}

    @property
    def current_player(self) -> Player:
        return self.players[self.turn_index]

    @property
    def active_players(self):
        return [p for p in self.players if not p.eliminated]

    def _find_player(self, user_id: int) -> Player:
        for p in self.players:
            if p.user_id == user_id:
                return p
        raise ValueError("Player not found in game.")

    def remove_player(self, user_id: int):
        """Remove a player while preserving authoritative turn/pending state."""
        idx = next((i for i, p in enumerate(self.players) if p.user_id == user_id), None)
        if idx is None:
            return False
        was_current = idx == self.turn_index
        self.pending_uno.discard(user_id)
        self.buzzer_pending.discard(user_id)
        self.buzzer_order = [uid for uid in self.buzzer_order if uid != user_id]
        self.drawn_card.pop(user_id, None)
        if self.pending_exchange_user == user_id:
            self.pending_exchange_user = None
        if self.pending_bluff:
            if self.pending_bluff.get("target_id") == user_id:
                self.pending_bluff = None
            elif self.pending_bluff.get("bluffer_id") == user_id:
                self.pending_bluff = None

        self.players.pop(idx)
        if not self.players:
            self.active = False
            self.winner_id = None
            self.turn_index = 0
            return True

        if idx < self.turn_index:
            self.turn_index -= 1
        elif idx == self.turn_index:
            self.turn_index = min(self.turn_index, len(self.players) - 1)

        # Re-home the turn on an active player if the removed player owned it.
        if was_current:
            self.turn_index = self._next_index(self.turn_index, 0)
            if self.players[self.turn_index].eliminated:
                self._advance()

        if self.buzzer_pending and len(self.buzzer_order) >= len(self.buzzer_pending):
            self._finish_buzzer()

        active = self.active_players
        if self.active and len(active) <= 1:
            if active:
                self._round_winner(active[0])
            else:
                self.active = False
        return True

    def _next_index(self, index: int, steps: int = 1) -> int:
        if not self.players:
            return index
        i = index
        for _ in range(steps):
            i = (i + self.direction) % len(self.players)
            while self.players[i].eliminated and i != index:
                i = (i + self.direction) % len(self.players)
        return i

    def _draw_card(self) -> Optional[Card]:
        if not self.deck:
            if len(self.discard) <= 1:
                return None
            self.deck = self.discard[:-1]
            self.discard = [self.discard[-1]]
            for c in self.deck:
                if c.is_wild:
                    c.color = "wild"
            random.shuffle(self.deck)
        return self.deck.pop() if self.deck else None

    def _advance(self, steps: int = 1):
        self.turn_index = self._next_index(self.turn_index, steps)
        self.drawn_card.pop(self.current_player.user_id, None)

    def _set_event(self, text: str, event_type: str, sound_cue: str = ""):
        self.event_id += 1
        self.event_type = event_type
        self.sound_cue = sound_cue or ""
        self.last_action = text

    def _can_stack_draw(self, card_type: str) -> bool:
        if not self.pending_draw_count:
            return True
        if card_type == self.pending_draw_type:
            return True
        if not self.rules.get("responses") and not self.rules.get("advanced_responses"):
            return False
        # No Mercy response hierarchy: only cards from the same family may
        # be stacked, and only an equal/stronger draw value may answer.
        normal = {"draw_two": 2, "draw_four": 4, "draw_five": 5}
        wild = {"wild_draw_two": 2, "wild_draw_six": 6, "wild_draw_ten": 10}
        if self.rules.get("no_mercy"):
            if self.pending_draw_type in normal and card_type in normal:
                return normal[card_type] >= normal.get(self.pending_draw_type, 0)
            if self.pending_draw_type in wild and card_type in wild:
                return wild[card_type] >= wild.get(self.pending_draw_type, 0)
        return card_type == self.pending_draw_type

    def _is_playable_for_player(self, card: Card, top: Card, player: Player) -> bool:
        if self.pending_draw_count:
            if card.card_type == self.pending_draw_type:
                return True
            if self.rules.get("advanced_responses") and card.card_type in ("skip", "reverse", "wild"):
                return True
            return False
        if self.rules.get("super_interceptions"):
            # Used only for out-of-turn interception checks; normal turn play
            # still follows ordinary UNO matching.
            pass
        return is_card_playable(card.to_dict(), top.to_dict(), self.current_color)

    def _score_hand(self, hand):
        total = 0
        for c in hand:
            total += (c.value or 0) if c.card_type == "number" else CARD_SCORES.get(c.card_type, 0)
        return total

    def _round_winner(self, player: Player):
        self.active = False
        self.winner_id = player.user_id
        self.round_score = sum(self._score_hand(p.hand) for p in self.players if p.user_id != player.user_id and not p.eliminated)
        self._set_event(f"{player.name} فاز", "ROUND_WON", "ROUND_END")

    def _deal_start_card(self):
        top = self._draw_card()
        # A starting wild draw card is not used as the opening card.
        invalid_start = (
            "wild_draw_four", "wild_draw_two", "wild_draw_six",
            "wild_draw_ten", "wild_reverse_draw_four", "color_roulette"
        )
        while top and top.card_type in invalid_start:
            self.deck.insert(0, top)
            top = self._draw_card()
        self.discard.append(top)
        self.current_color = random.choice(COLORS if not self.dark_side else DARK_COLORS) if top.is_wild else top.color
        return top

    def _transform_flip_side(self):
        light_to_dark = dict(zip(COLORS, DARK_COLORS))
        dark_to_light = dict(zip(DARK_COLORS, COLORS))
        color_map = light_to_dark if self.dark_side else dark_to_light
        type_map = {
            (True, "skip"): "skip_everyone",
            (False, "skip_everyone"): "skip",
            (True, "draw_two"): "draw_five",
            (False, "draw_five"): "draw_two",
            (True, "wild"): "color_roulette",
            (False, "color_roulette"): "wild",
            (True, "wild_draw_two"): "wild_draw_four",
            (False, "wild_draw_four"): "wild_draw_two",
        }
        def transform(card):
            if card.color in color_map:
                card.color = color_map[card.color]
            key = (self.dark_side, card.card_type)
            if key in type_map:
                card.card_type = type_map[key]
            if card.card_type == "flip":
                card.color = "wild"
        for collection in (self.deck, self.discard):
            for card in collection:
                transform(card)
        for p in self.players:
            for card in p.hand:
                transform(card)

    def start(self):
        if self.active:
            raise RuntimeError("Game is already active.")
        if len(self.active_players) < 2:
            raise RuntimeError("UNO requires at least two active players.")
        self.direction = 1
        self.turn_index = 0
        self.current_color = ""
        self.dark_side = False
        self.winner_id = None
        self.drawn_card.clear()
        self.pending_uno.clear()
        self.pending_draw_count = 0
        self.pending_draw_type = ""
        self.buzzer_pending.clear()
        self.buzzer_order.clear()
        self.pending_exchange_user = None
        self.pending_bluff = None
        self.pending_score_adjustments.clear()
        self.round_score = 0
        self.discard.clear()
        self.deck = create_uno_deck(self.rules)
        for p in self.players:
            p.hand.clear()
            p.eliminated = False
        for _ in range(7):
            for p in self.players:
                p.hand.append(self._draw_card())
        top = self._deal_start_card()
        self.active = True
        self.turn_index = 0
        if top.card_type == "reverse":
            self.direction *= -1
            if len(self.players) == 2:
                self._advance()
        elif top.card_type == "skip":
            self._advance()
        elif top.card_type == "draw_two":
            if self.rules.get("responses"):
                self.pending_draw_count = 2
                self.pending_draw_type = "draw_two"
                self._advance()
            else:
                self.current_player.hand.extend([self._draw_card(), self._draw_card()])
                self._advance()
        self._set_event(f"الجولة {self.round_number}", "ROUND_START", "UNO_DEAL")

    def state_for(self, viewer_id: int) -> dict:
        try:
            viewer = self._find_player(viewer_id)
            hand_cards = [c.to_dict(include_id=True) for c in viewer.hand]
            drawn_id = self.drawn_card[viewer_id].card_id if viewer_id in self.drawn_card else None
        except ValueError:
            hand_cards = []
            drawn_id = None
        return {
            "active": self.active,
            "winner_id": self.winner_id,
            "current_player_id": self.current_player.user_id if self.players else None,
            "current_player_name": self.current_player.name if self.players else "",
            "current_color": self.current_color,
            "top_card": self.discard[-1].to_dict(include_id=True) if self.discard else None,
            "players": [{"user_id": p.user_id, "name": p.name, "card_count": len(p.hand), "eliminated": p.eliminated} for p in self.players],
            "hand": hand_cards,
            "drawn_card_id": drawn_id,
            "pending_uno_players": [{"user_id": p.user_id, "name": p.name} for p in self.players if p.user_id in self.pending_uno],
            "target_score": self.target_score,
            "round_score": self.round_score,
            "last_action": self.last_action,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "sound_cue": self.sound_cue,
            "rules": self.rules,
            "pending_draw_count": self.pending_draw_count,
            "buzzer_pending": bool(self.buzzer_pending),
            "pending_exchange_user": self.pending_exchange_user,
            # Bluff resolution is private to the player who must respond;
            # score adjustments are internal server state and must never be
            # exposed to clients.
            "pending_bluff": (dict(self.pending_bluff) if self.pending_bluff and self.pending_bluff.get("target_id") == viewer_id else None),
            "dark_side": self.dark_side,
            "score_adjustments": {},
        }

    def _finish_buzzer(self):
        if not self.buzzer_order:
            return
        slowest = self._find_player(self.buzzer_order[-1])
        self._draw_penalty(slowest, 2)
        self._set_event(f"{slowest.name} كان الأبطأ وسحب كارتين", "BUZZER_PENALTY", "CARD_DRAW_TWO")
        self.buzzer_pending.clear()
        self.buzzer_order.clear()
        if not self._check_zero_card_winner():
            # The buzzer card has consumed the current turn; after the global
            # response window is resolved, continue with the next active player.
            if self.active and self.players:
                self._advance()

    def _check_zero_card_winner(self):
        if not self.active:
            return False
        if self.pending_draw_count or self.pending_bluff or self.pending_exchange_user is not None or self.buzzer_pending:
            return False
        for p in self.active_players:
            if len(p.hand) == 0:
                self._round_winner(p)
                return True
        return False

    def _handle_buzzer(self, user_id):
        if user_id not in self.buzzer_pending:
            raise ValueError("لا يوجد جرس الآن.")
        if user_id in self.buzzer_order:
            return
        self.buzzer_order.append(user_id)
        if len(self.buzzer_order) == len(self.buzzer_pending):
            self._finish_buzzer()
        else:
            self._set_event(f"{self._find_player(user_id).name} ضغط الجرس", "BUZZER_PRESSED")

    def _apply_zero_seven(self, player, card):
        if not self.rules.get("zero_seven") or card.card_type != "number":
            return
        if card.value == 0:
            active = self.active_players
            if len(active) > 1:
                hands = [list(p.hand) for p in active]
                order = list(range(len(active))) if self.direction == 1 else list(reversed(range(len(active))))
                for idx, src in enumerate(order):
                    active[order[(idx + 1) % len(order)]].hand = hands[src]
                self.pending_uno = {p.user_id for p in active if len(p.hand) == 1}
            self._set_event(f"{player.name} لعب 0 ومرر الأيدي", "ZERO_PASSED_HANDS")

    def _auto_straight_cards(self, player, first_card):
        if not self.rules.get("straights") or first_card.card_type != "number":
            return []
        same_color = [c for c in player.hand if c.card_type == "number" and c.color == first_card.color]
        by_value = {c.value: c for c in same_color}

        # Support both legal directions. Choose the longer available run; on
        # a tie, prefer ascending to keep the behaviour deterministic.
        asc = [first_card]
        value = first_card.value
        while value < 9 and (value + 1) in by_value:
            nxt = by_value[value + 1]
            asc.append(nxt)
            value += 1

        desc = [first_card]
        value = first_card.value
        while value > 0 and (value - 1) in by_value:
            nxt = by_value[value - 1]
            desc.append(nxt)
            value -= 1

        chosen = asc if len(asc) >= len(desc) else desc
        if len(chosen) < 2:
            return []
        for c in chosen[1:]:
            player.hand.remove(c)
            self.discard.append(c)
            self.current_color = c.color
        return chosen

    def _check_elimination(self, player):
        if self.rules.get("eliminate_too_many") and len(player.hand) >= 25 and not player.eliminated:
            player.eliminated = True
            player.hand.clear()
            self.pending_score_adjustments[player.user_id] = self.pending_score_adjustments.get(player.user_id, 0) - 250
            self._set_event(f"{player.name} أُقصي وسُجلت عليه 250 نقطة جزاء", "PLAYER_ELIMINATED")
            remaining = self.active_players
            if len(remaining) == 1:
                self._round_winner(remaining[0])
            elif self.active and self.players:
                # The eliminated player can never retain the authoritative turn.
                if self.current_player.user_id == player.user_id:
                    self._advance()
                elif self.current_player.eliminated:
                    self.turn_index = self._next_index(self.turn_index, 0)
            return True
        return False

    def _draw_penalty(self, player, count):
        drawn = []
        for _ in range(count):
            c = self._draw_card()
            if c:
                player.hand.append(c)
                drawn.append(c)
        self._check_elimination(player)
        return drawn

    def action(self, user_id: int, action_type: str, card_id: str = "", chosen_color: str = ""):
        if not self.active:
            raise RuntimeError("The game has ended or not started.")
        player = self._find_player(user_id)
        act = (action_type or "").strip().lower()

        # Buzzer is a global interruption state. While it is pending, the only
        # legal action for every active player is to press the buzzer.
        if self.buzzer_pending:
            if act != "buzzer":
                raise ValueError("يجب ضغط الجرس أولًا.")
            if not self.rules.get("buzzer"):
                raise ValueError("قاعدة الجرس غير مفعلة.")
            return self._handle_buzzer(user_id)

        if act == "buzzer":
            if not self.rules.get("buzzer"):
                raise ValueError("قاعدة الجرس غير مفعلة.")
            raise ValueError("لا يوجد جرس معلق الآن.")

        # A Wild Draw Four with Bluff creates a mandatory decision window.
        # The target may only challenge or accept the penalty by drawing; no
        # normal play, interception, UNO catch, or other action may bypass it.
        if self.pending_bluff:
            target_id = self.pending_bluff["target_id"]
            if user_id != target_id:
                raise ValueError("يوجد تحدي خداع معلق للاعب التالي فقط.")
            if act not in ("challenge_bluff", "bluff", "draw"):
                raise ValueError("يجب تحدي الخداع أو سحب 4 كروت.")

        if self.pending_exchange_user is not None and act != "exchange_hand":
            if user_id == self.pending_exchange_user:
                raise ValueError("يجب إكمال تبديل اليد أولًا.")
            raise ValueError("هناك تبديل أيدي معلق ويجب إكماله أولًا.")

        if act in ("challenge_bluff", "bluff"):
            if not self.rules.get("bluff") or not self.pending_bluff:
                raise ValueError("لا يوجد تحدي خداع متاح الآن.")
            if user_id != self.pending_bluff["target_id"]:
                raise ValueError("التحدي متاح للاعب التالي فقط.")
            bluffer = self._find_player(self.pending_bluff["bluffer_id"])
            target = self._find_player(user_id)
            had_matching_color = bool(self.pending_bluff.get("had_matching_color"))
            self.pending_bluff = None
            if had_matching_color:
                self._draw_penalty(bluffer, 4)
                self._set_event(f"{target.name} كشف خداع {bluffer.name}، و{bluffer.name} سحب 4 كروت جزاء", "BLUFF_CAUGHT", "BLUFF_CHALLENGE")
                if not self._check_zero_card_winner():
                    pass
                return
            self._draw_penalty(target, 6)
            self._set_event(f"{target.name} اتهم بالخداع خطأ وسحب 6 كروت", "BLUFF_FALSE", "BLUFF_CHALLENGE")
            if not self._check_zero_card_winner():
                self._advance()
            return

        if act in ("call_uno", "uno"):
            if len(player.hand) == 1 and user_id in self.pending_uno:
                self.pending_uno.discard(user_id)
                self._set_event(f"{player.name} قال UNO", "UNO_CALLED", "UNO_CALLED")
                return
            other_pending = [uid for uid in self.pending_uno if uid != user_id]
            if other_pending:
                target = self._find_player(other_pending[0])
                self._draw_penalty(target, UNO_PENALTY_CARDS)
                self.pending_uno.discard(target.user_id)
                self._set_event(f"{target.name} لم يقل UNO وأخذ {UNO_PENALTY_CARDS} كروت جزاء", "UNO_CAUGHT", "UNO_PENALTY")
                return
            if len(player.hand) == 1:
                self._set_event(f"{player.name} قال UNO", "UNO_CALLED", "UNO_CALLED")
                return
            raise ValueError("لا يوجد أونو لإعلانه حاليًا.")

        if act == "catch_uno":
            target_id = int(card_id) if card_id else (list(self.pending_uno)[0] if self.pending_uno else 0)
            target = self._find_player(target_id)
            if target_id not in self.pending_uno:
                raise ValueError("لا يوجد مخالفة أونو على هذا اللاعب.")
            self._draw_penalty(target, UNO_PENALTY_CARDS)
            self.pending_uno.discard(target_id)
            self._set_event(f"{target.name} لم يقل UNO وأخذ {UNO_PENALTY_CARDS} كروت جزاء", "UNO_CAUGHT", "UNO_PENALTY")
            return

        # Interception is allowed outside the normal turn only when the exact
        # same card is on top, or when Super Interceptions is enabled and the
        # number/symbol matches.
        top = self.discard[-1]
        if player.user_id != self.current_player.user_id:
            # Only an actual play may use an interception. Never change the
            # authoritative turn merely because a player attempted another action.
            if act != "play":
                raise ValueError("ليس دورك للعب.")
            if self.rules.get("interceptions") or self.rules.get("super_interceptions"):
                candidate = next((c for c in player.hand if c.card_id == card_id), None)
                if not candidate or candidate.is_wild:
                    raise ValueError("لا يمكن الاعتراض بهذا الكارت.")
                exact = candidate.card_type == top.card_type and candidate.color == top.color and (candidate.value == top.value if candidate.card_type == "number" else True)
                super_match = candidate.card_type == top.card_type and (candidate.value == top.value if candidate.card_type == "number" else True)
                if not ((self.rules.get("interceptions") and exact) or (self.rules.get("super_interceptions") and super_match)):
                    raise ValueError("كارت الاعتراض غير مطابق.")
                self.turn_index = self.players.index(player)
            else:
                raise ValueError("ليس دورك للعب.")

        if act == "draw":
            if self.pending_bluff:
                if user_id != self.pending_bluff["target_id"]:
                    raise ValueError("ليس دورك لتنفيذ عقوبة السحب.")
                count = 4
                self.pending_bluff = None
                self._draw_penalty(player, count)
                self._set_event(f"{player.name} سحب 4 كروت", "DRAW_PENALTY", "CARD_WILD_DRAW_FOUR")
                if not self._check_zero_card_winner():
                    self._advance()
                return
            if self.pending_draw_count:
                count = self.pending_draw_count
                self.pending_draw_count = 0
                self.pending_draw_type = ""
                self._draw_penalty(player, count)
                self._set_event(f"{player.name} سحب {count} كروت جزاء", "DRAW_PENALTY", "CARD_DRAW_TWO" if count == 2 else "CARD_DRAW")
                if not self._check_zero_card_winner():
                    self._advance()
                return
            # Standard UNO draw rule: if the player has any playable card,
            # drawing voluntarily is not allowed. Wild cards are playable too.
            # Penalty draws above this block are exempt because they are forced.
            playable_in_hand = any(
                self._is_playable_for_player(c, self.discard[-1], player)
                for c in player.hand
            )
            if playable_in_hand:
                raise ValueError("لديك كارت قابل للعب، لا يمكنك السحب الآن.")

            card = self._draw_card()
            if card:
                player.hand.append(card)
                if self._check_elimination(player):
                    return
                if self.rules.get("draw_until_playable"):
                    while not self._is_playable_for_player(card, self.discard[-1], player):
                        card = self._draw_card()
                        if not card:
                            break
                        player.hand.append(card)
                        if self._check_elimination(player):
                            return
            playable = self._is_playable_for_player(card, self.discard[-1], player) if card else False
            if playable and not self.rules.get("skip_after_draw"):
                self.drawn_card[user_id] = card
                self._set_event(f"{player.name} سحب كارت", "CARD_DRAWN", "CARD_DRAW")
            else:
                self.drawn_card.pop(user_id, None)
                self._advance()
                self._set_event(f"{player.name} سحب كارت", "CARD_DRAWN_AND_PASSED", "CARD_DRAW")
            return

        if act == "exchange_hand":
            if not self.rules.get("zero_seven") or self.pending_exchange_user != user_id:
                raise ValueError("لا يوجد تبديل أيدي معلق.")
            target = self._find_player(int(card_id))
            if target.user_id == user_id or target.eliminated:
                raise ValueError("يجب اختيار لاعب آخر غير مقصى للتبديل.")
            player.hand, target.hand = target.hand, player.hand
            self.pending_exchange_user = None
            for p in (player, target):
                if len(p.hand) == 1:
                    self.pending_uno.add(p.user_id)
                else:
                    self.pending_uno.discard(p.user_id)
            self._set_event(f"{player.name} بدّل يده مع {target.name}", "SEVEN_EXCHANGE")
            if not self._check_zero_card_winner():
                self._advance()
            return

        if act == "play":
            card = next((c for c in player.hand if c.card_id == card_id), None)
            if not card:
                raise ValueError("الكارت المحدد غير موجود في يدك.")
            drawn = self.drawn_card.get(user_id)
            if drawn is not None and card.card_id != drawn.card_id:
                raise ValueError("بعد السحب يمكنك لعب الكارت المسحوب فقط.")
            if self.pending_draw_count and not self._can_stack_draw(card.card_type):
                if not (self.rules.get("advanced_responses") and card.card_type in ("skip", "reverse", "wild")):
                    raise ValueError("يجب الرد بكارت سحب مناسب أو تنفيذ السحب.")
            elif not self._is_playable_for_player(card, self.discard[-1], player):
                raise ValueError("الكارت المحدد غير صالح للعب الآن.")
            chosen_color = (chosen_color or "").strip().lower()
            # The Buzzer is a wild-like color-changing card in this ruleset:
            # the client already opens the same color selector for it, so the
            # server must validate and persist the selected effective color.
            color_changing = card.is_wild or card.card_type == "buzzer"
            if color_changing and chosen_color not in (COLORS + DARK_COLORS):
                raise ValueError("يجب اختيار لون بعد لعب كارت بري.")

            previous_color = self.current_color
            player.hand.remove(card)
            self.discard.append(card)
            # Preserve pending UNO violations for other players. A play only
            # clears the current player's own pending violation.
            self.pending_uno.discard(user_id)
            self.current_color = chosen_color if color_changing else card.color
            self.drawn_card.pop(user_id, None)
            played_text = f"{player.name} لعب {card.display_name_ar}"
            if card.is_wild:
                played_text += f" {COLOR_NAMES_AR.get(chosen_color, chosen_color)}"
            event_type = "SPECIAL_CARD_PLAYED" if card.card_type != "number" else "CARD_PLAYED"
            sound_cue = "" if card.card_type == "number" else "place_special"
            if card.card_type == "draw_two":
                sound_cue = "CARD_DRAW_TWO"
            elif card.card_type == "wild_draw_four":
                sound_cue = "CARD_WILD_DRAW_FOUR"
            elif card.card_type in ("wild", "wild_draw_two", "wild_draw_six", "wild_draw_ten", "color_roulette"):
                sound_cue = "CARD_WILD_COLOR"
            elif card.card_type == "skip":
                sound_cue = "CARD_SKIP"
            elif card.card_type == "reverse":
                sound_cue = "CARD_REVERSE"

            if card.card_type == "buzzer":
                self.buzzer_pending = {p.user_id for p in self.active_players}
                self.buzzer_order = []
                self._set_event(f"{player.name} لعب الجرس", "BUZZER_STARTED", "place_special")
                return

            if card.card_type == "color_roulette" and self.rules.get("color_roulette"):
                if chosen_color not in (COLORS + DARK_COLORS):
                    raise ValueError("اختر لونًا لعجلة الألوان.")
                self._advance()
                target = self.current_player
                count = 0
                while True:
                    drawn = self._draw_card()
                    if not drawn:
                        break
                    target.hand.append(drawn)
                    count += 1
                    if drawn.color == chosen_color or count > 100:
                        break
                self._check_elimination(target)
                played_text += f" — {target.name} سحب حتى وجد {COLOR_NAMES_AR.get(chosen_color, chosen_color)}"
                self._set_event(played_text, event_type, sound_cue)
                if not self._check_zero_card_winner():
                    if len(player.hand) == 1:
                        self.pending_uno.add(user_id)
                return

            if card.card_type == "wild_reverse_draw_four" and self.rules.get("wild_reverse_draw_four"):
                self.direction *= -1
                self._advance()
                target = self.current_player
                self._draw_penalty(target, 4)
                played_text += f" — {target.name} سحب 4 كروت"
                self._set_event(played_text, event_type, sound_cue)
                if not self._check_zero_card_winner():
                    if len(player.hand) == 1:
                        self.pending_uno.add(user_id)
                    self._advance()
                return

            if card.card_type == "flip" and self.rules.get("uno_flip"):
                self.dark_side = not self.dark_side
                self._transform_flip_side()
                colors = DARK_COLORS if self.dark_side else COLORS
                self.current_color = random.choice(colors)
                self._set_event(f"{player.name} قلب اللعبة", "FLIP")
                if not self._check_zero_card_winner():
                    if len(player.hand) == 1:
                        self.pending_uno.add(user_id)
                    self._advance()
                return

            if card.card_type == "discard_all" and self.rules.get("discard_all"):
                same_color = [c for c in list(player.hand) if c.color == card.color]
                for c in same_color:
                    player.hand.remove(c)
                    self.discard.append(c)
                played_text += f" — أسقط {len(same_color)} كروت"

            if card.card_type == "skip_everyone" and self.rules.get("skip_everyone"):
                self._set_event(played_text, event_type)
                if not self._check_zero_card_winner():
                    if len(player.hand) == 1:
                        self.pending_uno.add(user_id)
                return

            # Draw-chain rules.
            effective_card = card
            draw_value = {"draw_one": 1, "draw_two": 2, "wild_draw_two": 2, "wild_draw_four": 4, "draw_five": 5, "wild_draw_six": 6, "wild_draw_ten": 10, "wild_reverse_draw_four": 4}.get(card.card_type)
            if draw_value:
                if card.card_type == "wild_draw_four" and self.rules.get("bluff"):
                    had_matching_color = any((not c.is_wild) and c.color == previous_color for c in player.hand)
                    self._advance()
                    self.pending_bluff = {"bluffer_id": player.user_id, "target_id": self.current_player.user_id, "had_matching_color": had_matching_color}
                    played_text += " — اختر التحدي أو السحب"
                elif self.rules.get("responses") or self.rules.get("advanced_responses"):
                    if self.pending_draw_count and not self._can_stack_draw(card.card_type):
                        raise ValueError("لا يمكن وضع هذا الكارت في سلسلة السحب.")
                    self.pending_draw_count += draw_value
                    self.pending_draw_type = card.card_type
                    self._advance()
                    played_text += f" — السحب المطلوب {self.pending_draw_count}"
                else:
                    self._advance()
                    target = self.current_player
                    self._draw_penalty(target, draw_value)
                    played_text += f" — {target.name} سحب {draw_value} كروت"
                    self._advance()
            elif card.card_type == "reverse":
                if self.pending_draw_count and self.rules.get("advanced_responses"):
                    self.direction *= -1
                    self._advance()
                else:
                    self.direction *= -1
                    if len(self.active_players) == 2:
                        self._advance()
                    self._advance()
            elif card.card_type == "skip":
                if self.pending_draw_count and self.rules.get("advanced_responses"):
                    self._advance()
                else:
                    self._advance()
                    self._advance()
            else:
                seq = []
                if self.rules.get("straights") and card.card_type == "number":
                    seq = self._auto_straight_cards(player, card)
                    if seq:
                        played_text += f" — متتالية من {len(seq)} كروت"

                effective_card = seq[-1] if seq else card
                defer_advance = (
                    effective_card.card_type == "number"
                    and effective_card.value == 7
                    and self.rules.get("zero_seven")
                )
                if not defer_advance:
                    self._advance()

                if effective_card.card_type == "number":
                    if effective_card.value == 0 and self.rules.get("zero_seven"):
                        self._apply_zero_seven(player, effective_card)
                    if effective_card.value == 7 and self.rules.get("zero_seven"):
                        self.pending_exchange_user = user_id
                        played_text += " — اختر لاعبًا لتبديل اليد"

            if len(player.hand) == 0:
                # A zero-card hand does not end the round while a mandatory
                # special decision is still unresolved. This includes draw
                # chains, a +4 bluff challenge, a 7 exchange, and the buzzer
                # response window. The game must resolve that state first.
                if (self.pending_draw_count or self.pending_bluff or
                        self.pending_exchange_user is not None or self.buzzer_pending):
                    self._set_event(played_text, event_type, sound_cue)
                    return
                self._round_winner(player)
                return
            if not (effective_card.card_type == "number" and effective_card.value == 0 and self.rules.get("zero_seven")):
                if len(player.hand) == 1:
                    self.pending_uno.add(user_id)
            self._set_event(played_text, event_type, sound_cue)
            return

        raise ValueError("إجراء غير معروف.")
