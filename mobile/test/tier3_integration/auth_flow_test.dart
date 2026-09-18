// Tier 3 Integration Test: Auth Flow (Login, Token Persistence, HomeView Navigation, Auto-Login)

import '../harness/test_engine.dart';
import '../harness/mock_api_adapter.dart';
import '../tier1_unit/auth_storage_test.dart';
import '../tier1_unit/activity_service_test.dart';

class AuthFlowController {
  final MockApiAdapter api;
  final TestAuthStorageService storage;
  final TestActivityLogService activityLog;

  String? currentView;
  String? currentDisplayName;
  String? errorMessage;

  AuthFlowController({
    required this.api,
    required this.storage,
    required this.activityLog,
  }) {
    currentView = 'AuthView';
  }

  /// Flow 1: User Login
  Future<bool> login(String username, String password) async {
    errorMessage = null;
    try {
      final res = await api.login(username, password);
      final token = res['access_token'] as String;
      final user = res['user'] as Map<String, dynamic>;
      final displayName = user['display_name'] as String;

      // 1. Persist to secure storage
      await storage.saveActiveAccount(
        username: username,
        password: password,
        displayName: displayName,
        token: token,
      );

      // 2. Record return greeting in centralized ActivityLog
      activityLog.addEvent({
        'text': 'مرحبًا بعودتك $displayName.',
        'category': 'GAMEPLAY',
      });

      // 3. Navigate to HomeView
      currentDisplayName = displayName;
      currentView = 'HomeView';
      return true;
    } catch (e) {
      errorMessage = e.toString().replaceAll('Exception: ', '');
      return false;
    }
  }

  /// Flow 2: User Register -> Auto-Login
  Future<bool> registerAndAutoLogin(String username, String displayName, String password) async {
    errorMessage = null;
    try {
      await api.register(username, displayName, password);
      return await login(username, password);
    } catch (e) {
      errorMessage = e.toString().replaceAll('Exception: ', '');
      return false;
    }
  }

  /// Flow 3: App Launch Auto-Login Check
  Future<bool> checkAutoLoginOnStartup() async {
    final active = await storage.loadActiveAccount();
    if (active == null || active['token'] == null) {
      currentView = 'AuthView';
      return false;
    }

    try {
      api.authToken = active['token'];
      final me = await api.getMe();
      final displayName = me['display_name'] ?? active['display_name'] ?? active['username'];

      // Add greeting and navigate to HomeView
      activityLog.addEvent({
        'text': 'مرحبًا بعودتك $displayName.',
        'category': 'GAMEPLAY',
      });

      currentDisplayName = displayName;
      currentView = 'HomeView';
      return true;
    } catch (_) {
      // Token invalid / expired: clear active session
      await storage.clearActiveSession();
      currentView = 'AuthView';
      return false;
    }
  }

  /// Flow 4: Logout
  Future<void> logout() async {
    await api.logout();
    await storage.clearActiveSession();
    currentDisplayName = null;
    currentView = 'AuthView';
  }
}

void main() async {
  defineTests();
  await runSuite('Tier 3 Integration: Auth Flow Tests');
}

void defineTests() {
  group('Authentication Flow Integration', () {
    late MockApiAdapter api;
    late MockSecureStorage mockSecure;
    late TestAuthStorageService storage;
    late TestActivityLogService activityLog;
    late AuthFlowController controller;

    setUp(() {
      api = MockApiAdapter();
      mockSecure = MockSecureStorage();
      storage = TestAuthStorageService(mockSecure);
      activityLog = TestActivityLogService();
      controller = AuthFlowController(
        api: api,
        storage: storage,
        activityLog: activityLog,
      );
    });

    test('Full Login Flow: Authenticates, persists token, greets user, and navigates to HomeView', () async {
      expect(controller.currentView, equals('AuthView'));

      final success = await controller.login('ahmed_player', 'secret123');
      expect(success, isTrue);

      // 1. Navigation state
      expect(controller.currentView, equals('HomeView'));
      expect(controller.currentDisplayName, equals('أحمد البطل'));

      // 2. Token persistence
      final active = await storage.loadActiveAccount();
      expect(active?['username'], equals('ahmed_player'));
      expect(active?['token'], isNotNull);

      // 3. Centralized ActivityLog updated with return greeting
      expect(activityLog.events, hasLength(1));
      expect(activityLog.events.first['text'], equals('مرحبًا بعودتك أحمد البطل.'));
      expect(activityLog.events.first['category'], equals('GAMEPLAY'));
    });

    test('Login Failure: Empty credentials displays error and remains on AuthView', () async {
      final success = await controller.login('', '');
      expect(success, isFalse);

      expect(controller.currentView, equals('AuthView'));
      expect(controller.errorMessage, contains('يرجى كتابة اسم المستخدم وكلمة المرور'));

      final active = await storage.loadActiveAccount();
      expect(active, isNull);
      expect(activityLog.events, hasLength(0));
    });

    test('Register and Auto-Login Flow: Registers user, auto-logs in, and navigates to HomeView', () async {
      final success = await controller.registerAndAutoLogin('new_user', 'مستخدم جديد', 'pass123');
      expect(success, isTrue);

      expect(controller.currentView, equals('HomeView'));
      expect(controller.currentDisplayName, equals('مستخدم جديد'));

      // Token persisted
      final active = await storage.loadActiveAccount();
      expect(active?['username'], equals('new_user'));

      // Activity log greeting
      expect(activityLog.events.first['text'], equals('مرحبًا بعودتك مستخدم جديد.'));
    });

    test('Startup Auto-Login Flow: Automatically navigates to HomeView when saved session token is valid', () async {
      // Pre-populate valid session in storage
      await storage.saveActiveAccount(
        username: 'sara_vip',
        password: 'password',
        displayName: 'سارة',
        token: 'valid_token_sara',
      );

      final loggedIn = await controller.checkAutoLoginOnStartup();
      expect(loggedIn, isTrue);

      expect(controller.currentView, equals('HomeView'));
      expect(controller.currentDisplayName, equals('سارة'));
      expect(activityLog.events.first['text'], equals('مرحبًا بعودتك سارة.'));
    });

    test('Startup Auto-Login Fallback: Clears session and stays on AuthView when token rejected by server', () async {
      // Pre-populate session
      await storage.saveActiveAccount(
        username: 'expired_user',
        password: 'password',
        displayName: 'منتهي',
        token: 'invalid_expired_token',
      );

      // Server simulates network / 401 error
      api.simulateNetworkError = true;
      api.nextErrorMessage = '401 Session expired';

      final loggedIn = await controller.checkAutoLoginOnStartup();
      expect(loggedIn, isFalse);

      expect(controller.currentView, equals('AuthView'));
      expect(controller.currentDisplayName, isNull);

      // Active session token was cleared
      final token = await mockSecure.read(key: TestAuthStorageService.sessionTokenKey);
      expect(token, isNull);
    });

    test('Logout Flow: Revokes session on server, clears active session, and redirects to AuthView', () async {
      // First login
      await controller.login('ahmed_player', 'secret123');
      expect(controller.currentView, equals('HomeView'));

      // Logout
      await controller.logout();

      expect(controller.currentView, equals('AuthView'));
      expect(controller.currentDisplayName, isNull);
      expect(api.hasCalled('POST', '/api/auth/logout'), isTrue);

      final token = await mockSecure.read(key: TestAuthStorageService.sessionTokenKey);
      expect(token, isNull);
    });
  });
}
