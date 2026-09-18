// Self-contained, zero-dependency Test Engine for TableVerse Mobile E2E Test Suite.
// Compatible with both standalone Dart SDK and Flutter test runners.

import 'dart:async';

class TestFailure implements Exception {
  final String message;
  final String? reason;
  TestFailure(this.message, [this.reason]);

  @override
  String toString() {
    if (reason != null && reason!.isNotEmpty) {
      return 'TestFailure: $message (Reason: $reason)';
    }
    return 'TestFailure: $message';
  }
}

class TestCase {
  final String name;
  final String groupName;
  final FutureOr<void> Function() body;
  final List<void Function()> setUps;
  final List<void Function()> tearDowns;

  TestCase({
    required this.name,
    required this.groupName,
    required this.body,
    required this.setUps,
    required this.tearDowns,
  });

  String get fullName => groupName.isEmpty ? name : '$groupName > $name';
}

class TestResult {
  final TestCase test;
  final bool passed;
  final Object? error;
  final StackTrace? stackTrace;
  final Duration duration;

  TestResult({
    required this.test,
    required this.passed,
    this.error,
    this.stackTrace,
    required this.duration,
  });
}

class TestContext {
  static final TestContext instance = TestContext();

  final List<TestCase> tests = [];
  final List<String> _groupStack = [];
  final List<void Function()> _setUps = [];
  final List<void Function()> _tearDowns = [];

  String get currentGroupName => _groupStack.join(' > ');

  void reset() {
    tests.clear();
    _groupStack.clear();
    _setUps.clear();
    _tearDowns.clear();
  }

  void pushGroup(String name) {
    _groupStack.add(name);
  }

  void popGroup() {
    if (_groupStack.isNotEmpty) _groupStack.removeLast();
  }

  void addSetUp(void Function() fn) {
    _setUps.add(fn);
  }

  void addTearDown(void Function() fn) {
    _tearDowns.add(fn);
  }

  void addTest(String name, FutureOr<void> Function() body) {
    tests.add(TestCase(
      name: name,
      groupName: currentGroupName,
      body: body,
      setUps: List.from(_setUps),
      tearDowns: List.from(_tearDowns),
    ));
  }
}

// Global test functions
void group(String name, void Function() body) {
  TestContext.instance.pushGroup(name);
  try {
    body();
  } finally {
    TestContext.instance.popGroup();
  }
}

void test(String name, FutureOr<void> Function() body) {
  TestContext.instance.addTest(name, body);
}

void setUp(void Function() body) {
  TestContext.instance.addSetUp(body);
}

void tearDown(void Function() body) {
  TestContext.instance.addTearDown(body);
}

// Matchers and assertions
void expect(dynamic actual, dynamic matcher, {String? reason}) {
  if (matcher is bool) {
    if (actual != matcher) {
      throw TestFailure('Expected $matcher but got $actual', reason);
    }
  } else if (matcher is _Matcher) {
    if (!matcher.matches(actual)) {
      throw TestFailure(matcher.describeMismatch(actual), reason);
    }
  } else {
    // Exact value match
    if (actual != matcher) {
      throw TestFailure('Expected: $matcher\n  Actual: $actual', reason);
    }
  }
}

abstract class _Matcher {
  bool matches(dynamic item);
  String describeMismatch(dynamic item);
}

class _EqualsMatcher extends _Matcher {
  final dynamic expected;
  _EqualsMatcher(this.expected);

  @override
  bool matches(dynamic item) {
    if (expected is List && item is List) {
      if (expected.length != item.length) return false;
      for (int i = 0; i < expected.length; i++) {
        if (expected[i] != item[i]) return false;
      }
      return true;
    }
    if (expected is Map && item is Map) {
      if (expected.length != item.length) return false;
      for (final key in expected.keys) {
        if (!item.containsKey(key) || item[key] != expected[key]) return false;
      }
      return true;
    }
    return item == expected;
  }

  @override
  String describeMismatch(dynamic item) => 'Expected: $expected\n  Actual: $item';
}

class _ContainsMatcher extends _Matcher {
  final dynamic expected;
  _ContainsMatcher(this.expected);

  @override
  bool matches(dynamic item) {
    if (item is String && expected is String) {
      return item.contains(expected);
    }
    if (item is Iterable) {
      return item.contains(expected);
    }
    if (item is Map) {
      return item.containsKey(expected);
    }
    return false;
  }

  @override
  String describeMismatch(dynamic item) => 'Expected $item to contain $expected';
}

class _HasLengthMatcher extends _Matcher {
  final int expectedLength;
  _HasLengthMatcher(this.expectedLength);

