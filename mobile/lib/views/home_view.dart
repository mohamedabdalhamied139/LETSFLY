import 'package:flutter/material.dart';
import '../core/localization.dart';
import '../services/api_service.dart';
import 'auth_view.dart';
import 'friends_view.dart';
import 'rooms_menu_view.dart';
import 'activity_log_widget.dart';
import 'settings_dialog.dart';
import 'social_dialogs.dart';
import 'online_users_dialog.dart';

class HomeView extends StatefulWidget {
  final String userDisplayName;

  const HomeView({super.key, required this.userDisplayName});

  @override
  State<HomeView> createState() => _HomeViewState();
}

class _HomeViewState extends State<HomeView> {
  int _onlineCount = 0;
  final List<Map<String, dynamic>> _activityEvents = [];

  @override
  void initState() {
    super.initState();
    // Rule: "مرحبًا بعودتك {name}" must be recorded as an event inside Activity Log, NOT a separate screen banner.
    _activityEvents.add({
      'text': tr('مرحبًا بعودتك {name}.', {'name': widget.userDisplayName}),
      'category': 'GAMEPLAY',
      'time': '',
    });
    _fetchOnlineCount();
    _fetchRecentActivity();
  }

  Future<void> _fetchOnlineCount() async {
    try {
      final res = await ApiService.instance.getOnlineUsers();
      if (res is List && mounted) {
        setState(() => _onlineCount = res.length);
      }
    } catch (_) {}
  }

  Future<void> _fetchRecentActivity() async {
    try {
      final res = await ApiService.instance.get('/api/activity?limit=50');
      if (res is Map && res['events'] is List && mounted) {
        final List<dynamic> evts = res['events'];
        setState(() {
          for (final e in evts) {
            if (e is Map<String, dynamic>) {
              _activityEvents.add(e);
            }
          }
        });
      }
    } catch (_) {}
  }

  void _onMenuSelected(String tag) {
    switch (tag) {
      case 'rooms':
        Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => const RoomsMenuView()),
        );
        break;
      case 'friends':
        Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => const FriendsView()),
        );
        break;
      case 'online':
        Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => const OnlineUsersDialog()),
        );
        break;
      case 'my_profile':
        Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => MyProfileDialog(
              userDisplayName: widget.userDisplayName,
              onProfileUpdated: () {
                setState(() {});
              },
            ),
          ),
        );
        break;
      case 'settings':
        Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => const SettingsDialog()),
        );
        break;
      case 'notifications':
        Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => const NotificationsDialog()),
        );
        break;
      case 'contact':
        Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => const ContactUsDialog()),
        );
        break;
      case 'logout':
        _confirmLogout();
        break;
    }
  }

  void _confirmLogout() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF2D2D2D),
        title: Text(tr('تأكيد تسجيل الخروج'), style: const TextStyle(color: Colors.white)),
        content: Text(
          tr('هل أنت متأكد من تسجيل الخروج؟'),
          style: const TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: Text(tr('لا'), style: const TextStyle(color: Colors.white70)),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.of(ctx).pop();
              ApiService.instance.logout();
              Navigator.of(context).pushReplacement(
                MaterialPageRoute(builder: (_) => const AuthView()),
              );
            },
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: Text(tr('نعم'), style: const TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    // Exact 8 canonical items from Windows client (client/views/home_view.py)
    final menuItems = [
      {'title': 'الطاولات', 'tag': 'rooms'},
      {'title': 'الأصدقاء', 'tag': 'friends'},
      {'title': 'المتصلون ($_onlineCount)', 'tag': 'online'},
      {'title': 'ملفي الشخصي', 'tag': 'my_profile'},
      {'title': 'الإعدادات', 'tag': 'settings'},
      {'title': 'الإشعارات', 'tag': 'notifications'},
      {'title': 'تحدث معنا', 'tag': 'contact'},
      {'title': 'تسجيل الخروج', 'tag': 'logout'},
    ];

    return Scaffold(
      backgroundColor: const Color(0xFF1E1E1E),
      appBar: AppBar(
        title: Text(tr('القائمة الرئيسية')),
        backgroundColor: const Color(0xFF2D2D2D),
        centerTitle: false,
      ),
      body: Column(
        children: [
          // 8 Canonical Menu Items matching Windows
          Expanded(
            flex: 6,
            child: ListView.separated(
              itemCount: menuItems.length,
              separatorBuilder: (_, __) => const Divider(height: 1, color: Color(0xFF333333)),
              itemBuilder: (context, index) {
                final item = menuItems[index];
                final title = tr(item['title'] as String);
                final tag = item['tag'] as String;

                return Semantics(
                  button: true,
                  label: title,
                  child: ListTile(
                    tileColor: const Color(0xFF252526),
                    title: Text(
                      title,
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 17,
                        color: Colors.white,
                      ),
                    ),
                    trailing: const Icon(Icons.arrow_forward_ios, size: 14, color: Colors.white54),
                    onTap: () => _onMenuSelected(tag),
                  ),
                );
              },
            ),
          ),
          // Canonical Activity Log panel at the bottom, matching Windows layout
          Expanded(
            flex: 4,
            child: ActivityLogWidget(
              events: _activityEvents,
              onCategoryChanged: (cat) {
                // optionally fetch per category
              },
            ),
          ),
        ],
      ),
    );
  }
}
