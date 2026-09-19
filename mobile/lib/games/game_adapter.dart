import 'package:flutter/material.dart';
import '../core/accessibility_manager.dart';
import '../core/localization.dart';
import 'ninety_nine_adapter.dart';
import 'scopa_adapter.dart';
import 'uno_adapter.dart';

/// Abstract adapter that each game implements to provide its board UI
/// and directional gesture actions (Space, Turn, Top/State).
abstract class GameAdapter {
  /// Canonical uppercase game ID (e.g. UNO, SCOPA, NINETY_NINE, etc.)
  String get gameId;

  /// Localized or user-facing name of the game
  String get displayName;

  /// Builds the in-game board/hand widget when game is active.
  Widget buildBoard(BuildContext context, Map<String, dynamic> state);

  /// Action executed when the user performs a 2-finger swipe down (Spacebar).
  void onSpaceAction(BuildContext context, Map<String, dynamic> state, String roomId);

  /// Action executed when the user performs a 2-finger swipe left (R shortcut: Top card / table status).
  void announceTop(BuildContext context, Map<String, dynamic> state);

  /// Action executed when the user performs a 2-finger swipe up (T shortcut: Current player's turn).
  void announceTurn(BuildContext context, Map<String, dynamic> state) {
    final name = (state['current_player_name'] ?? state['current_turn_name'] ?? '').toString();
    if (name.isNotEmpty) {
      AccessibilityManager.instance.announce(tr('دور {name}', {'name': name}));
    } else {
      AccessibilityManager.instance.announce(tr('غير محدد'));
    }
  }
}

/// Registry storing active game adapters.
class GameAdapterRegistry {
  static final GameAdapterRegistry instance = GameAdapterRegistry._();
  GameAdapterRegistry._();

  final Map<String, GameAdapter> _adapters = {};
  bool _defaultsRegistered = false;

  void ensureDefaultsRegistered() {
    if (_defaultsRegistered) return;
    _defaultsRegistered = true;
    register(UnoGameAdapter());
    register(ScopaGameAdapter());
    register(NinetyNineGameAdapter());
  }

  void register(GameAdapter adapter) {
    _adapters[adapter.gameId.toUpperCase()] = adapter;
  }

  GameAdapter? get(String gameId) {
    ensureDefaultsRegistered();
    return _adapters[gameId.toUpperCase()];
  }

  List<GameAdapter> get allAdapters {
    ensureDefaultsRegistered();
    return _adapters.values.toList();
  }
}
