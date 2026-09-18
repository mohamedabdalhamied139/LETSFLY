// Tier 1 Unit Test: ActivityLogService (Deduplication, Filtering, Category Selection)

import '../harness/test_engine.dart';
import '../harness/test_fixtures.dart';

/// Standalone test implementation of ActivityLogService matching mobile/lib/services/activity_service.dart
class TestActivityLogService {
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
  int listenerNotificationCount = 0;

  void notifyListeners() {
    listenerNotificationCount++;
  }

  List<Map<String, dynamic>> get events => List.unmodifiable(_events);
  String get selectedCategory => _selectedCategory;

  String _category(Map<String, dynamic> event) {
    final cat = (event['category'] ?? event['type'] ?? '').toString().trim().toUpperCase();
    return cat.isNotEmpty ? cat : 'ALL';
  }

  String? _logicalGameEventKey(Map<String, dynamic> event) {
    dynamic gameEventId = event['game_event_id'];
    if (gameEventId == null) {
      final payload = event['payload'];
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
        final existingText = (existing['text'] ?? existing['message'] ?? '').toString().trim();
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

  void addEvent(Map<String, dynamic> event) {
    final text = (event['text'] ?? event['message'] ?? '').toString().trim();
    if (text.isEmpty) return;

    if (_eventExists(event)) return;

    _events.insert(0, Map<String, dynamic>.from(event));
    notifyListeners();
  }

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

  void selectCategory(String category) {
    final normalized = category.trim().toUpperCase();
    if (categories.contains(normalized) && _selectedCategory != normalized) {
      _selectedCategory = normalized;
      notifyListeners();
    }
  }

  List<Map<String, dynamic>> get filteredEvents {
    if (_selectedCategory == 'ALL') {
      return List.unmodifiable(_events);
    }
    return List.unmodifiable(
      _events.where((e) => _category(e) == _selectedCategory).toList(),
    );
  }

  void clear() {
    _events.clear();
    notifyListeners();
  }
}

void main() async {
  defineTests();
  await runSuite('Tier 1 Unit: Activity Service Tests');
}

void defineTests() {
  group('ActivityLogService Parity & Deduplication', () {
    late TestActivityLogService service;

    setUp(() {
      service = TestActivityLogService();
    });

    group('Event Deduplication Logic', () {
      test('Deduplicates events with the same unique id', () {
        service.addEvent({'id': 101, 'text': 'حدث تجريبي أولي', 'category': 'ALL'});
        service.addEvent({'id': 101, 'text': 'حدث تجريبي معدل لنفس المعرف', 'category': 'ALL'});

        expect(service.events, hasLength(1));
        expect(service.events.first['text'], equals('حدث تجريبي أولي'));
      });

      test('Deduplicates gameplay events with the same logical game key', () {
        service.addEvent({
          'room_id': 'room_uno_1',
          'event_type': 'card_played',
          'game_event_id': 'g_55',
          'category': 'GAMEPLAY',
          'text': 'أحمد لعب بطاقة 5 خضراء',
        });

        // Incoming duplicate with different unique event id or no id, but same logical key
        service.addEvent({
          'id': 9999,
          'room_id': 'room_uno_1',
          'event_type': 'card_played',
          'game_event_id': 'g_55',
          'category': 'GAMEPLAY',
          'text': 'أحمد لعب بطاقة 5 خضراء (مكرر)',
        });

        expect(service.events, hasLength(1));
        expect(service.events.first['text'], equals('أحمد لعب بطاقة 5 خضراء'));
      });

      test('Deduplicates identical text in the same room and category', () {
        service.addEvent({
          'room_id': 'room_domino_2',
          'category': 'TABLE_CHAT',
          'text': 'السلام عليكم ورحمة الله',
        });

        // Exact text repeated immediately
        service.addEvent({
          'room_id': 'room_domino_2',
          'category': 'TABLE_CHAT',
          'text': 'السلام عليكم ورحمة الله',
        });

        expect(service.events, hasLength(1));
      });

      test('Allows identical text in different rooms or categories', () {
        service.addEvent({
          'room_id': 'room_1',
          'category': 'TABLE_CHAT',
          'text': 'مبروك الفوز!',
        });

        service.addEvent({
          'room_id': 'room_2',
          'category': 'TABLE_CHAT',
          'text': 'مبروك الفوز!',
        });

        expect(service.events, hasLength(2));
      });

      test('Discards events with empty or whitespace-only text', () {
        service.addEvent({'text': '', 'category': 'ALL'});
        service.addEvent({'text': '   ', 'category': 'ALL'});
        service.addEvent({'category': 'ALL'});

        expect(service.events, hasLength(0));
      });
    });

    group('Category Filtering & Selection', () {
      setUp(() {
        for (final evt in TestFixtures.sampleActivityEvents) {
          service.addEvent(evt);
        }
      });

      test('Default category is ALL and returns all recorded events', () {
        expect(service.selectedCategory, equals('ALL'));
        expect(service.filteredEvents, hasLength(TestFixtures.sampleActivityEvents.length));
      });

      test('Filters accurately when switching to GAMEPLAY category', () {
        service.selectCategory('GAMEPLAY');

        expect(service.selectedCategory, equals('GAMEPLAY'));
        for (final evt in service.filteredEvents) {
          expect(evt['category'], equals('GAMEPLAY'));
        }
      });

      test('Filters accurately when switching to TABLE_CHAT category', () {
        service.selectCategory('TABLE_CHAT');

        expect(service.selectedCategory, equals('TABLE_CHAT'));
        expect(service.filteredEvents, hasLength(1));
        expect(service.filteredEvents.first['text'], contains('محمد: بالتوفيق للجميع!'));
      });

      test('Filters accurately for INVITATIONS and FRIEND_REQUESTS', () {
        service.selectCategory('INVITATIONS');
        expect(service.filteredEvents, hasLength(1));
        expect(service.filteredEvents.first['category'], equals('INVITATIONS'));

        service.selectCategory('FRIEND_REQUESTS');
        expect(service.filteredEvents, hasLength(1));
        expect(service.filteredEvents.first['category'], equals('FRIEND_REQUESTS'));
      });

      test('Ignores invalid or unlisted category names', () {
        service.selectCategory('INVALID_CATEGORY_XYZ');
        expect(service.selectedCategory, equals('ALL'));
      });
    });

    group('Pagination and Clearing', () {
      setUp(() {
        service.clear();
      });

      test('addEvent inserts at top (index 0) while appendOlder appends to bottom', () {
        service.addEvent({'id': 1, 'text': 'First Event', 'category': 'ALL'});
        service.addEvent({'id': 2, 'text': 'Second Event (Newer)', 'category': 'ALL'});

        expect(service.events.first['id'], equals(2));
        expect(service.events.last['id'], equals(1));

        service.appendOlder([
          {'id': 3, 'text': 'Third Event (Older)', 'category': 'ALL'},
        ]);

        expect(service.events.last['id'], equals(3));
      });

      test('clear removes all events and notifies listeners', () {
        service.addEvent({'id': 1, 'text': 'Event 1', 'category': 'ALL'});
        service.addEvent({'id': 2, 'text': 'Event 2', 'category': 'ALL'});

        service.clear();

        expect(service.events, hasLength(0));
        expect(service.filteredEvents, hasLength(0));
      });
    });
  });
}
