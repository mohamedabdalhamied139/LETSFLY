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

  Future<dynamic> post(String path, {dynamic data}) async {
    final response = await _dio.post(path, data: data);
    return response.data;
  }

  Future<dynamic> get(String path, {Map<String, dynamic>? queryParameters}) async {
    final response = await _dio.get(path, queryParameters: queryParameters);
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

  Future<dynamic> joinRoom(String roomId, {String? password}) {
    return post('/api/rooms/$roomId/join', data: {'password': password});
  }

  Future<dynamic> leaveRoom(String roomId) {
    return post('/api/rooms/$roomId/leave');
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
