import 'package:flutter/material.dart';
import '../core/localization.dart';
import '../services/api_service.dart';
import 'auth_view.dart';

// Profile Edit Dialog matching MyProfileEditDialog
class MyProfileDialog extends StatefulWidget {
  final String userDisplayName;
  final VoidCallback? onProfileUpdated;

  const MyProfileDialog({
    super.key,
    required this.userDisplayName,
    this.onProfileUpdated,
  });

  @override
  State<MyProfileDialog> createState() => _MyProfileDialogState();
}

class _MyProfileDialogState extends State<MyProfileDialog> {
  final _nameController = TextEditingController();
  final _bioController = TextEditingController();
  String _gender = 'غير محدد';
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _nameController.text = widget.userDisplayName;
    _fetchProfile();
  }

  Future<void> _fetchProfile() async {
    setState(() => _isLoading = true);
    try {
      final res = await ApiService.instance.get('/api/auth/me');
      if (res is Map && mounted) {
        final u = res['user'] ?? res;
        _nameController.text = u['display_name'] ?? widget.userDisplayName;
        _bioController.text = u['bio'] ?? '';
        final g = u['gender'] ?? '';
        _gender = (g == 'male' || g == 'ذكر') ? 'ذكر' : ((g == 'female' || g == 'أنثى') ? 'أنثى' : 'غير محدد');
      }
    } catch (_) {}
    if (mounted) setState(() => _isLoading = false);
  }

  Future<void> _saveProfile() async {
    setState(() => _isLoading = true);
    try {
      await ApiService.instance.post('/api/users/me/profile', data: {
        'display_name': _nameController.text.trim(),
        'gender': _gender,
        'bio': _bioController.text.trim(),
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(tr('تم حفظ الملف الشخصي بنجاح'))),
        );
        widget.onProfileUpdated?.call();
        Navigator.of(context).pop();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(tr('تعذر حفظ الملف الشخصي'))),
        );
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _confirmDeleteAccount() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF2D2D2D),
        title: Text(tr('تأكيد حذف الحساب'), style: const TextStyle(color: Colors.white)),
        content: Text(
          tr('هل أنت متأكد تمامًا من رغبتك في حذف الحساب؟ لا يمكن التراجع عن هذا الإجراء.'),
          style: const TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: Text(tr('إلغاء'), style: const TextStyle(color: Colors.white70)),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.of(ctx).pop();
              try {
                await ApiService.instance.post('/api/users/me/delete');
              } catch (_) {}
              ApiService.instance.logout();
              if (mounted) {
                Navigator.of(context).pushAndRemoveUntil(
                  MaterialPageRoute(builder: (_) => const AuthView()),
                  (route) => false,
                );
              }
            },
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: Text(tr('حذف نهائي'), style: const TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF1E1E1E),
      appBar: AppBar(
        title: Text(tr('ملفي الشخصي')),
        backgroundColor: const Color(0xFF2D2D2D),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                TextField(
                  controller: _nameController,
                  style: const TextStyle(color: Colors.white),
                  decoration: InputDecoration(
                    labelText: tr('الاسم المستعار'),
                    labelStyle: const TextStyle(color: Colors.white70),
                    border: const OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 16),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(tr('الجنس'), style: const TextStyle(color: Colors.white)),
                  trailing: DropdownButton<String>(
                    value: _gender,
                    dropdownColor: const Color(0xFF2D2D2D),
                    style: const TextStyle(color: Colors.white),
                    items: [
                      DropdownMenuItem(value: 'ذكر', child: Text(tr('ذكر'))),
                      DropdownMenuItem(value: 'أنثى', child: Text(tr('أنثى'))),
                      DropdownMenuItem(value: 'غير محدد', child: Text(tr('غير محدد'))),
                    ],
                    onChanged: (v) {
                      if (v != null) setState(() => _gender = v);
                    },
                  ),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _bioController,
                  maxLines: 3,
                  style: const TextStyle(color: Colors.white),
                  decoration: InputDecoration(
                    labelText: tr('النبذة الشخصية'),
                    labelStyle: const TextStyle(color: Colors.white70),
                    border: const OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 24),
                ElevatedButton(
                  onPressed: _saveProfile,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.blueAccent,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                  child: Text(tr('حفظ'), style: const TextStyle(fontSize: 16, color: Colors.white)),
                ),
                const SizedBox(height: 24),
                const Divider(color: Colors.white24),
                ListTile(
                  leading: const Icon(Icons.delete_forever, color: Colors.red),
                  title: Text(tr('حذف الحساب'), style: const TextStyle(color: Colors.red)),
                  onTap: _confirmDeleteAccount,
                ),
              ],
            ),
    );
  }
}

// Notifications Dialog matching NotificationsView
class NotificationsDialog extends StatefulWidget {
  const NotificationsDialog({super.key});

