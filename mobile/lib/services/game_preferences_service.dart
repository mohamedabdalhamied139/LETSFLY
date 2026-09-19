import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

/// Persistent per-game preferences matching client/game_preferences.py.
class GamePreferencesService {
  static final GamePreferencesService instance = GamePreferencesService._();
  GamePreferencesService._();

  static const String _storageKey = 'tv_game_preferences';
  final Map<String, dynamic> _memoryCache = {};
  bool _initialized = false;

  Future<void> _ensureLoaded() async {
    if (_initialized) return;
    _initialized = true;
    try {
      final prefs = await SharedPreferences.getInstance();
      final jsonStr = prefs.getString(_storageKey);
      if (jsonStr != null && jsonStr.isNotEmpty) {
        final decoded = json.decode(jsonStr);
        if (decoded is Map<String, dynamic>) {
          _memoryCache.addAll(decoded);
        }
      }
    } catch (_) {}
  }

  Future<MapEntry<int, Map<String, dynamic>>> load(
    String gameType,
    int defaultTarget,
    Map<String, dynamic> defaultRules,
  ) async {
    await _ensureLoaded();
    final gt = gameType.toUpperCase();
    final data = _memoryCache[gt] as Map<String, dynamic>?;

    int target = defaultTarget;
    final rules = Map<String, dynamic>.from(defaultRules);

    if (data != null) {
      if (data['target_score'] != null) {
        target = int.tryParse(data['target_score'].toString()) ?? defaultTarget;
      }
      if (data['rules'] is Map) {
        rules.addAll(Map<String, dynamic>.from(data['rules'] as Map));
      }
    }

    return MapEntry(target, rules);
  }

  Future<void> save(
    String gameType,
    int target,
    Map<String, dynamic> rules,
  ) async {
    await _ensureLoaded();
    final gt = gameType.toUpperCase();
    _memoryCache[gt] = {
      'target_score': target,
      'rules': Map<String, dynamic>.from(rules),
    };

    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_storageKey, json.encode(_memoryCache));
    } catch (_) {}
  }
}
