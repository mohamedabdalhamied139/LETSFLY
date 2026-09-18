import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';

class WebSocketService {
  static final WebSocketService instance = WebSocketService._();
  WebSocketService._();

  WebSocketChannel? _channel;
  StreamSubscription? _subscription;
  Timer? _heartbeatTimer;
  bool _isConnected = false;
  bool _isDisposed = false;

  final StreamController<Map<String, dynamic>> _messageController =
      StreamController<Map<String, dynamic>>.broadcast();

  Stream<Map<String, dynamic>> get messages => _messageController.stream;
  bool get isConnected => _isConnected;

  void connect(String wsUrl, {String? token}) {
    disconnect();
    _isDisposed = false;

    try {
      final uri = Uri.parse(wsUrl);
      _channel = WebSocketChannel.connect(uri);
      _isConnected = true;

      _subscription = _channel?.stream.listen(
        (message) {
          if (message is String) {
            try {
              final data = json.decode(message);
              if (data is Map<String, dynamic>) {
                if (data['type'] == 'pong') {
                  // Heartbeat response
                  return;
                }
                _messageController.add(data);
              }
            } catch (_) {}
          }
        },
        onError: (err) {
          _handleDisconnect();
        },
        onDone: () {
          _handleDisconnect();
        },
      );

      _startHeartbeat();
    } catch (_) {
      _handleDisconnect();
    }
  }

  void _startHeartbeat() {
    _heartbeatTimer?.cancel();
    // 10-second heartbeat matching the optimized server protocol
    _heartbeatTimer = Timer.periodic(const Duration(seconds: 10), (timer) {
      if (_isConnected && _channel != null) {
        sendJson({'type': 'ping'});
      }
    });
  }

  bool sendJson(Map<String, dynamic> data) {
    if (_isConnected && _channel != null) {
      try {
        _channel?.sink.add(json.encode(data));
        return true;
      } catch (_) {
        return false;
      }
    }
    return false;
  }

  void _handleDisconnect() {
    _isConnected = false;
    _heartbeatTimer?.cancel();
    _messageController.add({'type': 'ws_disconnected'});
  }

  void disconnect() {
    _isDisposed = true;
    _isConnected = false;
    _heartbeatTimer?.cancel();
    _subscription?.cancel();
    _channel?.sink.close();
    _channel = null;
  }
}
