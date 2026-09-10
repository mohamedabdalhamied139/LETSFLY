import random
import uuid
from typing import List, Dict, Optional, Tuple, Any

SUITS = ["hearts", "diamonds", "clubs", "spades"]

def create_deck(num_decks=2) -> List[Dict[str, Any]]:
    deck = []
    for _ in range(num_decks):
        for suit in SUITS:
            for val in range(1, 14):
                deck.append({"id": uuid.uuid4().hex[:8], "suit": suit, "value": val})
    random.shuffle(deck)
    return deck

class NinetyNineGame:
    def __init__(self, players: List[Tuple[int, str]], target_score: Optional[int] = None, rules: Optional[dict] = None):
        self.players = list(players)
        self.player_ids = [p[0] for p in players]
        self.player_names = {p[0]: p[1] for p in players}
        
        initial_tokens = 11
        if rules and "starting_tokens" in rules and rules["starting_tokens"] is not None:
            try:
                initial_tokens = int(rules["starting_tokens"])
            except (ValueError, TypeError):
                initial_tokens = 11
        elif target_score is not None:
            try:
                ts = int(target_score)
                initial_tokens = 11 if ts in (0, 99) else ts
            except (ValueError, TypeError):
                initial_tokens = 11

        self.starting_tokens = max(1, initial_tokens)
        self.tokens: Dict[int, int] = {uid: self.starting_tokens for uid in self.player_ids}
        self.eliminated: set[int] = set()
        
        self.active = False
        self.winner_id: Optional[int] = None
        self.round_finished = False
        
        self.dealer_index = 0
        self.current_turn_index = 0
        self.direction = 1
        
        self.deck: List[Dict[str, Any]] = []
        self.discard_pile: List[Dict[str, Any]] = []
        self.pile_value = 0
        
        self.hands: Dict[int, List[Dict[str, Any]]] = {uid: [] for uid in self.player_ids}
        
        self.pending_choice: Optional[Dict[str, Any]] = None
        
        self.round_number = 0
        self.event_id = 0
        self.event_type = ""
        self.last_action = ""
        self.sound_cue = ""
        
        self.start_new_round()
        
    @property
    def match_finished(self) -> bool:
        return self.winner_id is not None
        
    @property
    def active_players(self) -> List[int]:
        return [uid for uid in self.player_ids if uid not in self.eliminated]

    @property
    def current_player_id(self) -> int:
        return self.player_ids[self.current_turn_index]
        
    def start_new_round(self):
        self.round_finished = False
        active = self.active_players
        if len(active) <= 1:
            if len(active) == 1:
                self.winner_id = active[0]
            self.active = False
            wname = self.player_names.get(self.winner_id, "الفائز") if self.winner_id else "لا يوجد"
            scores_summary = "، ".join(f"{self.player_names.get(uid, 'لاعب')}: {self.tokens.get(uid, 0)}" for uid in self.player_ids)
            self.event_type = "MATCH_FINISHED"
            self.sound_cue = "MATCH_WIN"
            self.last_action = f"نهاية المباراة! الفائز: {wname}. النتائج: {scores_summary}"
            return
            
        self.round_number += 1
        self.active = True
        self.direction = 1
        self.pile_value = 0
        self.discard_pile = []
        self.pending_choice = None
        
        num_decks = 2 if len(self.players) <= 4 else 3
        self.deck = create_deck(num_decks)
        
        self.hands = {uid: [] for uid in self.player_ids}
        for _ in range(3):
            for uid in active:
                self.hands[uid].append(self.deck.pop())
                
        self.current_turn_index = (self.dealer_index + 1) % len(self.player_ids)
        while self.player_ids[self.current_turn_index] in self.eliminated:
            self.current_turn_index = (self.current_turn_index + 1) % len(self.player_ids)
            
        self.event_id += 1
        self.event_type = "ROUND_START"
        self.last_action = f"الجولة {self.round_number}"
        self.sound_cue = ""
        
    def _advance_turn(self, steps=1):
        for _ in range(steps):
            self.current_turn_index = (self.current_turn_index + self.direction) % len(self.player_ids)
            while self.player_ids[self.current_turn_index] in self.eliminated:
                self.current_turn_index = (self.current_turn_index + self.direction) % len(self.player_ids)
                
    def _deduct_token(self, uid: int, amount: int):
        if uid in self.eliminated:
            return
        self.tokens[uid] = max(0, self.tokens.get(uid, 0) - amount)
        if self.tokens[uid] == 0:
            self.eliminated.add(uid)
            self.hands[uid] = []
            
    def _check_eliminations(self):
        active = self.active_players
        if len(active) <= 1:
            if len(active) == 1:
                self.winner_id = active[0]
            self.active = False
            wname = self.player_names.get(self.winner_id, "الفائز") if self.winner_id else "لا يوجد"
            scores_summary = "، ".join(f"{self.player_names.get(uid, 'لاعب')}: {self.tokens.get(uid, 0)}" for uid in self.player_ids)
            self.event_type = "MATCH_FINISHED"
            self.sound_cue = "MATCH_WIN"
            self.last_action = f"نهاية المباراة! الفائز: {wname}. النتائج: {scores_summary}"
            
    def action(self, user_id: int, action: str, data: Any = None):
        if not self.active:
            raise ValueError("اللعبة ليست نشطة.")
        uid = int(user_id)
        if uid not in self.active_players:
            raise ValueError("أنت لست في اللعبة.")
        if self.player_ids[self.current_turn_index] != uid:
            raise ValueError("ليس دورك.")
            
        action = str(action or "").lower()
        
        if action == "play":
            if self.pending_choice:
                raise ValueError("يجب اختيار قيمة الورقة أولاً.")
            card_id = str(data or "")
            card_idx = next((i for i, c in enumerate(self.hands[uid]) if c["id"] == card_id), -1)
            if card_idx == -1:
                raise ValueError("الورقة غير موجودة.")
            card = self.hands[uid][card_idx]
            val = card["value"]
            
            # Smart automatic safe Ace/10 selection:
            # - At 24 or higher: 24 <= pile <= 33
            # - At 57 or higher: 57 <= pile <= 66
            # - Above 90: pile >= 90
            if (24 <= self.pile_value <= 33) or (57 <= self.pile_value <= 66) or (self.pile_value >= 90):
                if val == 10:
                    self._apply_card(uid, card_idx, -10)
                    return self.state_for(uid)
                elif val == 1:
                    self._apply_card(uid, card_idx, 1)
                    return self.state_for(uid)
            
            if val == 10:
                self.pending_choice = {"card_id": card_id, "type": "10", "player_id": uid, "card_value": 10}
                self.event_id += 1
                self.event_type = "PENDING_CHOICE"
                self.sound_cue = "NINETY_NINE_PROMPT"
                self.last_action = "اختر قيمة 10: +10 أو -10."
                return self.state_for(uid)
            if val == 1:
                self.pending_choice = {"card_id": card_id, "type": "A", "player_id": uid, "card_value": 1}
                self.event_id += 1
                self.event_type = "PENDING_CHOICE"
                self.sound_cue = "NINETY_NINE_PROMPT"
                self.last_action = "اختر قيمة آس: +1 أو +11."
                return self.state_for(uid)
                
            self._apply_card(uid, card_idx, None)
            return self.state_for(uid)

        elif action == "cancel_choice":
            if self.pending_choice and self.pending_choice.get("player_id") == uid:
                self.pending_choice = None
                self.event_id += 1
                self.event_type = "CHOICE_CANCELLED"
            return self.state_for(uid)
            
        elif action == "choose":
            if not self.pending_choice:
                raise ValueError("لا يوجد اختيار معلق.")
            choice_val = int(data)
            card_id = self.pending_choice["card_id"]
            card_idx = next((i for i, c in enumerate(self.hands[uid]) if c["id"] == card_id), -1)
            if card_idx == -1:
                self.pending_choice = None
                raise ValueError("حدث خطأ في الورقة المعلقة.")
                
            ctype = self.pending_choice["type"]
            if ctype == "10" and choice_val not in (10, -10):
                raise ValueError("اختيار غير صالح.")
            if ctype == "A" and choice_val not in (1, 11):
                raise ValueError("اختيار غير صالح.")
                
            self.pending_choice = None
            self._apply_card(uid, card_idx, choice_val)
            return self.state_for(uid)
            
        else:
            raise ValueError(f"إجراء غير معروف: {action}")
            
    def _apply_card(self, uid: int, card_idx: int, choice_val: Optional[int]):
        card = self.hands[uid].pop(card_idx)
        val = card["value"]
        
        prev_total = self.pile_value
        new_total = prev_total
        
        if val in (3, 4, 5, 6, 7, 8):
            new_total += val
        elif val == 9:
            pass
        elif val in (11, 12, 13):
            new_total += 10
        elif val == 10:
            new_total += choice_val
        elif val == 1:
            new_total += choice_val
        elif val == 2:
            if prev_total % 2 == 0 and prev_total > 49:
                new_total = prev_total // 2
            else:
                new_total = prev_total * 2
                
        self.discard_pile.append(card)
        self.pile_value = new_total
        
        action_text = f"{self.player_names[uid]} لعب {self._card_name(card)} والمجموع {new_total}."
        
        self.event_id += 1
        self.sound_cue = "NINETY_NINE_PLACE"
        self.event_type = "CARD_PLAYED"
        
        round_ended = False
        
        if new_total == 99:
            self.sound_cue = "NINETY_NINE_REACH"
            for p in list(self.active_players):
                if p != uid:
                    self._deduct_token(p, 2)
            scores_summary = "، ".join(f"{self.player_names.get(p, 'لاعب')}: {self.tokens.get(p, 0)}" for p in self.player_ids)
            action_text += f" نهاية الجولة {self.round_number}. النتائج: {scores_summary}"
            round_ended = True
            self.event_type = "ROUND_FINISHED"
            
        elif new_total > 99:
            self.sound_cue = "NINETY_NINE_EXCEED"
            loss_amount = 3 if val == 2 else 2
            self._deduct_token(uid, loss_amount)
            scores_summary = "، ".join(f"{self.player_names.get(p, 'لاعب')}: {self.tokens.get(p, 0)}" for p in self.player_ids)
            action_text += f" نهاية الجولة {self.round_number}. النتائج: {scores_summary}"
            round_ended = True
            self.event_type = "ROUND_FINISHED"
            
        else:
            if new_total in (33, 66):
                self.sound_cue = "NINETY_NINE_REACH"
                for p in list(self.active_players):
                    if p != uid:
                        self._deduct_token(p, 1)
                        action_text += f" {self.player_names[p]} خسر نقطة."
            else:
                if prev_total < 33 and new_total > 33:
                    self.sound_cue = "NINETY_NINE_EXCEED"
                    self._deduct_token(uid, 1)
                    action_text += f" {self.player_names[uid]} خسر نقطة."
                elif prev_total < 66 and new_total > 66:
                    self.sound_cue = "NINETY_NINE_EXCEED"
                    self._deduct_token(uid, 1)
                    action_text += f" {self.player_names[uid]} خسر نقطة."
                    
        self.last_action = action_text
        
        if uid in self.eliminated:
            self.last_action += f" خرج {self.player_names.get(uid)} من اللعبة."
            
        self._check_eliminations()
        if not self.active:
            return
            
        if round_ended:
            self.round_finished = True
            self.dealer_index = (self.dealer_index - 1) % len(self.player_ids)
            return
            
        if uid not in self.eliminated:
            if not self.deck:
                if self.discard_pile:
                    self.deck = list(self.discard_pile)
                    self.discard_pile = []
                    random.shuffle(self.deck)
                else:
                    self.deck = create_deck(2)
            if self.deck:
                self.hands[uid].append(self.deck.pop())
            
        steps = 1
        if val == 4:
            if len(self.active_players) > 2:
                self.direction *= -1
                self.last_action += " تم عكس الاتجاه."
                if not round_ended:
                    self.sound_cue = "NINETY_NINE_REVERSE"
        elif val == 11:
            steps = 2
            self.last_action += " تخطي الدور."
            if not round_ended:
                self.sound_cue = "NINETY_NINE_SKIP"

        self._advance_turn(steps)
            
    def _card_name(self, card: Dict[str, Any]) -> str:
        """Return Arabic presentation text while keeping card IDs/suits canonical internally."""
        v = int(card.get("value", 0) or 0)
        suit = str(card.get("suit", "")).lower()
        rank_ar = {1: "آس", 11: "جاك", 12: "كوين", 13: "ملك"}.get(v, str(v))
        suit_ar = {
            "diamonds": "ديناري",
            "hearts": "قلب",
            "spades": "بستوني",
            "clubs": "شجرة",
        }.get(suit, suit)
        return f"{rank_ar} من {suit_ar}"

    def full_state(self) -> dict:
        curr_turn_id = self.player_ids[self.current_turn_index] if self.active else None
        curr_name = self.player_names.get(curr_turn_id, "") if (self.active and curr_turn_id is not None) else ""
        return {
            "game_type": "NINETY_NINE",
            "event_id": self.event_id,
            "event_type": self.event_type,
            "last_action": self.last_action,
            "sound_cue": self.sound_cue,
            "active": self.active,
            "winner_id": self.winner_id,
            "pile_value": self.pile_value,
            "round_finished": self.round_finished,
            "current_turn_index": self.current_turn_index,
            "current_turn_id": curr_turn_id,
            "current_player_id": curr_turn_id,
            "current_player_name": curr_name,
            "direction": self.direction,
            "tokens": self.tokens,
            "eliminated": list(self.eliminated),
            "pending_choice": self.pending_choice,
            "players": [{"id": p, "name": self.player_names[p]} for p in self.player_ids]
        }
        
    def state_for(self, user_id: int) -> dict:
        st = self.full_state()
        st["hand"] = [] if self.round_finished else self.hands.get(user_id, [])
        if self.pending_choice:
            if int(user_id) == int(self.pending_choice.get("player_id", -999)):
                st["pending_choice"] = dict(self.pending_choice)
            else:
                st["pending_choice"] = {"player_id": self.pending_choice["player_id"]}
        else:
            st["pending_choice"] = None
        return st
