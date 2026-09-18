// Mock API Client providing deterministic responses matching server endpoints and specs.

import 'test_fixtures.dart';

class MockApiAdapter {
  String? authToken;
  Map<String, dynamic>? currentUser;

  final List<Map<String, dynamic>> _rooms = [];
  final List<Map<String, dynamic>> _savedTables = [];
  final List<Map<String, dynamic>> _onlineUsers = [];
  final List<Map<String, dynamic>> recordedCalls = [];

  bool simulateNetworkError = false;
  String? nextErrorMessage;

  final Map<String, Map<String, dynamic>> _registeredUsers = {};

  MockApiAdapter() {
    reset();
  }

  void reset() {
    authToken = null;
    currentUser = null;
    simulateNetworkError = false;
    nextErrorMessage = null;
    recordedCalls.clear();
    _registeredUsers.clear();

    _rooms.clear();
    for (final r in TestFixtures.sampleRoomsJson) {
      _rooms.add(Map<String, dynamic>.from(r));
    }

    _savedTables.clear();
    for (final s in TestFixtures.sampleSavedTablesJson) {
      _savedTables.add(Map<String, dynamic>.from(s));
    }

    _onlineUsers.clear();
    _onlineUsers.addAll([
      {'id': 1, 'username': 'ahmed', 'display_name': 'أحمد'},
      {'id': 2, 'username': 'mohamed', 'display_name': 'محمد'},
      {'id': 3, 'username': 'sara', 'display_name': 'سارة'},
      {'id': 4, 'username': 'khaled', 'display_name': 'خالد'},
    ]);
  }

  void _recordCall(String method, String path, [dynamic body]) {
    recordedCalls.add({
      'method': method,
      'path': path,
      'body': body,
      'token': authToken,
      'timestamp': DateTime.now().toIso8601String(),
    });
  }

  void _checkError() {
    if (simulateNetworkError) {
      throw Exception(nextErrorMessage ?? 'Network connection error');
    }
  }

  // Auth Endpoints
  Future<Map<String, dynamic>> login(String username, String password) async {
    _recordCall('POST', '/api/auth/login', {'username': username, 'password': password});
    _checkError();

    if (username.isEmpty || password.isEmpty) {
      throw Exception('يرجى كتابة اسم المستخدم وكلمة المرور');
    }

    final token = 'mock_token_${username}_${DateTime.now().millisecondsSinceEpoch}';
    authToken = token;
    final displayName = _registeredUsers[username]?['display_name'] ??
        (username == 'ahmed_player' ? 'أحمد البطل' : username);

    currentUser = {
      'id': 42,
      'username': username,
      'display_name': displayName,
    };

    return {
      'access_token': token,
      'token_type': 'bearer',
      'user': currentUser,
    };
  }

  Future<Map<String, dynamic>> register(String username, String displayName, String password) async {
    _recordCall('POST', '/api/auth/register', {
      'username': username,
      'display_name': displayName,
      'password': password,
    });
    _checkError();

    if (username.isEmpty || displayName.isEmpty || password.isEmpty) {
      throw Exception('يرجى ملء جميع الحقول');
    }

    final user = {
      'id': 99,
      'username': username,
      'display_name': displayName,
    };
    _registeredUsers[username] = user;

    return {
      'ok': true,
      'user': user,
    };
  }

  Future<Map<String, dynamic>> logout() async {
    _recordCall('POST', '/api/auth/logout');
    _checkError();
    authToken = null;
    currentUser = null;
    return {'ok': true};
  }

  Future<Map<String, dynamic>> getMe() async {
    _recordCall('GET', '/api/auth/me');
    _checkError();
    if (authToken == null) {
      throw Exception('401 Unauthorized');
    }
    if (currentUser != null) return currentUser!;
    return {'id': 42, 'username': 'session_user', 'display_name': null};
  }


  // Room Endpoints
  Future<List<Map<String, dynamic>>> getRooms() async {
    _recordCall('GET', '/api/rooms');
    _checkError();
    return List<Map<String, dynamic>>.from(_rooms);
  }

  Future<Map<String, dynamic>> createRoom({
    required String name,
    required String gameType,
    required int maxPlayers,
    String? password,
  }) async {
    _recordCall('POST', '/api/rooms', {
      'name': name,
      'game_type': gameType,
      'max_players': maxPlayers,
      'password': password,
    });
    _checkError();

    final newId = 'room_${_rooms.length + 1}';
    final room = {
      'id': newId,
      'name': name,
      'game_type': gameType,
      'host_name': currentUser?['display_name'] ?? 'أنا',
      'players': [currentUser?['display_name'] ?? 'أنا'],
      'max_players': maxPlayers,
      'status': 'waiting',
      'has_password': password != null && password.isNotEmpty,
    };
    _rooms.add(room);
    return {'ok': true, 'id': newId, 'room': room};
  }

