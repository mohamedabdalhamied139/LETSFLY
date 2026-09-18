import 'package:flutter/material.dart';
import '../core/localization.dart';
import '../services/api_service.dart';
import 'auth_view.dart';
import 'friends_view.dart';
import 'rooms_menu_view.dart';

class HomeView extends StatefulWidget {
  final String userDisplayName;

  const HomeView({super.key, required this.userDisplayName});

  @override
  State<HomeView> createState() => _HomeViewState();
}

class _HomeViewState extends State<HomeView> {
  int _onlineCount = 0;
  final List<String> _activityEvents = [];

  @override
  void initState() {
    super.initState();
    _fetchOnlineCount();
  }

  Future<void> _fetchOnlineCount() async {
    try {
      final res = await ApiService.instance.getOnlineUsers();
      if (res is List && mounted) {
        setState(() => _onlineCount = res.length);
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
      case 'online':
        Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => const FriendsView()),
        );
        break;
      case 'logout':
        ApiService.instance.logout();
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const AuthView()),
        );
        break;
      case 'my_profile':
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('${tr('ملفي الشخصي')}: ${widget.userDisplayName}')),
        );
        break;
      default:
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(tr('قريبًا...'))),
        );
        break;
    }
  }

  @override
  Widget build(BuildContext context) {
    final menuItems = [
      {'title': 'الطاولات', 'tag': 'rooms', 'icon': Icons.table_restaurant},
      {'title': 'الأصدقاء', 'tag': 'friends', 'icon': Icons.people},
      {'title': 'المتصلون ($_onlineCount)', 'tag': 'online', 'icon': Icons.circle, 'color': Colors.green},
      {'title': 'ملفي الشخصي', 'tag': 'my_profile', 'icon': Icons.account_circle},
      {'title': 'الإعدادات', 'tag': 'settings', 'icon': Icons.settings},
      {'title': 'الإشعارات', 'tag': 'notifications', 'icon': Icons.notifications},
      {'title': 'تحدث معنا', 'tag': 'contact', 'icon': Icons.support_agent},
      {'title': 'تسجيل الخروج', 'tag': 'logout', 'icon': Icons.exit_to_app, 'color': Colors.red},
    ];

    return Scaffold(
      appBar: AppBar(
        title: Text(tr('مرحبًا بعودتك {name}.', {'name': widget.userDisplayName})),
        centerTitle: false,
      ),
      body: Column(
        children: [
          // Greeting Banner
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            color: Theme.of(context).colorScheme.surfaceVariant,
            child: Semantics(
              header: true,
              label: tr('عنوان القائمة الرئيسية'),
              child: Text(
                tr('القائمة الرئيسية'),
                style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              ),
            ),
          ),
          // 8 Canonical Menu Items (Exact match to Windows client)
          Expanded(
            child: ListView.separated(
              itemCount: menuItems.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (context, index) {
                final item = menuItems[index];
                final title = tr(item['title'] as String);
                final tag = item['tag'] as String;
                final icon = item['icon'] as IconData;
                final color = item['color'] as Color?;

                return Semantics(
                  button: true,
                  label: title,
                  hint: tr('انقر مرتين لفتح هذا القسم'),
                  child: ListTile(
                    leading: Icon(icon, color: color ?? Theme.of(context).colorScheme.primary),
                    title: Text(
                      title,
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 18,
                        color: color,
                      ),
                    ),
                    trailing: const Icon(Icons.arrow_forward_ios, size: 16),
                    onTap: () => _onMenuSelected(tag),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
