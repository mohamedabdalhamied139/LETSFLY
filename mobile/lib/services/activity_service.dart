import 'dart:convert';
import 'package:flutter/foundation.dart';

/// Centralized reactive event store for the 8 canonical activity categories.
/// Provides deduplication matching Windows client architecture and cross-screen synchronization.
class ActivityLogService extends ChangeNotifier {
  static final ActivityLogService instance = ActivityLogService._();
  ActivityLogService._();

  static const List<String> categories = [
    'TABLE_CHAT',
    'PRIVATE_MESSAGES',
    'FRIENDS',
    'GAMEPLAY',
    'ALL',
    'FRIEND_REQUESTS',
    'INVITATIONS',
    'GIFTS',
  ];

  final List<Map<String, dynamic>> _events = [];
  String _selectedCategory = 'ALL';

  List<Map<String, dynamic>> get events => List.unmodifiable(_events);
  String get selectedCategory => _selectedCategory;

  String _category(Map<String, dynamic> event) {
    final cat = (event['category'] ?? event['type'] ?? '').toString().trim().toUpperCase();
    return cat.isNotEmpty ? cat : 'ALL';
  }

  String? _logicalGameEventKey(Map<String, dynamic> event) {
    dynamic gameEventId = event['game_event_id'];
    if (gameEventId == null) {
      dynamic payload = event['payload'];
      if (payload is String) {
        try {
          payload = json.decode(payload);
        } catch (_) {
          payload = null;
        }
      }
      if (payload is Map) {
        gameEventId = payload['game_event_id'];
      }
    }
    if (gameEventId == null) return null;

    final roomId = (event['room_id'] ?? '').toString();
    final eventType = (event['event_type'] ?? '').toString();
    return 'game:$roomId:$eventType:$gameEventId';
  }

  bool _eventExists(Map<String, dynamic> event) {
    final eventId = event['id'];
    final text = (event['text'] ?? event['message'] ?? '').toString().trim();
    final logicalKey = _logicalGameEventKey(event);

    for (final existing in _events) {
      // 1. Check duplicate unique ID
      if (eventId != null &&
          existing['id'] != null &&
          existing['id'].toString() == eventId.toString()) {
        return true;
      }

      // 2. Check logical game key
      if (logicalKey != null) {
        final existingKey = _logicalGameEventKey(existing);
        if (existingKey != null && existingKey == logicalKey) {
          return true;
        }
      }

      // 3. Check identical text within same game / room / category
      if (text.isNotEmpty) {
        final existingText =
            (existing['text'] ?? existing['message'] ?? '').toString().trim();
        if (existingText == text) {
          final roomA = (event['room_id'] ?? '').toString();
          final roomB = (existing['room_id'] ?? '').toString();
          final catA = _category(event);
          final catB = _category(existing);

          if ((roomA.isEmpty || roomB.isEmpty || roomA == roomB) &&
              (catA == catB || catA == 'GAMEPLAY' || catB == 'GAMEPLAY')) {
            return true;
          }
        }
      }
    }
    return false;
  }

  /// Add a single activity event if not a duplicate
  void addEvent(Map<String, dynamic> event) {
    final text = (event['text'] ?? event['message'] ?? '').toString().trim();
    if (text.isEmpty) return;

    if (_eventExists(event)) return;

    _events.insert(0, Map<String, dynamic>.from(event));
    notifyListeners();
  }

  /// Add multiple events, maintaining deduplication
  void addEvents(List<Map<String, dynamic>> newEvents) {
    bool addedAny = false;
    for (final event in newEvents) {
      final text = (event['text'] ?? event['message'] ?? '').toString().trim();
      if (text.isEmpty) continue;
      if (!_eventExists(event)) {
        _events.insert(0, Map<String, dynamic>.from(event));
        addedAny = true;
      }
    }
    if (addedAny) {
      notifyListeners();
    }
  }

  /// Append older paginated events to the end of the list
  void appendOlder(List<Map<String, dynamic>> olderEvents) {
    bool addedAny = false;
    for (final event in olderEvents) {
      final text = (event['text'] ?? event['message'] ?? '').toString().trim();
      if (text.isEmpty) continue;
      if (!_eventExists(event)) {
        _events.add(Map<String, dynamic>.from(event));
        addedAny = true;
      }
    }
    if (addedAny) {
      notifyListeners();
    }
  }

  /// Switch the active filter category
  void selectCategory(String category) {
    final normalized = category.trim().toUpperCase();
    if (categories.contains(normalized) && _selectedCategory != normalized) {
      _selectedCategory = normalized;
      notifyListeners();
    }
  }

  /// Filtered list of events based on currently selected category
  List<Map<String, dynamic>> get filteredEvents {
    if (_selectedCategory == 'ALL') {
      return List.unmodifiable(_events);
    }
    return List.unmodifiable(
      _events.where((e) => _category(e) == _selectedCategory).toList(),
    );
  }

  /// Clear all stored events
  void clear() {
    _events.clear();
    notifyListeners();
  }
}
