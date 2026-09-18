// Tier 1 Unit Test: Models Serialization & Deserialization (User, RoomSummary, SavedTable)

import '../harness/test_engine.dart';
import '../harness/test_fixtures.dart';
import '../../lib/models/room_models.dart';

void main() async {
  defineTests();
  await runSuite('Tier 1 Unit: Models Tests');
}

void defineTests() {
  group('Models Serialization & Deserialization', () {
    group('User Model', () {
      test('Deserializes standard User JSON correctly', () {
        final json = {
          'id': 42,
          'username': 'ahmed_player',
          'display_name': 'أحمد البطل',
        };

        final user = User.fromJson(json);

        expect(user.id, equals(42));
        expect(user.username, equals('ahmed_player'));
        expect(user.displayName, equals('أحمد البطل'));
      });

      test('Parses String ID to integer correctly', () {
        final json = {
          'id': '999',
          'username': 'str_user',
          'display_name': 'String ID User',
        };

        final user = User.fromJson(json);

        expect(user.id, equals(999));
      });

      test('Falls back to name or username when display_name is absent', () {
        final jsonWithName = {
          'id': 1,
          'username': 'user_one',
          'name': 'Name Fallback',
        };
        final user1 = User.fromJson(jsonWithName);
        expect(user1.displayName, equals('Name Fallback'));

        final jsonWithOnlyUser = {
          'id': 2,
          'username': 'only_user',
        };
        final user2 = User.fromJson(jsonWithOnlyUser);
        expect(user2.displayName, equals('only_user'));
      });

      test('Serializes User to JSON accurately', () {
        final user = User(id: 77, username: 'player_77', displayName: 'اللاعب 77');
        final json = user.toJson();

        expect(json['id'], equals(77));
        expect(json['username'], equals('player_77'));
        expect(json['display_name'], equals('اللاعب 77'));
      });
    });

    group('RoomSummary Model', () {
      test('Deserializes standard RoomSummary JSON correctly', () {
        final json = {
          'id': 'room_123',
          'name': 'طاولة أونو الكبرى',
          'game_type': 'UNO',
          'host_name': 'أحمد',
          'current_players': 3,
          'max_players': 10,
          'has_password': false,
          'status': 'waiting',
        };

        final room = RoomSummary.fromJson(json);

        expect(room.id, equals('room_123'));
        expect(room.name, equals('طاولة أونو الكبرى'));
        expect(room.gameType, equals('UNO'));
        expect(room.hostName, equals('أحمد'));
        expect(room.currentPlayers, equals(3));
        expect(room.maxPlayers, equals(10));
        expect(room.hasPassword, isFalse);
        expect(room.status, equals('waiting'));
      });

      test('Derives currentPlayers from players list when current_players is omitted', () {
        final json = {
          'id': 'room_456',
          'name': 'غرفة النرد',
          'game_type': 'FARKLE',
          'host_name': 'سارة',
          'players': ['سارة', 'خالد', 'منى', 'عمر'],
          'status': 'playing',
        };

        final room = RoomSummary.fromJson(json);

        expect(room.currentPlayers, equals(4));
        expect(room.maxPlayers, equals(4)); // Default fallback
        expect(room.status, equals('playing'));
      });

      test('Detects password protection via is_locked flag', () {
        final json = {
          'id': 'room_789',
          'name': 'طاولة خاصة',
          'game_type': 'SCOPA',
          'host_name': 'محمد',
          'is_locked': true,
        };

        final room = RoomSummary.fromJson(json);

        expect(room.hasPassword, isTrue);
      });
    });

    group('SavedTable Model', () {
      test('Deserializes standard SavedTable JSON correctly', () {
        final json = {
          'id': 101,
          'user_id': 42,
          'room_id': 'saved_uno_1',
          'game': 'UNO',
          'opponents_summary': 'محمد، سارة',
          'saved_at': '2026-09-18T14:30:00Z',
          'expires_at': '2026-09-25T14:30:00Z',
          'data': {'score': 250},
        };

        final table = SavedTable.fromJson(json);

        expect(table.id, equals(101));
        expect(table.userId, equals(42));
        expect(table.roomId, equals('saved_uno_1'));
        expect(table.game, equals('UNO'));
        expect(table.opponentsSummary, equals('محمد، سارة'));
        expect(table.savedAt, equals('2026-09-18T14:30:00Z'));
        expect(table.expiresAt, equals('2026-09-25T14:30:00Z'));
        expect(table.data?['score'], equals(250));
      });

      test('Parses String IDs and falls back to default opponents when omitted', () {
        final json = {
          'id': '202',
          'user_id': '42',
          'room_id': 'room_domino_2',
          'game': 'DOMINO',
          'saved_at': '2026-09-17T12:00:00Z',
          'expires_at': '2026-09-24T12:00:00Z',
        };

        final table = SavedTable.fromJson(json);

        expect(table.id, equals(202));
        expect(table.userId, equals(42));
        expect(table.opponentsSummary, equals('لا يوجد'));
      });

      test('Serializes SavedTable to JSON round-trip without loss', () {
        final original = SavedTable(
          id: 303,
          userId: 55,
          roomId: 'saved_tennis_3',
          game: 'TENNIS',
          opponentsSummary: 'عمر',
          savedAt: '2026-09-16T10:00:00Z',
          expiresAt: '2026-09-23T10:00:00Z',
          data: {'sets': [6, 4]},
        );

        final json = original.toJson();
        final reconstituted = SavedTable.fromJson(json);

        expect(reconstituted.id, equals(original.id));
        expect(reconstituted.userId, equals(original.userId));
        expect(reconstituted.roomId, equals(original.roomId));
        expect(reconstituted.game, equals(original.game));
        expect(reconstituted.opponentsSummary, equals(original.opponentsSummary));
        expect(reconstituted.savedAt, equals(original.savedAt));
        expect(reconstituted.expiresAt, equals(original.expiresAt));
        expect(reconstituted.data?['sets'], equals([6, 4]));
      });

      test('Supports alternative backend keys saved_time, expires_time, game_label and opponents list', () {
        final json = {
          'id': 404,
          'game': 'SCOPA',
          'game_label': 'إسكوبا',
          'opponents': ['خالد', 'منى'],
          'saved_time': '2026-09-15T08:00:00Z',
          'expires_time': '2026-09-22T08:00:00Z',
          'rawData': {'round': 3},
        };

        final table = SavedTable.fromJson(json);

        expect(table.id, equals(404));
        expect(table.game, equals('SCOPA'));
        expect(table.gameLabel, equals('إسكوبا'));
        expect(table.opponents, equals(['خالد', 'منى']));
        expect(table.opponentsSummary, equals('خالد، منى'));
        expect(table.savedAt, equals('2026-09-15T08:00:00Z'));
        expect(table.expiresAt, equals('2026-09-22T08:00:00Z'));
        expect(table.savedAtDateTime.year, equals(2026));
        expect(table.expiresAtDateTime?.month, equals(9));
        expect(table.data?['round'], equals(3));
      });

      test('Derives canonical game labels automatically when game_label is omitted', () {
        final uno = SavedTable.fromJson({'id': 1, 'game': 'UNO', 'saved_at': '2026-09-18T10:00:00Z'});
        final domino = SavedTable.fromJson({'id': 2, 'game': 'DOMINO', 'saved_at': '2026-09-18T10:00:00Z'});
        final tennis = SavedTable.fromJson({'id': 3, 'game': 'TENNIS', 'saved_at': '2026-09-18T10:00:00Z'});

        expect(uno.gameLabel, equals('أونو'));
        expect(domino.gameLabel, equals('دومينو كلاسيك'));
        expect(tennis.gameLabel, equals('التنس'));
      });
    });
  });
}
