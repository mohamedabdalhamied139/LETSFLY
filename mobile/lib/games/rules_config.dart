/// Configurable UNO rule variants derived from core_shared/rules_config.py.
/// Literal parity with Windows desktop client.

class RuleDefinition {
  final String key;
  final String label;
  final String description;

  const RuleDefinition(this.key, this.label, this.description);
}

const List<RuleDefinition> RULE_DEFINITIONS = [
  RuleDefinition('responses', 'الردود (+2 و+4)', 'يمكن رد سحب 2 بسحب 2، ورد سحب 4 بسحب 4، وتُجمع العقوبة.'),
  RuleDefinition('straights', 'المتتاليات', 'يمكن لعب أرقام متتالية من اللون نفسه في الدور نفسه.'),
  RuleDefinition('interceptions', 'الاعتراضات', 'يمكن لعب الكارت المطابق تمامًا للكارت الموجود حتى خارج الدور.'),
  RuleDefinition('super_interceptions', 'الاعتراضات الفائقة', 'الاعتراض يكون بنفس الرقم أو الرمز حتى مع اختلاف اللون.'),
  RuleDefinition('bluff', 'الخداع', 'يمكن تحدي كارت تبديل اللون وسحب 4 عند الشك في قانون الخداع.'),
  RuleDefinition('skip_after_draw', 'التخطي بعد السحب', 'بعد السحب يمر الدور بدل السماح بلعب الكارت المسحوب فورًا.'),
  RuleDefinition('zero_seven', 'قاعدة 0/7', 'الصفر يمرر الأيدي، والسبعة يسمح بتبديل اليد مع لاعب.'),
  RuleDefinition('buzzer', 'الجرس', 'عند لعب كارت الجرس يجب على الجميع الاستجابة.'),
  RuleDefinition('advanced_responses', 'الردود المتقدمة', 'تخطي/عكس/تبديل اللون يمكنها تمرير التزام السحب.'),
  RuleDefinition('draw_until_playable', 'السحب حتى كارت قابل للعب', 'يستمر اللاعب في السحب حتى يحصل على كارت قابل للعب.'),
  RuleDefinition('eliminate_too_many', 'إقصاء من يسحب كثيرًا', 'عند الوصول إلى 25 كارتًا يُقصى اللاعب ويُحسب له جزاء 250 نقطة.'),
  RuleDefinition('no_mercy', 'حزمة UNO No Mercy', 'تفعيل مجموعة قواعد No Mercy الخاصة.'),
  RuleDefinition('skip_everyone', 'تخطي الجميع', 'كل اللاعبين يتخطون ويعيد صاحب الكارت اللعب.'),
  RuleDefinition('discard_all', 'إسقاط كل الكروت من اللون', 'إسقاط كل كروت اللون المطابق من يد اللاعب.'),
  RuleDefinition('wild_draw_six_ten', 'تبديل اللون وسحب 6/10', 'كروت Wild Draw Six وWild Draw Ten.'),
  RuleDefinition('wild_reverse_draw_four', 'تبديل اللون وعكس وسحب 4', 'يعكس الاتجاه ويجعل اللاعب التالي يسحب 4.'),
  RuleDefinition('color_roulette', 'عجلة الألوان', 'اختيار لون ثم السحب حتى إيجاد كارت من اللون المطلوب.'),
  RuleDefinition('uno_flip', 'UNO Flip', 'استخدام الجانب الفاتح والجانب الداكن وقواعد Flip.'),
];

final Map<String, bool> DEFAULT_RULES = {
  for (final rule in RULE_DEFINITIONS) rule.key: false,
};

const Set<String> NO_MERCY_CHILDREN = {
  'skip_everyone',
  'discard_all',
  'wild_draw_six_ten',
  'wild_reverse_draw_four',
  'color_roulette',
};
