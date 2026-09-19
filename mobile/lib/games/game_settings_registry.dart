import 'rules_config.dart';

/// Setting field definition matching client/table_framework/settings_registry.py.
class SettingField {
  final String key;
  final String label;
  final String kind; // 'number', 'bool', 'choice', 'action'
  final dynamic defaultValue;
  final int minimum;
  final int? maximum;
  final int step;
  final List<String> options;
  final Map<String, String> labels;
  final String? group;
  final Map<String, String> conflictsWith;
  final String? description;

  const SettingField({
    required this.key,
    required this.label,
    this.kind = 'number',
    this.defaultValue,
    this.minimum = 1,
    this.maximum,
    this.step = 1,
    this.options = const [],
    this.labels = const {},
    this.group,
    this.conflictsWith = const {},
    this.description,
  });

  Map<String, dynamic> toDict(Map<String, dynamic>? currentRoom) {
    final rules = Map<String, dynamic>.from(currentRoom?['rules'] ?? {});
    dynamic val = defaultValue;

    if (key == 'target_score') {
      final target = currentRoom?['target_score'];
      if (target != null) {
        val = int.tryParse(target.toString()) ?? defaultValue;
      }
    } else if (rules.containsKey(key)) {
      val = rules[key];
    }

    final d = <String, dynamic>{
      'key': key,
      'label': label,
      'kind': kind,
      'value': val,
    };

    if (kind == 'number') {
      d['minimum'] = minimum;
      d['step'] = step;
      if (maximum != null) d['maximum'] = maximum;
    } else if (kind == 'choice') {
      d['options'] = options;
      d['labels'] = labels;
    } else if (kind == 'bool') {
      if (group != null) d['group'] = group;
      if (conflictsWith.isNotEmpty) d['conflicts_with'] = conflictsWith;
      if (description != null) d['description'] = description;
    }

    return d;
  }
}

/// Game settings definition matching client/table_framework/settings_registry.py.
class GameSettingsDefinition {
  final String gameType;
  final String title;
  final int defaultTargetScore;
  final Map<String, dynamic> defaultRules;
  final List<SettingField> customFields;
  final MapEntry<int, Map<String, dynamic>> Function(Map<String, dynamic> values)? ruleMapper;

  const GameSettingsDefinition({
    required this.gameType,
    required this.title,
    required this.defaultTargetScore,
    required this.defaultRules,
    required this.customFields,
    this.ruleMapper,
  });

  MapEntry<int, Map<String, dynamic>> extractTargetAndRules(Map<String, dynamic> values) {
    if (ruleMapper != null) {
      return ruleMapper!(values);
    }
    final target = int.tryParse(values['target_score']?.toString() ?? '') ?? defaultTargetScore;
    final rules = Map<String, dynamic>.from(defaultRules);
    for (final entry in values.entries) {
      if (entry.key != 'target_score' && entry.key != 'start' && entry.key != 'cancel') {
        rules[entry.key] = entry.value;
      }
    }
    return MapEntry(target, rules);
  }
}

// Timer options matching Windows settings_registry.py
final List<String> TIMER_OPTIONS = ['none'] +
    [for (int s = 3; s <= 10; s++) s.toString()] +
    ['15', '20', '25', '30', '35', '40', '45', '50', '55', '60'];

final Map<String, String> TIMER_LABELS = {
  'none': 'بدون وقت',
  for (int s = 3; s <= 60; s++)
    s.toString(): (s <= 10) ? '$s ثواني' : '$s ثانية',
};

// NINETY_NINE
MapEntry<int, Map<String, dynamic>> ninetyNineMapper(Map<String, dynamic> values) {
  final target = int.tryParse(values['target_score']?.toString() ?? '11') ?? 11;
  final timerVal = (values['turn_timer'] ?? 'none').toString();
  return MapEntry(target, {'starting_tokens': target, 'turn_timer': timerVal});
}

// SNAKES_LADDERS
MapEntry<int, Map<String, dynamic>> snakesMapper(Map<String, dynamic> values) {
  return MapEntry(100, {
    'knockout': values['knockout'] == true,
    'mystery_tiles': values['mystery_tiles'] == true,
  });
}