  @override
  State<NotificationsDialog> createState() => _NotificationsDialogState();
}

class _NotificationsDialogState extends State<NotificationsDialog> {
  List<dynamic> _notifications = [];
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _fetchNotifications();
  }

  Future<void> _fetchNotifications() async {
    setState(() => _isLoading = true);
    try {
      final res = await ApiService.instance.get('/api/notifications');
      if (res is Map && res['notifications'] is List && mounted) {
        setState(() => _notifications = res['notifications']);
      } else if (res is List && mounted) {
        setState(() => _notifications = res);
      }
    } catch (_) {}
    if (mounted) setState(() => _isLoading = false);
  }

  Future<void> _handleInvitation(dynamic notif, bool accept) async {
    final invId = notif['invitation_id'] ?? (notif['payload'] ?? {})['invitation_id'] ?? notif['id'];
    try {
      if (accept) {
        await ApiService.instance.post('/api/invitations/$invId/accept');
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(tr('تم قبول الدعوة.'))),
          );
        }
      } else {
        await ApiService.instance.post('/api/invitations/$invId/reject');
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(tr('تم رفض الدعوة.'))),
          );
        }
      }
      _fetchNotifications();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(tr('تعذر معالجة الدعوة'))),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF1E1E1E),
      appBar: AppBar(
        title: Text(tr('الإشعارات')),
        backgroundColor: const Color(0xFF2D2D2D),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _notifications.isEmpty
              ? Center(
                  child: Text(
                    tr('لا توجد إشعارات جديدة.'),
                    style: const TextStyle(color: Colors.white54, fontSize: 16),
                  ),
                )
              : ListView.separated(
                  itemCount: _notifications.length,
                  separatorBuilder: (_, __) => const Divider(color: Colors.white24, height: 1),
                  itemBuilder: (context, idx) {
                    final item = _notifications[idx];
                    final text = item['text'] ?? item['title'] ?? item.toString();
                    final isInvitation = item['event_type'] == 'CHALLENGE_INVITATION' || item['type'] == 'invitation';

                    return ListTile(
                      title: Text(tr(text.toString()), style: const TextStyle(color: Colors.white)),
                      subtitle: isInvitation
                          ? Row(
                              children: [
                                ElevatedButton(
                                  onPressed: () => _handleInvitation(item, true),
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: Colors.green,
                                    padding: const EdgeInsets.symmetric(horizontal: 12),
                                  ),
                                  child: Text(tr('قبول'), style: const TextStyle(color: Colors.white)),
                                ),
                                const SizedBox(width: 8),
                                OutlinedButton(
                                  onPressed: () => _handleInvitation(item, false),
                                  style: OutlinedButton.styleFrom(
                                    foregroundColor: Colors.red,
                                    side: const BorderSide(color: Colors.red),
                                  ),
                                  child: Text(tr('رفض')),
                                ),
                              ],
                            )
                          : null,
                    );
                  },
                ),
    );
  }
}

// Contact Us Dialog matching _open_contact_dialog
class ContactUsDialog extends StatefulWidget {
  const ContactUsDialog({super.key});

  @override
  State<ContactUsDialog> createState() => _ContactUsDialogState();
}

class _ContactUsDialogState extends State<ContactUsDialog> {
  final _msgController = TextEditingController();
  bool _isSending = false;

  Future<void> _sendFeedback() async {
    final text = _msgController.text.trim();
    if (text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(tr('اكتب رسالتك أولًا.'))),
      );
      return;
    }

    setState(() => _isSending = true);
    try {
      await ApiService.instance.post('/api/feedback', data: {'message': text});
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(tr('تم إرسال رسالتك بنجاح.'))),
        );
        Navigator.of(context).pop();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(tr('تعذر إرسال الرسالة'))),
        );
      }
    } finally {
      if (mounted) setState(() => _isSending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF1E1E1E),
      appBar: AppBar(
        title: Text(tr('تحدث معنا')),
        backgroundColor: const Color(0xFF2D2D2D),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              tr('اكتب رسالتك لنا:'),
              style: const TextStyle(color: Colors.white, fontSize: 16),
            ),
            const SizedBox(height: 12),
            Expanded(
              child: TextField(
                controller: _msgController,
                maxLines: null,
                expands: true,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  hintText: tr('اكتب رسالتك هنا'),
                  hintStyle: const TextStyle(color: Colors.white38),
                  border: const OutlineInputBorder(),
                  filled: true,
                  fillColor: const Color(0xFF252526),
                ),
              ),
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _isSending ? null : _sendFeedback,
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.blueAccent,
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
              child: _isSending
                  ? const CircularProgressIndicator(color: Colors.white)
                  : Text(tr('إرسال'), style: const TextStyle(fontSize: 16, color: Colors.white)),
            ),
          ],
        ),
      ),
    );
  }
}
