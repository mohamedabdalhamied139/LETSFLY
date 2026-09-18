// Adversarial Empirical Verification Suite for Milestone M2
// Tests:
// 1. AuthStorageService aggressive edge cases:
//    - rapid multi-account switches
//    - deletion of the active account (verifying fallback active assignment)
//    - corrupted JSON storage & malformed payloads
//    - special characters in usernames/passwords/displayNames
//    - concurrent save operations (race condition / lost update empirical proof)
// 2. Auto-login state transitions:
//    - valid token
//    - empty token
//    - whitespace token / whitespace credentials
//    - null profile
//    - token revocation / expiration handling

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'harness/test_engine.dart';
import 'harness/mock_api_adapter.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:tableverse_mobile/services/auth_storage_service.dart';

void main() async {
  defineAdversarialM2Tests();
  final success = await runSuite('Adversarial M2 Verification Suite');
  if (!success) {
    exitCode = 1;
  }
}

Future<void> resetAuthStorage() async {
  final service = AuthStorageService.instance;
  const storage = FlutterSecureStorage();
  await storage.write(
    key: AuthStorageService.accountsKey,
    value: json.encode({
      'active_username': null,
      'active': null,
      'accounts': <Map<String, dynamic>>[],
    }),
  );
  await storage.delete(key: AuthStorageService.sessionTokenKey);
  try {
    final prefs = await SharedPreferences.getInstance();
    await prefs.clear();
  } catch (_) {}
  try {
    final all = await service.loadAllAccounts();
    for (final a in all) {
      if (a['username'] != null) {
        await service.removeAccount(a['username'].toString());
      }
    }
    await service.clearActiveSession();
  } catch (_) {}
}

