from dataclasses import dataclass, field
from typing import Any, Optional, Callable, Dict, List

@dataclass
class SettingField:
    key: str
    label: str
    kind: str = "number"  # "number", "bool", "choice", "action"
    default_value: Any = None
    minimum: int = 1
    maximum: Optional[int] = None
    step: int = 1
    options: List[str] = field(default_factory=list)
    labels: Dict[str, str] = field(default_factory=dict)
    group: Optional[str] = None
    conflicts_with: Dict[str, str] = field(default_factory=dict)

    def to_dict(self, current_room=None):
        rules = (current_room or {}).get("rules") or {}
        val = self.default_value
        if self.key == "target_score":
            target = (current_room or {}).get("target_score")
            if target is not None:
                val = int(target)
        elif self.key in rules:
            val = rules[self.key]

        d = {
            "key": self.key,
            "label": self.label,
            "kind": self.kind,
            "value": val
        }
        if self.kind == "number":
            d["minimum"] = self.minimum
            d["step"] = self.step
            if self.maximum is not None:
                d["maximum"] = self.maximum
        elif self.kind == "choice":
            d["options"] = self.options
            d["labels"] = self.labels
        elif self.kind == "bool":
            if self.group:
                d["group"] = self.group
            if self.conflicts_with:
                d["conflicts_with"] = self.conflicts_with
        return d


