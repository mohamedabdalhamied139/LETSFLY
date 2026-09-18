import 'package:flutter/material.dart';
import '../core/localization.dart';
import '../services/api_service.dart';

class OnlineUsersDialog extends StatefulWidget {
  const OnlineUsersDialog({super.key});

  @override
  State<OnlineUsersDialog> createState() => _OnlineUsersDialogState();
}

class _OnlineUsersDialogState extends State<OnlineUsersDialog> {
  final _searchController = TextEditingController();
  List<dynamic> _users = [];
  List<dynamic> _filteredUsers = [];
  bool _isLoading = false;
  String _sortMode = 'alpha'; // 'alpha', 'oldest', 'newest'

  @override
  void initState() {
    super.initState();
    _fetchOnlineUsers();
  }

  Future<void> _fetchOnlineUsers() async {
    setState(() => _isLoading = true);
    try {
      final res = await ApiService.instance.getOnlineUsers();
      if (res is List && mounted) {
        setState(() {
          _users = res;
          _applyFilterAndSort();
        });
      }
    } catch (_) {}
    if (mounted) setState(() => _isLoading = false);
  }

  void _applyFilterAndSort() {
    final query = _searchController.text.trim().toLowerCase();
    List<dynamic> list = List.from(_users);

    if (query.isNotEmpty) {
      list = list.where((u) {
        final name = (u['display_name'] ?? u['username'] ?? '').toString().toLowerCase();
        return name.contains(query);
      }).toList();
    }

    if (_sortMode == 'alpha') {
      list.sort((a, b) {
        final na = (a['display_name'] ?? a['username'] ?? '').toString();
        final nb = (b['display_name'] ?? b['username'] ?? '').toString();
        return na.compareTo(nb);
      });
    }

    setState(() => _filteredUsers = list);
  }

  void _showUserActions(dynamic user) {
    final name = user['display_name'] ?? user['username'] ?? 'لاعب';
    final uid = user['id'];

    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF2D2D2D),
      builder: (ctx) => Container(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              '${tr('إجراءات')} $name',
              style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            ListTile(
              leading: const Icon(Icons.person, color: Colors.white),
              title: Text(tr('الملف الشخصي'), style: const TextStyle(color: Colors.white)),
              onTap: () {
                Navigator.of(ctx).pop();
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('${tr('الملف الشخصي لـ')} $name')),
                );
              },
            ),
            ListTile(
              leading: const Icon(Icons.person_add, color: Colors.blueAccent),
              title: Text(tr('إرسال طلب صداقة'), style: const TextStyle(color: Colors.white)),
              onTap: () async {
                Navigator.of(ctx).pop();
                try {
                  if (uid != null) {
                    await ApiService.instance.sendFriendRequest(uid is int ? uid : int.parse(uid.toString()));
                    if (mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(content: Text(tr('تم إرسال طلب الصداقة.'))),
                      );
                    }
                  }
                } catch (_) {}
              },
            ),
            ListTile(
              leading: const Icon(Icons.message, color: Colors.green),
              title: Text(tr('إرسال رسالة خاصة'), style: const TextStyle(color: Colors.white)),
              onTap: () {
                Navigator.of(ctx).pop();
                _showPrivateMessageInput(uid, name);
              },
            ),
          ],
        ),
      ),
    );
  }

  void _showPrivateMessageInput(dynamic uid, String name) {
    final msgCtrl = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF2D2D2D),
        title: Text(tr('إرسال رسالة إلى {name}', {'name': name}), style: const TextStyle(color: Colors.white)),
        content: TextField(
          controller: msgCtrl,
          style: const TextStyle(color: Colors.white),
          decoration: InputDecoration(
            hintText: tr('اكتب رسالتك:'),
            hintStyle: const TextStyle(color: Colors.white38),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: Text(tr('إلغاء'), style: const TextStyle(color: Colors.white70)),
          ),
          ElevatedButton(
            onPressed: () async {
              final txt = msgCtrl.text.trim();
              if (txt.isNotEmpty && uid != null) {
                Navigator.of(ctx).pop();
                try {
                  await ApiService.instance.post('/api/users/$uid/messages', data: {'message': txt});
                  if (mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text(tr('تم إرسال الرسالة.'))),
                    );
                  }
                } catch (_) {}
              }
            },
            child: Text(tr('إرسال')),
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
        title: Text(tr('البحث عن لاعبين')),
        backgroundColor: const Color(0xFF2D2D2D),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12.0),
            child: TextField(
              controller: _searchController,
              style: const TextStyle(color: Colors.white),
              decoration: InputDecoration(
                hintText: tr('اكتب اسم المستخدم للبحث'),
                hintStyle: const TextStyle(color: Colors.white38),
                prefixIcon: const Icon(Icons.search, color: Colors.white54),
                border: const OutlineInputBorder(),
                filled: true,
                fillColor: const Color(0xFF252526),
              ),
              onChanged: (_) => _applyFilterAndSort(),
            ),
          ),
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _filteredUsers.isEmpty
                    ? Center(
                        child: Text(
                          tr('لا يوجد لاعبين متطابقين.'),
                          style: const TextStyle(color: Colors.white54),
                        ),
                      )
                    : ListView.separated(
                        itemCount: _filteredUsers.length,
                        separatorBuilder: (_, __) => const Divider(color: Colors.white24, height: 1),
                        itemBuilder: (context, idx) {
                          final u = _filteredUsers[idx];
                          final name = u['display_name'] ?? u['username'] ?? 'لاعب';

                          return ListTile(
                            leading: const CircleAvatar(
                              backgroundColor: Colors.green,
                              radius: 16,
                              child: Icon(Icons.person, color: Colors.white, size: 18),
                            ),
                            title: Text(name, style: const TextStyle(color: Colors.white)),
                            subtitle: Text(
                              u['username'] ?? '',
                              style: const TextStyle(color: Colors.white38),
                            ),
                            onTap: () => _showUserActions(u),
                          );
                        },
                      ),
          ),
        ],
      ),
    );
  }
}
