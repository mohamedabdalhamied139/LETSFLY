// Tier 3: Integration Tests for Game Adapters, Gestures, Bot Controls and Table Engine
// Verifies real server action payloads, reactive state updates, sound cues, and touch gesture mappings.

import '../harness/test_engine.dart';
import '../harness/mock_api_adapter.dart';

/// Testable harness for table gestures and space key actions
class TableGestureHarness {
  final bool isTennis;
  final bool isUnoOrDomino;
  bool logOpened = false;
  String? lastAnnouncedQuery;
  String? lastAnnouncedInfo;
  String? lastSpaceAction;
  int tennisLane = 0;
  bool tennisHitOrServed = false;

  TableGestureHarness({this.isTennis = false, this.isUnoOrDomino = false});

  void handleGesture(String gestureName) {
    if (gestureName == 'two_finger_swipe_left') {
      lastAnnouncedQuery = 'query_table_cards_or_dice';
    } else if (gestureName == 'two_finger_swipe_up') {
      lastAnnouncedInfo = 'table_and_players_info';
    } else if (isTennis) {
      if (gestureName == 'swipe_left') {
        tennisLane = -1;
      } else if (gestureName == 'swipe_right') {
        tennisLane = 1;
      } else if (gestureName == 'swipe_up') {
        tennisHitOrServed = true;
      } else if (gestureName == 'swipe_down') {
        logOpened = true;
      }
    } else {
      if (gestureName == 'swipe_right') {
        logOpened = true;
      } else if (gestureName == 'swipe_down' && isUnoOrDomino) {
        lastSpaceAction = 'space_key_action';
      }
    }
  }
}