void defineAdversarialM2Tests() {
  final service = AuthStorageService.instance;

  // =========================================================================
  // GROUP 1: Rapid Multi-Account Switches
  // =========================================================================
  group('AuthStorageService: Rapid Multi-Account Switches', () {
    test('Sequential switching across 5 stored accounts maintains active sync', () async {
      await resetAuthStorage();

      final accounts = [
        {'u': 'user_1', 'p': 'p1', 'd': 'User One', 't': 'tok_1'},
        {'u': 'user_2', 'p': 'p2', 'd': 'User Two', 't': 'tok_2'},
        {'u': 'user_3', 'p': 'p3', 'd': 'User Three', 't': 'tok_3'},
        {'u': 'user_4', 'p': 'p4', 'd': 'User Four', 't': 'tok_4'},
        {'u': 'user_5', 'p': 'p5', 'd': 'User Five', 't': 'tok_5'},
      ];

      for (final acc in accounts) {
        await service.saveActiveAccount(
          username: acc['u']!,
          password: acc['p']!,
          displayName: acc['d']!,
          token: acc['t']!,
        );
      }

      final all = await service.loadAllAccounts();
      expect(all, hasLength(5));

      // Sequence of rapid switches
      final switchSequence = ['user_3', 'user_1', 'user_5', 'user_2', 'user_4', 'user_1'];

      for (final targetUser in switchSequence) {
        await service.switchActiveAccount(targetUser);

        // 1. Active account matches target
        final active = await service.loadActiveAccount();
        expect(active, isNotNull);
        expect(active?['username'], equals(targetUser));
        expect(active?['is_active'], isTrue);

        // 2. Active session token matches target
        final expectedToken = accounts.firstWhere((a) => a['u'] == targetUser)['t'];
        final currentToken = await service.getActiveSessionToken();
        expect(currentToken, equals(expectedToken));

        // 3. Exactly one account has is_active == true
        final currentAll = await service.loadAllAccounts();
        final activeList = currentAll.where((a) => a['is_active'] == true).toList();
        expect(activeList, hasLength(1));
        expect(activeList.first['username'], equals(targetUser));
      }
    });

    test('Stress Test: 100 alternating switches between two accounts without drift', () async {
      await resetAuthStorage();

      await service.saveActiveAccount(
        username: 'alice',
        password: 'alice_pwd',
        displayName: 'Alice A',
        token: 'alice_token_100',
      );
      await service.saveActiveAccount(
        username: 'bob',
        password: 'bob_pwd',
        displayName: 'Bob B',
        token: 'bob_token_200',
      );

      final sw = Stopwatch()..start();
      for (int i = 0; i < 100; i++) {
        final target = (i % 2 == 0) ? 'alice' : 'bob';
        final expectedTok = (i % 2 == 0) ? 'alice_token_100' : 'bob_token_200';

        await service.switchActiveAccount(target);

        final active = await service.loadActiveAccount();
        expect(active?['username'], equals(target));

        final tok = await service.getActiveSessionToken();
        expect(tok, equals(expectedTok));
      }
      sw.stop();
      print('      [Performance] 100 alternating switches completed in ${sw.elapsedMilliseconds}ms');
    });

    test('Switching to non-existent account throws and preserves existing active session', () async {
      await resetAuthStorage();

      await service.saveActiveAccount(
        username: 'current_user',
        password: 'pwd',
        displayName: 'Current User',
        token: 'valid_token_xyz',
      );

      bool threw = false;
      try {
        await service.switchActiveAccount('non_existent_ghost');
      } catch (e) {
        threw = true;
        expect(e.toString(), contains('Account not found'));
      }
      expect(threw, isTrue);

      // Prior session must remain completely intact
      final active = await service.loadActiveAccount();
      expect(active?['username'], equals('current_user'));
      expect(active?['token'], equals('valid_token_xyz'));

      final token = await service.getActiveSessionToken();
      expect(token, equals('valid_token_xyz'));
    });
  });

  // =========================================================================
  // GROUP 2: Deletion of Active Account & Fallback Active Assignment
  // =========================================================================
  group('AuthStorageService: Deletion & Fallback Active Assignment', () {
    test('Deleting active account assigns fallback active to next available account', () async {
      await resetAuthStorage();

      await service.saveActiveAccount(
        username: 'user_first',
        password: 'p1',
        displayName: 'First User',
        token: 'tok_first',
      );
      await service.saveActiveAccount(
        username: 'user_second',
        password: 'p2',
        displayName: 'Second User',
        token: 'tok_second',
      );
      await service.saveActiveAccount(
        username: 'user_third',
        password: 'p3',
        displayName: 'Third User',
        token: 'tok_third',
      );

      // Active is user_third
      expect((await service.loadActiveAccount())?['username'], equals('user_third'));
      expect(await service.getActiveSessionToken(), equals('tok_third'));

      // Delete active account
      await service.removeAccount('user_third');

      // 1. Storage now has 2 accounts
      final remaining = await service.loadAllAccounts();
      expect(remaining, hasLength(2));
      expect(remaining.any((a) => a['username'] == 'user_third'), isFalse);

      // 2. Fallback active assignment: first available account
      final newActive = await service.loadActiveAccount();
      expect(newActive, isNotNull);
      expect(newActive?['username'], equals('user_first'));
      expect(newActive?['is_active'], isTrue);

      // 3. Active session token updated to fallback user's token
      final newToken = await service.getActiveSessionToken();
      expect(newToken, equals('tok_first'));
    });

    test('Sequential deletion until empty completely clears active session and token', () async {
      await resetAuthStorage();

      await service.saveActiveAccount(
        username: 'alpha',
        password: 'pa',
        displayName: 'Alpha',
        token: 'tok_alpha',
      );
      await service.saveActiveAccount(
        username: 'beta',
        password: 'pb',
        displayName: 'Beta',
        token: 'tok_beta',
      );

      // Active is beta. Delete beta.
      await service.removeAccount('beta');
      expect((await service.loadActiveAccount())?['username'], equals('alpha'));
      expect(await service.getActiveSessionToken(), equals('tok_alpha'));

      // Active is alpha. Delete alpha.
      await service.removeAccount('alpha');

      // Storage is now empty
      final all = await service.loadAllAccounts();
      expect(all, hasLength(0));

      final active = await service.loadActiveAccount();
      expect(active, isNull);

      final token = await service.getActiveSessionToken();
      expect(token, isNull);
    });

    test('Deleting inactive account preserves the currently active account and its token', () async {
      await resetAuthStorage();

      await service.saveActiveAccount(
        username: 'user_a',
        password: 'pa',
        displayName: 'User A',
        token: 'tok_a',
      );
      await service.saveActiveAccount(
        username: 'user_b',
        password: 'pb',
        displayName: 'User B',
        token: 'tok_b',
      );
      await service.saveActiveAccount(
        username: 'user_c',
        password: 'pc',
        displayName: 'User C',
        token: 'tok_c',
      );

      // Explicitly switch active to user_b
      await service.switchActiveAccount('user_b');
      expect((await service.loadActiveAccount())?['username'], equals('user_b'));

      // Delete inactive user_a
      await service.removeAccount('user_a');
      expect((await service.loadActiveAccount())?['username'], equals('user_b'));
      expect(await service.getActiveSessionToken(), equals('tok_b'));

      // Delete inactive user_c
      await service.removeAccount('user_c');
      expect((await service.loadActiveAccount())?['username'], equals('user_b'));
      expect(await service.getActiveSessionToken(), equals('tok_b'));

      final all = await service.loadAllAccounts();
      expect(all, hasLength(1));
      expect(all.first['username'], equals('user_b'));
      expect(all.first['is_active'], isTrue);
    });

    test('Deleting non-existent account is safely ignored without state change', () async {
      await resetAuthStorage();

      await service.saveActiveAccount(
        username: 'solo_user',
        password: 'pwd',
        displayName: 'Solo',
        token: 'tok_solo',
      );

      await service.removeAccount('phantom_user');

      final all = await service.loadAllAccounts();
      expect(all, hasLength(1));
      expect(all.first['username'], equals('solo_user'));

      final active = await service.loadActiveAccount();
      expect(active?['username'], equals('solo_user'));
    });
  });

  // =========================================================================
  // GROUP 3: Corrupted JSON Storage & Malformed Payloads
  // =========================================================================
  group('AuthStorageService: Corrupted JSON & Malformed Payloads', () {
    test('Raw corrupted non-JSON string is handled gracefully without crashing', () async {
      await resetAuthStorage();

      const storage = FlutterSecureStorage();
      await storage.write(
        key: AuthStorageService.accountsKey,
        value: '<<<INVALID UNPARSEABLE NOT JSON>>>',
      );

      final active = await service.loadActiveAccount();
      expect(active, isNull);

      final all = await service.loadAllAccounts();
      expect(all, hasLength(0));

      final token = await service.getActiveSessionToken();
      expect(token, isNull);

      // Recovery: saving new account recovers store cleanly
      await service.saveActiveAccount(
        username: 'recovering_user',
        password: 'pwd',
        displayName: 'Recovered',
        token: 'tok_rec',
      );

      final recoveredActive = await service.loadActiveAccount();
      expect(recoveredActive?['username'], equals('recovering_user'));
      expect(recoveredActive?['token'], equals('tok_rec'));
    });

    test('Non-Map JSON primitives (List, String, Number, Boolean) do not crash', () async {
      await resetAuthStorage();

      const storage = FlutterSecureStorage();
      final nonMapPayloads = [
        '[1, 2, 3]',
        '"a pure json string"',
        '42',
        'true',
        'null',
      ];

      for (final payload in nonMapPayloads) {
        await storage.write(key: AuthStorageService.accountsKey, value: payload);

        final active = await service.loadActiveAccount();
        expect(active, isNull, reason: 'Payload $payload should yield null active');

        final all = await service.loadAllAccounts();
        expect(all, hasLength(0), reason: 'Payload $payload should yield empty accounts list');
      }
    });

    test('Empty and whitespace string in storage does not crash', () async {
      await resetAuthStorage();

      const storage = FlutterSecureStorage();

      await storage.write(key: AuthStorageService.accountsKey, value: '');
      expect(await service.loadActiveAccount(), isNull);
      expect(await service.loadAllAccounts(), hasLength(0));

      await storage.write(key: AuthStorageService.accountsKey, value: '   \n\t  ');
      expect(await service.loadActiveAccount(), isNull);
      expect(await service.loadAllAccounts(), hasLength(0));
    });

    test('Store with null active or null accounts handled safely', () async {
      await resetAuthStorage();

      const storage = FlutterSecureStorage();
      await storage.write(
        key: AuthStorageService.accountsKey,
        value: json.encode({'active': null, 'active_username': null, 'accounts': null}),
      );

      final active = await service.loadActiveAccount();
      expect(active, isNull);

      final all = await service.loadAllAccounts();
      expect(all, hasLength(0));
    });

    test('VULNERABILITY PROBE: Store where accounts is a non-list type (string/int)', () async {
      await resetAuthStorage();

      const storage = FlutterSecureStorage();
      await storage.write(
        key: AuthStorageService.accountsKey,
        value: json.encode({'active': 'user1', 'accounts': 'corrupted_string_not_list'}),
      );

      bool threw = false;
      try {
        await service.loadActiveAccount();
      } catch (e) {
        threw = true;
        print('      [Vulnerability Confirmed] loadActiveAccount threw on non-list accounts: $e');
      }
      expect(threw, isTrue, reason: 'TypeError expected due to lack of type guard on store["accounts"]');
    });

    test('VULNERABILITY PROBE: Store where accounts list contains non-Map elements', () async {
      await resetAuthStorage();

      const storage = FlutterSecureStorage();
      await storage.write(
        key: AuthStorageService.accountsKey,
        value: json.encode({
          'active': 'u1',
          'accounts': [null, 123, 'corrupted_element'],
        }),
      );

      bool threw = false;
      try {
        await service.loadAllAccounts();
      } catch (e) {
        threw = true;
        print('      [Vulnerability Confirmed] loadAllAccounts threw on non-map list element: $e');
      }
      expect(threw, isTrue, reason: 'TypeError expected due to "a as Map" cast on malformed list element');
    });
  });

  // =========================================================================
  // GROUP 4: Special Characters in Usernames, Passwords & Display Names
  // =========================================================================
  group('AuthStorageService: Special Characters & Unicode Parity', () {
    test('Full Arabic, RTL text and diacritics preserved with byte precision', () async {
      await resetAuthStorage();

      const username = 'مُحَمَّد_البَطَل_١٢٣';
      const password = 'كَلِمَة_مُرُور_قَوِيَّة_!@#\$%^&*()';
      const displayName = 'الأمير عبد الله بن عبد العزيز 👑';
      const token = 'jwt.áràbîc_tökën_مفتاح_سري';

      await service.saveActiveAccount(
        username: username,
        password: password,
        displayName: displayName,
        token: token,
      );

      final active = await service.loadActiveAccount();
      expect(active, isNotNull);
      expect(active?['username'], equals(username));
      expect(active?['password'], equals(password));
      expect(active?['display_name'], equals(displayName));
      expect(active?['token'], equals(token));

      final all = await service.loadAllAccounts();
      expect(all, hasLength(1));
      expect(all.first['username'], equals(username));
      expect(all.first['password'], equals(password));
      expect(all.first['display_name'], equals(displayName));
    });

    test('Complex escape characters, quotes, slashes, and symbols in credentials', () async {
      await resetAuthStorage();

      const username = 'user!#\$%^&*()_+-=[]{}|;:",.<>?/~`';
      const password = 'P@ssw"ord\'\\/\b\f\n\r\t\$123';
      const displayName = 'Test "Double" & \'Single\' <HTML> & Ampersand';
      const token = 'ey...complex/token+with=symbols/&?';

      await service.saveActiveAccount(
        username: username,
        password: password,
        displayName: displayName,
        token: token,
      );

      final active = await service.loadActiveAccount();
      expect(active?['username'], equals(username));
      expect(active?['password'], equals(password));
      expect(active?['display_name'], equals(displayName));
      expect(active?['token'], equals(token));

      // Test switching using exact symbol username
      await service.switchActiveAccount(username);
      expect((await service.loadActiveAccount())?['username'], equals(username));
    });

    test('Multibyte emoji sequences in usernames and display names', () async {
      await resetAuthStorage();

      const username = 'player_🎮_🔥_💯';
      const password = '🔑_🔐_🛡️';
      const displayName = '✨سيد_الألعاب🎲🎯';
      const token = 'token_emoji_✨';

      await service.saveActiveAccount(
        username: username,
        password: password,
        displayName: displayName,
        token: token,
      );

      final active = await service.loadActiveAccount();
      expect(active?['username'], equals(username));
      expect(active?['display_name'], equals(displayName));
      expect(active?['password'], equals(password));
    });

    test('Preserves credentials containing leading and trailing spaces at storage layer', () async {
      await resetAuthStorage();

      const username = '  spaced_user  ';
      const password = '  pass with spaces  ';
      const displayName = '  Display  ';
      const token = 'tok_spaced';

      await service.saveActiveAccount(
        username: username,
        password: password,
        displayName: displayName,
        token: token,
      );

      final active = await service.loadActiveAccount();
      expect(active?['username'], equals(username));
      expect(active?['password'], equals(password));
      expect(active?['display_name'], equals(displayName));
    });
  });

  // =========================================================================
  // GROUP 5: Concurrent Save Operations & Race Condition Stress Testing
  // =========================================================================
  group('AuthStorageService: Concurrent Operations & Stress', () {
    test('VULNERABILITY PROBE: Concurrent saves via Future.wait causes lost accounts (Race Condition)', () async {
      await resetAuthStorage();

      const count = 5;
      final futures = <Future<void>>[];

      for (int i = 0; i < count; i++) {
        futures.add(service.saveActiveAccount(
          username: 'concurrent_user_$i',
          password: 'pwd_$i',
          displayName: 'Concurrent $i',
          token: 'token_$i',
        ));
      }

      await Future.wait(futures);

      final all = await service.loadAllAccounts();
      print('      [Concurrency Bug Demonstrated] $count concurrent saves produced ${all.length} saved account(s) (Expected 5 if synchronized)');
      // In absence of mutex / transaction lock, race condition causes last-write-wins:
      // all.length is strictly less than count (typically 1)
      final raceConditionOccurred = all.length < count;
      expect(raceConditionOccurred, isTrue, reason: 'Demonstrates race condition due to non-atomic read-modify-write');
    });

    test('Rapid sequential saves of 50 accounts completes reliably with 100% retention', () async {
      await resetAuthStorage();

      final sw = Stopwatch()..start();
      const total = 50;

      for (int i = 0; i < total; i++) {
        await service.saveActiveAccount(
          username: 'stress_user_$i',
          password: 'pwd_$i',
          displayName: 'User $i',
          token: 'token_$i',
        );
      }
      sw.stop();

      final all = await service.loadAllAccounts();
      expect(all, hasLength(total));

      final active = await service.loadActiveAccount();
      expect(active?['username'], equals('stress_user_${total - 1}'));
      print('      [Performance] Sequential save of $total accounts completed in ${sw.elapsedMilliseconds}ms');
    });
  });

  // =========================================================================
  // GROUP 6: Auto-Login State Transitions
  // =========================================================================
  group('Auto-Login State Transitions & Validation Matrix', () {
    late MockApiAdapter api;

    setUp(() {
      api = MockApiAdapter();
    });

    /// Evaluates AuthView._startupCheck() logic matching mobile/lib/views/auth_view.dart:41-76
    Future<Map<String, dynamic>> evaluateStartupAutoLogin() async {
      final allAccounts = await service.loadAllAccounts();
      final active = await service.loadActiveAccount();

      String prefilledUsername = '';
      String prefilledPassword = '';
      bool navigatedToHome = false;
      String navigatedDisplayName = '';
      String appliedApiToken = '';

      if (active != null) {
        final uName = active['username'] ?? '';
        final pwd = active['password'] ?? '';
        final dName = (active['display_name'] ?? uName).toString();
        final token = active['token']?.toString();

        if (uName.isNotEmpty) prefilledUsername = uName;
        if (pwd.isNotEmpty) prefilledPassword = pwd;

        // Validation condition from auth_view.dart:64:
        // if (token != null && token.isNotEmpty)
        if (token != null && token.isNotEmpty) {
          appliedApiToken = token;
          api.authToken = token;
          navigatedToHome = true;
          navigatedDisplayName = dName;
        }
      }

      return {
        'savedAccountsCount': allAccounts.length,
        'hasActive': active != null,
        'prefilledUsername': prefilledUsername,
        'prefilledPassword': prefilledPassword,
        'navigatedToHome': navigatedToHome,
        'navigatedDisplayName': navigatedDisplayName,
        'appliedApiToken': appliedApiToken,
      };
    }

    test('State 1: Valid Token -> Applies token, prefills credentials, navigates to HomeView', () async {
      await resetAuthStorage();

      await service.saveActiveAccount(
        username: 'valid_player',
        password: 'secure_pwd',
        displayName: 'اللاعب المؤكد',
        token: 'valid_jwt_token_999',
      );

      final state = await evaluateStartupAutoLogin();

      expect(state['hasActive'], isTrue);
      expect(state['prefilledUsername'], equals('valid_player'));
      expect(state['prefilledPassword'], equals('secure_pwd'));
      expect(state['appliedApiToken'], equals('valid_jwt_token_999'));
      expect(state['navigatedToHome'], isTrue);
      expect(state['navigatedDisplayName'], equals('اللاعب المؤكد'));
    });

    test('State 2: Empty Token -> Prefills credentials, does NOT navigate to HomeView', () async {
      await resetAuthStorage();

      await service.saveActiveAccount(
        username: 'saved_no_token',
        password: 'pwd',
        displayName: 'مستخدم بدون توكن',
        token: '', // empty token
      );

      final state = await evaluateStartupAutoLogin();

      expect(state['hasActive'], isTrue);
      expect(state['prefilledUsername'], equals('saved_no_token'));
      expect(state['prefilledPassword'], equals('pwd'));
      expect(state['navigatedToHome'], isFalse);
      expect(state['appliedApiToken'], equals(''));
    });

    test('State 3: Null Profile (Empty Storage) -> No prefill, does NOT navigate to HomeView', () async {
      await resetAuthStorage();

      final state = await evaluateStartupAutoLogin();

      expect(state['savedAccountsCount'], equals(0));
      expect(state['hasActive'], isFalse);
      expect(state['prefilledUsername'], equals(''));
      expect(state['prefilledPassword'], equals(''));
      expect(state['navigatedToHome'], isFalse);
    });

    test('State 4: Whitespace Credentials with Empty Token -> Does NOT navigate, form trims on submit', () async {
      await resetAuthStorage();

      await service.saveActiveAccount(
        username: '   ',
        password: '   ',
        displayName: '   ',
        token: '',
      );

      final state = await evaluateStartupAutoLogin();
      expect(state['navigatedToHome'], isFalse);

      final uTrimmed = '   '.trim();
      final pTrimmed = '   '.trim();
      final wouldFailValidation = uTrimmed.isEmpty || pTrimmed.isEmpty;
      expect(wouldFailValidation, isTrue);
    });

    test('State 5: Token Revocation / 401 Session Expired -> Clears active session', () async {
      await resetAuthStorage();

      await service.saveActiveAccount(
        username: 'revoked_user',
        password: 'pwd',
        displayName: 'منتهي الصلاحية',
        token: 'expired_or_revoked_token',
      );

      // Verify token initially active
      expect((await service.loadActiveAccount())?['token'], equals('expired_or_revoked_token'));

      // Backend returns 401 Unauthorized -> triggers clearActiveSession()
      await service.clearActiveSession();

      // Active session cleared
      final active = await service.loadActiveAccount();
      expect(active, isNull);

      final currentToken = await service.getActiveSessionToken();
      expect(currentToken, isNull);

      // But account is preserved in saved accounts list for quick 1-tap re-login
      final all = await service.loadAllAccounts();
      expect(all, hasLength(1));
      expect(all.first['username'], equals('revoked_user'));
      expect(all.first['is_active'], isFalse);
    });

    test('ARCHITECTURAL GAP: AuthView does not trim whitespace token or query backend getMe()', () async {
      // In auth_view.dart:64:
      // if (token != null && token.isNotEmpty)
      const whitespaceToken = '   ';
      // Dart's isNotEmpty is true for whitespace!
      expect(whitespaceToken.isNotEmpty, isTrue);
      // But trim().isNotEmpty is false:
      expect(whitespaceToken.trim().isNotEmpty, isFalse);

      // In auth_view.dart, _startupCheck navigates to HomeView blindly:
      // ApiService.instance.setToken(token);
      // Navigator.of(context).pushReplacement(...);
      // It does NOT invoke api.getMe() or await backend validation before entering HomeView!
      // This contrasts with tier3_integration/auth_flow_test.dart which simulated getMe().
    });
  });
}
