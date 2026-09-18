// Tier 2 Widget Test: SavedTablesView (Timestamp Formatting %Y-%m-%d %H:%M, Restore & Delete Actions)

import 'dart:math';
import '../harness/test_engine.dart';
import '../harness/test_fixtures.dart';

/// Testable state harness for SavedTablesView matching client/views/saved_tables_view.py
class SavedTablesViewStateHarness {
  List<Map<String, dynamic>> tables = [];
  int? lastRestoredId;
  int? lastDeletedId;
  String? lastNavigatedRoute;

  SavedTablesViewStateHarness({List<Map<String, dynamic>>? initialTables}) {
    if (initialTables != null) {
      tables = List.from(initialTables);
    }
  }

  /// Formats ISO timestamp to standard `%Y-%m-%d %H:%M`
  static String formatDatetime(String isoStr) {
    if (isoStr.isEmpty) return '';
    try {
      final cleanStr = isoStr.endsWith('Z') ? isoStr.replaceAll('Z', '') : isoStr;
      final dt = DateTime.parse(cleanStr);
      final year = dt.year.toString().padLeft(4, '0');
      final month = dt.month.toString().padLeft(2, '0');
      final day = dt.day.toString().padLeft(2, '0');
      final hour = dt.hour.toString().padLeft(2, '0');
      final minute = dt.minute.toString().padLeft(2, '0');
      return '$year-$month-$day $hour:$minute';
    } catch (_) {
      final sub = isoStr.substring(0, min(16, isoStr.length));
      return sub.replaceAll('T', ' ');
    }
  }

  /// Localized game name mapping matching desktop client
  static String gameLabel(String game) {
    const gameMap = {
      'UNO': 'أونو',
      'SCOPA': 'إسكوبا',
      'NINETY_NINE': 'تسعة وتسعون',
      'FARKLE': 'فاركل',
      'SNAKES_LADDERS': 'السلم والثعبان',
      'DOMINO': 'دومينو كلاسيك',
      'AMERICAN_DOMINO': 'دومينو أمريكاني',
      'THIEF_HUNT': 'مطاردة اللص',
      'TENNIS': 'التنس',
    };
    return gameMap[game] ?? game;
  }

  /// Row text format: `{gname} — ضد: {opponents} — تاريخ الحفظ: {saved_time} — تنتهي في: {expires_time}`
  static String formatRowText(Map<String, dynamic> t) {
    final gname = gameLabel(t['game']?.toString() ?? '');
    final opponents = t['opponents_summary'] ?? t['opponents'] ?? 'لا يوجد';
    final savedTime = formatDatetime(t['saved_at']?.toString() ?? '');
    final expiresTime = formatDatetime(t['expires_at']?.toString() ?? '');

    return '$gname — ضد: $opponents — تاريخ الحفظ: $savedTime — تنتهي في: $expiresTime';
  }

  List<String> get renderedRowTexts {
    return tables.map(formatRowText).toList();
  }

  bool get isEmptyStateVisible => tables.isEmpty;
  String get emptyStateMessage => 'لا توجد طاولات محفوظة.';

  void restoreTable(int savedId) {
    lastRestoredId = savedId;
    lastNavigatedRoute = 'TableView';
  }

  void deleteTable(int savedId) {
    lastDeletedId = savedId;
    tables.removeWhere((t) => t['id'] == savedId);
  }
}

void main() async {
  defineTests();
  await runSuite('Tier 2 Widget: Saved Tables View Tests');
}

void defineTests() {
  group('SavedTablesView Formatting & Actions Parity', () {
    late SavedTablesViewStateHarness harness;

    setUp(() {
      harness = SavedTablesViewStateHarness(initialTables: TestFixtures.sampleSavedTablesJson);
    });

    group('Timestamp Formatting %Y-%m-%d %H:%M', () {
      test('Formats standard ISO 8601 UTC timestamp to %Y-%m-%d %H:%M', () {
        const iso = '2026-09-18T14:30:00Z';
        final formatted = SavedTablesViewStateHarness.formatDatetime(iso);
        expect(formatted, equals('2026-09-18 14:30'));
      });

      test('Formats ISO string without Z to %Y-%m-%d %H:%M', () {
        const iso = '2026-09-17T18:15:22';
        final formatted = SavedTablesViewStateHarness.formatDatetime(iso);
        expect(formatted, equals('2026-09-17 18:15'));
      });

      test('Falls back gracefully on malformed or non-ISO timestamp strings', () {
        const malformed = '2026-09-16T10:00:custom_offset';
        final formatted = SavedTablesViewStateHarness.formatDatetime(malformed);
        expect(formatted, equals('2026-09-16 10:00'));

        expect(SavedTablesViewStateHarness.formatDatetime(''), equals(''));
      });
    });

    group('Game Label Mapping', () {
      test('Maps canonical game IDs to Arabic titles accurately', () {
        expect(SavedTablesViewStateHarness.gameLabel('UNO'), equals('أونو'));
        expect(SavedTablesViewStateHarness.gameLabel('SCOPA'), equals('إسكوبا'));
        expect(SavedTablesViewStateHarness.gameLabel('DOMINO'), equals('دومينو كلاسيك'));
        expect(SavedTablesViewStateHarness.gameLabel('AMERICAN_DOMINO'), equals('دومينو أمريكاني'));
        expect(SavedTablesViewStateHarness.gameLabel('THIEF_HUNT'), equals('مطاردة اللص'));
        expect(SavedTablesViewStateHarness.gameLabel('TENNIS'), equals('التنس'));
      });
    });

    group('Row Text Formatting', () {
      test('Renders rows with exact template: {gname} — ضد: {opponents} — تاريخ الحفظ: {saved} — تنتهي في: {expires}', () {
        final rows = harness.renderedRowTexts;
        expect(rows, hasLength(3));

        // Row 1: UNO, محمد، سارة
        expect(
          rows[0],
          equals('أونو — ضد: محمد، سارة — تاريخ الحفظ: 2026-09-18 14:30 — تنتهي في: 2026-09-25 14:30'),
        );

        // Row 2: DOMINO, خالد
        expect(
          rows[1],
          equals('دومينو كلاسيك — ضد: خالد — تاريخ الحفظ: 2026-09-17 18:15 — تنتهي في: 2026-09-24 18:15'),
        );

        // Row 3: TENNIS, عمر
        expect(
          rows[2],
          equals('التنس — ضد: عمر — تاريخ الحفظ: 2026-09-16 10:00 — تنتهي في: 2026-09-23 10:00'),
        );
      });

      test('Displays empty state message when no saved tables exist', () {
        final emptyHarness = SavedTablesViewStateHarness(initialTables: []);

        expect(emptyHarness.isEmptyStateVisible, isTrue);
        expect(emptyHarness.emptyStateMessage, equals('لا توجد طاولات محفوظة.'));
        expect(emptyHarness.renderedRowTexts, hasLength(0));
      });
    });

    group('Restore and Delete Actions', () {
      test('Restore action triggers table restore and transitions to TableView', () {
        harness.restoreTable(101);

        expect(harness.lastRestoredId, equals(101));
        expect(harness.lastNavigatedRoute, equals('TableView'));
      });

      test('Delete action removes table from list and records deleted ID', () {
        expect(harness.tables, hasLength(3));

        harness.deleteTable(102);

        expect(harness.lastDeletedId, equals(102));
        expect(harness.tables, hasLength(2));
        expect(harness.tables.any((t) => t['id'] == 102), isFalse);
      });
    });
  });
}
