// Tier 1 Unit Test: Auth Storage (Multi-Account Serialization, Profile Switching, Secure Storage Simulation)

import 'dart:convert';
import '../harness/test_engine.dart';

/// Simulated secure storage representing flutter_secure_storage / Windows DPAPI
class MockSecureStorage {
  final Map<String, String> _storage = {};

  Future<void> write({required String key, required String value}) async {
    _storage[key] = value;
  }

  Future<String?> read({required String key}) async {
    return _storage[key];
  }

  Future<void> delete({required String key}) async {
    _storage.remove(key);
  }

  Future<bool> containsKey({required String key}) async {
    return _storage.containsKey(key);
  }

  Future<void> deleteAll() async {
    _storage.clear();
  }
}

/// Standalone test implementation of AuthStorageService matching PROJECT.md interface contract
class TestAuthStorageService {
  final MockSecureStorage storage;
  static const String accountsKey = 'tv_accounts_store';
  static const String sessionTokenKey = 'tv_session_token';

  TestAuthStorageService(this.storage);

  Future<Map<String, dynamic>> _readStore() async {
    final raw = await storage.read(key: accountsKey);
    if (raw == null || raw.isEmpty) {
      return {'active': null, 'accounts': <Map<String, dynamic>>[]};
    }
    try {
      final decoded = json.decode(raw);
      if (decoded is Map<String, dynamic>) {
        return decoded;
      }
    } catch (_) {}
    return {'active': null, 'accounts': <Map<String, dynamic>>[]};
  }

  Future<void> _writeStore(Map<String, dynamic> data) async {
    await storage.write(key: accountsKey, value: json.encode(data));
  }

  Future<void> saveActiveAccount({
    required String username,
    required String password,
    required String displayName,
    required String token,
  }) async {
    final store = await _readStore();
    final List<dynamic> accounts = store['accounts'] ?? [];

    // Remove if exists to update
    accounts.removeWhere((a) => a['username'] == username);
    accounts.add({
      'username': username,
      'password': password,
      'display_name': displayName,
      'token': token,
      'updated_at': DateTime.now().toIso8601String(),
    });

    store['accounts'] = accounts;
    store['active'] = username;

    await _writeStore(store);
    await storage.write(key: sessionTokenKey, value: token);
  }

  Future<Map<String, dynamic>?> loadActiveAccount() async {
    final store = await _readStore();
    final activeUsername = store['active'];
    if (activeUsername == null) return null;

    final List<dynamic> accounts = store['accounts'] ?? [];
    for (final a in accounts) {
      if (a['username'] == activeUsername) {
        return Map<String, dynamic>.from(a as Map);
      }
    }
    return null;
  }

  Future<List<Map<String, dynamic>>> loadAllAccounts() async {
    final store = await _readStore();
    final List<dynamic> accounts = store['accounts'] ?? [];
    final activeUsername = store['active'];

    return accounts.map((a) {
      final m = Map<String, dynamic>.from(a as Map);
      m['is_active'] = (m['username'] == activeUsername);
      return m;
    }).toList();
  }

  Future<void> switchActiveAccount(String username) async {
    final store = await _readStore();
    final List<dynamic> accounts = store['accounts'] ?? [];
    final exists = accounts.any((a) => a['username'] == username);
    if (!exists) {
      throw Exception('Account not found: $username');
    }

    store['active'] = username;
    await _writeStore(store);

    // Update active session token to the newly selected account's token
    for (final a in accounts) {
      if (a['username'] == username && a['token'] != null) {
        await storage.write(key: sessionTokenKey, value: a['token'].toString());
        break;
      }
    }
  }

  Future<void> removeAccount(String username) async {
    final store = await _readStore();
    final List<dynamic> accounts = store['accounts'] ?? [];
    accounts.removeWhere((a) => a['username'] == username);

    if (store['active'] == username) {
      store['active'] = accounts.isNotEmpty ? accounts.first['username'] : null;
    }

    store['accounts'] = accounts;
    await _writeStore(store);
  }

  Future<void> clearActiveSession() async {
    await storage.delete(key: sessionTokenKey);
    final store = await _readStore();
    store['active'] = null;
    await _writeStore(store);
  }
}

void main() async {
  defineTests();
  await runSuite('Tier 1 Unit: Auth Storage Tests');
}

