import 'package:flutter/material.dart';
import '../core/app_theme.dart';
import '../core/localization.dart';
import '../core/accessibility_manager.dart';
import '../core/sound_service.dart';
import '../services/api_service.dart';
import '../services/auth_storage_service.dart';
import '../views/auth_view.dart';
import '../views/online_users_dialog.dart';

/// Universal Navigation Drawer available everywhere in the game.
/// Hosts all canonical Home screen items (excluding Tables which is the primary screen).
class AppNavigationDrawer extends StatefulWidget {
  const AppNavigationDrawer({super.key});

  @override
  State<AppNavigationDrawer> createState() => _AppNavigationDrawerState();
}

class _AppNavigationDrawerState extends State<AppNavigationDrawer> {
  String _displayName = 'محمد';
  int _onlineCount = 0;

  @override
  void initState() {
    super.initState();
    _loadUserInfo();
    _fetchOnlineCount();
  }

  Future<void> _loadUserInfo() async {
    final user = await AuthStorageService.instance.getActiveUser();
    if (user != null && mounted) {
      setState(() => _displayName = user.displayName);
    }
  }

  Future<void> _fetchOnlineCount() async {
    try {
      final res = await ApiService.instance.getOnlineUsers();
      if (res is Map && res['count'] != null) {
        if (mounted) {
          setState(() => _onlineCount = int.tryParse(res['count'].toString()) ?? 0);
        }
      } else if (res is List) {
        if (mounted) {
          setState(() => _onlineCount = res.length);
        }
      }
    } catch (_) {}
  }

  void _onItemTapped(String tag) {
    Navigator.of(context).pop(); // Close drawer first

    switch (tag) {
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
            child: Text(tr('لا'), style: const TextStyle(color: AppColors.textSecondary)),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.of(ctx).pop();
              try {
                await ApiService.instance.logout();
              } catch (_) {}
              await AuthStorageService.instance.clearActiveSession();
              ApiService.instance.setToken(null);
              SoundService.instance.playSound('PLAYER_LEFT');
              if (mounted) {
                Navigator.of(context).pushAndRemoveUntil(
                  MaterialPageRoute(builder: (_) => const AuthView()),
                  (route) => false,
                );
              }
            },
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.error),
            child: Text(tr('نعم'), style: const TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    // Exact canonical items from Home screen in exact order (omitting 'rooms')
    final menuItems = [
      {'title': tr('الأصدقاء'), 'tag': 'friends', 'icon': Icons.people},
      {
        'title': _onlineCount > 0 ? '${tr('المتصلون')} ($_onlineCount)' : tr('المتصلون'),
        'tag': 'online',
        'icon': Icons.circle,
        'iconColor': Colors.green,
      },
      {'title': tr('ملفي الشخصي'), 'tag': 'my_profile', 'icon': Icons.person},
      {'title': tr('الإعدادات'), 'tag': 'settings', 'icon': Icons.settings},
      {'title': tr('الإشعارات'), 'tag': 'notifications', 'icon': Icons.notifications},
      {'title': tr('تحدث معنا'), 'tag': 'contact', 'icon': Icons.headset_mic},
      {'title': tr('تسجيل الخروج'), 'tag': 'logout', 'icon': Icons.logout, 'isDestructive': true},
    ];

    return Drawer(
      backgroundColor: AppColors.surface,
      child: SafeArea(
        child: Column(
          children: [
            // Drawer Header with Player Greeting & Online status
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
              decoration: const BoxDecoration(
                color: AppColors.header,
                border: Border(bottom: BorderSide(color: AppColors.divider, width: 1)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  CircleAvatar(
                    radius: 28,
                    backgroundColor: AppColors.primary,
                    child: Text(
                      _displayName.isNotEmpty ? _displayName[0].toUpperCase() : 'U',
                      style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Colors.white),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    _displayName,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      const Icon(Icons.circle, color: Colors.green, size: 10),
                      const SizedBox(width: 6),
                      Text(
                        '$_onlineCount ${tr('لاعب متصل الآن')}',
                        style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
                      ),
                    ],
                  ),
                ],
              ),
            ),

            // Navigation Items List
            Expanded(
              child: ListView.separated(
                padding: const EdgeInsets.symmetric(vertical: 8),
                itemCount: menuItems.length,
                separatorBuilder: (_, __) => const Divider(color: AppColors.divider, height: 1),
                itemBuilder: (ctx, idx) {
                  final item = menuItems[idx];
                  final isDestructive = item['isDestructive'] == true;

                  return ListTile(
                    leading: Icon(
                      item['icon'] as IconData,
                      color: isDestructive
                          ? AppColors.error
                          : (item['iconColor'] as Color? ?? AppColors.textSecondary),
                    ),
                    title: Text(
                      item['title'] as String,
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w500,
                        color: isDestructive ? AppColors.error : AppColors.textPrimary,
                      ),
                    ),
                    onTap: () => _onItemTapped(item['tag'] as String),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
