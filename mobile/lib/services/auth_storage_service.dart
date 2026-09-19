import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Secure storage service managing credentials, multi-account profiles,
/// and active session tokens matching the Windows desktop client authentication architecture.
class AuthStorageService {
  static final AuthStorageService instance = AuthStorageService._();
  AuthStorageService._();

  final FlutterSecureStorage _secureStorage = const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
    iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
  );

  static const String accountsKey = 'tv_accounts_store';
  static const String sessionTokenKey = 'tv_session_token';

  // In-memory fallback cache for headless environments or unsupported platforms
  final Map<String, String> _memoryFallback = {};

  Future<void> _writeString(String key, String value) async {
    _memoryFallback[key] = value;

    try {
      await _secureStorage.write(key: key, value: value);
    } catch (_) {
      try {
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString(key, value);
      } catch (_) {}
    }
  }

  Future<String?> _readString(String key) async {
    try {
      final val = await _secureStorage.read(key: key);
      if (val != null && val.isNotEmpty) {
        return val;
      }
    } catch (_) {}

    try {
      final prefs = await SharedPreferences.getInstance();
      final val = prefs.getString(key);
      if (val != null && val.isNotEmpty) {
        return val;
      }
    } catch (_) {}

    return _memoryFallback[key];
  }

  Future<void> _deleteString(String key) async {
    _memoryFallback.remove(key);

    try {
      await _secureStorage.delete(key: key);
    } catch (_) {}

    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(key);
    } catch (_) {}
  }

  Future<Map<String, dynamic>> _readStore() async {
    try {
      final raw = await _readString(accountsKey);
      if (raw == null || raw.isEmpty) {
        return {
          'active_username': null,
          'active': null,
          'accounts': <Map<String, dynamic>>[],
        };
      }
      final decoded = json.decode(raw);
      if (decoded is Map<String, dynamic>) {
        return decoded;
      }
    } catch (_) {}
    return {
      'active_username': null,
      'active': null,
      'accounts': <Map<String, dynamic>>[],
    };
  }

  Future<void> _writeStore(Map<String, dynamic> data) async {
    await _writeString(accountsKey, json.encode(data));
  }

  /// Saves or updates an account profile and sets it as the active session.
  Future<void> saveActiveAccount({
    required String username,
    required String password,
    required String displayName,
    required String token,
  }) async {
    final store = await _readStore();
    final List<dynamic> accounts = List<dynamic>.from(store['accounts'] ?? []);

    // Remove existing profile with identical username to update
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
    store['active_username'] = username;

    await _writeStore(store);
    await _writeString(sessionTokenKey, token);
  }

  /// Loads the active account profile dictionary or null if none is active.
  Future<Map<String, dynamic>?> loadActiveAccount() async {
    final store = await _readStore();
    final activeUsername = store['active_username'] ?? store['active'];
    if (activeUsername == null) return null;

    final List<dynamic> accounts = store['accounts'] ?? [];
    for (final a in accounts) {
      if (a is Map && a['username'] == activeUsername) {
        final m = Map<String, dynamic>.from(a);
        m['is_active'] = true;
        return m;
      }
    }
    return null;
  }

  /// Alias for loadActiveAccount returning active profile or null
  Future<Map<String, dynamic>?> getActiveUser() => loadActiveAccount();

  /// Retrieves the active session token, checking token key first then active account.
  Future<String?> getActiveSessionToken() async {
    final token = await _readString(sessionTokenKey);
    if (token != null && token.isNotEmpty) {
      return token;
    }
    final active = await loadActiveAccount();
    return active?['token'] as String?;
  }

  /// Loads all stored account profiles with `is_active` marker.
  Future<List<Map<String, dynamic>>> loadAllAccounts() async {
    final store = await _readStore();
    final List<dynamic> accounts = store['accounts'] ?? [];
    final activeUsername = store['active_username'] ?? store['active'];

    return accounts.map((a) {
      final m = Map<String, dynamic>.from(a as Map);
      m['is_active'] = (m['username'] == activeUsername);
      return m;
    }).toList();
  }

  /// Switches the active account profile and updates the active session token.
  Future<void> switchActiveAccount(String username) async {
    final store = await _readStore();
    final List<dynamic> accounts = store['accounts'] ?? [];
    final exists = accounts.any((a) => a is Map && a['username'] == username);
    if (!exists) {
      throw Exception('Account not found: $username');
    }

    store['active'] = username;
    store['active_username'] = username;
    await _writeStore(store);

    for (final a in accounts) {
      if (a is Map && a['username'] == username && a['token'] != null) {
        await _writeString(sessionTokenKey, a['token'].toString());
        break;
      }
    }
  }

  /// Removes an account profile. If it was active, sets next available as active.
  Future<void> removeAccount(String username) async {
    final store = await _readStore();
    final List<dynamic> accounts = List<dynamic>.from(store['accounts'] ?? []);
    accounts.removeWhere((a) => a is Map && a['username'] == username);

    final activeUsername = store['active_username'] ?? store['active'];
    if (activeUsername == username) {
      final newActive = accounts.isNotEmpty ? (accounts.first as Map)['username'] : null;
      store['active'] = newActive;
      store['active_username'] = newActive;
      if (newActive != null) {
        final firstAcc = accounts.first as Map;
        if (firstAcc['token'] != null) {
          await _writeString(sessionTokenKey, firstAcc['token'].toString());
        }
      } else {
        await _deleteString(sessionTokenKey);
      }
    }

    store['accounts'] = accounts;
    await _writeStore(store);
  }

  /// Clears the active session token and active account pointer while keeping saved accounts.
  Future<void> clearActiveSession() async {
    await _deleteString(sessionTokenKey);
    final store = await _readStore();
    store['active'] = null;
    store['active_username'] = null;
    await _writeStore(store);
  }
}
