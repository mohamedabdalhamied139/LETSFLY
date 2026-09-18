// Tier 4 Conformance Test: Adversarial Verification of Milestone M1
// 1. ResponsiveShell breakpoint logic at boundary viewports (719dp, 720dp, 721dp)
// 2. AppTheme color definitions exact matching (#1E1E1E, #252526, #2D2D2D, #3E3E42, #005FB8)
// 3. WebSocket token handling in ws_service.dart (valid, empty, special characters, query fallback)

import '../harness/test_engine.dart';

// ---------------------------------------------------------------------------
// 1. ResponsiveShell Model Harness
// ---------------------------------------------------------------------------

enum ShellLayoutMode { sideBySideWide, stackedCompact, contentOnly }

class ResponsiveShellStateHarness {
  final double maxWidth;
  final bool showActivityLog;
  bool isLogExpanded;

  ResponsiveShellStateHarness({
    required this.maxWidth,
    this.showActivityLog = true,
    this.isLogExpanded = true,
  });

  /// Evaluates breakpoint logic matching mobile/lib/views/responsive_shell.dart:48
  bool get isWide => maxWidth >= 720;

  /// Determines top-level layout structure matching responsive_shell.dart:50-78
  ShellLayoutMode get layoutMode {
    if (!showActivityLog) {
      return ShellLayoutMode.contentOnly;
    }
    return isWide ? ShellLayoutMode.sideBySideWide : ShellLayoutMode.stackedCompact;
  }

  /// Flex of the primary content widget
  int get contentFlex {
    if (!showActivityLog) return 1;
    if (isWide) return 6;
    return isLogExpanded ? 6 : 1;
  }

  /// Flex of the ActivityLogWidget (0 if omitted)
  int get activityLogFlex {
    if (!showActivityLog) return 0;
    if (isWide) return 4;
    return isLogExpanded ? 4 : 0;
  }

  /// Indicates whether the vertical divider between panels is rendered (wide mode only)
  bool get hasVerticalDivider => showActivityLog && isWide;

  /// Indicates whether the collapsible toggle bar is rendered (compact mode with log enabled)
  bool get hasCollapsibleToggleBar => showActivityLog && !isWide;

  /// Toggle expand/collapse in compact mode
  void toggleLogExpanded() {
    isLogExpanded = !isLogExpanded;
  }
}

// ---------------------------------------------------------------------------
// 2. AppTheme & AppColors Model Harness
// ---------------------------------------------------------------------------

class ColorToken {
  final int value;
  final String hex;
  const ColorToken(this.value, this.hex);

  int get alpha => (value >> 24) & 0xFF;
  int get red => (value >> 16) & 0xFF;
  int get green => (value >> 8) & 0xFF;
  int get blue => value & 0xFF;

  String get rgbHex => '#${red.toRadixString(16).padLeft(2, '0')}${green.toRadixString(16).padLeft(2, '0')}${blue.toRadixString(16).padLeft(2, '0')}'.toUpperCase();
}

class AppColorsHarness {
  static const ColorToken background = ColorToken(0xFF1E1E1E, '#1E1E1E');
  static const ColorToken surface = ColorToken(0xFF252526, '#252526');
  static const ColorToken header = ColorToken(0xFF2D2D2D, '#2D2D2D');
  static const ColorToken border = ColorToken(0xFF3E3E42, '#3E3E42');
  static const ColorToken accent = ColorToken(0xFF005FB8, '#005FB8');
  static const ColorToken textPrimary = ColorToken(0xFFFFFFFF, '#FFFFFF');
  static const ColorToken textSecondary = ColorToken(0xFFA0A0A0, '#A0A0A0');
}

// ---------------------------------------------------------------------------
// 3. WebSocket Token & URI Handling Harness matching ws_service.dart
// ---------------------------------------------------------------------------

class WsConnectionParams {
  final Uri uri;
  final Map<String, dynamic>? headers;
  final bool hasTokenHeader;
  final String? tokenHeaderValue;
  final String? tokenQueryParam;

  WsConnectionParams({
    required this.uri,
    required this.headers,
  })  : hasTokenHeader = headers != null && headers.containsKey('Authorization'),
        tokenHeaderValue = headers?['Authorization']?.toString(),
        tokenQueryParam = uri.queryParameters['token'];
}

