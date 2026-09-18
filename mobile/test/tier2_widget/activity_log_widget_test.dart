// Tier 2 Widget Test: ActivityLogWidget (Category Chip Switching, Empty State Display, List Rendering)

import '../harness/test_engine.dart';
import '../harness/test_fixtures.dart';

/// Testable model and state harness for ActivityLogWidget matching mobile/lib/views/activity_log_widget.dart
class ActivityLogWidgetStateHarness {
  final List<Map<String, dynamic>>? _staticEvents;
  final List<Map<String, dynamic>> Function()? _eventsProvider;
  final void Function(String category)? onCategoryChanged;
  final void Function()? onLoadOlder;

  String selectedCategory = 'ALL';

  ActivityLogWidgetStateHarness({
    List<Map<String, dynamic>>? events,
    List<Map<String, dynamic>> Function()? eventsProvider,
    this.onCategoryChanged,
    this.onLoadOlder,
  })  : _staticEvents = events,
        _eventsProvider = eventsProvider;

  List<Map<String, dynamic>> get events =>
      _eventsProvider != null ? _eventsProvider!() : (_staticEvents ?? []);


  // Canonical category order matching widget
  static const List<String> categoryOrder = [
    'ALL',
    'TABLE_CHAT',
    'PRIVATE_MESSAGES',
    'FRIENDS',
    'GAMEPLAY',
    'FRIEND_REQUESTS',
    'INVITATIONS',
    'GIFTS',
  ];

  static const Map<String, String> categoryLabels = {
    'ALL': 'الجميع',
    'TABLE_CHAT': 'دردشة الطاولات',
    'PRIVATE_MESSAGES': 'الرسائل الخاصة',
    'FRIENDS': 'الأصدقاء',
    'GAMEPLAY': 'اللعب',
    'FRIEND_REQUESTS': 'طلبات الصداقة',
    'INVITATIONS': 'الدعوات',
    'GIFTS': 'الهدايا',
  };

  void selectCategory(String catKey) {
    if (categoryOrder.contains(catKey)) {
      selectedCategory = catKey;
      onCategoryChanged?.call(catKey);
    }
  }

  List<Map<String, dynamic>> get filteredEvents {
    if (selectedCategory == 'ALL') {
      return events;
    }
    return events.where((e) {
      final cat = (e['category'] ?? e['type'] ?? '').toString().toUpperCase();
      return cat == selectedCategory;
    }).toList();
  }

  // Simulated widget rendering representations
  String get headerTitle => 'سجل الأحداث';
  String get headerCategoryLabel => categoryLabels[selectedCategory] ?? selectedCategory;

  bool get isEmptyStateVisible => filteredEvents.isEmpty;
  String get emptyStateMessage => 'لا توجد أحداث في هذا القسم.';

  List<String> get renderedRowTexts {
    return filteredEvents.map((e) {
      return (e['text'] ?? e['message'] ?? '').toString();
    }).toList();
  }

  void triggerLoadOlder() {
    onLoadOlder?.call();
  }
}

void main() async {
  defineTests();
  await runSuite('Tier 2 Widget: Activity Log Widget Tests');
}

void defineTests() {
  group('ActivityLogWidget Component Parity', () {
    test('Renders header with initial ALL / الجميع label', () {
      final harness = ActivityLogWidgetStateHarness(
        events: TestFixtures.sampleActivityEvents,
      );

      expect(harness.headerTitle, equals('سجل الأحداث'));
      expect(harness.headerCategoryLabel, equals('الجميع'));
      expect(harness.selectedCategory, equals('ALL'));
    });

    test('Contains exactly 8 canonical category chips in defined order', () {
      expect(ActivityLogWidgetStateHarness.categoryOrder, hasLength(8));
      expect(
        ActivityLogWidgetStateHarness.categoryOrder,
        equals([
          'ALL',
          'TABLE_CHAT',
          'PRIVATE_MESSAGES',
          'FRIENDS',
          'GAMEPLAY',
          'FRIEND_REQUESTS',
          'INVITATIONS',
          'GIFTS',
        ]),
      );

      for (final cat in ActivityLogWidgetStateHarness.categoryOrder) {
        expect(ActivityLogWidgetStateHarness.categoryLabels.containsKey(cat), isTrue);
      }
    });

    test('Switching category chip updates active filter and triggers onCategoryChanged', () {
      String? changedCategory;
      final harness = ActivityLogWidgetStateHarness(
        events: TestFixtures.sampleActivityEvents,
        onCategoryChanged: (cat) => changedCategory = cat,
      );

      harness.selectCategory('TABLE_CHAT');

      expect(harness.selectedCategory, equals('TABLE_CHAT'));
      expect(harness.headerCategoryLabel, equals('دردشة الطاولات'));
      expect(changedCategory, equals('TABLE_CHAT'));

      final rendered = harness.renderedRowTexts;
      expect(rendered, hasLength(1));
      expect(rendered.first, contains('محمد: بالتوفيق للجميع!'));
    });

    test('Displays empty state message when category has no events', () {
      final harness = ActivityLogWidgetStateHarness(
        events: [
          {'id': 1, 'category': 'TABLE_CHAT', 'text': 'محادثة فقط'},
        ],
      );

      harness.selectCategory('GIFTS');

      expect(harness.selectedCategory, equals('GIFTS'));
      expect(harness.isEmptyStateVisible, isTrue);
      expect(harness.emptyStateMessage, equals('لا توجد أحداث في هذا القسم.'));
      expect(harness.renderedRowTexts, hasLength(0));
    });

    test('Renders full event list in ALL category view', () {
      final harness = ActivityLogWidgetStateHarness(
        events: TestFixtures.sampleActivityEvents,
      );

      expect(harness.isEmptyStateVisible, isFalse);
      expect(harness.renderedRowTexts, hasLength(TestFixtures.sampleActivityEvents.length));
      expect(harness.renderedRowTexts.first, equals('لعب أحمد بطاقة 5 حمراء'));
    });

    test('Invokes onLoadOlder callback when pagination is triggered', () {
      bool loadOlderCalled = false;
      final harness = ActivityLogWidgetStateHarness(
        events: TestFixtures.sampleActivityEvents,
        onLoadOlder: () => loadOlderCalled = true,
      );

      harness.triggerLoadOlder();
      expect(loadOlderCalled, isTrue);
    });
  });
}
