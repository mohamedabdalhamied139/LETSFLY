// Adversarial Empirical Verification Suite for ActivityLogService and ActivityLogWidget
// Zero-dependency executable test harness for Dart SDK / Flutter runner.

import 'dart:convert';
import 'dart:io';
import 'harness/test_engine.dart';
import '../lib/services/activity_service.dart';

void main() async {
  defineAdversarialTests();
  final success = await runSuite('Adversarial ActivityLog Verification Suite');
  if (!success) {
    exitCode = 1;
  }
}

void defineAdversarialTests() {
  final service = ActivityLogService.instance;

  void resetService() {
    service.clear();
    service.selectCategory('ALL');
  }

  // =========================================================================
  // GROUP 1: Aggressive Deduplication Verification
  // =========================================================================
  group('Adversarial Deduplication Verification', () {
    setUp(resetService);

    test('Deduplication by ID: int vs string vs negative vs zero vs large int', () {
      // 1. int vs string ID
      service.addEvent({'id': 100, 'text': 'ID as integer', 'category': 'ALL'});
      service.addEvent({'id': '100', 'text': 'ID as string', 'category': 'ALL'});
      expect(service.events, hasLength(1));
      expect(service.events.first['text'], equals('ID as integer'));

      // 2. string first, then int
      service.addEvent({'id': '200', 'text': 'ID 200 first', 'category': 'ALL'});
      service.addEvent({'id': 200, 'text': 'ID 200 duplicate', 'category': 'ALL'});
      expect(service.events, hasLength(2));

      // 3. Zero ID deduplication
      service.addEvent({'id': 0, 'text': 'Zero ID original', 'category': 'ALL'});
      service.addEvent({'id': 0, 'text': 'Zero ID duplicate', 'category': 'ALL'});
      service.addEvent({'id': '0', 'text': 'Zero ID string duplicate', 'category': 'ALL'});
      expect(service.events, hasLength(3));

      // 4. Negative ID deduplication
      service.addEvent({'id': -42, 'text': 'Negative ID original', 'category': 'ALL'});
      service.addEvent({'id': -42, 'text': 'Negative ID duplicate', 'category': 'ALL'});
      expect(service.events, hasLength(4));

      // 5. Large 64-bit int ID deduplication
      service.addEvent({'id': 9007199254740991, 'text': 'BigInt original', 'category': 'ALL'});
      service.addEvent({'id': 9007199254740991, 'text': 'BigInt duplicate', 'category': 'ALL'});
      expect(service.events, hasLength(5));

      // 6. Null ID should NOT match other events with null ID if text differs
      service.addEvent({'id': null, 'text': 'Null ID Event Alpha', 'room_id': 'room_a', 'category': 'ALL'});
      service.addEvent({'id': null, 'text': 'Null ID Event Beta', 'room_id': 'room_b', 'category': 'ALL'});
      expect(service.events, hasLength(7));
    });

    test('Deduplication by Logical Game Key: game:{room_id}:{event_type}:{game_event_id}', () {
      // 1. game_event_id in root
      service.addEvent({
        'room_id': 'table_404',
        'event_type': 'dice_roll',
        'game_event_id': 'dice_99',
        'category': 'GAMEPLAY',
        'text': 'رمى اللاعب النرد: 6',
      });

      // 2. Incoming duplicate with different event id, but matching logical key in root
      service.addEvent({
        'id': 99999,
        'room_id': 'table_404',
        'event_type': 'dice_roll',
        'game_event_id': 'dice_99',
        'category': 'GAMEPLAY',
        'text': 'رمى اللاعب النرد: 6 (مكرر 1)',
      });
      expect(service.events, hasLength(1));

      // 3. Incoming duplicate where game_event_id is inside payload Map
      service.addEvent({
        'id': 88888,
        'room_id': 'table_404',
        'event_type': 'dice_roll',
        'payload': {'game_event_id': 'dice_99', 'val': 6},
        'category': 'GAMEPLAY',
        'text': 'رمى اللاعب النرد: 6 (مكرر عبر Map payload)',
      });
      expect(service.events, hasLength(1));

      // 4. Incoming duplicate where game_event_id is inside payload JSON-encoded String
      service.addEvent({
        'id': 77777,
        'room_id': 'table_404',
        'event_type': 'dice_roll',
        'payload': json.encode({'game_event_id': 'dice_99', 'val': 6}),
        'category': 'GAMEPLAY',
        'text': 'رمى اللاعب النرد: 6 (مكرر عبر JSON string)',
      });
      expect(service.events, hasLength(1));

      // 5. Different room_id with same event_type and game_event_id must NOT be deduplicated
      service.addEvent({
        'room_id': 'table_505',
        'event_type': 'dice_roll',
        'game_event_id': 'dice_99',
        'category': 'GAMEPLAY',
        'text': 'رمى اللاعب النرد في غرفة أخرى: 6',
      });
      expect(service.events, hasLength(2));

      // 6. Different event_type with same room_id and game_event_id must NOT be deduplicated
      service.addEvent({
        'room_id': 'table_404',
        'event_type': 'turn_end',
        'game_event_id': 'dice_99',
        'category': 'GAMEPLAY',
        'text': 'انتهى دور اللاعب',
      });
      expect(service.events, hasLength(3));

      // 7. Int vs String game_event_id: 123 vs "123"
      service.addEvent({
        'room_id': 'table_domino',
        'event_type': 'tile_placed',
        'game_event_id': 123,
        'category': 'GAMEPLAY',
        'text': 'وضع قطعة 6-6',
      });
      service.addEvent({
        'room_id': 'table_domino',
        'event_type': 'tile_placed',
        'game_event_id': '123',
        'category': 'GAMEPLAY',
        'text': 'وضع قطعة 6-6 مكرر',
      });
      expect(service.events, hasLength(4));
    });

    test('Deduplication by Room Message Text: same vs different rooms/categories', () {
      // 1. Identical text in same room & same category
      service.addEvent({
        'room_id': 'chat_room_1',
        'category': 'TABLE_CHAT',
        'text': 'أهلاً وسهلاً بالجميع',
      });
      service.addEvent({
        'room_id': 'chat_room_1',
        'category': 'TABLE_CHAT',
        'text': 'أهلاً وسهلاً بالجميع',
      });
      expect(service.events, hasLength(1));

      // 2. Identical text with whitespace variations (leading/trailing)
      service.addEvent({
        'room_id': 'chat_room_1',
        'category': 'TABLE_CHAT',
        'text': '   أهلاً وسهلاً بالجميع   \n',
      });
      expect(service.events, hasLength(1));

      // 3. Identical text across DIFFERENT rooms -> ALLOWED
      service.addEvent({
        'room_id': 'chat_room_2',
        'category': 'TABLE_CHAT',
        'text': 'أهلاً وسهلاً بالجميع',
      });
      expect(service.events, hasLength(2));

      // 4. Identical text in same room across DIFFERENT non-GAMEPLAY categories -> ALLOWED
      service.addEvent({
        'room_id': 'chat_room_1',
        'category': 'PRIVATE_MESSAGES',
        'text': 'أهلاً وسهلاً بالجميع',
      });
      expect(service.events, hasLength(3));

      // 5. Identical text where one category is GAMEPLAY and other is something else in same room -> DEDUPLICATED
      service.addEvent({
        'room_id': 'game_room_9',
        'category': 'GAMEPLAY',
        'text': 'فاز الفريق باللعبة!',
      });
      service.addEvent({
        'room_id': 'game_room_9',
        'category': 'ALL',
        'text': 'فاز الفريق باللعبة!',
      });
      expect(service.events, hasLength(4));

      // 6. Message fallback: event with 'message' instead of 'text'
      service.addEvent({
        'room_id': 'msg_room',
        'category': 'FRIENDS',
        'message': 'صديقك متصل الآن',
      });
      service.addEvent({
        'room_id': 'msg_room',
        'category': 'FRIENDS',
        'text': 'صديقك متصل الآن',
      });
      expect(service.events, hasLength(5));
    });

    test('Deduplication with empty / whitespace text: discarded', () {
      service.addEvent({'text': ''});
      service.addEvent({'text': '   '});
      service.addEvent({'text': '\t\n\r'});
      service.addEvent({'message': ''});
      service.addEvent({'message': '   '});
      service.addEvent({});
      expect(service.events, hasLength(0));
    });
  });

  // =========================================================================
  // GROUP 2: Canonical 8 Categories Filtering & Parity
  // =========================================================================
  group('Canonical 8 Categories Filtering & Parity', () {
    setUp(resetService);

    const canonicalCategories = [
      'TABLE_CHAT',
      'PRIVATE_MESSAGES',
      'FRIENDS',
      'GAMEPLAY',
      'ALL',
      'FRIEND_REQUESTS',
      'INVITATIONS',
      'GIFTS',
    ];

    test('ActivityLogService exposes exactly the 8 canonical categories', () {
      expect(ActivityLogService.categories, hasLength(8));
      expect(ActivityLogService.categories, equals(canonicalCategories));
    });

    test('Event filtering isolates each of the 8 categories correctly', () {
      // Add one distinct event for each category
      final eventsData = [
        {'id': 1, 'category': 'TABLE_CHAT', 'text': 'رسالة دردشة طاولة'},
        {'id': 2, 'category': 'PRIVATE_MESSAGES', 'text': 'رسالة خاصة سرية'},
        {'id': 3, 'category': 'FRIENDS', 'text': 'علي أصبح متصلاً'},
        {'id': 4, 'category': 'GAMEPLAY', 'text': 'سحب بطاقة جديدة'},
        {'id': 5, 'category': 'ALL', 'text': 'إشعار عام للجميع'},
        {'id': 6, 'category': 'FRIEND_REQUESTS', 'text': 'طلب صداقة من سارة'},
        {'id': 7, 'category': 'INVITATIONS', 'text': 'دعوة للانضمام إلى طاولة 5'},
        {'id': 8, 'category': 'GIFTS', 'text': 'أرسل لك هدية 100 كوينز'},
      ];

      for (final evt in eventsData) {
        service.addEvent(evt);
      }

      expect(service.events, hasLength(8));

      // Test ALL: must return all 8 events
      service.selectCategory('ALL');
      expect(service.selectedCategory, equals('ALL'));
      expect(service.filteredEvents, hasLength(8));

      // Test each non-ALL category individually
      for (final cat in canonicalCategories) {
        if (cat == 'ALL') continue;
        service.selectCategory(cat);
        expect(service.selectedCategory, equals(cat));

        final filtered = service.filteredEvents;
        expect(filtered, hasLength(1), reason: 'Category $cat should have exactly 1 event');
        expect(filtered.first['category'], equals(cat));
      }
    });

    test('Category normalization handles lowercase, whitespace, and type fallback', () {
      // Category in lowercase with extra spaces
      service.addEvent({
        'id': 11,
        'category': '  gameplay  ',
        'text': 'حدث لعب منسق',
      });
      // Category passed via 'type' instead of 'category'
      service.addEvent({
        'id': 12,
        'type': 'gifts',
        'text': 'هدية عيد الفطر',
      });
      // Event with missing category defaults to ALL
      service.addEvent({
        'id': 13,
        'text': 'حدث بدون فئة محددة',
      });

      expect(service.events, hasLength(3));

      // Filter GAMEPLAY
      service.selectCategory('gameplay');
      expect(service.selectedCategory, equals('GAMEPLAY'));
      expect(service.filteredEvents, hasLength(1));
      expect(service.filteredEvents.first['id'], equals(11));

      // Filter GIFTS with leading spaces
      service.selectCategory('  gifts  ');
      expect(service.selectedCategory, equals('GIFTS'));
      expect(service.filteredEvents, hasLength(1));
      expect(service.filteredEvents.first['id'], equals(12));

      // Filter ALL includes the one without category
      service.selectCategory('ALL');
      expect(service.filteredEvents, hasLength(3));
    });

    test('Invalid category selection is safely rejected without modifying active filter', () {
      service.selectCategory('GAMEPLAY');
      expect(service.selectedCategory, equals('GAMEPLAY'));

      service.selectCategory('HACK_INJECTION_CAT');
      expect(service.selectedCategory, equals('GAMEPLAY'));

      service.selectCategory('');
      expect(service.selectedCategory, equals('GAMEPLAY'));
    });
  });

  // =========================================================================
  // GROUP 3: Edge Cases, Malformed Events, Null Safety, & Rapid Stress
  // =========================================================================
  group('Edge Cases, Malformed Payloads & Null Safety', () {
    setUp(resetService);

    test('Malformed payload: corrupted JSON string does not crash', () {
      service.addEvent({
        'id': 301,
        'room_id': 'r_err',
        'event_type': 'test',
        'payload': '{{corrupted: json string',
        'text': 'حدث مع حمولة تالفة',
      });
      expect(service.events, hasLength(1));
      expect(service.events.first['text'], equals('حدث مع حمولة تالفة'));
    });

    test('Non-standard payload types: int, list, bool, double do not crash', () {
      service.addEvent({'id': 302, 'payload': 12345, 'text': 'Payload int'});
      service.addEvent({'id': 303, 'payload': [1, 2, 'three'], 'text': 'Payload list'});
      service.addEvent({'id': 304, 'payload': true, 'text': 'Payload bool'});
      service.addEvent({'id': 305, 'payload': 3.14159, 'text': 'Payload double'});

      expect(service.events, hasLength(4));
    });

    test('Extreme null safety: events with null properties', () {
      service.addEvent({
        'id': null,
        'room_id': null,
        'event_type': null,
        'game_event_id': null,
        'payload': null,
        'category': null,
        'type': null,
        'text': 'حدث جميع حقوله فارغة باستثناء النص',
      });
      expect(service.events, hasLength(1));
    });

    test('Immutability: events and filteredEvents cannot be mutated externally', () {
      service.addEvent({'id': 401, 'text': 'محمي من التعديل'});

      bool threwOnEvents = false;
      try {
        service.events.add({'id': 999, 'text': 'اختراق'});
      } catch (_) {
        threwOnEvents = true;
      }
      expect(threwOnEvents, isTrue);

      bool threwOnFiltered = false;
      try {
        service.filteredEvents.clear();
      } catch (_) {
        threwOnFiltered = true;
      }
      expect(threwOnFiltered, isTrue);
    });

    test('Listener Notification Precision: duplicates & no-ops emit 0 notifications', () {
      int notifications = 0;
      service.addListener(() => notifications++);

      // 1. Add valid event -> 1 notification
      service.addEvent({'id': 501, 'text': 'حدث 1'});
      expect(notifications, equals(1));

      // 2. Add duplicate event -> 0 notifications
      service.addEvent({'id': 501, 'text': 'حدث 1 مكرر'});
      expect(notifications, equals(1));

      // 3. Add empty text -> 0 notifications
      service.addEvent({'text': ''});
      expect(notifications, equals(1));

      // 4. Batch add with all duplicates -> 0 notifications
      service.addEvents([
        {'id': 501, 'text': 'مكرر 1'},
        {'id': 501, 'text': 'مكرر 2'},
      ]);
      expect(notifications, equals(1));

      // 5. Batch add with 3 unique events -> exactly 1 notification for entire batch
      service.addEvents([
        {'id': 502, 'text': 'حدث 2'},
        {'id': 503, 'text': 'حدث 3'},
        {'id': 504, 'text': 'حدث 4'},
      ]);
      expect(notifications, equals(2));

      // 6. Select same category -> 0 notifications
      service.selectCategory('ALL');
      expect(notifications, equals(2));

      // 7. Select new category -> 1 notification
      service.selectCategory('GAMEPLAY');
      expect(notifications, equals(3));

      // 8. Clear -> 1 notification
      service.clear();
      expect(notifications, equals(4));
    });

    test('Stress Test: Rapid additions of 2,000 unique events', () {
      final sw = Stopwatch()..start();
      const count = 2000;
      for (int i = 0; i < count; i++) {
        service.addEvent({
          'id': i,
          'room_id': 'room_${i % 10}',
          'category': 'GAMEPLAY',
          'text': 'حدث سريع رقم $i',
        });
      }
      sw.stop();
      expect(service.events, hasLength(count));
      print('      [Performance] Added $count unique events in ${sw.elapsedMilliseconds}ms');
    });

    test('Stress Test: Rapid flood of 2,000 duplicate events rejected instantly', () {
      // First populate 500 events
      const baseCount = 500;
      for (int i = 0; i < baseCount; i++) {
        service.addEvent({
          'id': i,
          'room_id': 'room_${i % 10}',
          'category': 'GAMEPLAY',
          'text': 'حدث أساسي رقم $i',
        });
      }
      expect(service.events, hasLength(baseCount));

      final sw = Stopwatch()..start();
      const duplicateCount = 2000;
      for (int i = 0; i < duplicateCount; i++) {
        // Attempting to re-insert duplicates of the base events
        service.addEvent({
          'id': i % baseCount,
          'room_id': 'room_${(i % baseCount) % 10}',
          'category': 'GAMEPLAY',
          'text': 'حدث أساسي رقم ${i % baseCount}',
        });
      }
      sw.stop();
      // Length should remain strictly at baseCount (all duplicates rejected)
      expect(service.events, hasLength(baseCount));
      print('      [Performance] Verified $duplicateCount duplicates rejected in ${sw.elapsedMilliseconds}ms against $baseCount stored events');
    });

    test('Batch addEvents with multiple internal duplicates in single batch', () {
      int notifyCount = 0;
      service.addListener(() => notifyCount++);

      final batch = [
        {'id': 801, 'text': 'Event 801 A'},
        {'id': 801, 'text': 'Event 801 duplicate in same batch'},
        {'id': 802, 'text': 'Event 802'},
        {'id': 801, 'text': 'Event 801 duplicate again'},
        {'id': 803, 'text': 'Event 803'},
        {'text': ''}, // empty text
      ];

      service.addEvents(batch);

      // Exactly 3 unique events added
      expect(service.events, hasLength(3));
      expect(service.events.map((e) => e['id']).toList(), equals([803, 802, 801]));
      // Exactly 1 listener notification for the entire batch
      expect(notifyCount, equals(1));
    });

    test('Stress Test: Alternating stream of 4,000 unique and duplicate events', () {
      int notifyCount = 0;
      service.addListener(() => notifyCount++);

      final sw = Stopwatch()..start();
      const streamCount = 4000;
      for (int i = 0; i < streamCount; i++) {
        // Even indices are unique, odd indices duplicate the previous even index
        final id = (i % 2 == 0) ? i : (i - 1);
        service.addEvent({
          'id': id,
          'room_id': 'stream_room',
          'category': 'GAMEPLAY',
          'text': 'حدث متدفق $id',
        });
      }
      sw.stop();

      // Exactly half (2000) must be accepted, 2000 rejected
      expect(service.events, hasLength(streamCount ~/ 2));
      expect(notifyCount, equals(streamCount ~/ 2));
      print('      [Performance] Alternating stream ($streamCount events) processed in ${sw.elapsedMilliseconds}ms');
    });

    test('Empty string payload does not throw FormatException', () {
      service.addEvent({
        'id': 991,
        'room_id': 'r_empty',
        'event_type': 'test',
        'payload': '', // empty string
        'text': 'حدث مع حمولة فارغة النص',
      });
      expect(service.events, hasLength(1));
    });

    test('Non-string category/type types (int, bool) do not crash', () {
      service.addEvent({
        'id': 992,
        'category': 12345,
        'text': 'فئة كرقم صحيح',
      });
      service.addEvent({
        'id': 993,
        'type': true,
        'text': 'نوع كقيمة منطقية',
      });
      expect(service.events, hasLength(2));
      // ALL category contains both
      service.selectCategory('ALL');
      expect(service.filteredEvents, hasLength(2));
    });

    test('Pagination: appendOlder appends to end and deduplicates against top events', () {
      service.clear();
      service.addEvent({'id': 10, 'text': 'Newest event'});
      service.addEvent({'id': 20, 'text': 'Latest event'});

      // Latest is at index 0
      expect(service.events.first['id'], equals(20));

      // Append older
      service.appendOlder([
        {'id': 5, 'text': 'Older event 5'},
        {'id': 1, 'text': 'Oldest event 1'},
        {'id': 10, 'text': 'Duplicate of 10 in older page'}, // duplicate!
      ]);

      expect(service.events, hasLength(4));
      expect(service.events.first['id'], equals(20));
      expect(service.events.last['id'], equals(1));
    });
  });

  // =========================================================================
  // GROUP 4: ActivityLogWidget Source Parity & Accessibility Verification
  // =========================================================================
  group('ActivityLogWidget Desktop Parity & Accessibility', () {
    test('ActivityLogWidget source file contains exact canonical desktop categories and order', () {
      final file = File('lib/views/activity_log_widget.dart');
      expect(file.existsSync(), isTrue, reason: 'activity_log_widget.dart must exist');

      final content = file.readAsStringSync();

      // Verify all 8 categories exist in activityCategoryOrder
      expect(content.contains("'TABLE_CHAT'"), isTrue);
      expect(content.contains("'PRIVATE_MESSAGES'"), isTrue);
      expect(content.contains("'FRIENDS'"), isTrue);
      expect(content.contains("'GAMEPLAY'"), isTrue);
      expect(content.contains("'ALL'"), isTrue);
      expect(content.contains("'FRIEND_REQUESTS'"), isTrue);
      expect(content.contains("'INVITATIONS'"), isTrue);
      expect(content.contains("'GIFTS'"), isTrue);

      // Verify exact Arabic labels matching client/views/activity_log_widget.py
      expect(content.contains("'TABLE_CHAT': 'دردشة الطاولات'"), isTrue);
      expect(content.contains("'PRIVATE_MESSAGES': 'الرسائل الخاصة'"), isTrue);
      expect(content.contains("'FRIENDS': 'الأصدقاء'"), isTrue);
      expect(content.contains("'GAMEPLAY': 'اللعب'"), isTrue);
      expect(content.contains("'ALL': 'الجميع'"), isTrue);
      expect(content.contains("'FRIEND_REQUESTS': 'طلبات الصداقة'"), isTrue);
      expect(content.contains("'INVITATIONS': 'الدعوات'"), isTrue);
      expect(content.contains("'GIFTS': 'الهدايا'"), isTrue);

      // Verify empty state message
      expect(content.contains("tr('لا توجد أحداث في هذا القسم.')"), isTrue);

      // Verify Arrow Left / Arrow Right accessibility handlers
      expect(content.contains('LogicalKeyboardKey.arrowLeft'), isTrue);
      expect(content.contains('LogicalKeyboardKey.arrowRight'), isTrue);
      expect(content.contains('_moveCategory(-1)'), isTrue);
      expect(content.contains('_moveCategory(1)'), isTrue);
    });

    test('Verification of Arrow Navigation delta clamp model', () {
      const order = [
        'TABLE_CHAT',
        'PRIVATE_MESSAGES',
        'FRIENDS',
        'GAMEPLAY',
        'ALL',
        'FRIEND_REQUESTS',
        'INVITATIONS',
        'GIFTS',
      ];

      String moveCategory(String current, int delta) {
        final idx = order.indexOf(current);
        final newIdx = (idx + delta).clamp(0, order.length - 1);
        return order[newIdx];
      }

      // Start at ALL (index 4)
      expect(moveCategory('ALL', -1), equals('GAMEPLAY'));
      expect(moveCategory('ALL', 1), equals('FRIEND_REQUESTS'));

      // Left boundary (index 0)
      expect(moveCategory('TABLE_CHAT', -1), equals('TABLE_CHAT'));
      expect(moveCategory('TABLE_CHAT', 1), equals('PRIVATE_MESSAGES'));

      // Right boundary (index 7)
      expect(moveCategory('GIFTS', 1), equals('GIFTS'));
      expect(moveCategory('GIFTS', -1), equals('INVITATIONS'));
    });
  });
}