void defineTests() {
  group('AuthStorageService & Multi-Account Parity', () {
    late MockSecureStorage mockStorage;
    late TestAuthStorageService authStorage;

    setUp(() {
      mockStorage = MockSecureStorage();
      authStorage = TestAuthStorageService(mockStorage);
    });

    test('Initial state: loadActiveAccount returns null when empty', () async {
      final active = await authStorage.loadActiveAccount();
      expect(active, isNull);

      final all = await authStorage.loadAllAccounts();
      expect(all, hasLength(0));
    });

    test('Saves first account, marks as active, and persists token', () async {
      await authStorage.saveActiveAccount(
        username: 'player_one',
        password: 'password123',
        displayName: 'اللاعب الأول',
        token: 'token_jwt_001',
      );

      final active = await authStorage.loadActiveAccount();
      expect(active, isNotNull);
      expect(active?['username'], equals('player_one'));
      expect(active?['display_name'], equals('اللاعب الأول'));
      expect(active?['token'], equals('token_jwt_001'));

      final sessionToken = await mockStorage.read(key: TestAuthStorageService.sessionTokenKey);
      expect(sessionToken, equals('token_jwt_001'));
    });

    test('Supports multiple accounts and marks current active profile', () async {
      await authStorage.saveActiveAccount(
        username: 'user_a',
        password: 'pwd_a',
        displayName: 'مستخدم أ',
        token: 'token_a',
      );

      await authStorage.saveActiveAccount(
        username: 'user_b',
        password: 'pwd_b',
        displayName: 'مستخدم ب',
        token: 'token_b',
      );

      final all = await authStorage.loadAllAccounts();
      expect(all, hasLength(2));

      // user_b was saved last, so it should be active
      final active = await authStorage.loadActiveAccount();
      expect(active?['username'], equals('user_b'));

      final userA = all.firstWhere((a) => a['username'] == 'user_a');
      final userB = all.firstWhere((a) => a['username'] == 'user_b');
      expect(userA['is_active'], isFalse);
      expect(userB['is_active'], isTrue);
    });

    test('Switches active profile seamlessly and updates active token', () async {
      await authStorage.saveActiveAccount(
        username: 'user_a',
        password: 'pwd_a',
        displayName: 'مستخدم أ',
        token: 'token_a',
      );
      await authStorage.saveActiveAccount(
        username: 'user_b',
        password: 'pwd_b',
        displayName: 'مستخدم ب',
        token: 'token_b',
      );

      // Switch back to user_a
      await authStorage.switchActiveAccount('user_a');

      final active = await authStorage.loadActiveAccount();
      expect(active?['username'], equals('user_a'));

      final currentToken = await mockStorage.read(key: TestAuthStorageService.sessionTokenKey);
      expect(currentToken, equals('token_a'));
    });

    test('Throws exception when switching to non-existent profile', () async {
      bool caught = false;
      try {
        await authStorage.switchActiveAccount('ghost_user');
      } catch (e) {
        caught = true;
      }
      expect(caught, isTrue);
    });

    test('Removes account from storage and re-assigns active profile if active was removed', () async {
      await authStorage.saveActiveAccount(
        username: 'user_1',
        password: 'p1',
        displayName: 'واحد',
        token: 'tok1',
      );
      await authStorage.saveActiveAccount(
        username: 'user_2',
        password: 'p2',
        displayName: 'اثنان',
        token: 'tok2',
      );

      // Active is user_2. Remove user_2
      await authStorage.removeAccount('user_2');

      final all = await authStorage.loadAllAccounts();
      expect(all, hasLength(1));
      expect(all.first['username'], equals('user_1'));

      // Active should fallback to remaining user_1
      final active = await authStorage.loadActiveAccount();
      expect(active?['username'], equals('user_1'));
    });

    test('Clears active session while preserving stored credentials', () async {
      await authStorage.saveActiveAccount(
        username: 'persistent_user',
        password: 'secret',
        displayName: 'محفوظ',
        token: 'active_tok',
      );

      await authStorage.clearActiveSession();

      // Session token cleared
      final token = await mockStorage.read(key: TestAuthStorageService.sessionTokenKey);
      expect(token, isNull);

      // Active is null
      final active = await authStorage.loadActiveAccount();
      expect(active, isNull);

      // But account still in saved list for quick re-login!
      final all = await authStorage.loadAllAccounts();
      expect(all, hasLength(1));
      expect(all.first['username'], equals('persistent_user'));
      expect(all.first['password'], equals('secret'));
    });

    test('Handles corrupted storage payload gracefully without crashing', () async {
      await mockStorage.write(
        key: TestAuthStorageService.accountsKey,
        value: '<<<INVALID NOT JSON DATA>>>',
      );

      final active = await authStorage.loadActiveAccount();
      expect(active, isNull);

      final all = await authStorage.loadAllAccounts();
      expect(all, hasLength(0));
    });
  });
}
