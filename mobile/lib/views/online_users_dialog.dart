import 'dart:async';
import 'package:flutter/material.dart';
import '../core/localization.dart';
import '../services/api_service.dart';
import 'table_view.dart';

class OnlineUsersDialog extends StatefulWidget {
  final String? currentRoomId;

  const OnlineUsersDialog({super.key, this.currentRoomId});

  @override
  State<OnlineUsersDialog> createState() => _OnlineUsersDialogState();
}

class _OnlineUsersDialogState extends State<OnlineUsersDialog> {
  final _searchController = TextEditingController();
  List<Map<String, dynamic>> _users = [];
  List<Map<String, dynamic>> _displayUsers = [];
  bool _isLoading = false;
  String _sortMode = 'alpha'; // 'alpha', 'oldest', 'newest'
  Timer? _debounceTimer;

  static const Map<String, String> _gameLabels = {
    'UNO': 'أونو',
    'DOMINO': 'دومينو كلاسيك',
    'AMERICAN_DOMINO': 'دومينو أمريكاني',
    'FARKLE': 'فاركل',
    'SCOPA': 'إسكوبا',
    'NINETY_NINE': 'تسعة وتسعون',
    'SNAKES_LADDERS': 'السلم والثعبان',
    'THIEF_HUNT': 'مطاردة اللص',
    'TENNIS': 'التنس',
  };

  @override
  void initState() {
    super.initState();
    _fetchOnlineUsers();
  }

  @override
  void dispose() {
    _debounceTimer?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _fetchOnlineUsers() async {
    setState(() => _isLoading = true);
    try {
      final res = await ApiService.instance.getOnlineUsers();
      if (res is List && mounted) {
        setState(() {
          _users = res.map((e) => Map<String, dynamic>.from(e as Map)).toList();
          _applySort();
        });
      }
    } catch (_) {}
    if (mounted) setState(() => _isLoading = false);
  }

  void _onSearchChanged(String text) {
    _debounceTimer?.cancel();
    _debounceTimer = Timer(const Duration(milliseconds: 350), () {
      _executeSearch(text.trim());
    });
  }

  Future<void> _executeSearch(String query) async {
    if (query.isEmpty) {
      _applySort();
      return;
    }

    setState(() => _isLoading = true);
    try {
      final res = await ApiService.instance.searchUsers(query);
      if (res is Map && res['users'] is List && mounted) {
        setState(() {
          _displayUsers = (res['users'] as List)
              .map((e) => Map<String, dynamic>.from(e as Map))
              .toList();
          _sortList(_displayUsers);
        });
      }
    } catch (_) {
      // Fallback to local filter
      if (mounted) {
        final q = query.toLowerCase();
        final filtered = _users.where((u) {
          final n = (u['display_name'] ?? u['username'] ?? '').toString().toLowerCase();
          return n.contains(q);
        }).toList();
        setState(() {
          _displayUsers = List.from(filtered);
          _sortList(_displayUsers);
        });
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _applySort() {
    final list = List<Map<String, dynamic>>.from(_users);
    _sortList(list);
    setState(() => _displayUsers = list);
  }

  void _sortList(List<Map<String, dynamic>> list) {
    if (_sortMode == 'alpha') {
      list.sort((a, b) {
        final na = (a['display_name'] ?? a['username'] ?? '').toString();
        final nb = (b['display_name'] ?? b['username'] ?? '').toString();
        return na.compareTo(nb);
      });
    } else if (_sortMode == 'newest') {
      list.sort((a, b) {
        final ta = double.tryParse((a['connected_at'] ?? 0).toString()) ?? 0;
        final tb = double.tryParse((b['connected_at'] ?? 0).toString()) ?? 0;
        return tb.compareTo(ta);
      });
    } else if (_sortMode == 'oldest') {
      list.sort((a, b) {
        final ta = double.tryParse((a['connected_at'] ?? 0).toString()) ?? 0;
        final tb = double.tryParse((b['connected_at'] ?? 0).toString()) ?? 0;
        return ta.compareTo(tb);
      });
    }
  }

  void _showUserActions(Map<String, dynamic> user) {
    final name = (user['display_name'] ?? user['username'] ?? 'لاعب').toString();
    final uid = int.tryParse((user['id'] ?? 0).toString()) ?? 0;
    final isFriend = user['is_friend'] == true;
    final hasPending = user['has_pending_request'] == true;
    final inTable = user['in_table'] == true;
    final isPrivate = user['room_private'] == true;
    final userRoomId = user['room_id']?.toString();
    final canInvite = widget.currentRoomId != null && widget.currentRoomId!.isNotEmpty;

    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF2D2D2D),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(vertical: 12),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: Text(
                  '${tr('إجراءات')} $name',
                  style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                ),
              ),
              const Divider(color: Colors.white24),

              // 1. Profile
              ListTile(
                leading: const Icon(Icons.account_circle, color: Colors.white),
                title: Text(tr('زيارة الملف الشخصي'), style: const TextStyle(color: Colors.white)),
                onTap: () {
                  Navigator.of(ctx).pop();
                  _showProfileDialog(uid, name);
                },
              ),

              // 2. Add / Cancel Friend Request
              if (isFriend)
                ListTile(
                  leading: const Icon(Icons.check, color: Colors.green),
                  title: Text(tr('اللاعب صديق بالفعل'), style: const TextStyle(color: Colors.white54)),
                  enabled: false,
                )
              else if (hasPending)
                ListTile(
                  leading: const Icon(Icons.person_remove, color: Colors.orangeAccent),
                  title: Text(tr('إلغاء طلب الصداقة'), style: const TextStyle(color: Colors.white)),
                  onTap: () async {
                    Navigator.of(ctx).pop();
                    try {
                      await ApiService.instance.cancelFriendRequestToUser(uid);
                      _fetchOnlineUsers();
                    } catch (_) {}
                  },
                )
              else
                ListTile(
                  leading: const Icon(Icons.person_add, color: Colors.greenAccent),
                  title: Text(tr('إضافة صديق'), style: const TextStyle(color: Colors.white)),
                  onTap: () async {
                    Navigator.of(ctx).pop();
                    try {
                      await ApiService.instance.sendFriendRequest(uid);
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text(tr('تم إرسال طلب الصداقة.'))),
                        );
                      }
                      _fetchOnlineUsers();
                    } catch (_) {}
                  },
                ),