@dataclass
class GameSettingsDefinition:
    game_type: str
    title: str
    default_target_score: int
    default_rules: Dict[str, Any]
    state_getter: str
    state_applier: str
    custom_fields: List[SettingField]
    # Optional logic to override target score and rules mapping from values
    rule_mapper: Optional[Callable[[Dict[str, Any]], tuple[int, Dict[str, Any]]]] = None

    def extract_target_and_rules(self, values: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
        if self.rule_mapper:
            return self.rule_mapper(values)
            
        target = int(values.get("target_score", self.default_target_score))
        rules = dict(self.default_rules)
        for k, v in values.items():
            if k not in ("target_score", "start", "cancel"):
                rules[k] = v
        return target, rules


from core_shared.rules_config import RULE_DEFINITIONS, DEFAULT_RULES, NO_MERCY_CHILDREN

# NINETY_NINE
def ninety_nine_mapper(values):
    target = int(values.get("target_score", 11) or 11)
    return target, {"starting_tokens": target}

# SNAKES_LADDERS
def snakes_mapper(values):
    return 100, {"knockout": bool(values.get("knockout")), "mystery_tiles": bool(values.get("mystery_tiles"))}

# SCOPA
def scopa_mapper(values):
    target = int(values.get("target_score", 11))
    # Exactly one base ruleset is authoritative. "Inverted" is a scoring
    # modifier and may be combined with the selected base mode; it must never
    # silently become a competing base mode.
    if values.get("mode_scopone"):
        scopa_mode = "scopone"
    elif values.get("mode_escoba_15"):
        scopa_mode = "escoba_15"
    elif values.get("mode_asso"):
        scopa_mode = "asso_piglia_tutto"
    else:
        scopa_mode = "classic"

    rules = {
        "scopa_mode": scopa_mode,
        "classic": scopa_mode == "classic",
        "escoba_15": scopa_mode == "escoba_15",
        "asso_piglia_tutto": scopa_mode == "asso_piglia_tutto",
        "scopone": scopa_mode == "scopone",
        "inverted": bool(values.get("mode_inverted", False)),
        "teams_enabled": bool(values.get("teams_enabled", False)),
    }
    return target, rules

# DOMINO
def domino_mapper(values):
    target = int(values.get("target_score", 100))
    mode_val = "block" if values.get("mode_block") else "draw"
    return target, {"mode": mode_val, "hand_size": 7}

# AMERICAN_DOMINO
def am_domino_mapper(values):
    target = int(values.get("target_score", 150))
    scoring_mode = "unit" if values.get("scoring_unit") else "standard"
    if scoring_mode == "unit" and target == 150:
        target = 30
    return target, {"hand_size": 7, "scoring_mode": scoring_mode}

# UNO
def uno_mapper(values):
    target = int(values.get("target_score", 500))
    rules = {k: bool(values.get(k, DEFAULT_RULES.get(k, False))) for k, _label, _desc in RULE_DEFINITIONS}
    if not rules.get("no_mercy"):
        for child in NO_MERCY_CHILDREN:
            rules[child] = False
    if rules.get("uno_flip") and rules.get("no_mercy"):
        rules["no_mercy"] = False
        for child in NO_MERCY_CHILDREN:
            rules[child] = False
    return target, rules

# THIEF_HUNT
def thief_hunt_mapper(values):
    rounds = int(values.get("rounds", 5))
    return rounds, {
        "rounds": rounds,
        "allow_human_thief": bool(values.get("allow_human_thief")),
        "elimination_mode": bool(values.get("elimination_mode"))
    }

# FARKLE
def farkle_mapper(values):
    target = int(values.get("target_score", 1500))
    return target, {
        "min_bank": int(values.get("min_bank", 30)),
        "first_bank_min": int(values.get("first_bank_min", 50))
    }

# TENNIS
def tennis_mapper(values):
    target = int(values.get("target_score", 1))
    cur_diff = str(values.get("bot_difficulty", "NORMAL")).upper()
    return target, {"bot_difficulty": cur_diff if cur_diff in ("EASY", "NORMAL", "HARD", "EXPERT") else "NORMAL"}

GAME_SETTINGS_REGISTRY = {
    "NINETY_NINE": GameSettingsDefinition(
        game_type="NINETY_NINE",
        title="تسعة وتسعون",
        default_target_score=11,
        default_rules={"starting_tokens": 11},
        state_getter="uno_state",
        state_applier="_apply_uno_state",
        custom_fields=[
            SettingField("target_score", "عدد النقاط النهائي", kind="number", default_value=11, minimum=1, maximum=99, step=1)
        ],
        rule_mapper=ninety_nine_mapper
    ),
    "SNAKES_LADDERS": GameSettingsDefinition(
        game_type="SNAKES_LADDERS",
        title="السلم والثعبان",
        default_target_score=100,
        default_rules={"knockout": False, "mystery_tiles": False},
        state_getter="snakes_state",
        state_applier="_apply_snakes_state",
        custom_fields=[
            SettingField("knockout", "إسقاط المنافسين عند الوقوف على نفس المربع", kind="bool", default_value=False),
            SettingField("mystery_tiles", "صناديق الحظ والمفاجآت", kind="bool", default_value=False)
        ],
        rule_mapper=snakes_mapper
    ),
    "SCOPA": GameSettingsDefinition(
        game_type="SCOPA",
        title="إسكوبا",
        default_target_score=11,
        default_rules={
            "scopa_mode": "classic",
            "classic": True,
            "escoba_15": False,
            "asso_piglia_tutto": False,
            "scopone": False,
            "inverted": False,
            "teams_enabled": False,
        },
        state_getter="scopa_state",
        state_applier="_apply_scopa_state",
        custom_fields=[
            SettingField("target_score", "عدد النقاط النهائي", kind="number", default_value=11, minimum=1, step=1),
            SettingField("mode_classic", "الوضع الكلاسيكي (مطابقة القيمة)", kind="bool", default_value=True, group="scopa_base_mode"),
            SettingField("mode_escoba_15", "وضع إسكوبا 15 (مجموع 15)", kind="bool", default_value=False, group="scopa_base_mode"),
            SettingField("mode_asso", "قاعدة الآس يمسح الكل (Asso piglia tutto)", kind="bool", default_value=False),
            SettingField("mode_scopone", "وضع إسكوبوني (توزيع كل الكروت)", kind="bool", default_value=False),
            SettingField("mode_inverted", "الوضع المعكوس (أقل نقاط يفوز)", kind="bool", default_value=False),
            SettingField("teams_enabled", "وضع الفرق (لـ 4 أو 6 لاعبين)", kind="bool", default_value=False),
        ],
        rule_mapper=scopa_mapper
    ),
    "FARKLE": GameSettingsDefinition(
        game_type="FARKLE",
        title="فاركل",
        default_target_score=1500,
        default_rules={"min_bank": 30, "first_bank_min": 50},
        state_getter="farkle_state",
        state_applier="_apply_farkle_state",
        custom_fields=[
            SettingField("target_score", "عدد النقاط النهائي", kind="number", default_value=1500, minimum=1, step=50),
            SettingField("min_bank", "الحد الأدنى للتثبيت", kind="number", default_value=30, minimum=30, step=10),
            SettingField("first_bank_min", "الحد الأدنى لأول تثبيت", kind="number", default_value=50, minimum=50, step=10),
        ],
        rule_mapper=farkle_mapper
    ),
    "THIEF_HUNT": GameSettingsDefinition(
        game_type="THIEF_HUNT",
        title="مطاردة اللص",
        default_target_score=1,
        default_rules={"rounds": 5, "allow_human_thief": False, "elimination_mode": False},
        state_getter="thief_state",
        state_applier="_apply_thief_state",
        custom_fields=[
            SettingField("rounds", "عدد الجولات", kind="number", default_value=5, minimum=1, step=1),
            SettingField("allow_human_thief", "السماح باللص البشري", kind="bool", default_value=False),
            SettingField("elimination_mode", "نظام الخروج المباشر", kind="bool", default_value=False),
        ],
        rule_mapper=thief_hunt_mapper
    ),
    "DOMINO": GameSettingsDefinition(
        game_type="DOMINO",
        title="الدومينو الكلاسيك",
        default_target_score=100,
        default_rules={"mode": "draw", "hand_size": 7},
        state_getter="domino_state",
        state_applier="_apply_domino_state",
        custom_fields=[
            SettingField("target_score", "عدد النقاط النهائي", kind="number", default_value=100, minimum=1, step=10),
            SettingField("mode_draw", "طريقة السحب (Draw)", kind="bool", default_value=True, group="domino_mode"),
            SettingField("mode_block", "طريقة القفل (Block)", kind="bool", default_value=False, group="domino_mode"),
        ],
        rule_mapper=domino_mapper
    ),
    "AMERICAN_DOMINO": GameSettingsDefinition(
        game_type="AMERICAN_DOMINO",
        title="الدومينو الأمريكاني",
        default_target_score=150,
        default_rules={"hand_size": 7, "scoring_mode": "standard"},
        state_getter="american_domino_state",
        state_applier="_apply_domino_state",
        custom_fields=[
            SettingField("target_score", "عدد النقاط النهائي", kind="number", default_value=150, minimum=1, step=10),
            SettingField("scoring_standard", "النظام المباشر (5، 10، 15 نقطة)", kind="bool", default_value=True, group="domino_scoring"),
            SettingField("scoring_unit", "نظام الوحدات العالمي (1، 2، 3 وحدات)", kind="bool", default_value=False, group="domino_scoring"),
        ],
        rule_mapper=am_domino_mapper
    ),
    "UNO": GameSettingsDefinition(
        game_type="UNO",
        title="أونو",
        default_target_score=500,
        default_rules=dict(DEFAULT_RULES),
        state_getter="uno_state",
        state_applier="_apply_uno_state",
        custom_fields=[
            SettingField("target_score", "عدد النقاط النهائي", kind="number", default_value=500, minimum=1, step=50)
        ] + [
            SettingField(
                key, label, kind="bool",
                default_value=bool(DEFAULT_RULES.get(key, False)),
                conflicts_with={"uno_flip": "لا يمكن الجمع بين No Mercy و UNO Flip"} if key == "no_mercy" else ({"no_mercy": "لا يمكن الجمع بين No Mercy و UNO Flip"} if key == "uno_flip" else {})
            )
            for key, label, _ in RULE_DEFINITIONS
        ],
        rule_mapper=uno_mapper
    ),
    "TENNIS": GameSettingsDefinition(
        game_type="TENNIS",
        title="تنس",
        default_target_score=1,
        default_rules={"bot_difficulty": "NORMAL"},
        state_getter="tennis_state",
        state_applier="_apply_tennis_state",
        custom_fields=[
            SettingField("target_score", "عدد المجموعات للفوز", kind="number", default_value=1, minimum=1, maximum=5, step=1),
            SettingField("bot_difficulty", "صعوبة البوت", kind="choice", default_value="NORMAL", 
                options=["EASY", "NORMAL", "HARD", "EXPERT"],
                labels={"EASY": "سهل", "NORMAL": "متوسط", "HARD": "صعب", "EXPERT": "محترف"}
            )
        ],
        rule_mapper=tennis_mapper
    )
}
