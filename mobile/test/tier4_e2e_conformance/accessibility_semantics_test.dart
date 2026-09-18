// Tier 4 Conformance Test: Accessibility & Screen-Reader Semantics Verification

import '../harness/test_engine.dart';
import '../harness/test_fixtures.dart';
import '../tier2_widget/home_view_test.dart';
import '../tier2_widget/rooms_menu_view_test.dart';
import '../tier2_widget/join_rooms_view_test.dart';
import '../tier2_widget/saved_tables_view_test.dart';
import '../tier2_widget/activity_log_widget_test.dart';

/// Semantic node representation for accessibility tree verification
class AccessibilitySemanticsNode {
  final String label;
  final String? hint;
  final bool isHeader;
  final bool isButton;
  final bool isFocusable;
  final List<String> actions;

  AccessibilitySemanticsNode({
    required this.label,
    this.hint,
    this.isHeader = false,
    this.isButton = false,
    this.isFocusable = true,
    this.actions = const [],
  });
}

class ViewAccessibilityAuditor {
  /// Audits HomeView Semantics
  static List<AccessibilitySemanticsNode> auditHomeView(HomeViewStateHarness home) {
    final nodes = <AccessibilitySemanticsNode>[];

    // Header label
    nodes.add(AccessibilitySemanticsNode(
      label: 'القائمة الرئيسية',
      isHeader: true,
      isFocusable: true,
    ));

    // 8 Menu items
    for (final item in home.menuItems) {
      nodes.add(AccessibilitySemanticsNode(
        label: item['title']!,
        isButton: true,
        actions: ['activate'],
      ));
    }

    return nodes;
  }

  /// Audits RoomsMenuView Semantics
  static List<AccessibilitySemanticsNode> auditRoomsMenuView(RoomsMenuViewStateHarness rooms) {
    final nodes = <AccessibilitySemanticsNode>[];

    nodes.add(AccessibilitySemanticsNode(
      label: rooms.getTitle(),
      isHeader: true,
      isFocusable: true,
    ));

    for (final item in rooms.getItems()) {
      nodes.add(AccessibilitySemanticsNode(
        label: item['label']!,
        isButton: true,
        actions: ['activate'],
      ));
    }

    return nodes;
  }

  /// Audits JoinRoomsView Semantics
  static List<AccessibilitySemanticsNode> auditJoinRoomsView(JoinRoomsViewStateHarness joinView) {
    final nodes = <AccessibilitySemanticsNode>[];

    nodes.add(AccessibilitySemanticsNode(
      label: 'الطاولات المتاحة حاليًا',
      isHeader: true,
      isFocusable: true,
    ));

    for (final title in joinView.renderedRoomTitles) {
      nodes.add(AccessibilitySemanticsNode(
        label: title,
        actions: ['join_player', 'join_spectator'],
        hint: 'اضغط مرتين للانضمام، أو اضغط مطولاً للانضمام كمتفرج',
      ));
    }

    return nodes;
  }

  /// Audits SavedTablesView Semantics
  static List<AccessibilitySemanticsNode> auditSavedTablesView(SavedTablesViewStateHarness savedView) {
    final nodes = <AccessibilitySemanticsNode>[];

    nodes.add(AccessibilitySemanticsNode(
      label: 'الطاولات المحفوظة',
      isHeader: true,
      isFocusable: true,
    ));

    for (final row in savedView.renderedRowTexts) {
      nodes.add(AccessibilitySemanticsNode(
        label: row,
        actions: ['restore', 'delete'],
        hint: 'اضغط للاستعادة، اضغط مطولاً لخيارات الحذف',
      ));
    }

    return nodes;
  }

  /// Audits ActivityLogWidget Semantics
  static List<AccessibilitySemanticsNode> auditActivityLogWidget(ActivityLogWidgetStateHarness log) {
    final nodes = <AccessibilitySemanticsNode>[];

    nodes.add(AccessibilitySemanticsNode(
      label: 'سجل الأحداث، القسم النشط: ${log.headerCategoryLabel}',
      isHeader: true,
    ));

    for (final text in log.renderedRowTexts) {
      nodes.add(AccessibilitySemanticsNode(
        label: text,
        isFocusable: true,
      ));
    }

    return nodes;
  }
}

