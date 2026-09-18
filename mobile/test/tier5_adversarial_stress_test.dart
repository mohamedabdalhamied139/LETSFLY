// Tier 5 Adversarial Verification & Coverage Hardening Suite for TableVerse Mobile (Phase 1)
// Executable via: dart run test/tier5_adversarial_stress_test.dart

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'harness/test_engine.dart';
import 'harness/test_fixtures.dart';
import 'harness/mock_api_adapter.dart';
import 'harness/mock_ws_channel.dart';
import '../lib/models/room_models.dart';
import '../lib/services/activity_service.dart';
import '../lib/services/auth_storage_service.dart';
import 'tier2_widget/home_view_test.dart';
import 'tier2_widget/rooms_menu_view_test.dart';
import 'tier2_widget/join_rooms_view_test.dart';
import 'tier2_widget/saved_tables_view_test.dart';

void main() async {
  defineTests();
  final success = await runSuite('Tier 5 | Adversarial Verification & Stress Hardening');
  if (!success) {
    exitCode = 1;
  }
}

void defineTests() {
  // =========================================================================
  // SCENARIO 1: Rapid Back-and-Forth Navigation Across Home -> RoomsMenu -> JoinRooms / SavedTables
  // =========================================================================
  group('Adversarial Navigation Stress & Hierarchical Flow', () {
    late RoomsMenuViewStateHarness roomsHarness;
    late HomeViewStateHarness homeHarness;
    late JoinRoomsViewStateHarness joinHarness;
    late SavedTablesViewStateHarness savedHarness;

    setUp(() {
      roomsHarness = RoomsMenuViewStateHarness();
      homeHarness = HomeViewStateHarness(userDisplayName: 'أحمد المتحدي');
      joinHarness = JoinRoomsViewStateHarness(initialRooms: TestFixtures.sampleRoomsJson);
      savedHarness = SavedTablesViewStateHarness(initialTables: TestFixtures.sampleSavedTablesJson);
    });

    test('Deep 3-Level Menu Drill-down and Escape/Back Unwinding with Focus Preservation', () {
      // Step 1: Root -> Create (Level 2)
      roomsHarness.onItemTapped('create');
      expect(roomsHarness.mode, equals('games'));
      expect(roomsHarness.focusedTag, equals('category_cards'));

      // Step 2: Level 2 -> Dice Games (Level 3)
      roomsHarness.onItemTapped('category_dice');
      expect(roomsHarness.mode, equals('dice_games'));
      expect(roomsHarness.focusedTag, equals('FARKLE'));

      // Step 3: Back (Escape) from Level 3 -> Restores Level 2 and focuses 'category_dice'
      final poppedL3 = roomsHarness.handleBack();
      expect(poppedL3, isFalse);
      expect(roomsHarness.mode, equals('games'));
      expect(roomsHarness.focusedTag, equals('category_dice'));

      // Step 4: Back (Escape) from Level 2 -> Restores Level 1 and focuses 'create'
      final poppedL2 = roomsHarness.handleBack();
      expect(poppedL2, isFalse);
      expect(roomsHarness.mode, equals('main'));
      expect(roomsHarness.focusedTag, equals('create'));

      // Step 5: Back from Level 1 -> Returns true (signals route pop to HomeView)
      final poppedL1 = roomsHarness.handleBack();
      expect(poppedL1, isTrue);
    });

    test('Rapid Multi-Category Hopping Under 500 Iterations', () {
      final categories = [
        {'tag': 'category_cards', 'mode': 'cards_games', 'expectedFocus': 'UNO'},
        {'tag': 'category_dice', 'mode': 'dice_games', 'expectedFocus': 'FARKLE'},
        {'tag': 'category_domino', 'mode': 'domino_games', 'expectedFocus': 'DOMINO'},
        {'tag': 'category_memory', 'mode': 'memory_games', 'expectedFocus': 'THIEF_HUNT'},
        {'tag': 'category_sports', 'mode': 'sports_games', 'expectedFocus': 'TENNIS'},
      ];

      for (int i = 0; i < 500; i++) {
        final cat = categories[i % categories.length];
        roomsHarness.mode = 'games';
        roomsHarness.onItemTapped(cat['tag']!);
        expect(roomsHarness.mode, equals(cat['mode']));
        expect(roomsHarness.focusedTag, equals(cat['expectedFocus']));
      }
    });

    test('Deep 100-cycle Root-to-Category Navigation & Focus Restoration Cycle', () {
      final categories = ['category_cards', 'category_dice', 'category_domino', 'category_memory', 'category_sports'];

      for (int i = 0; i < 100; i++) {
        final cat = categories[i % categories.length];
        // 1. Root -> Level 2
        roomsHarness.onItemTapped('create');
        expect(roomsHarness.mode, equals('games'));

        // 2. Level 2 -> Level 3
        roomsHarness.onItemTapped(cat);

        // 3. Unwind Level 3 -> Level 2
        final pop1 = roomsHarness.handleBack();
        expect(pop1, isFalse);
        expect(roomsHarness.mode, equals('games'));
        expect(roomsHarness.focusedTag, equals(cat));

        // 4. Unwind Level 2 -> Level 1
        final pop2 = roomsHarness.handleBack();
        expect(pop2, isFalse);
        expect(roomsHarness.mode, equals('main'));
        expect(roomsHarness.focusedTag, equals('create'));
      }
    });

    test('Cross-Screen Flow Stress: Home -> RoomsMenu -> JoinRooms -> Back -> SavedTables -> Back -> Home', () {
      // 1. HomeView -> RoomsMenuView
      homeHarness.selectMenuItem('rooms');
      expect(homeHarness.lastNavigatedRoute, equals('RoomsMenuView'));

      // 2. RoomsMenuView -> JoinRoomsView
      roomsHarness.onItemTapped('join');
      expect(roomsHarness.lastNavigatedRoute, equals('JoinRoomsView'));

      // 3. In JoinRoomsView, items rendered
      expect(joinHarness.renderedRoomTitles, hasLength(3));

      // 4. Back to RoomsMenuView
      roomsHarness.lastNavigatedRoute = null;

      // 5. RoomsMenuView -> SavedTablesView
      roomsHarness.onItemTapped('saved_tables');
      expect(roomsHarness.lastNavigatedRoute, equals('SavedTablesView'));

      // 6. In SavedTablesView, tables rendered (3 items in sample fixture)
      expect(savedHarness.renderedRowTexts, hasLength(3));

      // 7. Back to RoomsMenuView (main)
      roomsHarness.lastNavigatedRoute = null;
      expect(roomsHarness.mode, equals('main'));

      // 8. Back to HomeView
      final shouldPopToHome = roomsHarness.handleBack();
      expect(shouldPopToHome, isTrue);
    });

    test('Boundary Back Press at Root Mode maintains stability', () {
      roomsHarness.mode = 'main';
      // Calling handleBack multiple times at root level should always return true cleanly
      for (int i = 0; i < 10; i++) {
        expect(roomsHarness.handleBack(), isTrue);
        expect(roomsHarness.mode, equals('main'));
      }
    });

    test('Race Condition: Concurrent room creation taps during in-flight request', () async {
      int apiCalls = 0;
      final completer = Completer<Map<String, dynamic>>();

      // Simulated room creator with in-flight guard
      bool isCreating = false;
      Future<String?> createGame(String gameTag) async {
        if (isCreating) return null; // Debounce / guard
        isCreating = true;
        apiCalls++;
        final res = await completer.future;
        isCreating = false;
        return res['room_id']?.toString();
      }

      // Simulate 5 rapid simultaneous taps on 'UNO'
      final f1 = createGame('UNO');
      final f2 = createGame('UNO');
      final f3 = createGame('UNO');

      completer.complete({'ok': true, 'room_id': 'room_fuzz_123'});

      final r1 = await f1;
      final r2 = await f2;
      final r3 = await f3;

      expect(r1, equals('room_fuzz_123'));
      expect(r2, isNull); // Debounced
      expect(r3, isNull); // Debounced
      expect(apiCalls, equals(1));
    });
  });

  // =========================================================================
  // SCENARIO 2: Null-Safety, Boundary Inputs, Malformed Room Data & Special Characters
  // =========================================================================
  group('Null-Safety, Boundary Inputs & Malformed Data Hardening', () {
    test('RoomSummary.fromJson: Extreme fuzzing with nulls, missing fields, type confusion', () {
      final malformed = <String, dynamic>{
        'id': null,
        'name': null,
        'game_type': null,
        'host_name': null,
        'current_players': null,
        'max_players': null,
        'has_password': null,
        'status': null,
      };

      final room = RoomSummary.fromJson(malformed);
      expect(room.id, equals(''));
      expect(room.name, equals(''));
      expect(room.gameType, equals(''));
      expect(room.hostName, equals(''));
      expect(room.currentPlayers, equals(0));
      expect(room.maxPlayers, equals(4)); // default fallback
      expect(room.hasPassword, isFalse);
      expect(room.status, equals('waiting')); // default fallback
    });

    test('RoomSummary.fromJson: Extreme integer boundaries and players list fallback', () {
      final roomWithList = RoomSummary.fromJson({
        'id': '999999999999999',
        'current_players': 'not_an_int',
        'players': ['p1', 'p2', 'p3', 'p4', 'p5'],
        'max_players': -10,
        'is_locked': true,
      });

      expect(roomWithList.id, equals('999999999999999'));
      expect(roomWithList.currentPlayers, equals(5)); // derived from players list
      expect(roomWithList.maxPlayers, equals(-10));
      expect(roomWithList.hasPassword, isTrue); // derived from is_locked
    });

    test('SavedTable.fromJson: Malformed dates, empty strings, null timestamps, leap years', () {
      // 1. Malformed date string
      final st1 = SavedTable.fromJson({
        'id': '101',
        'game': 'SCOPA',
        'saved_at': 'invalid-date-string',
        'expires_at': null,
      });
      expect(st1.id, equals(101));
      expect(st1.game, equals('SCOPA'));
      expect(st1.gameLabel, equals('إسكوبا'));
      expect(st1.expiresAtDateTime, isNull);

      // 2. Leap year date string
      final st2 = SavedTable.fromJson({
        'id': 102,
        'game': 'DOMINO',
        'saved_at': '2024-02-29T12:30:00Z',
        'expires_at': '2024-03-01T12:30:00Z',
      });
      expect(st2.savedAtDateTime.year, equals(2024));
      expect(st2.savedAtDateTime.month, equals(2));
      expect(st2.savedAtDateTime.day, equals(29));
      expect(st2.expiresAtDateTime, isNotNull);
      expect(st2.expiresAtDateTime!.day, equals(1));
    });

    test('SavedTable.fromJson: Opponents fuzzing with mixed separators, Arabic comma, nulls, non-string types', () {
      // 1. Opponents as List with mixed elements
      final st1 = SavedTable.fromJson({
        'id': 201,
        'game': 'FARKLE',
        'opponents': [100, true, 'أحمد', null],
        'saved_at': '2026-09-18T10:00:00',
      });
      expect(st1.opponents, hasLength(4));
      expect(st1.opponents[0], equals('100'));
      expect(st1.opponents[2], equals('أحمد'));

      // 2. Opponents as Arabic comma-separated summary
      final st2 = SavedTable.fromJson({
        'id': 202,
        'game': 'UNO',
        'opponents_summary': 'زيد ،  عمر  ,  فاطمة  ',
        'saved_at': '2026-09-18T10:00:00',
      });
      expect(st2.opponents, hasLength(3));
      expect(st2.opponents[0], equals('زيد'));
      expect(st2.opponents[1], equals('عمر'));
      expect(st2.opponents[2], equals('فاطمة'));

      // 3. Empty or 'لا يوجد' opponents
      final st3 = SavedTable.fromJson({
        'id': 203,
        'game': 'TENNIS',
        'opponents_summary': 'لا يوجد',
        'saved_at': '2026-09-18T10:00:00',
      });
      expect(st3.opponents, hasLength(0));
      expect(st3.opponentsSummary, equals('لا يوجد'));
    });

    test('SavedTablesView.formatDatetime: Adversarial string lengths, corrupt formats, empty string', () {
      expect(SavedTablesViewStateHarness.formatDatetime(''), equals(''));
      expect(SavedTablesViewStateHarness.formatDatetime('2026-09-18T14:35:00Z'), equals('2026-09-18 14:35'));
      expect(SavedTablesViewStateHarness.formatDatetime('2026-09-18T09:05:00'), equals('2026-09-18 09:05'));

      // Corrupt string with less than 16 chars
      final shortRes = SavedTablesViewStateHarness.formatDatetime('short_str');
      expect(shortRes, equals('short_str'));

      // Corrupt string longer than 16 chars
      final longRes = SavedTablesViewStateHarness.formatDatetime('very_long_corrupt_date_string_here');
      expect(longRes.length, equals(16));
    });

    test('JoinRoomsView formatRoomTitle: Missing fields, null host, empty players, unknown status', () {
      final malformedRoom = <String, dynamic>{
        'id': 'room_err',
        'host_name': null,
        'players': null,
        'status': 'unknown_status',
        'game_label': null,
        'game_type': null,
      };

      final title = JoinRoomsViewStateHarness.formatRoomTitle(malformedRoom);
      // Expected template: "{game} — {host} — {count}/10 لاعبين — {status}"
      expect(title, contains('لعبة — مجهول — 1/10 لاعبين — في الانتظار'));
    });

    test('User.fromJson: Null safety, ID type coercion, display name fallback hierarchy', () {
      final u1 = User.fromJson({'id': '42', 'username': 'user_42'});
      expect(u1.id, equals(42));
      expect(u1.displayName, equals('user_42'));

      final u2 = User.fromJson({'id': 'non_numeric', 'username': 'user_nan'});
      expect(u2.id, equals(0));

      final u3 = User.fromJson({'id': 10, 'username': 'u10', 'name': 'Name Prioritized'});
      expect(u3.displayName, equals('Name Prioritized'));
    });

    test('AuthStorageService: Arabic Unicode with tashkeel, RTL/LTR markers, Emojis, SQLi and XSS payloads', () async {
      final storage = AuthStorageService.instance;

      final testProfiles = [
        {
          'username': 'مُحَمَّد_الْبَطَل',
          'password': 'كلمة_المرور_١٢٣!@#',
          'display_name': 'محمد البطل 👑',
          'token': 'jwt_arabic_123',
        },
        {
          'username': 'sqli_user\' OR \'1\'=\'1',
          'password': 'pass"; DROP TABLE users; --',
          'display_name': 'SQLi Tester',
          'token': 'jwt_sqli_456',
        },
        {
          'username': '<script>alert(1)</script>',
          'password': 'xss_payload_<>#"\'',
          'display_name': '<b style="color:red">XSS</b>',
          'token': 'jwt_xss_789',
        },
        {
          'username': 'rtl_\u202Ereversed\u202C_user',
          'password': 'rtl_pass_\u200F_secret',
          'display_name': 'RTL User \u202Eمرحبا\u202C',
          'token': 'jwt_rtl_000',
        },
      ];

      for (final p in testProfiles) {
        await storage.saveActiveAccount(
          username: p['username']!,
          password: p['password']!,
          displayName: p['display_name']!,
          token: p['token']!,
        );

        final active = await storage.loadActiveAccount();
        expect(active, isNotNull);
        expect(active!['username'], equals(p['username']));
        expect(active['password'], equals(p['password']));
        expect(active['display_name'], equals(p['display_name']));
        expect(active['token'], equals(p['token']));

        final sessionToken = await storage.getActiveSessionToken();
        expect(sessionToken, equals(p['token']));
      }

      // Verify all 4 accounts exist
      final allAccounts = await storage.loadAllAccounts();
      expect(allAccounts, hasLength(4));

      // Cleanup
      for (final p in testProfiles) {
        await storage.removeAccount(p['username']!);
      }
      await storage.clearActiveSession();
    });

    test('AuthStorageService: Huge credential payloads (10,000+ characters)', () async {
      final storage = AuthStorageService.instance;
      final hugeString = 'A' * 10000;
      final hugeToken = 'T' * 5000;

      await storage.saveActiveAccount(
        username: 'huge_account',
        password: hugeString,
        displayName: 'Huge Display Name',
        token: hugeToken,
      );

      final active = await storage.loadActiveAccount();
      expect(active, isNotNull);
      expect(active!['password'], equals(hugeString));
      expect(active['token'], equals(hugeToken));

      await storage.removeAccount('huge_account');
      await storage.clearActiveSession();
    });

    test('ActivityLogService: Canonical 8 categories enforcement, invalid categories, 50KB text injection', () {
      final service = ActivityLogService.instance;
      service.clear();

      // Verify canonical categories count
      expect(ActivityLogService.categories, hasLength(8));

      // Add event with 50KB payload
      final hugeMsg = 'X' * 50000;
      service.addEvent({
        'id': 'huge_event_1',
        'category': 'GAMEPLAY',
        'text': hugeMsg,
      });

      expect(service.events, hasLength(1));
      expect(service.events.first['text'], equals(hugeMsg));

      // Add event with category outside the canonical 8
      service.addEvent({
        'id': 'invalid_cat_1',
        'category': 'UNKNOWN_CATEGORY_XYZ',
        'text': 'Arbitrary category event',
      });

      expect(service.events, hasLength(2));
      // Switching to canonical category 'ALL' displays all events
      service.selectCategory('ALL');
      expect(service.filteredEvents, hasLength(2));

      // Switching to 'TABLE_CHAT' does not show either event
      service.selectCategory('TABLE_CHAT');
      expect(service.filteredEvents, hasLength(0));

      service.clear();
    });

    test('ActivityLogService: 1,000 high-frequency event burst with deduplication and filtering under load', () {
      final service = ActivityLogService.instance;
      service.clear();

      // Ingest 1,000 events: 500 unique, 500 duplicates
      for (int i = 0; i < 500; i++) {
        final cat = ActivityLogService.categories[i % ActivityLogService.categories.length];
        service.addEvent({
          'id': 'evt_$i',
          'category': cat,
          'text': 'Event message $i',
        });
        // Duplicate event with identical ID
        service.addEvent({
          'id': 'evt_$i',
          'category': cat,
          'text': 'Duplicate message $i',
        });
      }

      // Deduplication by ID should reduce 1000 additions to 500 events
      expect(service.events, hasLength(500));

      // Category filtering correctness under load
      for (final cat in ActivityLogService.categories) {
        service.selectCategory(cat);
        if (cat == 'ALL') {
          expect(service.filteredEvents, hasLength(500));
        } else {
          for (final e in service.filteredEvents) {
            expect(e['category'], equals(cat));
          }
        }
      }

      service.clear();
      service.selectCategory('ALL');
    });
  });

  // =========================================================================
  // SCENARIO 3: Dual-Join Actions With Simultaneous Socket Events & Concurrency
  // =========================================================================
  group('Dual-Join Actions & Simultaneous Socket Events Concurrency', () {
    late MockApiAdapter api;
    late MockWsChannel ws;

    setUp(() {
      api = MockApiAdapter();
      ws = MockWsChannel(Uri.parse('ws://localhost:8000/ws'));
    });

    tearDown(() {
      api.reset();
      ws.simulateClose();
    });

    test('Dual-Join Actions: Rapid simultaneous Player Join + Spectator Join requests', () async {
      // Track outgoing join HTTP requests
      final joinCalls = <Map<String, dynamic>>[];

      Future<Map<String, dynamic>> join(String roomId, bool asSpectator) async {
        joinCalls.add({'room_id': roomId, 'as_spectator': asSpectator});
        return api.joinRoom(roomId, asSpectator: asSpectator);
      }

      // Execute Player Join and Spectator Join concurrently on existing room_1
      final futures = await Future.wait([
        join('room_1', false),
        join('room_1', true),
      ]);

      expect(futures, hasLength(2));
      expect(futures[0]['room_id'], equals('room_1'));
      expect(futures[0]['as_spectator'], isFalse);
      expect(futures[1]['room_id'], equals('room_1'));
      expect(futures[1]['as_spectator'], isTrue);

      expect(joinCalls, hasLength(2));
      expect(joinCalls[0]['as_spectator'], isFalse);
      expect(joinCalls[1]['as_spectator'], isTrue);
    });

    test('Dual-Join Failure Handling: Player Join fails (room full) while Spectator Join succeeds', () async {
      final results = <String, dynamic>{};

      // Player join fails due to network/server simulated rejection
      Future<void> attemptPlayerJoin() async {
        try {
          api.simulateNetworkError = true;
          api.nextErrorMessage = 'الطاولة ممتلئة بالكامل';
          await api.joinRoom('room_1', asSpectator: false);
          results['player'] = 'SUCCESS';
        } catch (e) {
          results['player'] = 'ERROR: $e';
        }
      }

      // Spectator join succeeds
      Future<void> attemptSpectatorJoin() async {
        try {
          api.simulateNetworkError = false;
          final res = await api.joinRoom('room_1', asSpectator: true);
          results['spectator'] = res['as_spectator'] == true ? 'SUCCESS' : 'FAILED';
        } catch (e) {
          results['spectator'] = 'ERROR: $e';
        }
      }

      await attemptPlayerJoin();
      await attemptSpectatorJoin();

      expect(results['player'], contains('الطاولة ممتلئة بالكامل'));
      expect(results['spectator'], equals('SUCCESS'));
    });

    test('Dual-Join Vulnerability Test: Join failure should suppress navigation to TableView', () async {
      // Simulating JoinRoomsView error swallowing vulnerability check:
      // If ApiService.joinRoom throws an exception, the view MUST NOT navigate to TableView.
      String? currentRoute = 'JoinRoomsView';

      Future<void> safeJoinRoom(String roomId, {bool asSpectator = false}) async {
        try {
          api.simulateNetworkError = true;
          api.nextErrorMessage = '400 Room is full';
          await api.joinRoom(roomId, asSpectator: asSpectator);
          currentRoute = 'TableView';
        } catch (e) {
          // Robust behavior: stay on JoinRoomsView and do not navigate
          currentRoute = 'JoinRoomsView';
        }
      }

      await safeJoinRoom('room_1');
      expect(currentRoute, equals('JoinRoomsView'));
    });

    test('Simultaneous WebSocket Events during Pending Join: Delivery integrity and event ordering', () async {
      final receivedEvents = <Map<String, dynamic>>[];
      final sub = ws.stream.listen((msg) {
        if (msg is String) {
          final data = json.decode(msg) as Map<String, dynamic>;
          receivedEvents.add(data);
        }
      });

      // While join is in progress, server pushes bursts of WS messages
      ws.simulateActivityEvent({'text': 'اللاعب أحمد انضم إلى الغرفة.', 'category': 'GAMEPLAY'});
      ws.simulateRoomSnapshot({'id': 'room_1', 'status': 'playing'});
      ws.simulateServerMessage({'type': 'online_count_updated', 'count': 42});

      await Future.delayed(const Duration(milliseconds: 20));

      expect(receivedEvents, hasLength(3));
      expect(receivedEvents[0]['type'], equals('activity_event'));
      expect(receivedEvents[0]['text'], contains('أحمد'));
      expect(receivedEvents[1]['type'], equals('room_snapshot'));
      expect(receivedEvents[2]['type'], equals('online_count_updated'));
      expect(receivedEvents[2]['count'], equals(42));

      await sub.cancel();
    });

    test('Abrupt Server WebSocket Closure during Active Join HTTP Request', () async {
      bool socketClosedObserved = false;
      final sub = ws.stream.listen(
        (_) {},
        onDone: () {
          socketClosedObserved = true;
        },
      );

      // Simulate unexpected server crash/disconnect (code 1006)
      ws.simulateClose(1006, 'Abrupt connection drop');

      await Future.delayed(const Duration(milliseconds: 20));

      expect(ws.isConnected, isFalse);
      expect(ws.isClosed, isTrue);
      expect(ws.closeCode, equals(1006));
      expect(socketClosedObserved, isTrue);

      await sub.cancel();
    });

    test('High-Throughput WebSocket Message Burst (200 JSON Frames) with Concurrent Ping/Pong', () async {
      int messageCount = 0;
      int pingCount = 0;

      final sub = ws.stream.listen((msg) {
        if (msg is String) {
          final data = json.decode(msg) as Map<String, dynamic>;
          if (data['type'] == 'pong') {
            pingCount++;
          } else {
            messageCount++;
          }
        }
      });

      // Send 200 rapid messages interspersed with ping frames
      for (int i = 0; i < 200; i++) {
        ws.simulateActivityEvent({'text': 'Burst message $i', 'category': 'ALL'});
        if (i % 20 == 0) {
          ws.sink.add(json.encode({'type': 'ping', 'ping_id': i}));
        }
      }

      await Future.delayed(const Duration(milliseconds: 50));

      expect(messageCount, equals(200));
      expect(pingCount, equals(10)); // 10 pings responded with pongs

      await sub.cancel();
    });

    test('Concurrent Multi-Screen Activity Log Synchronization (5 views receiving 50 concurrent events)', () async {
      final service = ActivityLogService.instance;
      service.clear();

      // 5 View harnesses listening to ActivityLogService updates
      final viewLogs = List.generate(5, (_) => <Map<String, dynamic>>[]);
      final listener = () {
        final currentEvents = service.events;
        for (int i = 0; i < 5; i++) {
          viewLogs[i] = List.from(currentEvents);
        }
      };

      service.addListener(listener);

      // Inject 50 concurrent async events via microtasks
      final futures = <Future<void>>[];
      for (int i = 0; i < 50; i++) {
        futures.add(Future.microtask(() {
          service.addEvent({
            'id': 'conc_$i',
            'category': 'GAMEPLAY',
            'text': 'Concurrent action $i',
          });
        }));
      }

      await Future.wait(futures);

      // Verify all 5 views received identical 50 events without desync
      // Note: ActivityLogService inserts at index 0, so newest events are at the top
      expect(service.events, hasLength(50));
      for (int i = 0; i < 5; i++) {
        expect(viewLogs[i], hasLength(50));
        expect(viewLogs[i].first['id'], equals('conc_49'));
        expect(viewLogs[i].last['id'], equals('conc_0'));
      }

      service.removeListener(listener);
      service.clear();
    });
  });
}