// SCOPA
MapEntry<int, Map<String, dynamic>> scopaMapper(Map<String, dynamic> values) {
  final target = int.tryParse(values['target_score']?.toString() ?? '11') ?? 11;
  String scopaMode = 'classic';
  if (values['mode_scopone'] == true) {
    scopaMode = 'scopone';
  } else if (values['mode_escoba_15'] == true) {
    scopaMode = 'escoba_15';
  } else if (values['mode_asso'] == true) {
    scopaMode = 'asso_piglia_tutto';
  }

  final rules = {
    'scopa_mode': scopaMode,
    'classic': scopaMode == 'classic',
    'escoba_15': scopaMode == 'escoba_15',
    'asso_piglia_tutto': scopaMode == 'asso_piglia_tutto',
    'scopone': scopaMode == 'scopone',
    'inverted': values['mode_inverted'] == true,
    'teams_enabled': values['teams_enabled'] == true,
  };
  return MapEntry(target, rules);
}

// DOMINO
MapEntry<int, Map<String, dynamic>> dominoMapper(Map<String, dynamic> values) {
  final target = int.tryParse(values['target_score']?.toString() ?? '100') ?? 100;
  final modeVal = values['mode_block'] == true ? 'block' : 'draw';
  return MapEntry(target, {'mode': modeVal, 'hand_size': 7});
}

// AMERICAN_DOMINO
MapEntry<int, Map<String, dynamic>> amDominoMapper(Map<String, dynamic> values) {
  var target = int.tryParse(values['target_score']?.toString() ?? '150') ?? 150;
  final scoringMode = values['scoring_unit'] == true ? 'unit' : 'standard';
  if (scoringMode == 'unit' && target == 150) {
    target = 30;
  }
  return MapEntry(target, {'hand_size': 7, 'scoring_mode': scoringMode});
}

// UNO
MapEntry<int, Map<String, dynamic>> unoMapper(Map<String, dynamic> values) {
  final target = int.tryParse(values['target_score']?.toString() ?? '500') ?? 500;
  final rules = <String, dynamic>{};
  for (final rule in RULE_DEFINITIONS) {
    rules[rule.key] = values[rule.key] == true;
  }

  if (rules['no_mercy'] != true) {
    for (final child in NO_MERCY_CHILDREN) {
      rules[child] = false;
    }
  }
  if (rules['uno_flip'] == true && rules['no_mercy'] == true) {
    rules['no_mercy'] = false;
    for (final child in NO_MERCY_CHILDREN) {
      rules[child] = false;
    }
  }
  rules['turn_timer'] = (values['turn_timer'] ?? 'none').toString();
  return MapEntry(target, rules);
}

// THIEF_HUNT
MapEntry<int, Map<String, dynamic>> thiefHuntMapper(Map<String, dynamic> values) {
  final rounds = int.tryParse(values['rounds']?.toString() ?? '5') ?? 5;
  return MapEntry(rounds, {
    'rounds': rounds,
    'elimination_mode': values['elimination_mode'] == true,
  });
}

// FARKLE
MapEntry<int, Map<String, dynamic>> farkleMapper(Map<String, dynamic> values) {
  final target = int.tryParse(values['target_score']?.toString() ?? '1500') ?? 1500;
  return MapEntry(target, {
    'min_bank': int.tryParse(values['min_bank']?.toString() ?? '30') ?? 30,
    'first_bank_min': int.tryParse(values['first_bank_min']?.toString() ?? '50') ?? 50,
  });
}

// TENNIS
MapEntry<int, Map<String, dynamic>> tennisMapper(Map<String, dynamic> values) {
  final isGrandSlam = values['grand_slam'] == true;
  final target = isGrandSlam ? 3 : 2;
  return MapEntry(target, {'grand_slam': isGrandSlam});
}

