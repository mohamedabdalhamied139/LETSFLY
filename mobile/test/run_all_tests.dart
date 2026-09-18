// Master Test Runner for TableVerse / LETSFLY Mobile E2E Test Suite (Tiers 1-4)
// Can be executed directly via:
//   dart run test/run_all_tests.dart

import 'dart:io';
import 'harness/test_engine.dart';

// Tier 1: Unit
import 'tier1_unit/models_test.dart' as models_test;
import 'tier1_unit/localization_test.dart' as localization_test;
import 'tier1_unit/auth_storage_test.dart' as auth_storage_test;
import 'tier1_unit/activity_service_test.dart' as activity_service_test;

// Tier 2: Widget
import 'tier2_widget/activity_log_widget_test.dart' as activity_log_widget_test;
import 'tier2_widget/home_view_test.dart' as home_view_test;
import 'tier2_widget/rooms_menu_view_test.dart' as rooms_menu_view_test;
import 'tier2_widget/join_rooms_view_test.dart' as join_rooms_view_test;
import 'tier2_widget/saved_tables_view_test.dart' as saved_tables_view_test;

// Tier 3: Integration
import 'tier3_integration/auth_flow_test.dart' as auth_flow_test;
import 'tier3_integration/rooms_navigation_flow_test.dart' as rooms_navigation_flow_test;
import 'tier3_integration/synchronized_log_test.dart' as synchronized_log_test;
import 'tier3_integration/game_adapters_and_gestures_test.dart' as game_adapters_and_gestures_test;

// Tier 4: E2E Conformance
import 'tier4_e2e_conformance/socket_auth_conformance_test.dart' as socket_auth_conformance_test;
import 'tier4_e2e_conformance/saved_table_lifecycle_test.dart' as saved_table_lifecycle_test;
import 'tier4_e2e_conformance/accessibility_semantics_test.dart' as accessibility_semantics_test;

// Tier 5: Adversarial Stress & Hardening
import 'tier5_adversarial_stress_test.dart' as tier5_adversarial_stress_test;

class SuiteInfo {
  final String tier;
  final String name;
  final void Function() define;

  SuiteInfo(this.tier, this.name, this.define);
}

void main() async {
  final stopwatch = Stopwatch()..start();

  final suites = <SuiteInfo>[
    // Tier 1: Unit
    SuiteInfo('Tier 1', 'Models (User, RoomSummary, SavedTable)', models_test.defineTests),
    SuiteInfo('Tier 1', 'Localization (Lookup, Params, Fallback)', localization_test.defineTests),
    SuiteInfo('Tier 1', 'Auth Storage & Multi-Account', auth_storage_test.defineTests),
    SuiteInfo('Tier 1', 'ActivityLogService & Deduplication', activity_service_test.defineTests),

    // Tier 2: Widget
    SuiteInfo('Tier 2', 'ActivityLogWidget Parity', activity_log_widget_test.defineTests),
    SuiteInfo('Tier 2', 'HomeView 8 Canonical Menu Items', home_view_test.defineTests),
    SuiteInfo('Tier 2', 'RoomsMenuView 3-Level Hierarchy', rooms_menu_view_test.defineTests),
    SuiteInfo('Tier 2', 'JoinRoomsView & Dual-Join Actions', join_rooms_view_test.defineTests),
    SuiteInfo('Tier 2', 'SavedTablesView Formatting & Actions', saved_tables_view_test.defineTests),

    // Tier 3: Integration
    SuiteInfo('Tier 3', 'Authentication Flow Integration', auth_flow_test.defineTests),
    SuiteInfo('Tier 3', 'Rooms Navigation Flow Integration', rooms_navigation_flow_test.defineTests),
    SuiteInfo('Tier 3', 'Cross-Screen Synchronized Log', synchronized_log_test.defineTests),
    SuiteInfo('Tier 3', 'Game Adapters, Gestures & Engine Integration', game_adapters_and_gestures_test.defineTests),

    // Tier 4: E2E Conformance
    SuiteInfo('Tier 4', 'WebSocket Auth Protocol Conformance', socket_auth_conformance_test.defineTests),
    SuiteInfo('Tier 4', 'Saved Table Full Lifecycle', saved_table_lifecycle_test.defineTests),
    SuiteInfo('Tier 4', 'Screen-Reader Accessibility Semantics', accessibility_semantics_test.defineTests),

    // Tier 5: Adversarial Stress & Hardening
    SuiteInfo('Tier 5', 'Adversarial Verification & Stress Hardening', tier5_adversarial_stress_test.defineTests),
  ];

  print('========================================================================');
  print(' TABLEVERSE MOBILE E2E TEST RUNNER — 5 TIERS (17 SUITES)');
  print(' Target: 100% Behavioral & Architectural Parity with Windows Desktop');
  print('========================================================================\n');

  int grandTotalTests = 0;
  int grandPassedTests = 0;
  int grandFailedTests = 0;
  final suiteSummaries = <Map<String, dynamic>>[];

  for (final suite in suites) {
    TestContext.instance.reset();
    suite.define();

    final runner = TestSuiteRunner('${suite.tier} | ${suite.name}');
    final results = await runner.run();

    final passed = results.where((r) => r.passed).length;
    final failed = results.where((r) => !r.passed).length;

    grandTotalTests += results.length;
    grandPassedTests += passed;
    grandFailedTests += failed;

    suiteSummaries.add({
      'tier': suite.tier,
      'name': suite.name,
      'total': results.length,
      'passed': passed,
      'failed': failed,
      'ok': failed == 0,
    });
  }

  stopwatch.stop();

  // Print Grand Summary Table
  print('\n\n');
  print('========================================================================');
  print('                    COMPREHENSIVE TEST SUITE REPORT                     ');
  print('========================================================================');
  print(' Tier   | Suite Name                              | Tests | Pass | Fail | Status');
  print('--------+-----------------------------------------+-------+------+------+-------');
  for (final s in suiteSummaries) {
    final tierStr = s['tier'].toString().padRight(6);
    final nameStr = s['name'].toString().padRight(39);
    final totalStr = s['total'].toString().padLeft(5);
    final passStr = s['passed'].toString().padLeft(4);
    final failStr = s['failed'].toString().padLeft(4);
    final statusStr = (s['ok'] as bool) ? '  PASS ' : ' [FAIL]';
    print(' $tierStr | $nameStr | $totalStr | $passStr | $failStr | $statusStr');
  }
  print('--------+-----------------------------------------+-------+------+------+-------');
  print(' GRAND TOTAL: $grandTotalTests Tests across ${suites.length} Suites in ${stopwatch.elapsedMilliseconds}ms');
  print(' PASSED:      $grandPassedTests / $grandTotalTests');
  print(' FAILED:      $grandFailedTests / $grandTotalTests');
  print(' VERDICT:     ${grandFailedTests == 0 ? "SUCCESS — 100% PASS RATE" : "FAILURE — DEFECTS FOUND"}');
  print('========================================================================\n');

  if (grandFailedTests > 0) {
    exit(1);
  } else {
    exit(0);
  }
}
