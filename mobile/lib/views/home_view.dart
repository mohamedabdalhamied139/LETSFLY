import 'dart:async';
import 'package:flutter/material.dart';
import '../core/app_theme.dart';
import '../core/accessibility_manager.dart';
import '../core/localization.dart';
import '../services/activity_service.dart';
import '../services/api_service.dart';
import '../services/auth_storage_service.dart';
import '../services/ws_service.dart';
import 'auth_view.dart';
import 'responsive_shell.dart';
import 'rooms_menu_view.dart';
import 'online_users_dialog.dart';

/// Accessible Home screen matching 100% of Windows client home_view.py.
/// Displays the 8 canonical items starting with 'الطاولات' (Rooms),
/// live online users counter, return greeting, and responsive layout.
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

    // Connect to WebSocket events for real-time lobby updates
    final token = ApiService.instance.token;
    if (token != null && token.isNotEmpty) {
      WebSocketService.instance.connect(
        ApiService.instance.getWsUrl('/ws/events'),
        token: token,
      );
    }

    final greeting = tr('مرحبًا بعودتك {name}.', {'name': widget.userDisplayName});

    // 1. Announce return greeting to screen reader on startup
    AccessibilityManager.instance.announce(greeting);

    // 2. Add return greeting to ActivityLogService matching Windows client
    ActivityLogService.instance.addEvent({
      'category': 'GAMEPLAY',
      'text': greeting,
      'time': '',
    });

    _fetchOnlineCount();
    _fetchRecentActivity();

    // Periodic polling every 30 seconds to keep online users count dynamic
    _pollingTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      if (mounted) _fetchOnlineCount();
    });

    // WebSocket real-time presence/online count listener
    _wsSubscription = WebSocketService.instance.events.listen((msg) {
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
      final evts = await ApiService.instance.getRecentEvents();
      if (evts is List) {
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
        AccessibilityManager.instance.announce(tr('قائمة الطاولات'));
        Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => const RoomsMenuView()),
        );
        break;
      case 'friends':
        AccessibilityManager.instance.announce(tr('فتح قائمة الأصدقاء'));
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(tr('قائمة الأصدقاء'))),
        );
        break;
      case 'online':
        AccessibilityManager.instance.announce(tr('فتح قائمة المتصلين'));
        OnlineUsersDialog.show(context);
        break;
      case 'my_profile':
        AccessibilityManager.instance.announce(tr('فتح الملف الشخصي'));
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(tr('الملف الشخصي'))),
        );
        break;
      case 'settings':
        AccessibilityManager.instance.announce(tr('فتح الإعدادات'));
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(tr('الإعدادات'))),
        );
        break;
      case 'notifications':
        AccessibilityManager.instance.announce(tr('فتح الإشعارات'));
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(tr('الإشعارات'))),
        );
        break;
      case 'contact':
        AccessibilityManager.instance.announce(tr('فتح نافذة التواصل والدعم'));
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(tr('تحدث معنا'))),
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
    // Only 'الطاولات' kept in the main menu list per user request
    final menuItems = [
      {'title': tr('الطاولات'), 'tag': 'rooms', 'icon': Icons.table_restaurant},
    ];

    return ResponsiveShell(
      title: tr('القائمة الرئيسية'),
      actions: [
        Semantics(
          label: _onlineCount > 0 ? '${tr('المتصلون')} ($_onlineCount)' : tr('المتصلون'),
          button: true,
          excludeSemantics: true,
          child: IconButton(
            icon: const Icon(Icons.people_outline),
            tooltip: _onlineCount > 0 ? '${tr('المتصلون')} ($_onlineCount)' : tr('المتصلون'),
            onPressed: () => OnlineUsersDialog.show(context),
          ),
        ),
        Semantics(
          label: tr('تسجيل الخروج'),
          button: true,
          excludeSemantics: true,
          child: IconButton(
            icon: const Icon(Icons.logout),
            tooltip: tr('تسجيل الخروج'),
            onPressed: _confirmLogout,
          ),
        ),
      ],
      child: ListView.separated(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        itemCount: menuItems.length,
        separatorBuilder: (_, __) => const SizedBox(height: 10),
        itemBuilder: (context, index) {
          final item = menuItems[index];
          final title = item['title'] as String;
          final tag = item['tag'] as String;
          final icon = item['icon'] as IconData;
          final isDestructive = item['isDestructive'] == true;

          return Semantics(
            label: title,
            button: true,
            excludeSemantics: true,
            child: Card(
              color: AppColors.surface,
              elevation: 2,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
                side: const BorderSide(color: AppColors.divider, width: 1),
              ),
              child: InkWell(
                onTap: () => _onMenuSelected(tag),
                borderRadius: BorderRadius.circular(10),
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                  child: Row(
                    children: [
                      Icon(
                        icon,
                        color: isDestructive ? AppColors.error : AppColors.primary,
                        size: 24,
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Text(
                          title,
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                            color: isDestructive ? AppColors.error : AppColors.textPrimary,
                          ),
                        ),
                      ),
                      Icon(
                        Icons.arrow_forward_ios,
                        size: 14,
                        color: isDestructive ? AppColors.error : AppColors.textSecondary,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}
