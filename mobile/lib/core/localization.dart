import 'dart:convert';
import 'package:flutter/services.dart';

/// Localization manager matching the Python client dictionary keys 100%.
class LocalizationService {
  static final LocalizationService instance = LocalizationService._();
  LocalizationService._();

  String currentLanguage = 'ar';
  Map<String, String> _translations = {};
  final List<void Function(String)> _listeners = [];

  Future<void> loadLanguage(String lang) async {
    currentLanguage = lang;
    try {
      final jsonString = await rootBundle.loadString('assets/locales/$lang.json');
      final Map<String, dynamic> jsonMap = json.decode(jsonString);
      _translations = jsonMap.map((key, value) => MapEntry(key, value.toString()));
    } catch (_) {
      // Fallback to empty if file missing
      _translations = {};
    }
    for (final listener in _listeners) {
      try {
        listener(lang);
      } catch (_) {}
    }
  }

  void subscribe(void Function(String) callback) {
    if (!_listeners.contains(callback)) {
      _listeners.add(callback);
    }
  }

  void unsubscribe(void Function(String) callback) {
    _listeners.remove(callback);
  }

  String translate(String key, [Map<String, dynamic>? params]) {
    String text = _translations[key] ?? key;
    if (params != null && params.isNotEmpty) {
      params.forEach((paramKey, paramValue) {
        text = text.replaceAll('{$paramKey}', paramValue.toString());
      });
    }
    return text;
  }
}

/// Global convenience function equivalent to `tr(...)` in Python client.
String tr(String key, [Map<String, dynamic>? params]) {
  return LocalizationService.instance.translate(key, params);
}
