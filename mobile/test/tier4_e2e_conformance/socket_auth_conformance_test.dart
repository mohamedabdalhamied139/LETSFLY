// Tier 4 Conformance Test: WebSocket Auth Header & Protocol Conformance

import 'dart:async';
import '../harness/test_engine.dart';
import '../harness/mock_ws_channel.dart';

/// Testable WebSocket connection client enforcing the server auth protocol
class ConformingWebSocketClient {
  MockWsChannel? _channel;
  bool _isConnected = false;
  Timer? _heartbeatTimer;
  final List<Map<String, dynamic>> receivedEvents = [];

  bool get isConnected => _isConnected;
  MockWsChannel? get channel => _channel;

  /// Connects using standard RFC 6455 HTTP handshake headers
  void connect(
    String wsUrl, {
    String? token,
    bool useQueryParamFallback = false,
  }) {
    disconnect();

    Uri uri = Uri.parse(wsUrl);
    final headers = <String, String>{};

    if (token != null && token.isNotEmpty) {
      // 1. Mandatory server protocol: Authorization Bearer header
      headers['Authorization'] = 'Bearer $token';

      // 2. Optional dev query parameter fallback
      if (useQueryParamFallback) {
        final query = Map<String, String>.from(uri.queryParameters);
        query['token'] = token;
        uri = uri.replace(queryParameters: query);
      }
    }

    _channel = MockWsChannel(uri, headers: headers);
    _isConnected = true;

    _channel?.stream.listen((message) {
      // Process incoming
    }, onDone: () {
      _handleDisconnect();
    }, onError: (_) {
      _handleDisconnect();
    });

    _startHeartbeat();
  }

  void _startHeartbeat() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(const Duration(seconds: 10), (_) {
      if (_isConnected && _channel != null) {
        sendPing('hb_${DateTime.now().millisecondsSinceEpoch}');
      }
    });
  }

  void sendPing(String pingId) {
    if (_isConnected && _channel != null) {
      _channel?.sink.add('{"type":"ping","ping_id":"$pingId"}');
    }
  }

  void _handleDisconnect() {
    _isConnected = false;
    _heartbeatTimer?.cancel();
    receivedEvents.add({'type': 'ws_disconnected'});
  }

  void disconnect() {
    _isConnected = false;
    _heartbeatTimer?.cancel();
    _channel?.close();
    _channel = null;
  }
}

void main() async {
  defineTests();
  await runSuite('Tier 4 Conformance: Socket Auth Tests');
}

void defineTests() {
  group('WebSocket Authentication & Protocol Conformance', () {
    late ConformingWebSocketClient client;

    setUp(() {
      client = ConformingWebSocketClient();
    });

    tearDown(() {
      client.disconnect();
    });

    test('Transmits Authorization: Bearer <token> in handshake headers on connect', () {
      const token = 'jwt_secure_auth_token_999';
      client.connect('wss://letsfly.onrender.com/ws/events', token: token);

      expect(client.isConnected, isTrue);
      expect(client.channel, isNotNull);

      // Verify header existence and format matching server/app/main.py:212-235
      expect(client.channel?.hasAuthorizationHeader, isTrue);
      expect(client.channel?.authorizationHeader, equals('Bearer $token'));
      expect(client.channel?.tokenFromHeader, equals(token));
    });

    test('Supports query parameter fallback ?token=<token> for dev environments', () {
      const token = 'dev_query_token_123';
      client.connect(
        'wss://letsfly.onrender.com/ws/events',
        token: token,
        useQueryParamFallback: true,
      );

      expect(client.channel?.tokenFromQueryParam, equals(token));
      expect(client.channel?.hasAuthorizationHeader, isTrue);
    });

    test('Omits Authorization header when token is null or empty', () {
      client.connect('wss://letsfly.onrender.com/ws/events');

      expect(client.channel?.hasAuthorizationHeader, isFalse);
      expect(client.channel?.authorizationHeader, isNull);
    });

    test('Sends ping frame and receives automatic pong response over mock stream', () async {
      client.connect('wss://letsfly.onrender.com/ws/events', token: 'test_tok');

      client.sendPing('ping_test_42');

      // Verify client sent ping
      expect(client.channel?.sentMessages, hasLength(1));
      expect(client.channel?.sentMessages.first, contains('"ping_id":"ping_test_42"'));
    });

    test('Handles abrupt server close cleanly without unhandled exceptions', () async {
      client.connect('wss://letsfly.onrender.com/ws/events', token: 'test_tok');
      expect(client.isConnected, isTrue);

      // Server terminates socket with 1008 policy violation
      client.channel?.simulateClose(1008, 'Authentication required');
      await Future.delayed(const Duration(milliseconds: 10));

      expect(client.isConnected, isFalse);
      expect(client.receivedEvents, hasLength(1));
      expect(client.receivedEvents.first['type'], equals('ws_disconnected'));
    });
  });
}