final Map<String, GameSettingsDefinition> GAME_SETTINGS_REGISTRY = {
  'NINETY_NINE': GameSettingsDefinition(
    gameType: 'NINETY_NINE',
    title: 'تسعة وتسعون',
    defaultTargetScore: 11,
    defaultRules: {'starting_tokens': 11},
    customFields: [
      SettingField(
        key: 'target_score',
        label: 'عدد النقاط النهائي',
        kind: 'number',
        defaultValue: 11,
        minimum: 1,
        maximum: 99,
        step: 1,
      ),
      SettingField(
        key: 'turn_timer',
        label: 'وقت الدور',
        kind: 'choice',
        defaultValue: 'none',
        options: TIMER_OPTIONS,
        labels: TIMER_LABELS,
      ),
    ],
    ruleMapper: ninetyNineMapper,
  ),

  'SNAKES_LADDERS': GameSettingsDefinition(
    gameType: 'SNAKES_LADDERS',
    title: 'السلم والثعبان',
    defaultTargetScore: 100,
    defaultRules: {'knockout': false, 'mystery_tiles': false},
    customFields: const [
      SettingField(
        key: 'knockout',
        label: 'إسقاط المنافسين عند الوقوف على نفس المربع',
        kind: 'bool',
        defaultValue: false,
      ),
      SettingField(
        key: 'mystery_tiles',
        label: 'صناديق الحظ والمفاجآت',
        kind: 'bool',
        defaultValue: false,
      ),
    ],
    ruleMapper: snakesMapper,
  ),

  'SCOPA': GameSettingsDefinition(
    gameType: 'SCOPA',
    title: 'إسكوبا',
    defaultTargetScore: 11,
    defaultRules: {
      'scopa_mode': 'classic',
      'classic': true,
      'escoba_15': false,
      'asso_piglia_tutto': false,
      'scopone': false,
      'inverted': false,
      'teams_enabled': false,
    },
    customFields: const [
      SettingField(
        key: 'target_score',
        label: 'عدد النقاط النهائي',
        kind: 'number',
        defaultValue: 11,
        minimum: 1,
        step: 1,
      ),
      SettingField(
        key: 'mode_classic',
        label: 'الوضع الكلاسيكي (مطابقة القيمة)',
        kind: 'bool',
        defaultValue: true,
        group: 'scopa_base_mode',
      ),
      SettingField(
        key: 'mode_escoba_15',
        label: 'وضع إسكوبا 15 (مجموع 15)',
        kind: 'bool',
        defaultValue: false,
        group: 'scopa_base_mode',
      ),
      SettingField(
        key: 'mode_asso',
        label: 'قاعدة الآس يمسح الكل (Asso piglia tutto)',
        kind: 'bool',
        defaultValue: false,
      ),
      SettingField(
        key: 'mode_scopone',
        label: 'وضع إسكوبوني (توزيع كل الكروت)',
        kind: 'bool',
        defaultValue: false,
      ),
      SettingField(
        key: 'mode_inverted',
        label: 'الوضع المعكوس (أقل نقاط يفوز)',
        kind: 'bool',
        defaultValue: false,
      ),
      SettingField(
        key: 'teams_enabled',
        label: 'وضع الفرق (لـ 4 أو 6 لاعبين)',
        kind: 'bool',
        defaultValue: false,
      ),
    ],
    ruleMapper: scopaMapper,
  ),

  'FARKLE': GameSettingsDefinition(
    gameType: 'FARKLE',
    title: 'فاركل',
    defaultTargetScore: 1500,
    defaultRules: {'min_bank': 30, 'first_bank_min': 50},
    customFields: const [
      SettingField(
        key: 'target_score',
        label: 'عدد النقاط النهائي',
        kind: 'number',
        defaultValue: 1500,
        minimum: 1,
        step: 50,
      ),
      SettingField(
        key: 'min_bank',
        label: 'الحد الأدنى للتثبيت',
        kind: 'number',
        defaultValue: 30,
        minimum: 30,
        step: 10,
      ),
      SettingField(
        key: 'first_bank_min',
        label: 'الحد الأدنى لأول تثبيت',
        kind: 'number',
        defaultValue: 50,
        minimum: 50,
        step: 10,
      ),
    ],
    ruleMapper: farkleMapper,
  ),

  'THIEF_HUNT': GameSettingsDefinition(
    gameType: 'THIEF_HUNT',
    title: 'مطاردة اللص',
    defaultTargetScore: 1,
    defaultRules: {'rounds': 5, 'elimination_mode': false},
    customFields: const [
      SettingField(
        key: 'rounds',
        label: 'عدد الجولات',
        kind: 'number',
        defaultValue: 5,
        minimum: 1,
        maximum: 100,
        step: 1,
      ),
      SettingField(
        key: 'elimination_mode',
        label: 'نظام الخروج المباشر',
        kind: 'bool',
        defaultValue: false,
      ),
    ],
    ruleMapper: thiefHuntMapper,
  ),

  'DOMINO': GameSettingsDefinition(
    gameType: 'DOMINO',
    title: 'الدومينو الكلاسيك',
    defaultTargetScore: 100,
    defaultRules: {'mode': 'draw', 'hand_size': 7},
    customFields: const [
      SettingField(
        key: 'target_score',
        label: 'عدد النقاط النهائي',
        kind: 'number',
        defaultValue: 100,
        minimum: 1,
        step: 10,
      ),
      SettingField(
        key: 'mode_draw',
        label: 'طريقة السحب (Draw)',
        kind: 'bool',
        defaultValue: true,
        group: 'domino_mode',
      ),
      SettingField(
        key: 'mode_block',
        label: 'طريقة القفل (Block)',
        kind: 'bool',
        defaultValue: false,
        group: 'domino_mode',
      ),
    ],
    ruleMapper: dominoMapper,
  ),

  'AMERICAN_DOMINO': GameSettingsDefinition(
    gameType: 'AMERICAN_DOMINO',
    title: 'الدومينو الأمريكاني',
    defaultTargetScore: 150,
    defaultRules: {'hand_size': 7, 'scoring_mode': 'standard'},
    customFields: const [
      SettingField(
        key: 'target_score',
        label: 'عدد النقاط النهائي',
        kind: 'number',
        defaultValue: 150,
        minimum: 1,
        step: 10,
      ),
      SettingField(
        key: 'scoring_standard',
        label: 'النظام المباشر (5، 10، 15 نقطة)',
        kind: 'bool',
        defaultValue: true,
        group: 'domino_scoring',
      ),
      SettingField(
        key: 'scoring_unit',
        label: 'نظام الوحدات العالمي (1، 2، 3 وحدات)',
        kind: 'bool',
        defaultValue: false,
        group: 'domino_scoring',
      ),
    ],
    ruleMapper: amDominoMapper,
  ),

  'UNO': GameSettingsDefinition(
    gameType: 'UNO',
    title: 'أونو',
    defaultTargetScore: 500,
    defaultRules: Map<String, dynamic>.from(DEFAULT_RULES),
    customFields: [
      const SettingField(
        key: 'target_score',
        label: 'عدد النقاط النهائي',
        kind: 'number',
        defaultValue: 500,
        minimum: 1,
        step: 50,
      ),
      SettingField(
        key: 'turn_timer',
        label: 'وقت الدور',
        kind: 'choice',
        defaultValue: 'none',
        options: TIMER_OPTIONS,
        labels: TIMER_LABELS,
      ),
      ...RULE_DEFINITIONS.map((r) => SettingField(
            key: r.key,
            label: r.label,
            description: r.description,
            kind: 'bool',
            defaultValue: DEFAULT_RULES[r.key] ?? false,
            conflictsWith: r.key == 'no_mercy'
                ? const {'uno_flip': 'لا يمكن الجمع بين No Mercy و UNO Flip'}
                : (r.key == 'uno_flip'
                    ? const {'no_mercy': 'لا يمكن الجمع بين No Mercy و UNO Flip'}
                    : const {}),
          )),
    ],
    ruleMapper: unoMapper,
  ),

  'TENNIS': GameSettingsDefinition(
    gameType: 'TENNIS',
    title: 'تنس',
    defaultTargetScore: 2,
    defaultRules: {'grand_slam': false},
    customFields: const [
      SettingField(
        key: 'grand_slam',
        label: 'نظام الجراند سلام (أفضل 5 مجموعات - الفوز بـ 3 مجموعات)',
        kind: 'bool',
        defaultValue: false,
      ),
    ],
    ruleMapper: tennisMapper,
  ),
};
