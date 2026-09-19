import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/io.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../core/accessibility.dart';
import '../core/localization.dart';
import '../core/sound_service.dart';

class WebSocketService {
  static final WebSocketService instance = WebSocketService._();
  WebSocketService._();

  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _subscription;
  Timer? _heartbeatTimer;
  bool _isConnected = false;
  bool _isDisposed = false;

  final StreamController<Map<String, dynamic>> _messageController =
      StreamController<Map<String, dynamic>>.broadcast();

  Stream<Map<String, dynamic>> get messages => _messageController.stream;
  Stream<Map<String, dynamic>> get events => _messageController.stream;
  bool get isConnected => _isConnected;
  bool get isDisposed => _isDisposed;

  void connect(String wsUrl, {String? token}) {
    disconnect();
    _isDisposed = false;

    try {
      var uri = Uri.parse(wsUrl);
      final Map<String, dynamic> headers = {};

      if (token != null && token.isNotEmpty) {
        // Standard bearer authorization header for IO platforms
        headers['Authorization'] = 'Bearer $token';

        // Query parameter fallback for dev/test environments & server compatibility
        final queryParams = Map<String, String>.from(uri.queryParameters);
        if (!queryParams.containsKey('token')) {
          queryParams['token'] = token;
          uri = uri.replace(queryParameters: queryParams);
        }
      }

      if (kIsWeb) {
        _channel = WebSocketChannel.connect(uri);
      } else {
        _channel = IOWebSocketChannel.connect(
          uri,
          headers: headers.isNotEmpty ? headers : null,
        );
      }
      _isConnected = true;

      _subscription = _channel?.stream.listen(
        (dynamic message) {
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
        onError: (Object err) {
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
    final wasConnected = _isConnected;
    _isConnected = false;
    _heartbeatTimer?.cancel();
    _messageController.add({'type': 'ws_disconnected'});

    if (!_isDisposed && wasConnected) {
      SoundService.instance.playSound('CONNECTION_LOST');
      AccessibilityManager.instance.announce(tr('connection lost'));
    }
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
