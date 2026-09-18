// Tier 3 Integration Test: Rooms Navigation Flow (HomeView -> RoomsMenuView -> JoinRoomsView / SavedTablesView -> TableView)

import '../harness/test_engine.dart';
import '../harness/mock_api_adapter.dart';
import '../tier2_widget/rooms_menu_view_test.dart';
import '../tier2_widget/join_rooms_view_test.dart';
import '../tier2_widget/saved_tables_view_test.dart';

/// Navigation coordinator tracking view stack transitions
class AppNavigationCoordinator {
  final MockApiAdapter api;
  final List<String> navigationStack = [];
  Map<String, dynamic>? currentTableSession;

  AppNavigationCoordinator(this.api) {
    navigationStack.add('HomeView');
  }

  String get currentView => navigationStack.isNotEmpty ? navigationStack.last : '';

  void push(String view) {
    navigationStack.add(view);
  }

  bool pop() {
    if (navigationStack.length > 1) {
      navigationStack.removeLast();
      return true;
    }
    return false;
  }

  /// Flow 1: HomeView -> RoomsMenuView -> JoinRoomsView -> Join -> TableView
  Future<void> executeJoinRoomFlow(String roomId, {bool asSpectator = false}) async {
    // 1. From HomeView, tap 'rooms'
    push('RoomsMenuView');

    // 2. From RoomsMenuView Level 1, tap 'join'
    push('JoinRoomsView');

    // 3. Fetch rooms and select room to join
    final rooms = await api.getRooms();
    final target = rooms.firstWhere((r) => r['id'].toString() == roomId);

    final joinResult = await api.joinRoom(roomId, asSpectator: asSpectator);
    currentTableSession = {
      'room_id': roomId,
      'game': target['game_type'] ?? target['game'],
      'as_spectator': asSpectator,
      'room_payload': joinResult['room'],
    };

    // 4. Navigate into TableView
    push('TableView');
  }

  /// Flow 2: HomeView -> RoomsMenuView -> SavedTablesView -> Restore -> TableView
  Future<void> executeRestoreSavedTableFlow(int savedId) async {
    // 1. From HomeView, tap 'rooms'
    push('RoomsMenuView');

    // 2. From RoomsMenuView Level 1, tap 'saved_tables'
    push('SavedTablesView');

    // 3. Fetch saved tables and restore
    final tables = await api.getSavedTables();
    final target = tables.firstWhere((t) => t['id'] == savedId);

    final restoreResult = await api.restoreSavedTable(savedId);
    currentTableSession = {
      'room_id': restoreResult['room_id'],
      'game': target['game'],
      'is_restored': true,
    };

    // 4. Navigate into TableView
    push('TableView');
  }

  /// Flow 3: HomeView -> RoomsMenuView (Level 1) -> Categories (Level 2) -> Games (Level 3) -> Create -> TableView
  Future<void> executeCreateGameFlow(String categoryTag, String gameId) async {
    // 1. HomeView -> RoomsMenuView Level 1
    push('RoomsMenuView');

    // 2. RoomsMenuView Level 1 -> tap 'create' (Level 2)
    final roomsHarness = RoomsMenuViewStateHarness();
    roomsHarness.onItemTapped('create');

    // 3. Level 2 Categories -> tap category (Level 3)
    roomsHarness.onItemTapped(categoryTag);

    // 4. Level 3 Games -> tap gameId -> Call API createRoom
    final res = await api.createRoom(
      name: 'طاولة $gameId جديدة',
      gameType: gameId,
      maxPlayers: 4,
    );

    currentTableSession = {
      'room_id': res['id'],
      'game': gameId,
      'is_host': true,
      'room_payload': res['room'],
    };

    // 5. Navigate into TableView
    push('TableView');
  }
}

void main() async {
  defineTests();
  await runSuite('Tier 3 Integration: Rooms Navigation Flow Tests');
}

void defineTests() {
  group('Rooms Navigation Flow Integration', () {
    late MockApiAdapter api;
    late AppNavigationCoordinator coordinator;

    setUp(() {
      api = MockApiAdapter();
      coordinator = AppNavigationCoordinator(api);
    });

    test('Flow 1: HomeView -> RoomsMenuView -> JoinRoomsView -> TableView (Player Join)', () async {
      expect(coordinator.currentView, equals('HomeView'));

      await coordinator.executeJoinRoomFlow('room_1', asSpectator: false);

      expect(coordinator.currentView, equals('TableView'));
      expect(coordinator.currentTableSession?['room_id'], equals('room_1'));
      expect(coordinator.currentTableSession?['as_spectator'], isFalse);

      expect(api.hasCalled('GET', '/api/rooms'), isTrue);
      expect(api.hasCalled('POST', '/api/rooms/room_1/join'), isTrue);

      // Back navigation pops TableView -> JoinRoomsView -> RoomsMenuView -> HomeView
      expect(coordinator.pop(), isTrue);
      expect(coordinator.currentView, equals('JoinRoomsView'));

      expect(coordinator.pop(), isTrue);
      expect(coordinator.currentView, equals('RoomsMenuView'));

      expect(coordinator.pop(), isTrue);
      expect(coordinator.currentView, equals('HomeView'));
    });

    test('Flow 2: HomeView -> RoomsMenuView -> JoinRoomsView -> TableView (Spectator Join)', () async {
      await coordinator.executeJoinRoomFlow('room_2', asSpectator: true);

      expect(coordinator.currentView, equals('TableView'));
      expect(coordinator.currentTableSession?['room_id'], equals('room_2'));
      expect(coordinator.currentTableSession?['as_spectator'], isTrue);

      final joinCall = api.getLastCall('/api/rooms/room_2/join');
      expect(joinCall?['body']?['as_spectator'], isTrue);
    });

    test('Flow 3: HomeView -> RoomsMenuView -> SavedTablesView -> Restore Table -> TableView', () async {
      await coordinator.executeRestoreSavedTableFlow(101);

      expect(coordinator.currentView, equals('TableView'));
      expect(coordinator.currentTableSession?['is_restored'], isTrue);
      expect(coordinator.currentTableSession?['game'], equals('UNO'));

      expect(api.hasCalled('GET', '/api/rooms/saved'), isTrue);
      expect(api.hasCalled('POST', '/api/rooms/saved/101/restore'), isTrue);

      // Back from table returns to SavedTablesView
      coordinator.pop();
      expect(coordinator.currentView, equals('SavedTablesView'));
    });

    test('Flow 4: HomeView -> RoomsMenuView (3 Levels) -> Create Game -> TableView', () async {
      await coordinator.executeCreateGameFlow('category_cards', 'UNO');

      expect(coordinator.currentView, equals('TableView'));
      expect(coordinator.currentTableSession?['game'], equals('UNO'));
      expect(coordinator.currentTableSession?['is_host'], isTrue);

      expect(api.hasCalled('POST', '/api/rooms'), isTrue);
      final createCall = api.getLastCall('/api/rooms');
      expect(createCall?['body']?['game_type'], equals('UNO'));
    });
  });
}
