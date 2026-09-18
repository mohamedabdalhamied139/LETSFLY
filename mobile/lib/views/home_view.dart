import 'dart:async';
import 'package:flutter/material.dart';
import '../core/app_theme.dart';
import '../core/localization.dart';
import '../services/activity_service.dart';
import '../services/api_service.dart';
import '../services/auth_storage_service.dart';
import '../services/ws_service.dart';
import 'auth_view.dart';
import 'friends_view.dart';
import 'rooms_menu_view.dart';
import 'settings_dialog.dart';
import 'social_dialogs.dart';
import 'online_users_dialog.dart';
import 'responsive_shell.dart';

class HomeView extends StatefulWidget {
  final String userDisplayName;

  const HomeView({super.key, required this.userDisplayName});

  @override
  State<HomeView> createState() => _HomeViewState();
}

class _HomeViewState extends State<HomeView> {
  int _onlineCount = 0;
  Timer? _pollingTimer;
  StreamSubscription<Map<String, dynamic>>? _wsSubscription;

  @override
  void initState() {
    super.initState();
    // Return greeting event on initState added to ActivityLogService
    ActivityLogService.instance.addEvent({
      'category': 'GAMEPLAY',
      'text': tr('مرحبًا بعودتك {name}.', {'name': widget.userDisplayName}),
      'time': '',
    });

    _fetchOnlineCount();
    _fetchRecentActivity();

    // Periodic polling every 30 seconds to keep online users count dynamic
    _pollingTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      if (mounted) _fetchOnlineCount();
    });

    // WebSocket real-time presence/online count listener
    _wsSubscription = WebSocketService.instance.messages.listen((msg) {
      final type = msg['type'] ?? msg['event'];
      if (type == 'online_count_updated' ||
          type == 'presence_updated' ||
          type == 'online_count') {
        final dynamic rawCount = msg['count'] ?? msg['data']?['count'];
        if (rawCount != null && mounted) {
          final int count = rawCount is int
              ? rawCount
              : (int.tryParse(rawCount.toString()) ?? 0);
          setState(() {
            _onlineCount = count < 0 ? 0 : count;
          });
        }
      }
    });
  }

  @override
  void dispose() {
    _pollingTimer?.cancel();
    _wsSubscription?.cancel();
    super.dispose();
  }

  Future<void> _fetchOnlineCount() async {
    try {
      final res = await ApiService.instance.getOnlineUsers();
      if (!mounted) return;
      if (res is List) {
        setState(() => _onlineCount = res.length);
      } else if (res is Map && res['count'] != null) {
        final int count = res['count'] is int
            ? res['count']
            : (int.tryParse(res['count'].toString()) ?? 0);
        setState(() => _onlineCount = count < 0 ? 0 : count);
      }
    } catch (_) {}
  }

  Future<void> _fetchRecentActivity() async {
    try {
      final res = await ApiService.instance.get('/api/activity?limit=50');
      if (res is Map && res['events'] is List && mounted) {
        final List<dynamic> evts = res['events'];
        for (final e in evts) {
          if (e is Map<String, dynamic>) {
            ActivityLogService.instance.addEvent(e);
          }
        }
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
        backgroundColor: AppColors.surface,
        title: Text(
          tr('تأكيد تسجيل الخروج'),
          style: const TextStyle(color: AppColors.textPrimary),
        ),
        content: Text(
          tr('هل أنت متأكد من تسجيل الخروج؟'),
          style: const TextStyle(color: AppColors.textSecondary),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: Text(
              tr('لا'),
              style: const TextStyle(color: AppColors.textSecondary),
            ),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.of(ctx).pop();
              try {
                await ApiService.instance.logout();
              } catch (_) {}
              await AuthStorageService.instance.clearActiveSession();
              ApiService.instance.setToken(null);
              if (mounted) {
                Navigator.of(context).pushAndRemoveUntil(
                  MaterialPageRoute(builder: (_) => const AuthView()),
                  (route) => false,
                );
              }
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.red,
            ),
            child: Text(
              tr('نعم'),
              style: const TextStyle(color: Colors.white),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    // Exact 8 canonical items in Windows order with exact tags
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

    return ResponsiveShell(
      title: tr('القائمة الرئيسية'),
      child: ListView.separated(
        padding: const EdgeInsets.symmetric(vertical: 8),
        itemCount: menuItems.length,
        separatorBuilder: (_, __) =>
            const Divider(height: 1, color: AppColors.border),
        itemBuilder: (context, index) {
          final item = menuItems[index];
          final rawTitle = item['title'] as String;
          final title = tr(rawTitle);
          final tag = item['tag'] as String;

          return Semantics(
            label: title,
            button: true,
            child: ListTile(
              tileColor: AppColors.surface,
              title: Text(
                title,
                style: const TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 17,
                  color: AppColors.textPrimary,
                ),
              ),
              trailing: const Icon(
                Icons.arrow_forward_ios,
                size: 14,
                color: AppColors.textSecondary,
              ),
              onTap: () => _onMenuSelected(tag),
            ),
          );
        },
      ),
    );
  }
}
