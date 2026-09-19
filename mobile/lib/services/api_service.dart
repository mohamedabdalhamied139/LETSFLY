import 'dart:async';
import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'auth_storage_service.dart';

class ApiService {
  static final ApiService instance = ApiService._();
  static const String defaultBaseUrl = 'https://letsfly.onrender.com';
  static const String _serverUrlPrefKey = 'tableverse_server_url';

  ApiService._() {
    _dio.options.baseUrl = defaultBaseUrl;
    _dio.options.connectTimeout = const Duration(seconds: 15);
    _dio.options.receiveTimeout = const Duration(seconds: 15);

    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = _token ?? await AuthStorageService.instance.getActiveSessionToken();
          if (token != null && token.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          return handler.next(options);
        },
      ),
    );
  }

  final Dio _dio = Dio();
  String? _token;

  String get baseUrl => _dio.options.baseUrl;

  void setBaseUrl(String url) {
    _dio.options.baseUrl = url.replaceAll(RegExp(r'/+$'), '');
  }

  Future<void> init() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final saved = prefs.getString(_serverUrlPrefKey);
      if (saved != null && saved.trim().isNotEmpty) {
        setBaseUrl(saved.trim());
      }
    } catch (_) {}
  }

  Future<void> saveBaseUrl(String url) async {
    setBaseUrl(url);
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_serverUrlPrefKey, url.trim());
    } catch (_) {}
  }

  Future<void> resetBaseUrl() async {
    setBaseUrl(defaultBaseUrl);
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_serverUrlPrefKey);
    } catch (_) {}
  }

  String getWsUrl([String path = '']) {
    var base = _dio.options.baseUrl.replaceAll(RegExp(r'/+$'), '');
    String wsBase;
    if (base.startsWith('https://')) {
      wsBase = 'wss://${base.substring(8)}';
    } else if (base.startsWith('http://')) {
      wsBase = 'ws://${base.substring(7)}';
    } else if (base.startsWith('wss://') || base.startsWith('ws://')) {
      wsBase = base;
    } else {
      wsBase = 'wss://$base';
    }
    if (path.isNotEmpty) {
      final cleanPath = path.startsWith('/') ? path : '/$path';
      return '$wsBase$cleanPath';
    }
    return wsBase;
  }

  void setToken(String? token) {
    _token = token;
  }

  String? get token => _token;

  Future<dynamic> get(String path, {Map<String, dynamic>? queryParameters}) async {
    final response = await _dio.get(path, queryParameters: queryParameters);
    return response.data;
  }

  Future<dynamic> post(String path, {dynamic data, Map<String, dynamic>? queryParameters}) async {
    final response = await _dio.post(path, data: data, queryParameters: queryParameters);
    return response.data;
  }

  Future<dynamic> put(String path, {dynamic data, Map<String, dynamic>? queryParameters}) async {
    final response = await _dio.put(path, data: data, queryParameters: queryParameters);
    return response.data;
  }

  Future<dynamic> delete(String path, {dynamic data, Map<String, dynamic>? queryParameters}) async {
    final response = await _dio.delete(path, data: data, queryParameters: queryParameters);
    return response.data;
  }

  // Auth Endpoints
  Future<dynamic> login(String username, String password) async {
    final res = await post('/api/auth/login', data: {
      'username': username,
      'password': password,
    });
    if (res is Map && res['token'] != null) {
      setToken(res['token'].toString());
    }
    return res;
  }

  Future<dynamic> register(String username, String password, String displayName) async {
    final res = await post('/api/auth/register', data: {
      'username': username,
      'password': password,
      'display_name': displayName,
    });
    if (res is Map && res['token'] != null) {
      setToken(res['token'].toString());
    }
    return res;
  }

  Future<dynamic> logout() async {
    try {
      await post('/api/auth/logout');
    } catch (_) {}
    setToken(null);
  }

  Future<dynamic> getMe() {
    return get('/api/auth/me');
  }

  // Rooms Endpoints
  Future<dynamic> getRooms() {
    return get('/api/rooms');
  }

  Future<dynamic> createRoom({
    String? game,
    String? name,
    String? gameType,
    int maxPlayers = 4,
    String? password,
    Map<String, dynamic>? settings,
  }) {
    final selectedGame = game ?? gameType ?? 'UNO';
    return post('/api/rooms', data: {
      'game': selectedGame,
      if (name != null) 'name': name,
      if (gameType != null) 'game_type': gameType,
      'max_players': maxPlayers,
      if (password != null) 'password': password,
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

  Future<dynamic> toggleSpectator(String roomId, {int? targetUserId}) {
    final payload = targetUserId != null ? {'target_user_id': targetUserId} : null;
    return post('/api/rooms/$roomId/spectator', data: payload);
  }

  Future<dynamic> transferHost(String roomId, int targetUserId) {
    return post('/api/rooms/$roomId/transfer_host', data: {'target_user_id': targetUserId});
  }

  Future<dynamic> setCoHost(String roomId, int targetUserId) {
    return post('/api/rooms/$roomId/set_co_host', data: {'target_user_id': targetUserId});
  }

  Future<dynamic> substitutePlayer(String roomId, int targetUserId, {int? replacementUserId, bool isBot = false}) {
    final payload = <String, dynamic>{
      'target_user_id': targetUserId,
      'is_bot': isBot,
    };
    if (replacementUserId != null) {
      payload['replacement_user_id'] = replacementUserId;
    }
    return post('/api/rooms/$roomId/substitute', data: payload);
  }

  Future<dynamic> kickPlayer(String roomId, int targetUserId) {
    return post('/api/rooms/$roomId/kick', data: {'target_user_id': targetUserId});
  }

  Future<dynamic> banPlayer(String roomId, int targetUserId) {
    return post('/api/rooms/$roomId/ban', data: {'target_user_id': targetUserId});
  }

  Future<dynamic> voiceMutePlayer(String roomId, int targetUserId) {
    return post('/api/rooms/$roomId/voice/mute', data: {'target_user_id': targetUserId});
  }

  Future<dynamic> voiceKickPlayer(String roomId, int targetUserId) {
    return post('/api/rooms/$roomId/voice/kick', data: {'target_user_id': targetUserId});
  }

  Future<dynamic> voiceBanPlayer(String roomId, int targetUserId) {
    return post('/api/rooms/$roomId/voice/ban', data: {'target_user_id': targetUserId});
  }

  Future<dynamic> inviteUserToRoom(String roomId, int targetUserId) {
    return post('/api/rooms/$roomId/invite/$targetUserId');
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
  Future<dynamic> getFriends() async {
    try {
      return await get('/api/friends');
    } catch (_) {
      return await get('/api/social/friends');
    }
  }

  Future<dynamic> getOnlineUsers() async {
    try {
      final res = await get('/api/users/online');
      if (res is Map && res['users'] is List) {
        return res['users'];
      }
      return res;
    } catch (_) {
      return await get('/api/social/online-users');
    }
  }

  Future<dynamic> sendFriendRequest(int recipientId) {
    return post('/api/friends/requests/$recipientId');
  }

  Future<dynamic> cancelFriendRequest(int requestId) {
    return delete('/api/friends/requests/$requestId');
  }

  Future<dynamic> cancelFriendRequestToUser(int recipientId) {
    return delete('/api/friends/requests/to/$recipientId');
  }

  Future<dynamic> acceptFriendRequest(int requestId) {
    return post('/api/friends/requests/$requestId/accept');
  }

  Future<dynamic> rejectFriendRequest(int requestId) {
    return post('/api/friends/requests/$requestId/reject');
  }

  Future<dynamic> unfriend(int userId) {
    return delete('/api/friends/$userId');
  }

  Future<dynamic> blockUser(int userId) {
    return post('/api/users/$userId/block');
  }

  Future<dynamic> unblockUser(int userId) {
    return delete('/api/users/$userId/block');
  }

  Future<dynamic> getBlockedUsers() {
    return get('/api/users/blocked');
  }

  Future<dynamic> getUserProfile(int userId) {
    return get('/api/users/$userId/profile');
  }

  Future<dynamic> updateMyProfile({String? displayName, String? gender, String? bio}) {
    return put('/api/users/me/profile', data: {
      if (displayName != null) 'display_name': displayName,
      if (gender != null) 'gender': gender,
      if (bio != null) 'bio': bio,
    });
  }

  Future<dynamic> deleteMyAccount() {
    return delete('/api/users/me');
  }

  Future<dynamic> getHeadToHead(int userId) {
    return get('/api/users/$userId/head-to-head');
  }

  Future<dynamic> sendPrivateMessage(int userId, String message) {
    return post('/api/users/$userId/messages', data: {'message': message});
  }

  Future<dynamic> getMutes(int userId) {
    return get('/api/users/$userId/mutes');
  }

  Future<dynamic> setMutes(int userId, Map<String, dynamic> flags) {
    return put('/api/users/$userId/mutes', data: flags);
  }

  Future<dynamic> updatePrivacy(Map<String, dynamic> payload) {
    return put('/api/users/me/privacy', data: payload);
  }

  Future<dynamic> challengeUser(int userId, {String game = 'UNO'}) {
    return post('/api/users/$userId/challenge', data: {'game': game});
  }

  Future<dynamic> giftUser(int userId, int amount) {
    return post('/api/users/$userId/gift', data: {'amount': amount});
  }

  Future<dynamic> searchUsers(String query) {
    return get('/api/users/search?q=${Uri.encodeComponent(query)}');
  }

  Future<dynamic> getPrivateMessages({int limit = 100}) {
    return get('/api/messages?limit=$limit');
  }

  Future<dynamic> getNotifications({int limit = 100}) {
    return get('/api/notifications?limit=$limit');
  }

  Future<dynamic> acceptChallenge(int invitationId) {
    return post('/api/invitations/$invitationId/accept');
  }

  Future<dynamic> rejectChallenge(int invitationId) {
    return post('/api/invitations/$invitationId/reject');
  }

  Future<dynamic> sendFeedback(String message) {
    return post('/api/feedback', data: {'message': message});
  }

  Future<dynamic> getRecentEvents() async {
    try {
      final res = await get('/api/activity/recent');
      return res;
    } catch (_) {
      return [];
    }
  }
}
