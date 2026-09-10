"""Shared UNO matching and display helpers."""
from core_shared.constants import COLOR_NAMES_AR, CARD_NAMES_AR, SUIT_NAMES_AR

WILD_TYPES = {
    "wild", "wild_draw_four", "wild_draw_two", "wild_draw_six", "wild_draw_ten",
    "wild_reverse_draw_four", "color_roulette", "flip"
}

def card_display_ar(card_dict: dict) -> str:
    if not card_dict:
        return "بطاقة فارغة"
    ctype = card_dict.get("type", "")
    color = card_dict.get("color", "")
    val = card_dict.get("value")
    suit = card_dict.get("suit")
    
    if suit and not ctype:
        val_name = {1: "Ace", 11: "Jack", 12: "Queen", 13: "King"}.get(val, str(val))
        suit_cap = str(suit).capitalize()
        return f"{val_name} of {suit_cap}"

    color_ar = COLOR_NAMES_AR.get(color, color or "بدون")
    if ctype == "number":
        return f"{color_ar} {val}"
    name_ar = CARD_NAMES_AR.get(ctype, ctype)
    if ctype in WILD_TYPES or color == "wild":
        return name_ar
    return f"{color_ar} {name_ar}"

def is_card_playable(card: dict, top_card: dict, active_color: str) -> bool:
    ctype = card.get("type", "")
    if ctype in WILD_TYPES:
        return True
    if ctype in ("buzzer", "flip", "skip_everyone"):
        return True
    if card.get("color") == active_color:
        return True
    if top_card and ctype == top_card.get("type"):
        if ctype == "number":
            return card.get("value") == top_card.get("value")
        return True
    if ctype == "number" and top_card and top_card.get("type") == "number":
        return card.get("value") == top_card.get("value")
    return False
