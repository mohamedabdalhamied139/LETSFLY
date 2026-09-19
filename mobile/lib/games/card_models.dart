import '../core/localization.dart';

/// Card constants and display helpers matching core_shared/constants.py and core_shared/uno_rules.py.
/// Adheres strictly to the Windows client literal parity rule.

const List<String> COLORS = ['red', 'yellow', 'green', 'blue'];
const List<String> DARK_COLORS = ['orange', 'pink', 'purple', 'teal'];

const Set<String> WILD_TYPES = {
  'wild',
  'wild_draw_four',
  'wild_draw_two',
  'wild_draw_six',
  'wild_draw_ten',
  'wild_reverse_draw_four',
  'color_roulette',
  'flip',
};

const Map<String, String> COLOR_NAMES_AR = {
  'red': 'أحمر',
  'yellow': 'أصفر',
  'green': 'أخضر',
  'blue': 'أزرق',
  'orange': 'برتقالي',
  'pink': 'وردي',
  'purple': 'بنفسجي',
  'teal': 'تركوازي',
  'wild': 'حر',
};

const Map<String, String> CARD_NAMES_AR = {
  'skip': 'تخطي',
  'reverse': 'عكس الاتجاه',
  'draw_two': 'سحب 2',
  'wild': 'تبديل اللون',
  'wild_draw_four': 'تبديل اللون وسحب 4',
  'buzzer': 'جرس',
  'skip_everyone': 'تخطي الجميع',
  'discard_all': 'إسقاط الكل',
  'draw_one': 'سحب 1',
  'draw_five': 'سحب 5',
  'wild_draw_two': 'تبديل اللون وسحب 2',
  'wild_draw_six': 'تبديل اللون وسحب 6',
  'wild_draw_ten': 'تبديل اللون وسحب 10',
  'wild_reverse_draw_four': 'تبديل اللون وعكس وسحب 4',
  'color_roulette': 'عجلة الألوان',
  'flip': 'قلب',
};

/// Exact literal reproduction of core_shared/uno_rules.py: card_display_ar
/// For suit cards (Scopa, 99), Windows outputs English strings (e.g. 'Ace of Hearts', '7 of Diamonds').
/// For UNO cards, Windows outputs Arabic strings (e.g. 'أحمر 5', 'أصفر تخطي', 'تبديل اللون').
String cardDisplayAr(Map<String, dynamic>? cardDict) {
  if (cardDict == null || cardDict.isEmpty) {
    return tr('بطاقة فارغة');
  }

  final ctype = (cardDict['type'] ?? '').toString();
  final color = (cardDict['color'] ?? '').toString();
  final val = cardDict['value'];
  final suit = cardDict['suit'];

  // Standard Playing Cards (Scopa, 99)
  if (suit != null && suit.toString().isNotEmpty && ctype.isEmpty) {
    final valMap = {1: 'Ace', 11: 'Jack', 12: 'Queen', 13: 'King'};
    final valInt = int.tryParse(val?.toString() ?? '');
    final valName = valMap[valInt] ?? val?.toString() ?? '';
    final suitStr = suit.toString();
    final suitCap = suitStr.isNotEmpty ? suitStr[0].toUpperCase() + suitStr.substring(1) : '';
    return '$valName of $suitCap';
  }

  // UNO Cards
  final colorAr = COLOR_NAMES_AR[color] ?? (color.isNotEmpty ? color : 'بدون');
  if (ctype == 'number') {
    return '$colorAr $val';
  }

  final nameAr = CARD_NAMES_AR[ctype] ?? ctype;
  if (WILD_TYPES.contains(ctype) || color == 'wild') {
    return nameAr;
  }

  return '$colorAr $nameAr';
}
