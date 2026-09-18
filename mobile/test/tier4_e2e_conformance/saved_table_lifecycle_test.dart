// Tier 4 Conformance Test: End-to-End Saved Table Lifecycle (List -> Restore -> TableView Transition -> Delete)

import '../harness/test_engine.dart';
import '../harness/mock_api_adapter.dart';
import '../tier1_unit/activity_service_test.dart';
import '../tier2_widget/saved_tables_view_test.dart';

/// End-to-End Controller coordinating saved tables actions and view transitions
class SavedTableLifecycleController {
  final MockApiAdapter api;
  final TestActivityLogService activityLog;

  String? currentView;
  Map<String, dynamic>? activeTableSession;
  final List<String> audioCues = [];
  final List<String> spokenAnnouncements = [];
  List<Map<String, dynamic>> displayedTables = [];

  SavedTableLifecycleController({
    required this.api,
    required this.activityLog,
  }) {
    currentView = 'SavedTablesView';
  }

  /// 1. Load saved tables list from API
  Future<void> loadSavedTables() async {
    final rawTables = await api.getSavedTables();
    displayedTables = List.from(rawTables);
  }

  /// 2. Restore saved table into active table session
  Future<bool> restoreTable(int savedId) async {
    try {
      spokenAnnouncements.add('استعادة الطاولة...');

      final res = await api.restoreSavedTable(savedId);
      final roomId = res['room_id'] as String;
      final game = res['game'] as String;

      // Audio & announcement cues matching Windows client
      audioCues.add('TABLE_JOIN');
      spokenAnnouncements.add('تم استرجاع الطاولة بنجاح.');

      // Centralized activity log event
      activityLog.addEvent({
        'category': 'GAMEPLAY',
        'text': 'تم استرجاع طاولة $game بنجاح.',
      });

      // Navigate to active table
      activeTableSession = {
        'room_id': roomId,
        'game': game,
        'is_restored': true,
      };
      currentView = 'TableView';
      return true;
    } catch (e) {
      audioCues.add('INVALID_ACTION');
      spokenAnnouncements.add('تعذر استرجاع الطاولة: $e');
      return false;
    }
  }

  /// 3. Delete saved table
  Future<bool> deleteTable(int savedId) async {
    try {
      await api.deleteSavedTable(savedId);

      audioCues.add('ACTION_CLICK');
      spokenAnnouncements.add('تم حذف الطاولة المحفوظة.');

      activityLog.addEvent({
        'category': 'ALL',
        'text': 'تم حذف الطاولة المحفوظة رقم $savedId.',
      });

      // Refresh list
      await loadSavedTables();
      return true;
    } catch (e) {
      spokenAnnouncements.add('تعذر حذف الطاولة: $e');
      return false;
    }
  }
}

void main() async {
  defineTests();
  await runSuite('Tier 4 Conformance: Saved Table Lifecycle Tests');
}

void defineTests() {
  group('Saved Table End-to-End Lifecycle Conformance', () {
    late MockApiAdapter api;
    late TestActivityLogService activityLog;
    late SavedTableLifecycleController controller;

    setUp(() {
      api = MockApiAdapter();
      activityLog = TestActivityLogService();
      controller = SavedTableLifecycleController(api: api, activityLog: activityLog);
    });

    test('Step 1: Fetches and displays formatted saved tables with %Y-%m-%d %H:%M timestamps', () async {
      await controller.loadSavedTables();

      expect(controller.displayedTables, hasLength(3));

      final firstTable = controller.displayedTables.first;
      expect(firstTable['id'], equals(101));
      expect(firstTable['game'], equals('UNO'));

      // Validate formatting matches Windows client format
      final formattedRow = SavedTablesViewStateHarness.formatRowText(firstTable);
      expect(formattedRow, contains('أونو — ضد: محمد، سارة'));
      expect(formattedRow, contains('تاريخ الحفظ: 2026-09-18 14:30'));
      expect(formattedRow, contains('تنتهي في: 2026-09-25 14:30'));
    });

    test('Step 2: Restores saved table, plays TABLE_JOIN audio, and transitions to TableView', () async {
      await controller.loadSavedTables();

      final success = await controller.restoreTable(101);
      expect(success, isTrue);

      // Transitions to TableView
      expect(controller.currentView, equals('TableView'));
      expect(controller.activeTableSession?['room_id'], equals('saved_room_uno'));
      expect(controller.activeTableSession?['game'], equals('UNO'));

      // Audio & Speech cues
      expect(controller.audioCues, contains('TABLE_JOIN'));
      expect(controller.spokenAnnouncements, contains('تم استرجاع الطاولة بنجاح.'));

      // Centralized activity log event
      expect(activityLog.events, hasLength(1));
      expect(activityLog.events.first['text'], contains('تم استرجاع طاولة UNO بنجاح.'));

      // REST call verified
      expect(api.hasCalled('POST', '/api/rooms/saved/101/restore'), isTrue);
    });

    test('Step 3: Handles restore error gracefully with INVALID_ACTION cue when table not found', () async {
      final success = await controller.restoreTable(99999); // Non-existent
      expect(success, isFalse);

      expect(controller.currentView, equals('SavedTablesView'));
      expect(controller.activeTableSession, isNull);
      expect(controller.audioCues, contains('INVALID_ACTION'));
      expect(controller.spokenAnnouncements.last, contains('تعذر استرجاع الطاولة'));
    });

    test('Step 4: Deletes saved table, plays ACTION_CLICK, and updates list in real-time', () async {
      await controller.loadSavedTables();
      expect(controller.displayedTables, hasLength(3));

      // Delete table 102 (DOMINO)
      final success = await controller.deleteTable(102);
      expect(success, isTrue);

      // List refreshed: table 102 is removed
      expect(controller.displayedTables, hasLength(2));
      expect(controller.displayedTables.any((t) => t['id'] == 102), isFalse);

      // Audio & announcements
      expect(controller.audioCues, contains('ACTION_CLICK'));
      expect(controller.spokenAnnouncements, contains('تم حذف الطاولة المحفوظة.'));

      // Centralized activity log
      expect(activityLog.events.first['text'], contains('تم حذف الطاولة المحفوظة رقم 102.'));

      // REST call verified
      expect(api.hasCalled('DELETE', '/api/rooms/saved/102'), isTrue);
    });
  });
}
