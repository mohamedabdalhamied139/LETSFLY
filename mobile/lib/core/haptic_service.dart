import 'package:flutter/services.dart';

/// Haptic feedback service providing tactile vibrations on mobile devices.
/// Strictly scoped per user request to trigger only on the player's turn.
class HapticService {
  static final HapticService instance = HapticService._();
  HapticService._();

  bool _enabled = true;
  bool get enabled => _enabled;

  set enabled(bool value) {
    _enabled = value;
  }

  /// Triggers a tactical vibration specifically when it is the user's turn to play.
  Future<void> playTurnHaptic() async {
    if (!_enabled) return;
    try {
      await HapticFeedback.vibrate();
      await Future.delayed(const Duration(milliseconds: 120));
      await HapticFeedback.vibrate();
    } catch (_) {
      try {
        await HapticFeedback.heavyImpact();
      } catch (_) {}
    }
  }
}