              // 3. Private Message
              ListTile(
                leading: const Icon(Icons.message, color: Colors.blueAccent),
                title: Text(tr('إرسال رسالة خاصة'), style: const TextStyle(color: Colors.white)),
                onTap: () {
                  Navigator.of(ctx).pop();
                  _showPrivateMessageInput(uid, name);
                },
              ),

              // 4. Join
              ListTile(
                leading: const Icon(Icons.meeting_room, color: Colors.tealAccent),
                title: Text(tr('انضمام للطاولة'), style: const TextStyle(color: Colors.white)),
                enabled: inTable && !isPrivate && userRoomId != null,
                subtitle: !inTable
                    ? Text(tr('اللاعب ليس في طاولة حاليًا'), style: const TextStyle(color: Colors.white38))
                    : (isPrivate ? Text(tr('اللاعب في طاولة خاصة'), style: const TextStyle(color: Colors.white38)) : null),
                onTap: () {
                  Navigator.of(ctx).pop();
                  if (userRoomId != null) {
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => TableView(roomId: userRoomId),
                      ),
                    );
                  }
                },
              ),

              // 5. Head to Head
              ListTile(
                leading: const Icon(Icons.sports_score, color: Colors.amberAccent),
                title: Text(tr('أنت ضده'), style: const TextStyle(color: Colors.white)),
                onTap: () {
                  Navigator.of(ctx).pop();
                  _showHeadToHeadDialog(uid, name);
                },
              ),

              // 6. Challenge
              ListTile(
                leading: const Icon(Icons.flash_on, color: Colors.yellowAccent),
                title: Text(tr('دعوة للتحدي'), style: const TextStyle(color: Colors.white)),
                enabled: !inTable,
                onTap: () {
                  Navigator.of(ctx).pop();
                  _openChallengeDialog(uid, name);
                },
              ),

              const Divider(color: Colors.white24),

              // 7. Block
              ListTile(
                leading: const Icon(Icons.block, color: Colors.red),
                title: Text(tr('حظر'), style: const TextStyle(color: Colors.red)),
                onTap: () {
                  Navigator.of(ctx).pop();
                  _confirmBlock(uid, name);
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showProfileDialog(int uid, String fallbackName) {
    showDialog(
      context: context,
      builder: (ctx) => FutureBuilder(
        future: ApiService.instance.getUserProfile(uid),
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          final data = snapshot.data is Map ? Map<String, dynamic>.from(snapshot.data as Map) : <String, dynamic>{};
          final name = data['display_name'] ?? fallbackName;
          final bio = data['bio'] ?? tr('لا يوجد بايو');
          final gender = data['gender'] ?? tr('غير محدد');
          final isOnline = data['online'] == true;
          final stats = (data['stats'] as List? ?? []);

          return AlertDialog(
            backgroundColor: const Color(0xFF2D2D2D),
            title: Text(name.toString(), style: const TextStyle(color: Colors.white)),
            content: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('${tr('الحالة')}: ${isOnline ? tr('متصل الآن') : tr('غير متصل')}',
                      style: TextStyle(color: isOnline ? Colors.greenAccent : Colors.white54)),
                  const SizedBox(height: 8),
                  Text('${tr('الجنس')}: $gender', style: const TextStyle(color: Colors.white70)),
                  const SizedBox(height: 8),
                  Text('${tr('النبذة')}: $bio', style: const TextStyle(color: Colors.white70)),
                  const Divider(color: Colors.white24, height: 24),
                  Text(tr('إحصائيات اللاعب'), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  if (stats.isEmpty)
                    Text(tr('لا توجد مباريات مسجلة.'), style: const TextStyle(color: Colors.white38))
                  else
                    ...stats.map((s) {
                      final gName = s['game_name'] ?? '';
                      return Text(
                        '$gName: لعب ${s['played']}, فاز ${s['wins']}, خسر ${s['losses']}',
                        style: const TextStyle(color: Colors.white70, fontSize: 13),
                      );
                    }),
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(),
                child: Text(tr('إغلاق'), style: const TextStyle(color: Colors.white70)),
              ),
            ],
          );
        },
      ),
    );
  }

  void _showPrivateMessageInput(int uid, String name) {
    final msgCtrl = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF2D2D2D),
        title: Text(tr('إرسال رسالة إلى {name}', {'name': name}), style: const TextStyle(color: Colors.white)),
        content: TextField(
          controller: msgCtrl,
          maxLength: 500,
          style: const TextStyle(color: Colors.white),
          decoration: InputDecoration(
            hintText: tr('اكتب رسالتك:'),
            hintStyle: const TextStyle(color: Colors.white38),
            filled: true,
            fillColor: const Color(0xFF1E1E1E),
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
              if (txt.isNotEmpty) {
                Navigator.of(ctx).pop();
                try {
                  await ApiService.instance.sendPrivateMessage(uid, txt);
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text(tr('تم إرسال الرسالة.'))),
                    );
                  }
                } catch (e) {
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
                  }
                }
              }
            },
            child: Text(tr('إرسال')),
          ),
        ],
      ),
    );
  }

  void _showHeadToHeadDialog(int uid, String name) {
    showDialog(
      context: context,
      builder: (ctx) => FutureBuilder(
        future: ApiService.instance.getHeadToHead(uid),
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          final data = snapshot.data is Map ? Map<String, dynamic>.from(snapshot.data as Map) : <String, dynamic>{};
          final total = data['total_played'] ?? 0;
          final youWins = data['you_wins'] ?? 0;
          final otherWins = data['other_wins'] ?? 0;
          final summary = (data['summary'] as List? ?? []);

          return AlertDialog(
            backgroundColor: const Color(0xFF2D2D2D),
            title: Text('${tr('أنت ضده')} — $name', style: const TextStyle(color: Colors.white)),
            content: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    'إجمالي المباريات: $total. فزت: $youWins، خسرت: $otherWins.',
                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                  ),
                  const Divider(color: Colors.white24, height: 24),
                  if (summary.isEmpty)
                    Text(tr('لم تلعبا أي مباراة مسجلة ضد بعضكما.'), style: const TextStyle(color: Colors.white38))
                  else
                    ...summary.map((s) {
                      final gTitle = _gameLabels[s['game_name']] ?? s['game_name'];
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Text(
                          '$gTitle: لعب ${s['played']} — فزت ${s['you_wins']} — خسرت ${s['other_wins']}',
                          style: const TextStyle(color: Colors.white70),
                        ),
                      );
                    }),
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(),
                child: Text(tr('إغلاق'), style: const TextStyle(color: Colors.white70)),
              ),
            ],
          );
        },
      ),
    );
  }

  void _openChallengeDialog(int uid, String name) {
    String selectedGame = 'UNO';
    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDlgState) => AlertDialog(
          backgroundColor: const Color(0xFF2D2D2D),
          title: Text('${tr('تحدي')} $name', style: const TextStyle(color: Colors.white)),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(tr('اختر اللعبة:'), style: const TextStyle(color: Colors.white70)),
              const SizedBox(height: 12),
              DropdownButton<String>(
                value: selectedGame,
                isExpanded: true,
                dropdownColor: const Color(0xFF2D2D2D),
                style: const TextStyle(color: Colors.white, fontSize: 16),
                items: _gameLabels.entries.map((e) {
                  return DropdownMenuItem(value: e.key, child: Text(e.value));
                }).toList(),
                onChanged: (v) {
                  if (v != null) setDlgState(() => selectedGame = v);
                },
              ),
            ],
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
                  final res = await ApiService.instance.challengeUser(uid, game: selectedGame);
                  if (res is Map && res['room_id'] != null) {
                    if (context.mounted) {
                      Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => TableView(roomId: res['room_id'].toString()),
                        ),
                      );
                    }
                  } else {
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(content: Text(tr('تم إرسال دعوة التحدي.'))),
                      );
                    }
                  }
                } catch (e) {
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
                  }
                }
              },
              style: ElevatedButton.styleFrom(backgroundColor: Colors.green),
              child: Text(tr('بدء التحدي'), style: const TextStyle(color: Colors.white)),
            ),
          ],
        ),
      ),
    );
  }

  void _confirmBlock(int uid, String name) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF2D2D2D),
        title: Text(tr('تأكيد الحظر'), style: const TextStyle(color: Colors.white)),
        content: Text(
          tr('هل أنت متأكد من رغبتك في حظر {name}؟', {'name': name}),
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
                await ApiService.instance.blockUser(uid);
                _fetchOnlineUsers();
              } catch (_) {}
            },
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: Text(tr('حظر نهائي'), style: const TextStyle(color: Colors.white)),
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
          // Search & Sort Bar
          Container(
            color: const Color(0xFF252526),
            padding: const EdgeInsets.all(12.0),
            child: Column(
              children: [
                TextField(
                  controller: _searchController,
                  style: const TextStyle(color: Colors.white),
                  decoration: InputDecoration(
                    hintText: tr('اكتب اسم المستخدم للبحث'),
                    hintStyle: const TextStyle(color: Colors.white38),
                    prefixIcon: const Icon(Icons.search, color: Colors.white54),
                    suffixIcon: _searchController.text.isNotEmpty
                        ? IconButton(
                            icon: const Icon(Icons.clear, color: Colors.white54),
                            onPressed: () {
                              _searchController.clear();
                              _executeSearch('');
                            },
                          )
                        : null,
                    border: const OutlineInputBorder(),
                    filled: true,
                    fillColor: const Color(0xFF1E1E1E),
                    contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  ),
                  onChanged: _onSearchChanged,
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Text(tr('ترتيب حسب:'), style: const TextStyle(color: Colors.white70)),
                    const SizedBox(width: 8),
                    Expanded(
                      child: DropdownButton<String>(
                        value: _sortMode,
                        isExpanded: true,
                        dropdownColor: const Color(0xFF2D2D2D),
                        style: const TextStyle(color: Colors.white),
                        underline: Container(height: 1, color: Colors.blueAccent),
                        items: [
                          DropdownMenuItem(value: 'alpha', child: Text(tr('الأحرف'))),
                          DropdownMenuItem(value: 'newest', child: Text(tr('الأحدث'))),
                          DropdownMenuItem(value: 'oldest', child: Text(tr('الأقدم'))),
                        ],
                        onChanged: (v) {
                          if (v != null) {
                            setState(() {
                              _sortMode = v;
                              _sortList(_displayUsers);
                            });
                          }
                        },
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),

          // User Results List
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _displayUsers.isEmpty
                    ? Center(
                        child: Text(
                          tr('لا يوجد لاعبين متطابقين.'),
                          style: const TextStyle(color: Colors.white54, fontSize: 16),
                        ),
                      )
                    : RefreshIndicator(
                        onRefresh: _fetchOnlineUsers,
                        child: ListView.separated(
                          itemCount: _displayUsers.length,
                          separatorBuilder: (_, __) => const Divider(color: Colors.white24, height: 1),
                          itemBuilder: (context, idx) {
                            final u = _displayUsers[idx];
                            final name = u['display_name'] ?? u['username'] ?? 'لاعب';
                            final isOnline = u['online'] == true;
                            final inTable = u['in_table'] == true;
                            final game = u['game'];

                            String statusText = isOnline ? tr('متصل') : tr('غير متصل');
                            if (isOnline && inTable && game != null) {
                              final gLabel = _gameLabels[game] ?? game;
                              statusText = '${tr('متصل')} — ${tr('يلعب')} $gLabel';
                            }

                            return ListTile(
                              leading: CircleAvatar(
                                backgroundColor: isOnline ? Colors.green : Colors.grey,
                                radius: 18,
                                child: Icon(Icons.person, color: Colors.white, size: 20),
                              ),
                              title: Text(name.toString(), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                              subtitle: Text(statusText, style: TextStyle(color: isOnline ? Colors.greenAccent : Colors.white38)),
                              trailing: const Icon(Icons.more_vert, color: Colors.white54),
                              onTap: () => _showUserActions(u),
                            );
                          },
                        ),
                      ),
          ),
        ],
      ),
    );
  }
}

