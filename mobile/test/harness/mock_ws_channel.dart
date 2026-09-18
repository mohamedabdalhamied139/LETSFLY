// Stream-based Mock WebSocket channel simulating ping/pong, activity events, and protocol conformance.

import 'dart:async';
import 'dart:convert';

class MockWsChannel {
  final Uri uri;
  final Map<String, String> headers;

  final StreamController<dynamic> _incomingController = StreamController<dynamic>.broadcast();
  final StreamController<dynamic> _outgoingController = StreamController<dynamic>();

  final List<dynamic> sentMessages = [];
  bool isConnected = false;
  bool isClosed = false;
  int? closeCode;
  String? closeReason;

  static MockWsChannel? lastCreated;

  MockWsChannel(this.uri, {Map<String, String>? headers})
      : headers = headers ?? {} {
    isConnected = true;
    lastCreated = this;
  }

  Stream<dynamic> get stream => _incomingController.stream;
  late final StreamSink<dynamic> sink = _MockSink(this);


  void _handleClientMessage(dynamic message) {
    if (message is String) {
      try {
        final data = json.decode(message);
        if (data is Map && data['type'] == 'ping') {
          // Automatic pong response matching server
          simulateServerMessage({
            'type': 'pong',
            'ping_id': data['ping_id'],
            'timestamp': DateTime.now().millisecondsSinceEpoch,
          });
        }
      } catch (_) {}
    }
  }

  /// Inject an arbitrary server message into the client stream
  void simulateServerMessage(Map<String, dynamic> data) {
    if (!isClosed) {
      _incomingController.add(json.encode(data));
    }
  }

  /// Inject an activity event into the client stream
  void simulateActivityEvent(Map<String, dynamic> event) {
    simulateServerMessage({
      'type': 'activity_event',
      ...event,
    });
  }

  /// Inject a room snapshot into the client stream
  void simulateRoomSnapshot(Map<String, dynamic> room, [Map<String, dynamic>? gameState]) {
    simulateServerMessage({
      'type': 'room_snapshot',
      'room': room,
      if (gameState != null) 'game_state': gameState,
    });
  }

  /// Simulate sudden disconnect or server close
  void simulateClose([int code = 1000, String reason = 'Normal closure']) {
    isClosed = true;
    isConnected = false;
    closeCode = code;
    closeReason = reason;
    _incomingController.close();
    _outgoingController.close();
  }

  void close() {
    simulateClose(1000, 'Client closed');
  }

  // Inspection helpers
  bool get hasAuthorizationHeader => headers.containsKey('Authorization');
  String? get authorizationHeader => headers['Authorization'];
  String? get tokenFromHeader {
    final auth = headers['Authorization'];
    if (auth != null && auth.startsWith('Bearer ')) {
      return auth.substring(7).trim();
    }
    return null;
  }

  String? get tokenFromQueryParam => uri.queryParameters['token'];
}

class _MockSink implements StreamSink<dynamic> {
  final MockWsChannel _channel;
  _MockSink(this._channel);

  @override
  void add(dynamic event) {
    _channel.sentMessages.add(event);
    _channel._handleClientMessage(event);
  }

  @override
  void addError(Object error, [StackTrace? stackTrace]) {}

  @override
  Future addStream(Stream stream) => stream.forEach(add);

  @override
  Future close() async {
    _channel.close();
  }

  @override
  Future get done => Future.value();
}