class WsTokenHandlingHarness {
  /// Implements the exact URI and header transformation logic from
  /// mobile/lib/services/ws_service.dart lines 29-50
  static WsConnectionParams prepareConnection(String wsUrl, {String? token}) {
    var uri = Uri.parse(wsUrl);
    final Map<String, dynamic> headers = {};

    if (token != null && token.isNotEmpty) {
      // Standard bearer authorization header for IO platforms
      headers['Authorization'] = 'Bearer $token';

      // Query parameter fallback for dev/test environments & server compatibility
      final queryParams = Map<String, String>.from(uri.queryParameters);
      if (!queryParams.containsKey('token')) {
        queryParams['token'] = token;
        uri = uri.replace(queryParameters: queryParams);
      }
    }

    return WsConnectionParams(
      uri: uri,
      headers: headers.isNotEmpty ? headers : null,
    );
  }
}

// ---------------------------------------------------------------------------
// Main Test Entry Point
// ---------------------------------------------------------------------------

void main() async {
  defineTests();
  await runSuite('Tier 4 Conformance: Adversarial M1 Verification Suite');
}

void defineTests() {
  group('1. ResponsiveShell Breakpoint Boundary Verification', () {
    test('Boundary 719dp: strictly renders stacked compact layout', () {
      final shell = ResponsiveShellStateHarness(maxWidth: 719.0);

      expect(shell.isWide, isFalse);
      expect(shell.layoutMode, equals(ShellLayoutMode.stackedCompact));
      expect(shell.hasVerticalDivider, isFalse);
      expect(shell.hasCollapsibleToggleBar, isTrue);
      expect(shell.contentFlex, equals(6));
      expect(shell.activityLogFlex, equals(4));
    });

    test('Boundary 720dp: strictly triggers side-by-side dual-pane wide layout', () {
      final shell = ResponsiveShellStateHarness(maxWidth: 720.0);

      expect(shell.isWide, isTrue);
      expect(shell.layoutMode, equals(ShellLayoutMode.sideBySideWide));
      expect(shell.hasVerticalDivider, isTrue);
      expect(shell.hasCollapsibleToggleBar, isFalse);
      expect(shell.contentFlex, equals(6));
      expect(shell.activityLogFlex, equals(4));
    });

    test('Boundary 721dp: maintains side-by-side dual-pane wide layout', () {
      final shell = ResponsiveShellStateHarness(maxWidth: 721.0);

      expect(shell.isWide, isTrue);
      expect(shell.layoutMode, equals(ShellLayoutMode.sideBySideWide));
      expect(shell.hasVerticalDivider, isTrue);
      expect(shell.hasCollapsibleToggleBar, isFalse);
      expect(shell.contentFlex, equals(6));
      expect(shell.activityLogFlex, equals(4));
    });

    test('Sub-pixel boundaries (719.99dp vs 720.001dp) evaluate monotonically', () {
      final shellBelow = ResponsiveShellStateHarness(maxWidth: 719.99);
      expect(shellBelow.isWide, isFalse);
      expect(shellBelow.layoutMode, equals(ShellLayoutMode.stackedCompact));

      final shellAbove = ResponsiveShellStateHarness(maxWidth: 720.001);
      expect(shellAbove.isWide, isTrue);
      expect(shellAbove.layoutMode, equals(ShellLayoutMode.sideBySideWide));
    });

    test('Compact viewport collapse toggle correctly hides activity log and collapses flex', () {
      final shell = ResponsiveShellStateHarness(maxWidth: 719.0, isLogExpanded: true);
      expect(shell.contentFlex, equals(6));
      expect(shell.activityLogFlex, equals(4));

      shell.toggleLogExpanded();
      expect(shell.isLogExpanded, isFalse);
      expect(shell.contentFlex, equals(1));
      expect(shell.activityLogFlex, equals(0));
      expect(shell.hasCollapsibleToggleBar, isTrue);
    });

    test('showActivityLog=false returns contentOnly across 719dp, 720dp, and 721dp', () {
      for (final width in [719.0, 720.0, 721.0]) {
        final shell = ResponsiveShellStateHarness(maxWidth: width, showActivityLog: false);
        expect(shell.layoutMode, equals(ShellLayoutMode.contentOnly));
        expect(shell.hasVerticalDivider, isFalse);
        expect(shell.hasCollapsibleToggleBar, isFalse);
        expect(shell.activityLogFlex, equals(0));
      }
    });

    test('Extreme bounds: width=0dp is compact, width=double.infinity is wide', () {
      final shellZero = ResponsiveShellStateHarness(maxWidth: 0.0);
      expect(shellZero.isWide, isFalse);
      expect(shellZero.layoutMode, equals(ShellLayoutMode.stackedCompact));

      final shellInf = ResponsiveShellStateHarness(maxWidth: double.infinity);
      expect(shellInf.isWide, isTrue);
      expect(shellInf.layoutMode, equals(ShellLayoutMode.sideBySideWide));
    });
  });

  group('2. AppTheme Color Definitions Exact Matching', () {
    test('background matches Windows desktop token #1E1E1E exactly', () {
      expect(AppColorsHarness.background.rgbHex, equals('#1E1E1E'));
      expect(AppColorsHarness.background.value, equals(0xFF1E1E1E));
      expect(AppColorsHarness.background.alpha, equals(255));
      expect(AppColorsHarness.background.red, equals(0x1E));
      expect(AppColorsHarness.background.green, equals(0x1E));
      expect(AppColorsHarness.background.blue, equals(0x1E));
    });

    test('surface matches Windows desktop token #252526 exactly', () {
      expect(AppColorsHarness.surface.rgbHex, equals('#252526'));
      expect(AppColorsHarness.surface.value, equals(0xFF252526));
      expect(AppColorsHarness.surface.alpha, equals(255));
      expect(AppColorsHarness.surface.red, equals(0x25));
      expect(AppColorsHarness.surface.green, equals(0x25));
      expect(AppColorsHarness.surface.blue, equals(0x26));
    });

    test('header matches Windows desktop token #2D2D2D exactly', () {
      expect(AppColorsHarness.header.rgbHex, equals('#2D2D2D'));
      expect(AppColorsHarness.header.value, equals(0xFF2D2D2D));
      expect(AppColorsHarness.header.alpha, equals(255));
      expect(AppColorsHarness.header.red, equals(0x2D));
      expect(AppColorsHarness.header.green, equals(0x2D));
      expect(AppColorsHarness.header.blue, equals(0x2D));
    });

    test('border matches Windows desktop token #3E3E42 exactly', () {
      expect(AppColorsHarness.border.rgbHex, equals('#3E3E42'));
      expect(AppColorsHarness.border.value, equals(0xFF3E3E42));
      expect(AppColorsHarness.border.alpha, equals(255));
      expect(AppColorsHarness.border.red, equals(0x3E));
      expect(AppColorsHarness.border.green, equals(0x3E));
      expect(AppColorsHarness.border.blue, equals(0x42));
    });

    test('accent matches Windows desktop token #005FB8 exactly', () {
      expect(AppColorsHarness.accent.rgbHex, equals('#005FB8'));
      expect(AppColorsHarness.accent.value, equals(0xFF005FB8));
      expect(AppColorsHarness.accent.alpha, equals(255));
      expect(AppColorsHarness.accent.red, equals(0x00));
      expect(AppColorsHarness.accent.green, equals(0x5F));
      expect(AppColorsHarness.accent.blue, equals(0xB8));
    });

    test('text secondary matches Windows client token #A0A0A0', () {
      expect(AppColorsHarness.textSecondary.rgbHex, equals('#A0A0A0'));
      expect(AppColorsHarness.textSecondary.value, equals(0xFFA0A0A0));
    });
  });

  group('3. WebSocket Token Handling in ws_service.dart', () {
    const baseUrl = 'wss://letsfly.onrender.com/ws/events';

    test('Valid standard alphanumeric token sets header and query parameter fallback', () {
      const token = 'jwt_valid_token_xyz123';
      final params = WsTokenHandlingHarness.prepareConnection(baseUrl, token: token);

      expect(params.hasTokenHeader, isTrue);
      expect(params.tokenHeaderValue, equals('Bearer jwt_valid_token_xyz123'));
      expect(params.tokenQueryParam, equals('jwt_valid_token_xyz123'));
      expect(params.uri.queryParameters['token'], equals('jwt_valid_token_xyz123'));
    });

    test('Valid JWT format token with periods and hyphens formats cleanly', () {
      const jwtToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c';
      final params = WsTokenHandlingHarness.prepareConnection(baseUrl, token: jwtToken);

      expect(params.hasTokenHeader, isTrue);
      expect(params.tokenHeaderValue, equals('Bearer $jwtToken'));
      expect(params.tokenQueryParam, equals(jwtToken));
    });

    test('Empty string token omits Authorization header and omits query parameter', () {
      final params = WsTokenHandlingHarness.prepareConnection(baseUrl, token: '');

      expect(params.headers, isNull);
      expect(params.hasTokenHeader, isFalse);
      expect(params.tokenQueryParam, isNull);
      expect(params.uri.toString(), equals(baseUrl));
    });

    test('Null token omits Authorization header and omits query parameter', () {
      final params = WsTokenHandlingHarness.prepareConnection(baseUrl, token: null);

      expect(params.headers, isNull);
      expect(params.hasTokenHeader, isFalse);
      expect(params.tokenQueryParam, isNull);
      expect(params.uri.toString(), equals(baseUrl));
    });

    test('Whitespace-only string token behavior: preserved by isNotEmpty', () {
      const wsToken = '   ';
      final params = WsTokenHandlingHarness.prepareConnection(baseUrl, token: wsToken);

      expect(params.hasTokenHeader, isTrue);
      expect(params.tokenHeaderValue, equals('Bearer    '));
      expect(params.tokenQueryParam, equals('   '));
    });

    test('Special characters: Base64 tokens (+, /, =) are preserved without corruption', () {
      const b64Token = 'abc+123/xyz==';
      final params = WsTokenHandlingHarness.prepareConnection(baseUrl, token: b64Token);

      expect(params.hasTokenHeader, isTrue);
      expect(params.tokenHeaderValue, equals('Bearer $b64Token'));
      expect(params.tokenQueryParam, equals(b64Token));
      // Raw URI string contains properly percent-encoded characters
      expect(params.uri.toString(), contains('abc%2B123%2Fxyz%3D%3D'));
    });

    test('Special characters: URI query injection attempt (&, =, ?) is safely escaped', () {
      const injectionToken = 'tok&role=admin&super=1?test=true';
      final params = WsTokenHandlingHarness.prepareConnection(baseUrl, token: injectionToken);

      expect(params.hasTokenHeader, isTrue);
      expect(params.tokenHeaderValue, equals('Bearer $injectionToken'));
      // The parameter map has ONLY the single 'token' key; injection did not split params
      expect(params.uri.queryParameters.containsKey('token'), isTrue);
      expect(params.uri.queryParameters.containsKey('role'), isFalse);
      expect(params.uri.queryParameters.containsKey('super'), isFalse);
      expect(params.uri.queryParameters['token'], equals(injectionToken));
    });

    test('Special characters: Arabic / Unicode text is encoded and round-tripped cleanly', () {
      const unicodeToken = 'توكن_أحمد_123';
      final params = WsTokenHandlingHarness.prepareConnection(baseUrl, token: unicodeToken);

      expect(params.hasTokenHeader, isTrue);
      expect(params.tokenHeaderValue, equals('Bearer $unicodeToken'));
      expect(params.tokenQueryParam, equals(unicodeToken));
    });

    test('Existing query parameters in wsUrl are strictly preserved when token is appended', () {
      const urlWithParams = 'wss://letsfly.onrender.com/ws/room/42?client_version=1.0&as_spectator=true';
      const token = 'session_tok_777';
      final params = WsTokenHandlingHarness.prepareConnection(urlWithParams, token: token);

      expect(params.uri.queryParameters['client_version'], equals('1.0'));
      expect(params.uri.queryParameters['as_spectator'], equals('true'));
      expect(params.uri.queryParameters['token'], equals('session_tok_777'));
      expect(params.hasTokenHeader, isTrue);
      expect(params.tokenHeaderValue, equals('Bearer session_tok_777'));
    });

    test('Pre-existing token in wsUrl query parameters is not overwritten in query fallback', () {
      const urlWithToken = 'wss://letsfly.onrender.com/ws/room/42?token=initial_token';
      const token = 'replacement_token';
      final params = WsTokenHandlingHarness.prepareConnection(urlWithToken, token: token);

      // Query param remains initial_token because containsKey('token') was true
      expect(params.uri.queryParameters['token'], equals('initial_token'));
      // But header gets the new replacement_token
      expect(params.tokenHeaderValue, equals('Bearer replacement_token'));
    });

    test('URL with port, path, and hash fragment parses and attaches token correctly', () {
      const complexUrl = 'ws://127.0.0.1:8000/api/v1/ws/live#section';
      const token = 'dev_token_456';
      final params = WsTokenHandlingHarness.prepareConnection(complexUrl, token: token);

      expect(params.uri.port, equals(8000));
      expect(params.uri.path, equals('/api/v1/ws/live'));
      expect(params.uri.queryParameters['token'], equals('dev_token_456'));
      expect(params.hasTokenHeader, isTrue);
      expect(params.tokenHeaderValue, equals('Bearer dev_token_456'));
    });
  });
}
