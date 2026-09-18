library flutter_secure_storage;

enum KeychainAccessibility {
  first_unlock,
}

class AndroidOptions {
  final bool encryptedSharedPreferences;
  const AndroidOptions({this.encryptedSharedPreferences = false});
}

class IOSOptions {
  final KeychainAccessibility? accessibility;
  const IOSOptions({this.accessibility});
}

class FlutterSecureStorage {
  final AndroidOptions? aOptions;
  final IOSOptions? iOptions;

  static final Map<String, String> _globalStorage = {};

  const FlutterSecureStorage({this.aOptions, this.iOptions});

  Future<void> write({required String key, required String value}) async {
    _globalStorage[key] = value;
  }

  Future<String?> read({required String key}) async {
    return _globalStorage[key];
  }

  Future<void> delete({required String key}) async {
    _globalStorage.remove(key);
  }

  Future<void> deleteAll() async {
    _globalStorage.clear();
  }

  Future<bool> containsKey({required String key}) async {
    return _globalStorage.containsKey(key);
  }

  static void resetGlobalStorage() {
    _globalStorage.clear();
  }

  static Map<String, String> get rawStorage => _globalStorage;
}
