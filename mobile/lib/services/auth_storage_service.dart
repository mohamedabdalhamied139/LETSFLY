import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Secure storage service managing credentials, multi-account profiles,
/// and active session tokens matching the Windows desktop client authentication architecture.
class AuthStorageService {
  static final AuthStorageService instance = AuthStorageService._();
  AuthStorageService._();

  final FlutterSecureStorage _storage = const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
    iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
  );

  static const String accountsKey = 'tv_accounts_store';
  static const String sessionTokenKey = 'tv_session_token';

  Future<Map<String, dynamic>> _readStore() async {
    try {
      final raw = await _storage.read(key: accountsKey);
      if (raw == null || raw.isEmpty) {
        return {'active': null, 'accounts': <Map<String, dynamic>>[]};
      }
      final decoded = json.decode(raw);
      if (decoded is Map<String, dynamic>) {
        return decoded;
      }
    } catch (_) {}
    return {'active': null, 'accounts': <Map<String, dynamic>>[]};
  }

  Future<void> _writeStore(Map<String, dynamic> data) async {
    await _storage.write(key: accountsKey, value: json.encode(data));
  }

  Future<void> saveActiveAccount({
    required String username,
    required String password,
    required String displayName,
    required String token,
  }) async {
    final store = await _readStore();
    final List<dynamic> accounts = List<dynamic>.from(store['accounts'] ?? []);

    // Remove existing if present to update
    accounts.removeWhere((a) => a is Map && a['username'] == username);
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
    await _storage.write(key: sessionTokenKey, value: token);
  }

  Future<Map<String, dynamic>?> loadActiveAccount() async {
    final store = await _readStore();
    final activeUsername = store['active'];
    if (activeUsername == null) return null;

    final List<dynamic> accounts = store['accounts'] ?? [];
    for (final a in accounts) {
      if (a is Map && a['username'] == activeUsername) {
        return Map<String, dynamic>.from(a);
      }
    }
    return null;
  }

  Future<String?> getActiveSessionToken() async {
    return _storage.read(key: sessionTokenKey);
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
    final exists = accounts.any((a) => a is Map && a['username'] == username);
    if (!exists) {
      throw Exception('Account not found: $username');
    }

    store['active'] = username;
    await _writeStore(store);

    for (final a in accounts) {
      if (a is Map && a['username'] == username && a['token'] != null) {
        await _storage.write(key: sessionTokenKey, value: a['token'].toString());
        break;
      }
    }
  }

  Future<void> removeAccount(String username) async {
    final store = await _readStore();
    final List<dynamic> accounts = List<dynamic>.from(store['accounts'] ?? []);
    accounts.removeWhere((a) => a is Map && a['username'] == username);

    if (store['active'] == username) {
      store['active'] = accounts.isNotEmpty ? (accounts.first as Map)['username'] : null;
    }

    store['accounts'] = accounts;
    await _writeStore(store);
  }

  Future<void> clearActiveSession() async {
    await _storage.delete(key: sessionTokenKey);
    final store = await _readStore();
    store['active'] = null;
    await _writeStore(store);
  }
}
