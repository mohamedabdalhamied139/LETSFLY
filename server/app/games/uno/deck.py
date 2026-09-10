"""Deck generation and card representations for configurable UNO."""
import random
from uuid import uuid4
from typing import Optional, List
from core_shared.constants import COLORS, DARK_COLORS, COLOR_NAMES_AR, CARD_NAMES_AR

class Card:
    def __init__(self, card_type: str, color: str, value: Optional[int] = None, card_id: Optional[str] = None):
        self.card_type = card_type
        self.color = color
        self.value = value
        self.card_id = card_id or uuid4().hex

    @property
    def is_wild(self) -> bool:
        return self.card_type in ("wild", "wild_draw_four", "wild_draw_two", "wild_draw_six", "wild_draw_ten", "wild_reverse_draw_four", "color_roulette", "flip")

    @property
    def display_name_ar(self) -> str:
        color_ar = COLOR_NAMES_AR.get(self.color, self.color or "حر")
        if self.card_type == "number":
            return f"{color_ar} {self.value}"
        name_ar = CARD_NAMES_AR.get(self.card_type, self.card_type)
        if self.is_wild:
            return name_ar
        return f"{color_ar} {name_ar}"

    def to_dict(self, include_id=True) -> dict:
        d = {"type": self.card_type, "color": self.color, "value": self.value, "name": self.display_name_ar}
        if include_id:
            d["id"] = self.card_id
        return d

def _add_classic_cards(deck, colors):
    for color in colors:
        deck.append(Card("number", color, 0))
        for v in range(1, 10):
            deck.append(Card("number", color, v))
            deck.append(Card("number", color, v))
        for action in ("skip", "reverse", "draw_two"):
            deck.append(Card(action, color))
            deck.append(Card(action, color))

def create_uno_deck(rules=None) -> List[Card]:
    rules = rules or {}
    deck: List[Card] = []
    if rules.get("uno_flip"):
        # Light side: yellow/red/blue/green. The exact pack counts are not
        # specified in the supplied text, so one flip card is used here.
        _add_classic_cards(deck, COLORS)
        deck.extend(Card("wild", "wild") for _ in range(4))
        deck.extend(Card("wild_draw_two", "wild") for _ in range(4))
        deck.append(Card("flip", "wild"))
    else:
        _add_classic_cards(deck, COLORS)
        deck.extend(Card("wild", "wild") for _ in range(4))
        deck.extend(Card("wild_draw_four", "wild") for _ in range(4))

        if rules.get("buzzer"):
            deck.extend(Card("buzzer", "wild") for _ in range(8))

        if rules.get("no_mercy"):
            # The supplied text names these special cards but does not state
            # their counts, so one copy per named special type is used.
            if rules.get("skip_everyone"):
                deck.append(Card("skip_everyone", "wild"))
            if rules.get("discard_all"):
                for color in COLORS:
                    deck.append(Card("discard_all", color))
            if rules.get("wild_draw_six_ten"):
                deck.append(Card("wild_draw_six", "wild"))
                deck.append(Card("wild_draw_ten", "wild"))
            if rules.get("wild_reverse_draw_four"):
                deck.append(Card("wild_reverse_draw_four", "wild"))
            if rules.get("color_roulette"):
                deck.append(Card("color_roulette", "wild"))

    random.shuffle(deck)
    return deck
