"""Shared constants for TableVerse v2."""
COLORS = ("red", "yellow", "green", "blue")
DARK_COLORS = ("orange", "pink", "purple", "teal")
ALL_COLORS = COLORS + DARK_COLORS
CARD_TYPES = (
    "number", "skip", "reverse", "draw_two", "wild", "wild_draw_four",
    "buzzer", "skip_everyone", "discard_all", "draw_one", "draw_five", "wild_draw_two", "wild_draw_six", "wild_draw_ten",
    "wild_reverse_draw_four", "color_roulette", "flip"
)
COLOR_NAMES_AR = {
    "red": "أحمر", "yellow": "أصفر", "green": "أخضر", "blue": "أزرق",
    "orange": "برتقالي", "pink": "وردي", "purple": "بنفسجي", "teal": "تركوازي", "wild": "حر",
}
CARD_NAMES_AR = {
    "skip": "تخطي", "reverse": "عكس الاتجاه", "draw_two": "سحب 2",
    "wild": "تبديل اللون", "wild_draw_four": "تبديل اللون وسحب 4",
    "buzzer": "جرس", "skip_everyone": "تخطي الجميع", "discard_all": "إسقاط الكل", "draw_one": "سحب 1", "draw_five": "سحب 5",
    "wild_draw_two": "تبديل اللون وسحب 2",
    "wild_draw_six": "تبديل اللون وسحب 6", "wild_draw_ten": "تبديل اللون وسحب 10",
    "wild_reverse_draw_four": "تبديل اللون وعكس وسحب 4", "color_roulette": "عجلة الألوان",
    "flip": "قلب",
}
CARD_SCORES = {
    "number": None, "skip": 20, "reverse": 20, "draw_two": 20,
    "wild": 50, "wild_draw_four": 50, "buzzer": 0, "skip_everyone": 50,
    "discard_all": 20, "draw_one": 10, "draw_five": 20, "wild_draw_two": 50, "wild_draw_six": 50, "wild_draw_ten": 50,
    "wild_reverse_draw_four": 50, "color_roulette": 50, "flip": 20,
}
UNO_PENALTY_CARDS = 4
INITIAL_HAND_SIZE = 7
DEFAULT_TARGET_SCORE = 500


# Shared semantic sound cues. These names are intentionally table-agnostic so
# future games/tables can reuse the same audio architecture without knowing
# the physical filenames used by the client.
SOUND_CUES = {
    "PLAYER_JOINED",
    "PLAYER_LEFT",
    "TURN_START",
    "ROUND_START",
    "ROUND_END",
    "MATCH_WIN",
    "MATCH_LOSS",
    "CARD_DRAW",
    "CARD_DRAW_TWO",
    "CARD_WILD_COLOR",
    "CARD_WILD_DRAW_FOUR",
    "CARD_SKIP",
    "CARD_REVERSE",
    "UNO_CALLED",
    "UNO_PENALTY",
    "BLUFF_CHALLENGE",
    "INVALID_ACTION",
}

SUIT_NAMES_AR = {
    "hearts": "قلب",
    "diamonds": "ديناري",
    "clubs": "شجرة",
    "spades": "بستوني"
}
