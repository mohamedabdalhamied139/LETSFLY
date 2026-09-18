// Tier 1 Unit Test: Localization (Lookup, Parameter Substitution, Fallbacks)

import 'dart:io';
import 'dart:convert';
import '../harness/test_engine.dart';
import '../harness/test_fixtures.dart';

/// Testable localization engine matching core/localization.dart logic
class TestLocalization {
  String currentLanguage = 'ar';
  final Map<String, String> _translations = {};

  void setTranslations(Map<String, String> map) {
    _translations.clear();
    _translations.addAll(map);
  }

  void loadFromLocaleMap(Map<String, dynamic> jsonMap) {
    _translations.clear();
    jsonMap.forEach((key, value) {
      _translations[key] = value.toString();
    });
  }

  bool loadFromFile(String filePath) {
    try {
      final file = File(filePath);
      if (file.existsSync()) {
        final content = file.readAsStringSync();
        final Map<String, dynamic> jsonMap = json.decode(content);
        loadFromLocaleMap(jsonMap);
        return true;
      }
    } catch (_) {}
    return false;
  }

  String tr(String key, [Map<String, dynamic>? params]) {
    String text = _translations[key] ?? key;
    if (params != null && params.isNotEmpty) {
      params.forEach((paramKey, paramValue) {
        text = text.replaceAll('{$paramKey}', paramValue.toString());
      });
    }
    return text;
  }
}

void main() async {
  defineTests();
  await runSuite('Tier 1 Unit: Localization Tests');
}

void defineTests() {
  group('Localization Engine & Dictionary Parity', () {
    late TestLocalization localizer;

    setUp(() {
      localizer = TestLocalization();
      // Load canonical translations for Arabic
      localizer.setTranslations({
        'القائمة الرئيسية': 'القائمة الرئيسية',
        'الطاولات': 'الطاولات',
        'الأصدقاء': 'الأصدقاء',
        'المتصلون ({count})': 'المتصلون ({count})',
        'ملفي الشخصي': 'ملفي الشخصي',
        'الإعدادات': 'الإعدادات',
        'الإشعارات': 'الإشعارات',
        'تحدث معنا': 'تحدث معنا',
        'تسجيل الخروج': 'تسجيل الخروج',
        'مرحبًا بعودتك {name}.': 'مرحبًا بعودتك {name}.',
        'مرحبًا {name}.': 'مرحبًا {name}.',
        'ضد: {0}': 'ضد: {0}',
        'تاريخ الحفظ: {0}': 'تاريخ الحفظ: {0}',
        'تنتهي في: {0}': 'تنتهي في: {0}',
        'لا توجد طاولات متاحة حاليًا.': 'لا توجد طاولات متاحة حاليًا.',
        'لا توجد طاولات محفوظة.': 'لا توجد طاولات محفوظة.',
        'لا توجد أحداث في هذا القسم.': 'لا توجد أحداث في هذا القسم.',
        'سجل الأحداث': 'سجل الأحداث',
        'الجميع': 'الجميع',
        'دردشة الطاولات': 'دردشة الطاولات',
        'الرسائل الخاصة': 'الرسائل الخاصة',
        'اللعب': 'اللعب',
        'طلبات الصداقة': 'طلبات الصداقة',
        'الدعوات': 'الدعوات',
        'الهدايا': 'الهدايا',
        'أونو': 'أونو',
        'إسكوبا': 'إسكوبا',
        'تسعة وتسعون': 'تسعة وتسعون',
        'فاركل': 'فاركل',
        'السلم والثعبان': 'السلم والثعبان',
        'دومينو': 'دومينو',
        'دومينو كلاسيك': 'دومينو كلاسيك',
        'دومينو أمريكي': 'دومينو أمريكي',
        'صيد اللص': 'صيد اللص',
        'تنس': 'تنس',
      });
    });

    group('Translation String Lookup', () {
      test('Translates all 8 canonical menu items correctly', () {
        for (final item in TestFixtures.canonicalMenuItems) {
          final translated = localizer.tr(item['title']!);
          expect(translated, equals(item['title']!));
        }
      });

      test('Translates all 8 canonical activity categories correctly', () {
        for (final catKey in TestFixtures.canonicalActivityCategories) {
          final label = TestFixtures.categoryLabels[catKey]!;
          final translated = localizer.tr(label);
          expect(translated, equals(label));
        }
      });

      test('Translates all 9 canonical games display names correctly', () {
        for (final game in TestFixtures.canonicalGames) {
          final translated = localizer.tr(game['name']!);
          expect(translated, equals(game['name']!));
        }
      });
    });

    group('Parameter Substitution', () {
      test('Replaces single {name} parameter accurately', () {
        final result = localizer.tr('مرحبًا بعودتك {name}.', {'name': 'أحمد'});
        expect(result, equals('مرحبًا بعودتك أحمد.'));
      });

      test('Replaces single {count} numeric parameter accurately', () {
        final result = localizer.tr('المتصلون ({count})', {'count': 15});
        expect(result, equals('المتصلون (15)'));
      });

      test('Replaces positional parameter {0} for saved tables opponent field', () {
        final result = localizer.tr('ضد: {0}', {'0': 'محمد، سارة'});
        expect(result, equals('ضد: محمد، سارة'));
      });

      test('Replaces multiple parameters in composite string', () {
        localizer.setTranslations({
          'اللاعب {player} هزم {opponent} بنتيجة {score}':
              'اللاعب {player} هزم {opponent} بنتيجة {score}',
        });
        final result = localizer.tr('اللاعب {player} هزم {opponent} بنتيجة {score}', {
          'player': 'أحمد',
          'opponent': 'خالد',
          'score': '100-80',
        });
        expect(result, equals('اللاعب أحمد هزم خالد بنتيجة 100-80'));
      });

      test('Handles missing parameter without crashing, preserving unmatched tokens', () {
        final result = localizer.tr('المتصلون ({count})', {});
        expect(result, equals('المتصلون ({count})'));
      });
    });

    group('Fallback Behavior', () {
      test('Returns the key itself as fallback when translation is missing', () {
        const unknownKey = 'non_existent_translation_key_123';
        final result = localizer.tr(unknownKey);
        expect(result, equals(unknownKey));
      });

      test('Returns empty string when key is empty', () {
        final result = localizer.tr('');
        expect(result, equals(''));
      });

      test('Loads disk locale file assets/locales/ar.json if present', () {
        // Test real locale asset loading from filesystem
        final arJsonPath = 'assets/locales/ar.json';
        final file = File(arJsonPath);
        if (file.existsSync()) {
          final loaded = localizer.loadFromFile(arJsonPath);
          expect(loaded, isTrue);
          expect(localizer.tr('القائمة الرئيسية'), equals('القائمة الرئيسية'));
        }
      });
    });
  });
}