  @override
  bool matches(dynamic item) {
    if (item is Iterable) return item.length == expectedLength;
    if (item is Map) return item.length == expectedLength;
    if (item is String) return item.length == expectedLength;
    return false;
  }

  @override
  String describeMismatch(dynamic item) =>
      'Expected length $expectedLength but item had length ${(item as dynamic).length}';
}

class _StartsWithMatcher extends _Matcher {
  final String prefix;
  _StartsWithMatcher(this.prefix);

  @override
  bool matches(dynamic item) => item is String && item.startsWith(prefix);

  @override
  String describeMismatch(dynamic item) => 'Expected "$item" to start with "$prefix"';
}

class _EndsWithMatcher extends _Matcher {
  final String suffix;
  _EndsWithMatcher(this.suffix);

  @override
  bool matches(dynamic item) => item is String && item.endsWith(suffix);

  @override
  String describeMismatch(dynamic item) => 'Expected "$item" to end with "$suffix"';
}

class _TypeMatcher<T> extends _Matcher {
  @override
  bool matches(dynamic item) => item is T;

  @override
  String describeMismatch(dynamic item) => 'Expected instance of $T but got ${item.runtimeType}';
}

class _ThrowsMatcher extends _Matcher {
  final Type? expectedType;
  _ThrowsMatcher([this.expectedType]);

  @override
  bool matches(dynamic item) {
    if (item is! Function) return false;
    try {
      item();
      return false; // Did not throw
    } catch (e) {
      if (expectedType != null) {
        return e.runtimeType == expectedType || e is Exception;
      }
      return true;
    }
  }

  @override
  String describeMismatch(dynamic item) => 'Expected function to throw ${expectedType ?? 'an exception'}';
}

class _AnyElementMatcher extends _Matcher {
  final bool Function(dynamic) predicate;
  final String description;
  _AnyElementMatcher(this.predicate, [this.description = 'predicate']);

  @override
  bool matches(dynamic item) {
    if (item is Iterable) {
      return item.any(predicate);
    }
    return false;
  }

  @override
  String describeMismatch(dynamic item) => 'No element matched $description in $item';
}

// Matcher factories
_Matcher equals(dynamic expected) => _EqualsMatcher(expected);
_Matcher contains(dynamic expected) => _ContainsMatcher(expected);
_Matcher hasLength(int length) => _HasLengthMatcher(length);
_Matcher startsWith(String prefix) => _StartsWithMatcher(prefix);
_Matcher endsWith(String suffix) => _EndsWithMatcher(suffix);
_Matcher isA<T>() => _TypeMatcher<T>();
_Matcher throwsA([Type? type]) => _ThrowsMatcher(type);
_Matcher anyElement(bool Function(dynamic) predicate, [String description = 'predicate']) =>
    _AnyElementMatcher(predicate, description);

const bool isTrue = true;
const bool isFalse = false;
final _Matcher isNull = _EqualsMatcher(null);
final _Matcher isNotNull = _TypeMatcher<Object>();

// Test Runner
class TestSuiteRunner {
  final String suiteName;
  TestSuiteRunner(this.suiteName);

  Future<List<TestResult>> run() async {
    final tests = List<TestCase>.from(TestContext.instance.tests);
    final results = <TestResult>[];

    print('\n============================================================');
    print(' RUNNING SUITE: $suiteName (${tests.length} tests)');
    print('============================================================');

    for (final testCase in tests) {
      final sw = Stopwatch()..start();
      bool passed = false;
      Object? error;
      StackTrace? st;

      try {
        // Run setUps
        for (final s in testCase.setUps) {
          s();
        }

        // Run body
        final res = testCase.body();
        if (res is Future) {
          await res;
        }

        // Run tearDowns
        for (final t in testCase.tearDowns) {
          t();
        }
        passed = true;
      } catch (e, stack) {
        passed = false;
        error = e;
        st = stack;
      } finally {
        sw.stop();
      }

      final result = TestResult(
        test: testCase,
        passed: passed,
        error: error,
        stackTrace: st,
        duration: sw.elapsed,
      );
      results.add(result);

      if (passed) {
        print('  [PASS] ${testCase.fullName} (${sw.elapsedMilliseconds}ms)');
      } else {
        print('  [FAIL] ${testCase.fullName} (${sw.elapsedMilliseconds}ms)');
        print('         Error: $error');
      }
    }

    return results;
  }
}

Future<bool> runSuite(String suiteName) async {
  final runner = TestSuiteRunner(suiteName);
  final results = await runner.run();
  final failures = results.where((r) => !r.passed).length;
  final passed = results.where((r) => r.passed).length;
  print('------------------------------------------------------------');
  print(' SUITE SUMMARY: $passed Passed, $failures Failed');
  print('------------------------------------------------------------');
  return failures == 0;
}