  Future<Map<String, dynamic>> joinRoom(
    String roomId, {
    String? password,
    bool asSpectator = false,
  }) async {
    _recordCall('POST', '/api/rooms/$roomId/join', {
      'password': password,
      'as_spectator': asSpectator,
    });
    _checkError();

    final roomIndex = _rooms.indexWhere((r) => r['id'].toString() == roomId);
    if (roomIndex == -1) {
      throw Exception('Room not found: $roomId');
    }

    final room = _rooms[roomIndex];
    if (asSpectator) {
      // Spectator join does not consume player slot
      return {
        'ok': true,
        'room_id': roomId,
        'as_spectator': true,
        'room': room,
      };
    } else {
      // Normal player join
      final players = List<String>.from(room['players'] as List? ?? []);
      final myName = currentUser?['display_name'] ?? 'أنا';
      if (!players.contains(myName)) {
        players.add(myName);
        room['players'] = players;
      }
      return {
        'ok': true,
        'room_id': roomId,
        'as_spectator': false,
        'room': room,
      };
    }
  }

  // Saved Tables Endpoints: GET /saved, POST /saved/{id}/restore, DELETE /saved/{id}
  Future<List<Map<String, dynamic>>> getSavedTables() async {
    _recordCall('GET', '/api/rooms/saved');
    _checkError();
    return List<Map<String, dynamic>>.from(_savedTables);
  }

  Future<Map<String, dynamic>> restoreSavedTable(int savedId) async {
    _recordCall('POST', '/api/rooms/saved/$savedId/restore');
    _checkError();

    final index = _savedTables.indexWhere((t) => t['id'] == savedId);
    if (index == -1) {
      throw Exception('Saved table not found or expired: $savedId');
    }

    final saved = _savedTables[index];
    final restoredRoomId = saved['room_id'] ?? 'restored_room_$savedId';

    return {
      'ok': true,
      'room_id': restoredRoomId,
      'game': saved['game'],
      'message': 'تم استرجاع الطاولة بنجاح.',
    };
  }

  Future<Map<String, dynamic>> deleteSavedTable(int savedId) async {
    _recordCall('DELETE', '/api/rooms/saved/$savedId');
    _checkError();

    final removed = _savedTables.removeWhere((t) => t['id'] == savedId);
    return {
      'ok': true,
      'deleted_id': savedId,
    };
  }

  // Online Users
  Future<List<Map<String, dynamic>>> getOnlineUsers() async {
    _recordCall('GET', '/api/social/online-users');
    _checkError();
    return List<Map<String, dynamic>>.from(_onlineUsers);
  }

  // Room Actions & Game Engine Endpoints
  Future<Map<String, dynamic>> startGame(String roomId, {int? targetScore, Map<String, dynamic>? rules}) async {
    _recordCall('POST', '/api/rooms/$roomId/start', {'target_score': targetScore, 'rules': rules});
    _checkError();
    return {'ok': true, 'status': 'playing'};
  }

  Future<Map<String, dynamic>> stopGame(String roomId) async {
    _recordCall('POST', '/api/rooms/$roomId/stop');
    _checkError();
    return {'ok': true, 'status': 'waiting'};
  }

  Future<Map<String, dynamic>> addBot(String roomId, {String? name}) async {
    _recordCall('POST', '/api/rooms/$roomId/bot', {'name': name});
    _checkError();
    return {'ok': true, 'bot_id': -1, 'name': name ?? 'بوت 1'};
  }

  Future<Map<String, dynamic>> removeBot(String roomId, {int? botId}) async {
    _recordCall('POST', '/api/rooms/$roomId/bot/remove', {'bot_id': botId});
    _checkError();
    return {'ok': true, 'removed': true};
  }

  Future<Map<String, dynamic>> saveTable(String roomId, {String? name}) async {
    _recordCall('POST', '/api/rooms/$roomId/save', {'name': name});
    _checkError();
    return {'ok': true, 'saved_id': 101, 'message': 'تم حفظ الطاولة'};
  }

  Future<Map<String, dynamic>> togglePrivacy(String roomId, {bool? isPrivate}) async {
    _recordCall('POST', '/api/rooms/$roomId/privacy', {'is_private': isPrivate});
    _checkError();
    return {'ok': true, 'is_private': isPrivate ?? true};
  }

  Future<Map<String, dynamic>> toggleSpectator(String roomId) async {
    _recordCall('POST', '/api/rooms/$roomId/spectator');
    _checkError();
    return {'ok': true, 'is_spectator': true};
  }

  Future<Map<String, dynamic>> getGameState(String roomId) async {
    _recordCall('GET', '/api/rooms/$roomId/game/state');
    _checkError();
    return {
      'ok': true,
      'room': {'id': roomId, 'status': 'playing', 'name': 'طاولة الاختبار'},
      'game_state': {'active': true, 'is_my_turn': true},
    };
  }

  Future<Map<String, dynamic>> sendGameAction(String roomId, Map<String, dynamic> payload) async {
    _recordCall('POST', '/api/rooms/$roomId/game/action', payload);
    _checkError();
    return {'ok': true, 'result': 'action_processed', 'payload': payload};
  }

  // Inspection helpers
  bool hasCalled(String method, String path) {
    return recordedCalls.any((c) => c['method'] == method && c['path'] == path);
  }

  Map<String, dynamic>? getLastCall(String path) {
    for (int i = recordedCalls.length - 1; i >= 0; i--) {
      if (recordedCalls[i]['path'] == path) {
        return recordedCalls[i];
      }
    }
    return null;
  }
}
