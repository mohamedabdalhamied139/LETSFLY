library shared_preferences;

class SharedPreferences {
  static final SharedPreferences _instance = SharedPreferences._();
  SharedPreferences._();

  static Future<SharedPreferences> getInstance() async => _instance;

  final Map<String, dynamic> _prefs = {};

  Future<bool> setString(String key, String value) async {
    _prefs[key] = value;
    return true;
  }

  String? getString(String key) => _prefs[key] as String?;

  Future<bool> remove(String key) async {
    _prefs.remove(key);
    return true;
  }

  Future<bool> clear() async {
    _prefs.clear();
    return true;
  }

  void reset() {
    _prefs.clear();
  }
}
