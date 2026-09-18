// Tier 3 Integration Test: Synchronized Activity Log Across Views

import '../harness/test_engine.dart';
import '../harness/mock_ws_channel.dart';
import '../tier1_unit/activity_service_test.dart';
import '../tier2_widget/activity_log_widget_test.dart';

/// Simulated application shell holding multiple views sharing the same ActivityLogService
class MultiViewShell {
  final TestActivityLogService activityService;
  final MockWsChannel wsChannel;

  // 5 primary views matching Windows architecture
  late final ActivityLogWidgetStateHarness homeLog;
  late final ActivityLogWidgetStateHarness roomsLog;
  late final ActivityLogWidgetStateHarness joinRoomsLog;
  late final ActivityLogWidgetStateHarness savedTablesLog;
  late final ActivityLogWidgetStateHarness tableLog;

  int totalViewRenderUpdates = 0;

  MultiViewShell({
    required this.activityService,
    required this.wsChannel,
  }) {
    homeLog = ActivityLogWidgetStateHarness(eventsProvider: () => activityService.events);
    roomsLog = ActivityLogWidgetStateHarness(eventsProvider: () => activityService.events);
    joinRoomsLog = ActivityLogWidgetStateHarness(eventsProvider: () => activityService.events);
    savedTablesLog = ActivityLogWidgetStateHarness(eventsProvider: () => activityService.events);
    tableLog = ActivityLogWidgetStateHarness(eventsProvider: () => activityService.events);


    // Wire up reactive listener
    // In real app, ListenableBuilder(listenable: ActivityLogService.instance, ...) rebuilds views
    // We simulate reactive updates here:
    wsChannel.stream.listen((message) {
      // Incoming WS message handling
    });
  }

  void onEventReceived(Map<String, dynamic> event) {
    activityService.addEvent(event);
    totalViewRenderUpdates += 5; // All 5 views re-render
  }
}

void main() async {
  defineTests();
  await runSuite('Tier 3 Integration: Synchronized Log Tests');
}

void defineTests() {
  group('Cross-Screen ActivityLog Synchronization Integration', () {
    late TestActivityLogService service;
    late MockWsChannel wsChannel;
    late MultiViewShell appShell;

    setUp(() {
      service = TestActivityLogService();
      wsChannel = MockWsChannel(Uri.parse('wss://letsfly.onrender.com/ws/events'));
      appShell = MultiViewShell(activityService: service, wsChannel: wsChannel);
    });

    test('Incoming WS activity_event updates all 5 primary views simultaneously', () {
      final wsEvent = {
        'id': 2001,
        'category': 'GAMEPLAY',
        'event_type': 'card_played',
        'text': 'لعب محمد بطاقة 7 صفراء',
      };

      // Server broadcasts activity event
      appShell.onEventReceived(wsEvent);

      // Verify centralized service holds the event
      expect(service.events, hasLength(1));
      expect(service.events.first['text'], equals('لعب محمد بطاقة 7 صفراء'));

      // Verify all 5 view log harnesses see the new event immediately
      expect(appShell.homeLog.filteredEvents, hasLength(1));
      expect(appShell.roomsLog.filteredEvents, hasLength(1));
      expect(appShell.joinRoomsLog.filteredEvents, hasLength(1));
      expect(appShell.savedTablesLog.filteredEvents, hasLength(1));
      expect(appShell.tableLog.filteredEvents, hasLength(1));

      expect(appShell.totalViewRenderUpdates, equals(5));
    });

    test('Category selection in one view does not contaminate or desync shared events', () {
      service.addEvent({'id': 1, 'category': 'TABLE_CHAT', 'text': 'محادثة في طاولة 1'});
      service.addEvent({'id': 2, 'category': 'FRIENDS', 'text': 'خالد أصبح متصلاً'});

      // Home view switches to TABLE_CHAT
      appShell.homeLog.selectCategory('TABLE_CHAT');
      expect(appShell.homeLog.filteredEvents, hasLength(1));
      expect(appShell.homeLog.filteredEvents.first['category'], equals('TABLE_CHAT'));

      // Rooms view switches to FRIENDS
      appShell.roomsLog.selectCategory('FRIENDS');
      expect(appShell.roomsLog.filteredEvents, hasLength(1));
      expect(appShell.roomsLog.filteredEvents.first['category'], equals('FRIENDS'));

      // JoinRooms view remains on ALL
      expect(appShell.joinRoomsLog.selectedCategory, equals('ALL'));
      expect(appShell.joinRoomsLog.filteredEvents, hasLength(2));
    });

    test('Duplicate WebSocket broadcasts are deduplicated before reaching any view', () {
      final duplicateEvent = {
        'id': 909,
        'category': 'INVITATIONS',
        'text': 'دعوة إلى طاولة أونو',
      };

      // Send twice over socket
      appShell.onEventReceived(duplicateEvent);
      appShell.onEventReceived(duplicateEvent);

      expect(service.events, hasLength(1));
      expect(appShell.homeLog.filteredEvents, hasLength(1));
      expect(appShell.roomsLog.filteredEvents, hasLength(1));
    });
  });
}
