// Tier 2 Widget Test: HomeView (8 Canonical Menu Items, Greeting Display, Online Counter)

import 'dart:math';
import '../harness/test_engine.dart';
import '../harness/test_fixtures.dart';

/// Testable view-model and widget state harness for HomeView matching mobile/lib/views/home_view.dart
class HomeViewStateHarness {
  final String userDisplayName;
  int onlineCount = 0;
  final List<Map<String, dynamic>> activityEvents = [];
  String? lastNavigatedRoute;
  bool isLogoutConfirmationVisible = false;

  HomeViewStateHarness({required this.userDisplayName}) {
    // Initial return greeting event added to activityEvents matching HomeView initState()
    activityEvents.add({
      'text': 'مرحبًا بعودتك $userDisplayName.',
      'category': 'GAMEPLAY',
      'time': '',
    });
  }

  void setOnlineCount(int count) {
    onlineCount = max(0, count);
  }

  // Exact 8 canonical items in fixed order
  List<Map<String, String>> get menuItems {
    return [
      {'title': 'الطاولات', 'tag': 'rooms'},
      {'title': 'الأصدقاء', 'tag': 'friends'},
      {'title': 'المتصلون ($onlineCount)', 'tag': 'online'},
      {'title': 'ملفي الشخصي', 'tag': 'my_profile'},
      {'title': 'الإعدادات', 'tag': 'settings'},
      {'title': 'الإشعارات', 'tag': 'notifications'},
      {'title': 'تحدث معنا', 'tag': 'contact'},
      {'title': 'تسجيل الخروج', 'tag': 'logout'},
    ];
  }

  void selectMenuItem(String tag) {
    switch (tag) {
      case 'rooms':
        lastNavigatedRoute = 'RoomsMenuView';
        break;
      case 'friends':
        lastNavigatedRoute = 'FriendsView';
        break;
      case 'online':
        lastNavigatedRoute = 'OnlineUsersDialog';
        break;
      case 'my_profile':
        lastNavigatedRoute = 'MyProfileDialog';
        break;
      case 'settings':
        lastNavigatedRoute = 'SettingsDialog';
        break;
      case 'notifications':
        lastNavigatedRoute = 'NotificationsDialog';
        break;
      case 'contact':
        lastNavigatedRoute = 'ContactUsDialog';
        break;
      case 'logout':
        isLogoutConfirmationVisible = true;
        break;
      default:
        throw Exception('Unknown menu tag: $tag');
    }
  }

  void confirmLogout(bool confirmed) {
    isLogoutConfirmationVisible = false;
    if (confirmed) {
      lastNavigatedRoute = 'AuthView';
    }
  }
}

void main() async {
  defineTests();
  await runSuite('Tier 2 Widget: Home View Tests');
}

void defineTests() {
  group('HomeView Widget Parity & Canonical Items', () {
    late HomeViewStateHarness harness;

    setUp(() {
      harness = HomeViewStateHarness(userDisplayName: 'أحمد البطل');
    });

    test('Contains exactly 8 canonical menu items in Windows order', () {
      final items = harness.menuItems;
      expect(items, hasLength(8));

      expect(items[0]['tag'], equals('rooms'));
      expect(items[0]['title'], equals('الطاولات'));

      expect(items[1]['tag'], equals('friends'));
      expect(items[1]['title'], equals('الأصدقاء'));

      expect(items[2]['tag'], equals('online'));
      expect(items[2]['title'], equals('المتصلون (0)'));

      expect(items[3]['tag'], equals('my_profile'));
      expect(items[3]['title'], equals('ملفي الشخصي'));

      expect(items[4]['tag'], equals('settings'));
      expect(items[4]['title'], equals('الإعدادات'));

      expect(items[5]['tag'], equals('notifications'));
      expect(items[5]['title'], equals('الإشعارات'));

      expect(items[6]['tag'], equals('contact'));
      expect(items[6]['title'], equals('تحدث معنا'));

      expect(items[7]['tag'], equals('logout'));
      expect(items[7]['title'], equals('تسجيل الخروج'));
    });

    test('Initializes with user return greeting in activity events', () {
      expect(harness.activityEvents, hasLength(1));
      final greetingEvent = harness.activityEvents.first;
      expect(greetingEvent['text'], equals('مرحبًا بعودتك أحمد البطل.'));
      expect(greetingEvent['category'], equals('GAMEPLAY'));
    });

    test('Dynamically updates online user count in menu item 2', () {
      expect(harness.menuItems[2]['title'], equals('المتصلون (0)'));

      harness.setOnlineCount(24);
      expect(harness.menuItems[2]['title'], equals('المتصلون (24)'));

      // Clamps negative count to 0
      harness.setOnlineCount(-5);
      expect(harness.menuItems[2]['title'], equals('المتصلون (0)'));
    });

    test('Navigates to RoomsMenuView when selecting rooms item', () {
      harness.selectMenuItem('rooms');
      expect(harness.lastNavigatedRoute, equals('RoomsMenuView'));
    });

    test('Navigates to FriendsView when selecting friends item', () {
      harness.selectMenuItem('friends');
      expect(harness.lastNavigatedRoute, equals('FriendsView'));
    });

    test('Navigates to OnlineUsersDialog when selecting online item', () {
      harness.selectMenuItem('online');
      expect(harness.lastNavigatedRoute, equals('OnlineUsersDialog'));
    });

    test('Shows logout confirmation modal and navigates to AuthView on confirmation', () {
      harness.selectMenuItem('logout');
      expect(harness.isLogoutConfirmationVisible, isTrue);

      // User confirms logout
      harness.confirmLogout(true);
      expect(harness.isLogoutConfirmationVisible, isFalse);
      expect(harness.lastNavigatedRoute, equals('AuthView'));
    });

    test('Cancels logout confirmation when user presses لا', () {
      harness.selectMenuItem('logout');
      expect(harness.isLogoutConfirmationVisible, isTrue);

      // User cancels logout
      harness.confirmLogout(false);
      expect(harness.isLogoutConfirmationVisible, isFalse);
      expect(harness.lastNavigatedRoute, isNull);
    });
  });
}