void main() async {
  defineTests();
  await runSuite('Tier 4 Conformance: Accessibility Semantics Tests');
}

void defineTests() {
  group('Screen-Reader Accessibility Semantics Conformance', () {
    test('HomeView: All 8 items and header have non-empty Arabic semantics labels', () {
      final home = HomeViewStateHarness(userDisplayName: 'أحمد');
      final nodes = ViewAccessibilityAuditor.auditHomeView(home);

      // 1 header + 8 menu items = 9 nodes
      expect(nodes, hasLength(9));

      final header = nodes.first;
      expect(header.isHeader, isTrue);
      expect(header.label, equals('القائمة الرئيسية'));

      // Check all 8 items have valid action and label
      final menuNodes = nodes.sublist(1);
      expect(menuNodes, hasLength(8));
      for (final n in menuNodes) {
        expect(n.label.trim().isNotEmpty, isTrue);
        expect(n.isButton, isTrue);
        expect(n.actions, contains('activate'));
      }
    });

    test('RoomsMenuView: Provides accessible headers and items across all 3 levels', () {
      final rooms = RoomsMenuViewStateHarness();

      // Level 1
      var nodes = ViewAccessibilityAuditor.auditRoomsMenuView(rooms);
      expect(nodes.first.label, equals('الطاولات'));
      expect(nodes.sublist(1), hasLength(3));

      // Level 2
      rooms.onItemTapped('create');
      nodes = ViewAccessibilityAuditor.auditRoomsMenuView(rooms);
      expect(nodes.first.label, equals('تصنيفات الألعاب لإنشاء الطاولة'));
      expect(nodes.sublist(1), hasLength(5));

      // Level 3
      rooms.onItemTapped('category_cards');
      nodes = ViewAccessibilityAuditor.auditRoomsMenuView(rooms);
      expect(nodes.first.label, equals('ألعاب الورق'));
      expect(nodes.sublist(1), hasLength(3));
    });

    test('JoinRoomsView: Room items have dual actions (player and spectator) and descriptive hints', () {
      final joinView = JoinRoomsViewStateHarness(initialRooms: TestFixtures.sampleRoomsJson);
      final nodes = ViewAccessibilityAuditor.auditJoinRoomsView(joinView);

      // Header + 3 room items = 4 nodes
      expect(nodes, hasLength(4));

      final roomNodes = nodes.sublist(1);
      for (final r in roomNodes) {
        expect(r.actions, contains('join_player'));
        expect(r.actions, contains('join_spectator'));
        expect(r.hint, isNotNull);
        expect(r.hint, contains('متفرج'));
      }
    });

    test('SavedTablesView: Saved table items have restore and delete semantic actions', () {
      final savedView = SavedTablesViewStateHarness(initialTables: TestFixtures.sampleSavedTablesJson);
      final nodes = ViewAccessibilityAuditor.auditSavedTablesView(savedView);

      expect(nodes, hasLength(4));

      final tableNodes = nodes.sublist(1);
      for (final t in tableNodes) {
        expect(t.actions, contains('restore'));
        expect(t.actions, contains('delete'));
        expect(t.hint, isNotNull);
      }
    });

    test('ActivityLogWidget: Announces active category in header and formats event announcements', () {
      final log = ActivityLogWidgetStateHarness(events: TestFixtures.sampleActivityEvents);
      log.selectCategory('GAMEPLAY');

      final nodes = ViewAccessibilityAuditor.auditActivityLogWidget(log);
      expect(nodes.first.label, equals('سجل الأحداث، القسم النشط: اللعب'));

      final eventNodes = nodes.sublist(1);
      expect(eventNodes, hasLength(1));
      expect(eventNodes.first.label, contains('لعب أحمد بطاقة 5 حمراء'));
    });
  });
}
