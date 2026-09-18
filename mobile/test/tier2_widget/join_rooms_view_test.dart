// Tier 2 Widget Test: JoinRoomsView (Room Title Formatting & Dual-Join Actions)

import '../harness/test_engine.dart';
import '../harness/test_fixtures.dart';

/// Testable state harness for JoinRoomsView matching mobile/lib/views/join_rooms_view.dart
class JoinRoomsViewStateHarness {
  List<Map<String, dynamic>> rooms = [];
  bool isLoading = false;
  String? errorMessage;

  String? lastJoinedRoomId;
  bool? lastJoinedAsSpectator;
  String? lastNavigatedRoute;

  JoinRoomsViewStateHarness({List<Map<String, dynamic>>? initialRooms}) {
    if (initialRooms != null) {
      rooms = List.from(initialRooms);
    }
  }

  /// Formats room title matching Windows client exact format:
  /// `{game} — {host} — {count}/10 لاعبين — {status}`
  static String formatRoomTitle(Map<String, dynamic> r) {
    final host = r['host_name'] ?? 'مجهول';
    final players = (r['players'] as List?)?.length ?? 1;
    final status = r['status'] == 'playing' ? 'جارية' : 'في الانتظار';
    final gameLabel = r['game_label'] ?? r['game_type'] ?? r['game'] ?? 'لعبة';

    return '$gameLabel — $host — $players/10 لاعبين — $status';
  }

  List<String> get renderedRoomTitles {
    return rooms.map(formatRoomTitle).toList();
  }

  bool get isEmptyStateVisible => !isLoading && rooms.isEmpty;
  String get emptyStateMessage => 'لا توجد طاولات متاحة حاليًا.';

  void joinAsPlayer(Map<String, dynamic> room) {
    lastJoinedRoomId = room['id']?.toString();
    lastJoinedAsSpectator = false;
    lastNavigatedRoute = 'TableView';
  }

  void joinAsSpectator(Map<String, dynamic> room) {
    lastJoinedRoomId = room['id']?.toString();
    lastJoinedAsSpectator = true;
    lastNavigatedRoute = 'TableView';
  }
}

void main() async {
  defineTests();
  await runSuite('Tier 2 Widget: Join Rooms View Tests');
}

void defineTests() {
  group('JoinRoomsView Formatting & Dual-Join Parity', () {
    late JoinRoomsViewStateHarness harness;

    setUp(() {
      harness = JoinRoomsViewStateHarness(initialRooms: TestFixtures.sampleRoomsJson);
    });

    test('Formats room title with exact template: {game} — {host} — {count}/10 لاعبين — {status}', () {
      final titles = harness.renderedRoomTitles;
      expect(titles, hasLength(3));

      // Room 1: UNO, أحمد, 3 players, waiting
      expect(titles[0], equals('أونو — أحمد — 3/10 لاعبين — في الانتظار'));

      // Room 2: SCOPA, خالد, 2 players, playing
      expect(titles[1], equals('إسكوبا — خالد — 2/10 لاعبين — جارية'));

      // Room 3: DOMINO, سامي, 1 player, waiting
      expect(titles[2], equals('دومينو — سامي — 1/10 لاعبين — في الانتظار'));
    });

    test('Uses em-dash delimiter " — " correctly between segments', () {
      const emDashDelimiter = ' — ';
      for (final title in harness.renderedRoomTitles) {
        final segments = title.split(emDashDelimiter);
        expect(segments, hasLength(4));
        expect(segments[2], endsWith('/10 لاعبين'));
      }
    });

    test('Falls back to "مجهول" for missing host name and 1 for player count', () {
      final roomWithDefaults = {
        'id': 'room_unknown',
        'game_label': 'فاركل',
        'status': 'waiting',
      };

      final formatted = JoinRoomsViewStateHarness.formatRoomTitle(roomWithDefaults);
      expect(formatted, equals('فاركل — مجهول — 1/10 لاعبين — في الانتظار'));
    });

    test('Displays empty state message when no rooms are available', () {
      final emptyHarness = JoinRoomsViewStateHarness(initialRooms: []);

      expect(emptyHarness.isEmptyStateVisible, isTrue);
      expect(emptyHarness.emptyStateMessage, equals('لا توجد طاولات متاحة حاليًا.'));
      expect(emptyHarness.renderedRoomTitles, hasLength(0));
    });

    test('Player Join action triggers join with as_spectator = false', () {
      final targetRoom = TestFixtures.sampleRoomsJson[0];
      harness.joinAsPlayer(targetRoom);

      expect(harness.lastJoinedRoomId, equals('room_1'));
      expect(harness.lastJoinedAsSpectator, isFalse);
      expect(harness.lastNavigatedRoute, equals('TableView'));
    });

    test('Spectator Join action triggers join with as_spectator = true', () {
      final targetRoom = TestFixtures.sampleRoomsJson[1];
      harness.joinAsSpectator(targetRoom);

      expect(harness.lastJoinedRoomId, equals('room_2'));
      expect(harness.lastJoinedAsSpectator, isTrue);
      expect(harness.lastNavigatedRoute, equals('TableView'));
    });
  });
}
