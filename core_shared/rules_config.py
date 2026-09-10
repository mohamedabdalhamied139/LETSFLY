"""Configurable UNO rule variants derived from the supplied game-rules document."""

RULE_DEFINITIONS = [
    ("responses", "الردود (+2 و+4)", "يمكن رد سحب 2 بسحب 2، ورد سحب 4 بسحب 4، وتُجمع العقوبة."),
    ("straights", "المتتاليات", "يمكن لعب أرقام متتالية من اللون نفسه في الدور نفسه."),
    ("interceptions", "الاعتراضات", "يمكن لعب الكارت المطابق تمامًا للكارت الموجود حتى خارج الدور."),
    ("super_interceptions", "الاعتراضات الفائقة", "الاعتراض يكون بنفس الرقم أو الرمز حتى مع اختلاف اللون."),
    ("bluff", "الخداع", "يمكن تحدي كارت تبديل اللون وسحب 4 عند الشك في قانون الخداع."),
    ("skip_after_draw", "التخطي بعد السحب", "بعد السحب يمر الدور بدل السماح بلعب الكارت المسحوب فورًا."),
    ("zero_seven", "قاعدة 0/7", "الصفر يمرر الأيدي، والسبعة يسمح بتبديل اليد مع لاعب."),
    ("buzzer", "الجرس", "عند لعب كارت الجرس يجب على الجميع الاستجابة."),
    ("advanced_responses", "الردود المتقدمة", "تخطي/عكس/تبديل اللون يمكنها تمرير التزام السحب."),
    ("draw_until_playable", "السحب حتى كارت قابل للعب", "يستمر اللاعب في السحب حتى يحصل على كارت قابل للعب."),
    ("eliminate_too_many", "إقصاء من يسحب كثيرًا", "عند الوصول إلى 25 كارتًا يُقصى اللاعب ويُحسب له جزاء 250 نقطة."),
    ("no_mercy", "حزمة UNO No Mercy", "تفعيل مجموعة قواعد No Mercy الخاصة."),
    ("skip_everyone", "تخطي الجميع", "كل اللاعبين يتخطون ويعيد صاحب الكارت اللعب."),
    ("discard_all", "إسقاط كل الكروت من اللون", "إسقاط كل كروت اللون المطابق من يد اللاعب."),
    ("wild_draw_six_ten", "تبديل اللون وسحب 6/10", "كروت Wild Draw Six وWild Draw Ten."),
    ("wild_reverse_draw_four", "تبديل اللون وعكس وسحب 4", "يعكس الاتجاه ويجعل اللاعب التالي يسحب 4."),
    ("color_roulette", "عجلة الألوان", "اختيار لون ثم السحب حتى إيجاد كارت من اللون المطلوب."),
    ("uno_flip", "UNO Flip", "استخدام الجانب الفاتح والجانب الداكن وقواعد Flip."),
]

DEFAULT_RULES = {key: False for key, _, _ in RULE_DEFINITIONS}

# Rules that are meaningful only as part of the No Mercy pack.
NO_MERCY_CHILDREN = {"skip_everyone", "discard_all", "wild_draw_six_ten", "wild_reverse_draw_four", "color_roulette"}
