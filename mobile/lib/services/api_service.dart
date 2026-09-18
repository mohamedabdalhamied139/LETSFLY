import 'dart:async';
import 'package:dio/dio.dart';

class ApiService {
  static final ApiService instance = ApiService._();
  ApiService._() {
    _dio = Dio(
      BaseOptions(
        baseUrl: defaultServerUrl,
        connectTimeout: const Duration(seconds: 10),
        receiveTimeout: const Duration(seconds: 15),
        headers: {
          'Content-Type': 'application/json',
          'Accept-Encoding': 'gzip, deflate',
        },
      ),
    );
  }

  static const String defaultServerUrl = 'https://letsfly.onrender.com';
  late final Dio _dio;
  String? authToken;

  void setBaseUrl(String url) {
    _dio.options.baseUrl = url.replaceAll(RegExp(r'/+$'), '');
  }

  void setToken(String? token) {
    authToken = token;
    if (token != null && token.isNotEmpty) {
      _dio.options.headers['Authorization'] = 'Bearer $token';
    } else {
      _dio.options.headers.remove('Authorization');
    }
  }

  String getWsUrl(String path) {
    String base = _dio.options.baseUrl;
    String wsBase;
    if (base.startsWith('https://')) {
      wsBase = 'wss://${base.substring(8)}';
    } else if (base.startsWith('http://')) {
      wsBase = 'ws://${base.substring(7)}';
    } else if (base.startsWith('wss://') || base.startsWith('ws://')) {
      wsBase = base;
    } else {
      wsBase = 'ws://$base';
    }
    final cleanPath = path.replaceAll(RegExp(r'^/+'), '');
    return cleanPath.isEmpty ? wsBase : '$wsBase/$cleanPath';
  }

  Future<dynamic> post(String path, {dynamic data, Map<String, dynamic>? queryParameters}) async {
    final response = await _dio.post(path, data: data, queryParameters: queryParameters);
    return response.data;
  }

  Future<dynamic> get(String path, {Map<String, dynamic>? queryParameters}) async {
    final response = await _dio.get(path, queryParameters: queryParameters);
    return response.data;
  }

  Future<dynamic> delete(String path, {dynamic data, Map<String, dynamic>? queryParameters}) async {
    final response = await _dio.delete(path, data: data, queryParameters: queryParameters);
    return response.data;
  }

  // Auth Endpoints
  Future<dynamic> register(String username, String displayName, String password) {
    return post('/api/auth/register', data: {
      'username': username,
      'display_name': displayName,
      'password': password,
    });
  }

  Future<dynamic> login(String username, String password) {
    return post('/api/auth/login', data: {
      'username': username,
      'password': password,
    });
  }

  Future<dynamic> logout() {
    return post('/api/auth/logout');
  }

  // Room Endpoints
  Future<dynamic> getRooms() {
    return get('/api/rooms');
  }

  Future<dynamic> createRoom({
    required String name,
    required String gameType,
    required int maxPlayers,
    String? password,
    Map<String, dynamic>? settings,
  }) {
    return post('/api/rooms', data: {
      'name': name,
      'game_type': gameType,
      'max_players': maxPlayers,
      'password': password,
      'settings': settings ?? {},
    });
  }

  Future<Map<String, dynamic>> joinRoom(
    String roomId, {
    String? password,
    bool asSpectator = false,
  }) async {
    final queryParams = asSpectator ? {'as_spectator': true} : null;
    final res = await post(
      '/api/rooms/$roomId/join',
      data: {
        if (password != null) 'password': password,
        'as_spectator': asSpectator,
      },
      queryParameters: queryParams,
    );
    if (res is Map<String, dynamic>) {
      return res;
    } else if (res is Map) {
      return Map<String, dynamic>.from(res);
    }
    return {'ok': true, 'room_id': roomId, 'as_spectator': asSpectator};
  }

  Future<dynamic> leaveRoom(String roomId) {
    return post('/api/rooms/$roomId/leave');
  }

  // Room Lifecycle & Management Endpoints
  Future<dynamic> startGame(String roomId, {int targetScore = 500, Map<String, dynamic>? rules}) {
    return post('/api/rooms/$roomId/start', data: {
      'target_score': targetScore,
      'rules': rules ?? {},
    });
  }

  Future<dynamic> stopGame(String roomId) {
    return post('/api/rooms/$roomId/stop');
  }

  Future<dynamic> addBot(String roomId) {
    return post('/api/rooms/$roomId/bot');
  }

  Future<dynamic> removeBot(String roomId) {
    return post('/api/rooms/$roomId/bot/remove');
  }

  Future<dynamic> saveTable(String roomId) {
    return post('/api/rooms/$roomId/save');
  }

  Future<dynamic> togglePrivacy(String roomId) {
    return post('/api/rooms/$roomId/privacy');
  }

  Future<dynamic> toggleSpectator(String roomId) {
    return post('/api/rooms/$roomId/spectator');
  }

  Future<dynamic> getGameState(String roomId) {
    return get('/api/rooms/$roomId/game/state');
  }

  Future<dynamic> sendGameAction(String roomId, Map<String, dynamic> actionPayload) {
    return post('/api/rooms/$roomId/game/action', data: actionPayload);
  }

  // Saved Tables Endpoints
  Future<List<Map<String, dynamic>>> getSavedTables() async {
    final res = await get('/api/rooms/saved');
    if (res is List) {
      return res.map((e) => Map<String, dynamic>.from(e as Map)).toList();
    } else if (res is Map && res['saved_tables'] is List) {
      return (res['saved_tables'] as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
    }
    return [];
  }

  Future<Map<String, dynamic>> restoreSavedTable(int savedId) async {
    final res = await post('/api/rooms/saved/$savedId/restore');
    if (res is Map<String, dynamic>) {
      return res;
    } else if (res is Map) {
      return Map<String, dynamic>.from(res);
    }
    return {'ok': true, 'room_id': 'restored_room_$savedId'};
  }

  Future<void> deleteSavedTable(int savedId) async {
    await delete('/api/rooms/saved/$savedId');
  }

  // Social / Friends Endpoints
  Future<dynamic> getFriends() {
    return get('/api/social/friends');
  }

  Future<dynamic> getOnlineUsers() {
    return get('/api/social/online-users');
  }

  Future<dynamic> sendFriendRequest(int targetUserId) {
    return post('/api/social/requests', data: {'target_user_id': targetUserId});
  }

  Future<dynamic> cancelFriendRequest(int targetUserId) {
    return post('/api/social/requests/cancel', data: {'target_user_id': targetUserId});
  }

  Future<dynamic> acceptFriendRequest(int requestId) {
    return post('/api/social/requests/$requestId/accept');
  }

  Future<dynamic> rejectFriendRequest(int requestId) {
    return post('/api/social/requests/$requestId/reject');
  }
}
