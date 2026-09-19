import 'package:flutter/material.dart';
import '../core/app_theme.dart';
import '../core/localization.dart';
import '../core/sound_service.dart';
import '../core/accessibility_manager.dart';
import '../services/api_service.dart';

/// Online users view dialog matching Windows OnlineUsersView (Ctrl+W).
/// Accessible keyboard/TalkBack friendly list of online users with search.
class OnlineUsersDialog extends StatefulWidget {
  const OnlineUsersDialog({super.key});

  static Future<void> show(BuildContext context) {
    return showDialog(
      context: context,
      builder: (ctx) => const OnlineUsersDialog(),
    );
  }

  @override
  State<OnlineUsersDialog> createState() => _OnlineUsersDialogState();
}

class _OnlineUsersDialogState extends State<OnlineUsersDialog> {
  final TextEditingController _searchController = TextEditingController();
  List<dynamic> _allUsers = [];
  List<dynamic> _filteredUsers = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _fetchOnlineUsers();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _fetchOnlineUsers() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final res = await ApiService.instance.getOnlineUsers();
      List<dynamic> users = [];
      if (res is List) {
        users = res;
      } else if (res is Map && res['users'] is List) {
        users = res['users'] as List;
      }

      if (mounted) {
        setState(() {
          _allUsers = users;
          _filteredUsers = users;
          _loading = false;
        });
        AccessibilityManager.instance.announce(
          tr('تم تحميل {count} لاعب متصل.', {'count': '${users.length}'}),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString();
          _loading = false;
        });
        SoundService.instance.playSound('INVALID_ACTION');
        AccessibilityManager.instance.announce(
          tr('تعذر تحميل المتصلين: {error}', {'error': e.toString()}),
        );
      }
    }
  }

  void _onSearchChanged(String query) {
    final cleanQuery = query.trim().toLowerCase();
    setState(() {
      if (cleanQuery.isEmpty) {
        _filteredUsers = _allUsers;
      } else {
        _filteredUsers = _allUsers.where((u) {
          final name = (u['display_name'] ?? u['username'] ?? '').toString().toLowerCase();
          return name.contains(cleanQuery);
        }).toList();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      backgroundColor: AppColors.surface,
      title: Text(
        tr('المتصلون ({count})', {'count': '${_filteredUsers.length}'}),
        style: const TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold),
      ),
      content: SizedBox(
        width: double.maxFinite,
        height: 400,
        child: Column(
          children: [
            TextField(
              controller: _searchController,
              onChanged: _onSearchChanged,
              decoration: InputDecoration(
                hintText: tr('اكتب اسم المستخدم للبحث'),
                prefixIcon: const Icon(Icons.search, color: AppColors.textSecondary),
                filled: true,
                fillColor: AppColors.surfaceLight,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide: BorderSide.none,
                ),
                contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              ),
            ),
            const SizedBox(height: 12),
            Expanded(
              child: _loading
                  ? const Center(child: CircularProgressIndicator(color: AppColors.primary))
                  : _error != null
                      ? Center(
                          child: Text(
                            tr('تعذر تحميل المتصلين: {error}', {'error': _error!}),
                            style: const TextStyle(color: AppColors.error),
                          ),
                        )
                      : _filteredUsers.isEmpty
                          ? Center(
                              child: Text(
                                tr('لا يوجد لاعبون متصلون حاليًا.'),
                                style: const TextStyle(color: AppColors.textSecondary),
                              ),
                            )
                          : ListView.separated(
                              itemCount: _filteredUsers.length,
                              separatorBuilder: (_, __) => const Divider(color: AppColors.divider, height: 1),
                              itemBuilder: (ctx, idx) {
                                final user = _filteredUsers[idx];
                                final name = (user['display_name'] ?? user['username'] ?? tr('لاعب')).toString();
                                final isFriend = user['is_friend'] == true;

                                return ListTile(
                                  leading: const Icon(Icons.person, color: AppColors.primary),
                                  title: Text(
                                    name,
                                    style: const TextStyle(color: AppColors.textPrimary, fontSize: 16),
                                  ),
                                  subtitle: isFriend
                                      ? Text(tr('صديق'), style: const TextStyle(color: AppColors.success, fontSize: 12))
                                      : null,
                                  onTap: () {
                                    AccessibilityManager.instance.announce(name);
                                  },
                                );
                              },
                            ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: Text(tr('إغلاق'), style: const TextStyle(color: AppColors.primary)),
        ),
      ],
    );
  }
}
