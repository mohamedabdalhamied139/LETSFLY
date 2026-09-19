import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_tts/flutter_tts.dart';

/// Accessibility manager providing deterministic focus routing,
/// live screen reader announcements, and TTS fallback matching Windows desktop client NVDA parity.
class AccessibilityManager {
  static final AccessibilityManager instance = AccessibilityManager._();
  AccessibilityManager._() {
    _initTts();
  }

  FlutterTts? _tts;
  bool _ttsEnabled = false;

  bool get ttsEnabled => _ttsEnabled;
  set ttsEnabled(bool val) => _ttsEnabled = val;

  Future<void> _initTts() async {
    try {
      _tts = FlutterTts();
      await _tts?.setLanguage('ar');
      await _tts?.setSpeechRate(0.5);
    } catch (_) {}
  }

  /// Announces critical game events directly to TalkBack (Android) or VoiceOver (iOS).
  Future<void> announce(
    String message, {
    bool interrupt = false,
    TextDirection textDirection = TextDirection.rtl,
  }) async {
    if (message.trim().isEmpty) return;

    // 1. Announce through native mobile semantics tree
    try {
      await SemanticsService.announce(message, textDirection);
    } catch (_) {}

    // 2. Fallback to FlutterTts if explicitly enabled in settings
    if (_ttsEnabled && _tts != null) {
      try {
        if (interrupt) {
          await _tts?.stop();
        }
        await _tts?.speak(message);
      } catch (_) {}
    }
  }

  /// Generates a stable deterministic ValueKey to prevent TalkBack focus jumping during rapid state updates
  static ValueKey<String> stableKey(String prefix, dynamic id) {
    return ValueKey<String>('${prefix}_${id.toString()}');
  }
}