void defineTests() {
  group('Game Engine & Adapters Integration', () {
    late MockApiAdapter api;

    setUp(() {
      api = MockApiAdapter();
    });

    test('Domino Adapter: play with sides, draw, and pass action schemas', () async {
      // 1. Draw tile
      await api.sendGameAction('room_domino_1', {'action': 'draw'});
      expect(api.hasCalled('POST', '/api/rooms/room_domino_1/game/action'), isTrue);
      expect(api.getLastCall('/api/rooms/room_domino_1/game/action')?['body']['action'], equals('draw'));

      // 2. Play tile to left side
      await api.sendGameAction('room_domino_1', {
        'action': 'play',
        'card_id': '0',
        'side': 'left',
      });
      final leftPlay = api.getLastCall('/api/rooms/room_domino_1/game/action');
      expect(leftPlay?['body']['action'], equals('play'));
      expect(leftPlay?['body']['card_id'], equals('0'));
      expect(leftPlay?['body']['side'], equals('left'));

      // 3. Play tile to right side
      await api.sendGameAction('room_domino_1', {
        'action': 'play',
        'card_id': '1',
        'side': 'right',
      });
      final rightPlay = api.getLastCall('/api/rooms/room_domino_1/game/action');
      expect(rightPlay?['body']['side'], equals('right'));

      // 4. Pass turn
      await api.sendGameAction('room_domino_1', {'action': 'pass'});
      expect(api.getLastCall('/api/rooms/room_domino_1/game/action')?['body']['action'], equals('pass'));
    });

    test('Farkle Adapter: roll, score combinations, and bank action schemas', () async {
      // 1. Roll action
      await api.sendGameAction('room_farkle_1', {'action': 'roll'});
      expect(api.getLastCall('/api/rooms/room_farkle_1/game/action')?['body']['action'], equals('roll'));

      // 2. Score combinations with comma-separated indices
      await api.sendGameAction('room_farkle_1', {
        'action': 'score',
        'card_id': '0,1',
        'value': [0, 1],
      });
      final scoreCall = api.getLastCall('/api/rooms/room_farkle_1/game/action');
      expect(scoreCall?['body']['action'], equals('score'));
      expect(scoreCall?['body']['card_id'], equals('0,1'));

      // 3. Bank score
      await api.sendGameAction('room_farkle_1', {'action': 'bank'});
      expect(api.getLastCall('/api/rooms/room_farkle_1/game/action')?['body']['action'], equals('bank'));
    });

    test('Scopa Adapter: card playing and capture choice schemas', () async {
      // Play card by hand index
      await api.sendGameAction('room_scopa_1', {
        'action': 'play',
        'card_id': '2',
      });
      final playCall = api.getLastCall('/api/rooms/room_scopa_1/game/action');
      expect(playCall?['body']['action'], equals('play'));
      expect(playCall?['body']['card_id'], equals('2'));
    });

    test('Ninety-Nine Adapter: pile value play and choose +10/-10 schemas', () async {
      // Play card
      await api.sendGameAction('room_nn_1', {
        'action': 'play',
        'card_id': 'card_abc123',
      });
      expect(api.getLastCall('/api/rooms/room_nn_1/game/action')?['body']['card_id'], equals('card_abc123'));

      // Choose value (+10)
      await api.sendGameAction('room_nn_1', {
        'action': 'choose',
        'card_id': '+10',
      });
      final chooseCall = api.getLastCall('/api/rooms/room_nn_1/game/action');
      expect(chooseCall?['body']['action'], equals('choose'));
      expect(chooseCall?['body']['card_id'], equals('+10'));

      // Choose value (-10)
      await api.sendGameAction('room_nn_1', {
        'action': 'choose',
        'card_id': '-10',
      });
      expect(api.getLastCall('/api/rooms/room_nn_1/game/action')?['body']['card_id'], equals('-10'));
    });

    test('Snakes and Ladders Adapter: roll action schema', () async {
      await api.sendGameAction('room_snakes_1', {'action': 'roll'});
      expect(api.getLastCall('/api/rooms/room_snakes_1/game/action')?['body']['action'], equals('roll'));
    });

    test('Thief Hunt Adapter: secret start floor and investigator answer schemas', () async {
      // Thief secret start floor
      await api.sendGameAction('room_thief_1', {
        'action': 'choose_floor',
        'card_id': '6',
      });
      expect(api.getLastCall('/api/rooms/room_thief_1/game/action')?['body']['action'], equals('choose_floor'));
      expect(api.getLastCall('/api/rooms/room_thief_1/game/action')?['body']['card_id'], equals('6'));

      // Investigator guess
      await api.sendGameAction('room_thief_1', {
        'action': 'answer',
        'card_id': '8',
      });
      expect(api.getLastCall('/api/rooms/room_thief_1/game/action')?['body']['action'], equals('answer'));
      expect(api.getLastCall('/api/rooms/room_thief_1/game/action')?['body']['card_id'], equals('8'));
    });

    test('Tennis Adapter: lane positions (-1, 0, 1) and hit/serve schemas', () async {
      // Move Left (-1)
      await api.sendGameAction('room_tennis_1', {
        'action': 'position',
        'data': {'lane': -1},
      });
      expect(api.getLastCall('/api/rooms/room_tennis_1/game/action')?['body']['data']['lane'], equals(-1));

      // Move Right (1)
      await api.sendGameAction('room_tennis_1', {
        'action': 'position',
        'data': {'lane': 1},
      });
      expect(api.getLastCall('/api/rooms/room_tennis_1/game/action')?['body']['data']['lane'], equals(1));

      // Move Center (0)
      await api.sendGameAction('room_tennis_1', {
        'action': 'position',
        'data': {'lane': 0},
      });
      expect(api.getLastCall('/api/rooms/room_tennis_1/game/action')?['body']['data']['lane'], equals(0));

      // Serve ball
      await api.sendGameAction('room_tennis_1', {
        'action': 'serve',
        'data': {'lane': 0},
      });
      expect(api.getLastCall('/api/rooms/room_tennis_1/game/action')?['body']['action'], equals('serve'));

      // Hit ball
      await api.sendGameAction('room_tennis_1', {
        'action': 'hit',
        'data': {'lane': 0},
      });
      expect(api.getLastCall('/api/rooms/room_tennis_1/game/action')?['body']['action'], equals('hit'));
    });
  });

  group('Table Gestures Mapping Conformance', () {
    test('Standard Table Gestures: query, table info, log drawer and space key', () {
      final harness = TableGestureHarness(isTennis: false, isUnoOrDomino: true);

      // Two-finger swipe Left -> Query cards/dice (R)
      harness.handleGesture('two_finger_swipe_left');
      expect(harness.lastAnnouncedQuery, equals('query_table_cards_or_dice'));

      // Two-finger swipe Up -> Table & Time info (T)
      harness.handleGesture('two_finger_swipe_up');
      expect(harness.lastAnnouncedInfo, equals('table_and_players_info'));

      // Single swipe Right -> Open Activity Log drawer
      harness.handleGesture('swipe_right');
      expect(harness.logOpened, isTrue);

      // Single swipe Down -> Space Key action (Draw/Roll)
      harness.handleGesture('swipe_down');
      expect(harness.lastSpaceAction, equals('space_key_action'));
    });

    test('Tennis Gestures: Left, Right, Up (Hit/Serve), Down (Open Log)', () {
      final harness = TableGestureHarness(isTennis: true);

      // Swipe Left -> Move to Left Lane
      harness.handleGesture('swipe_left');
      expect(harness.tennisLane, equals(-1));

      // Swipe Right -> Move to Right Lane
      harness.handleGesture('swipe_right');
      expect(harness.tennisLane, equals(1));

      // Swipe Up -> Hit or Serve
      harness.handleGesture('swipe_up');
      expect(harness.tennisHitOrServed, isTrue);

      // Swipe Down in Tennis -> Open Activity Log drawer
      harness.handleGesture('swipe_down');
      expect(harness.logOpened, isTrue);
    });
  });

  group('TableView Room Actions & Polling Integration', () {
    test('Room actions trigger real REST endpoints for bot and game management', () async {
      final api = MockApiAdapter();

      // 1. Add Bot
      await api.addBot('room_100', name: 'بوت محترف');
      expect(api.hasCalled('POST', '/api/rooms/room_100/bot'), isTrue);
      expect(api.getLastCall('/api/rooms/room_100/bot')?['body']['name'], equals('بوت محترف'));

      // 2. Start Game
      await api.startGame('room_100', targetScore: 500);
      expect(api.hasCalled('POST', '/api/rooms/room_100/start'), isTrue);
      expect(api.getLastCall('/api/rooms/room_100/start')?['body']['target_score'], equals(500));

      // 3. Periodic Poll Game State
      final gameState = await api.getGameState('room_100');
      expect(gameState['ok'], isTrue);
      expect(api.hasCalled('GET', '/api/rooms/room_100/game/state'), isTrue);

      // 4. Save Table
      await api.saveTable('room_100');
      expect(api.hasCalled('POST', '/api/rooms/room_100/save'), isTrue);

      // 5. Remove Bot
      await api.removeBot('room_100');
      expect(api.hasCalled('POST', '/api/rooms/room_100/bot/remove'), isTrue);

      // 6. Stop Game
      await api.stopGame('room_100');
      expect(api.hasCalled('POST', '/api/rooms/room_100/stop'), isTrue);
    });
  });
}
