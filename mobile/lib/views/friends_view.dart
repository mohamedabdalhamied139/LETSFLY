import 'package:flutter/material.dart';
import '../core/localization.dart';
import '../services/api_service.dart';
import 'table_view.dart';

class FriendsView extends StatefulWidget {
  final String? currentRoomId;

  const FriendsView({super.key, this.currentRoomId});

  @override
  State<FriendsView> createState() => _FriendsViewState();
}

class _FriendsViewState extends State<FriendsView> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  List<Map<String, dynamic>> _friends = [];
  List<Map<String, dynamic>> _incoming = [];
  List<Map<String, dynamic>> _outgoing = [];
  bool _isLoading = false;

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
    _tabController = TabController(length: 3, vsync: this);
    _loadData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    setState(() => _isLoading = true);
    try {
      final res = await ApiService.instance.getFriends();
      if (res is Map && mounted) {
        setState(() {
          _friends = (res['friends'] as List? ?? [])
              .map((e) => Map<String, dynamic>.from(e as Map))
              .toList();
          _incoming = (res['requests'] as List? ?? [])
              .map((e) => Map<String, dynamic>.from(e as Map))
              .toList();
          _outgoing = (res['sent'] as List? ?? [])
              .map((e) => Map<String, dynamic>.from(e as Map))
              .toList();
        });
      } else if (res is List && mounted) {
        setState(() {
          _friends = res.map((e) => Map<String, dynamic>.from(e as Map)).toList();
          _incoming = [];
          _outgoing = [];
        });
      }
    } catch (_) {}
    if (mounted) setState(() => _isLoading = false);
  }

  // --- 10 Canonical Friend Actions Dialog ---
  void _showFriendActions(Map<String, dynamic> friend) {
    final dName = friend['display_name'] ?? friend['username'] ?? 'لاعب';
    final uid = int.tryParse((friend['id'] ?? 0).toString()) ?? 0;
    final isOnline = friend['online'] == true;
    final inTable = friend['in_table'] == true;
    final isPrivate = friend['room_private'] == true;
    final friendRoomId = friend['room_id']?.toString();
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
                  '${tr('إجراءات')} $dName',
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
                  _openProfileDialog(uid, dName);
                },
              ),

              // 2. Private Message
              ListTile(
                leading: const Icon(Icons.message, color: Colors.blueAccent),
                title: Text(tr('إرسال رسالة'), style: const TextStyle(color: Colors.white)),
                onTap: () {
                  Navigator.of(ctx).pop();
                  _openMessageDialog(uid, dName);
                },
              ),

              // 3. Join Table
              ListTile(
                leading: const Icon(Icons.meeting_room, color: Colors.greenAccent),
                title: Text(tr('انضمام'), style: const TextStyle(color: Colors.white)),
                enabled: inTable && !isPrivate && friendRoomId != null,
                subtitle: (!inTable)
                    ? Text(tr('اللاعب ليس في طاولة حاليًا'), style: const TextStyle(color: Colors.white38))
                    : (isPrivate ? Text(tr('اللاعب في طاولة خاصة'), style: const TextStyle(color: Colors.white38)) : null),
                onTap: () {
                  Navigator.of(ctx).pop();
                  if (friendRoomId != null) {
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => TableView(roomId: friendRoomId),
                      ),
                    );
                  }
                },
              ),

              // 4. Head to Head
              ListTile(
                leading: const Icon(Icons.sports_score, color: Colors.amberAccent),
                title: Text(tr('أنت ضده'), style: const TextStyle(color: Colors.white)),
                onTap: () {
                  Navigator.of(ctx).pop();
                  _openHeadToHeadDialog(uid, dName);
                },
              ),

              // 5. Mute Notifications
              ListTile(
                leading: const Icon(Icons.notifications_off, color: Colors.orangeAccent),
                title: Text(tr('كتم الإشعارات'), style: const TextStyle(color: Colors.white)),
                onTap: () {
                  Navigator.of(ctx).pop();
                  _openMuteDialog(uid, dName);
                },
              ),

              // 6. Invite to Current Table
              ListTile(
                leading: const Icon(Icons.group_add, color: Colors.tealAccent),
                title: Text(tr('دعوة للطاولة'), style: const TextStyle(color: Colors.white)),
                enabled: canInvite && !inTable,
                subtitle: !canInvite
                    ? Text(tr('يجب أن تكون داخل طاولة لإرسال الدعوة'), style: const TextStyle(color: Colors.white38))
                    : (inTable ? Text(tr('اللاعب موجود حاليًا في طاولة'), style: const TextStyle(color: Colors.white38)) : null),
                onTap: () async {
                  Navigator.of(ctx).pop();
                  try {
                    await ApiService.instance.inviteUserToRoom(widget.currentRoomId!, uid);
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(content: Text(tr('تم إرسال دعوة الانضمام.'))),
                      );
                    }
                  } catch (e) {
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
                    }
                  }
                },
              ),

              // 7. Direct Challenge in a New Game
              ListTile(
                leading: const Icon(Icons.flash_on, color: Colors.yellowAccent),
                title: Text(tr('تحدي في لعبة جديدة'), style: const TextStyle(color: Colors.white)),
                enabled: isOnline && !inTable,
                subtitle: !isOnline
                    ? Text(tr('لا يمكن تحدي لاعب غير متصل'), style: const TextStyle(color: Colors.white38))
                    : (inTable ? Text(tr('اللاعب موجود في طاولة'), style: const TextStyle(color: Colors.white38)) : null),
                onTap: () {
                  Navigator.of(ctx).pop();
                  _openDirectChallengeDialog(uid, dName);
                },
              ),

              // 8. Gift Coins
              ListTile(
                leading: const Icon(Icons.card_giftcard, color: Colors.purpleAccent),
                title: Text(tr('إرسال هدية'), style: const TextStyle(color: Colors.white)),
                onTap: () {
                  Navigator.of(ctx).pop();
                  _openGiftDialog(uid, dName);
                },
              ),

              const Divider(color: Colors.white24),

              // 9. Unfriend
              ListTile(
                leading: const Icon(Icons.person_remove, color: Colors.redAccent),
                title: Text(tr('إلغاء الصداقة'), style: const TextStyle(color: Colors.redAccent)),
                onTap: () {
                  Navigator.of(ctx).pop();
                  _confirmUnfriend(uid, dName);
                },
              ),

              // 10. Block
              ListTile(
                leading: const Icon(Icons.block, color: Colors.red),
                title: Text(tr('حظر'), style: const TextStyle(color: Colors.red)),
                onTap: () {
                  Navigator.of(ctx).pop();
                  _confirmBlock(uid, dName);
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  // --- Sub-Dialogs ---

  void _openMessageDialog(int uid, String name) {
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
            hintText: tr('اكتب رسالتك هنا'),
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
                      SnackBar(content: Text(tr('تم إرسال الرسالة بنجاح.'))),
                    );
                  }
                } catch (e) {
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
                  }
                }
              }
            },
            style: ElevatedButton.styleFrom(backgroundColor: Colors.blueAccent),
            child: Text(tr('إرسال'), style: const TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  void _openProfileDialog(int uid, String fallbackName) {
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

  void _openHeadToHeadDialog(int uid, String name) {
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

  void _openMuteDialog(int uid, String name) async {
    Map<String, dynamic> currentFlags = {};
    try {
      final res = await ApiService.instance.getMutes(uid);
      if (res is Map) currentFlags = Map<String, dynamic>.from(res);
    } catch (_) {}

    bool muteAll = currentFlags['all'] == 1 || currentFlags['all'] == true;
    bool mutePm = currentFlags['private_messages'] == 1 || currentFlags['private_messages'] == true;
    bool muteInv = currentFlags['invitations'] == 1 || currentFlags['invitations'] == true;
    bool mutePresence = currentFlags['presence'] == 1 || currentFlags['presence'] == true;

    if (!mounted) return;
    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDlgState) => AlertDialog(
          backgroundColor: const Color(0xFF2D2D2D),
          title: Text('${tr('كتم الإشعارات')} — $name', style: const TextStyle(color: Colors.white)),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CheckboxListTile(
                title: Text(tr('كتم كل الإشعارات'), style: const TextStyle(color: Colors.white)),
                value: muteAll,
                onChanged: (v) => setDlgState(() => muteAll = v ?? false),
              ),
              CheckboxListTile(
                title: Text(tr('كتم الرسائل الخاصة'), style: const TextStyle(color: Colors.white)),
                value: mutePm,
                onChanged: (v) => setDlgState(() => mutePm = v ?? false),
              ),
              CheckboxListTile(
                title: Text(tr('كتم الدعوات'), style: const TextStyle(color: Colors.white)),
                value: muteInv,
                onChanged: (v) => setDlgState(() => muteInv = v ?? false),
              ),
              CheckboxListTile(
                title: Text(tr('كتم الحالة'), style: const TextStyle(color: Colors.white)),
                value: mutePresence,
                onChanged: (v) => setDlgState(() => mutePresence = v ?? false),
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
                  await ApiService.instance.setMutes(uid, {
                    'all': muteAll,
                    'private_messages': mutePm,
                    'invitations': muteInv,
                    'presence': mutePresence,
                  });
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text(tr('تم حفظ إعدادات الكتم.'))),
                    );
                  }
                } catch (e) {
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
                  }
                }
              },
              child: Text(tr('حفظ')),
            ),
          ],
        ),
      ),
    );
  }

  void _openGiftDialog(int uid, String name) {
    int selectedAmount = 5;
    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDlgState) => AlertDialog(
          backgroundColor: const Color(0xFF2D2D2D),
          title: Text('${tr('إرسال هدية')} — $name', style: const TextStyle(color: Colors.white)),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(tr('اختر قيمة الهدية (من 5 إلى 30 عملة):'), style: const TextStyle(color: Colors.white70)),
              const SizedBox(height: 12),
              DropdownButton<int>(
                value: selectedAmount,
                isExpanded: true,
                dropdownColor: const Color(0xFF2D2D2D),
                style: const TextStyle(color: Colors.white, fontSize: 16),
                items: List.generate(26, (i) => i + 5).map((n) {
                  return DropdownMenuItem(value: n, child: Text('$n عملة'));
                }).toList(),
                onChanged: (v) {
                  if (v != null) setDlgState(() => selectedAmount = v);
                },
              ),
              const SizedBox(height: 12),
              Text(
                tr('الحد اليومي للحساب: 30 عملة. الحد الشهري للحساب: 150 عملة.'),
                style: const TextStyle(color: Colors.white38, fontSize: 12),
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
                  await ApiService.instance.giftUser(uid, selectedAmount);
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text(tr('تم إرسال الهدية بنجاح.'))),
                    );
                  }
                } catch (e) {
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
                  }
                }
              },
              child: Text(tr('إرسال')),
            ),
          ],
        ),
      ),
    );
  }

  void _openDirectChallengeDialog(int uid, String name) {
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
              const SizedBox(height: 12),
              Text(
                tr('تكلفة إنشاء التحدي: 3 عملات (2 لفتح الطاولة + 1 للدعوة).'),
                style: const TextStyle(color: Colors.white38, fontSize: 12),
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

  void _confirmUnfriend(int uid, String name) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF2D2D2D),
        title: Text(tr('إلغاء الصداقة'), style: const TextStyle(color: Colors.white)),
        content: Text(
          tr('هل أنت متأكد من رغبتك في إلغاء الصداقة مع {name}؟', {'name': name}),
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
                await ApiService.instance.unfriend(uid);
                _loadData();
              } catch (e) {
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
                }
              }
            },
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: Text(tr('تأكيد الإلغاء'), style: const TextStyle(color: Colors.white)),
          ),
        ],
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
          tr('هل أنت متأكد من رغبتك في حظر {name}؟ سيتم إلغاء الصداقة وحظر الرسائل.', {'name': name}),
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
                _loadData();
              } catch (e) {
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
                }
              }
            },
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: Text(tr('حظر نهائي'), style: const TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  // --- Actions for Incoming & Outgoing Requests ---
  void _showIncomingActions(Map<String, dynamic> req) {
    final reqId = int.tryParse((req['request_id'] ?? req['id'] ?? 0).toString()) ?? 0;
    final senderId = int.tryParse((req['id'] ?? req['sender_id'] ?? 0).toString()) ?? 0;
    final dName = req['display_name'] ?? req['username'] ?? 'لاعب';

    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF2D2D2D),
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.check, color: Colors.green),
              title: Text(tr('قبول طلب الصداقة'), style: const TextStyle(color: Colors.white)),
              onTap: () async {
                Navigator.of(ctx).pop();
                try {
                  await ApiService.instance.acceptFriendRequest(reqId);
                  _loadData();
                } catch (e) {
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
                  }
                }
              },
            ),
            ListTile(
              leading: const Icon(Icons.close, color: Colors.redAccent),
              title: Text(tr('رفض طلب الصداقة'), style: const TextStyle(color: Colors.white)),
              onTap: () async {
                Navigator.of(ctx).pop();
                try {
                  await ApiService.instance.rejectFriendRequest(reqId);
                  _loadData();
                } catch (e) {
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
                  }
                }
              },
            ),
            ListTile(
              leading: const Icon(Icons.account_circle, color: Colors.white70),
              title: Text(tr('زيارة الملف الشخصي'), style: const TextStyle(color: Colors.white)),
              onTap: () {
                Navigator.of(ctx).pop();
                _openProfileDialog(senderId, dName);
              },
            ),
          ],
        ),
      ),
    );
  }

  void _showOutgoingActions(Map<String, dynamic> req) {
    final reqId = int.tryParse((req['request_id'] ?? req['id'] ?? 0).toString()) ?? 0;
    final targetId = int.tryParse((req['id'] ?? req['recipient_id'] ?? 0).toString()) ?? 0;
    final dName = req['display_name'] ?? req['username'] ?? 'لاعب';

    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF2D2D2D),
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.cancel, color: Colors.redAccent),
              title: Text(tr('إلغاء الطلب المرسل'), style: const TextStyle(color: Colors.white)),
              onTap: () async {
                Navigator.of(ctx).pop();
                try {
                  if (reqId > 0) {
                    await ApiService.instance.cancelFriendRequest(reqId);
                  } else {
                    await ApiService.instance.cancelFriendRequestToUser(targetId);
                  }
                  _loadData();
                } catch (e) {
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
                  }
                }
              },
            ),
            ListTile(
              leading: const Icon(Icons.account_circle, color: Colors.white70),
              title: Text(tr('زيارة الملف الشخصي'), style: const TextStyle(color: Colors.white)),
              onTap: () {
                Navigator.of(ctx).pop();
                _openProfileDialog(targetId, dName);
              },
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF1E1E1E),
      appBar: AppBar(
        title: Text(tr('الأصدقاء')),
        backgroundColor: const Color(0xFF2D2D2D),
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: Colors.blueAccent,
          tabs: [
            Tab(text: '${tr('الأصدقاء')} (${_friends.length})'),
            Tab(text: '${tr('الطلبات')} (${_incoming.length})'),
            Tab(text: '${tr('الطلبات المرسلة')} (${_outgoing.length})'),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : TabBarView(
              controller: _tabController,
              children: [
                // Tab 1: Friends
                _friends.isEmpty
                    ? Center(
                        child: Text(
                          tr('لا يوجد أصدقاء حالياً.'),
                          style: const TextStyle(color: Colors.white54, fontSize: 16),
                        ),
                      )
                    : RefreshIndicator(
                        onRefresh: _loadData,
                        child: ListView.separated(
                          itemCount: _friends.length,
                          separatorBuilder: (_, __) => const Divider(color: Colors.white24, height: 1),
                          itemBuilder: (context, idx) {
                            final f = _friends[idx];
                            final name = f['display_name'] ?? f['username'] ?? 'لاعب';
                            final isOnline = f['online'] == true;
                            final game = f['game'];

                            String statusText = isOnline ? tr('متصل') : tr('غير متصل');
                            if (isOnline && game != null && game.toString().isNotEmpty) {
                              final gLabel = _gameLabels[game] ?? game;
                              statusText = '${tr('متصل')} — ${tr('يلعب')} $gLabel';
                            }

                            return ListTile(
                              leading: CircleAvatar(
                                backgroundColor: isOnline ? Colors.green : Colors.grey,
                                radius: 18,
                                child: const Icon(Icons.person, color: Colors.white, size: 20),
                              ),
                              title: Text(name, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                              subtitle: Text(statusText, style: TextStyle(color: isOnline ? Colors.greenAccent : Colors.white38)),
                              trailing: const Icon(Icons.more_vert, color: Colors.white54),
                              onTap: () => _showFriendActions(f),
                            );
                          },
                        ),
                      ),

                // Tab 2: Incoming Requests
                _incoming.isEmpty
                    ? Center(
                        child: Text(
                          tr('لا توجد طلبات صداقة واردة.'),
                          style: const TextStyle(color: Colors.white54, fontSize: 16),
                        ),
                      )
                    : RefreshIndicator(
                        onRefresh: _loadData,
                        child: ListView.separated(
                          itemCount: _incoming.length,
                          separatorBuilder: (_, __) => const Divider(color: Colors.white24, height: 1),
                          itemBuilder: (context, idx) {
                            final req = _incoming[idx];
                            final name = req['display_name'] ?? req['username'] ?? 'لاعب';

                            return ListTile(
                              leading: const CircleAvatar(
                                backgroundColor: Colors.blueAccent,
                                child: Icon(Icons.person_add, color: Colors.white),
                              ),
                              title: Text(name, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                              subtitle: Text(tr('طلب صداقة وارد'), style: const TextStyle(color: Colors.white38)),
                              trailing: const Icon(Icons.more_vert, color: Colors.white54),
                              onTap: () => _showIncomingActions(req),
                            );
                          },
                        ),
                      ),

                // Tab 3: Outgoing Requests
                _outgoing.isEmpty
                    ? Center(
                        child: Text(
                          tr('لا توجد طلبات صداقة مرسلة.'),
                          style: const TextStyle(color: Colors.white54, fontSize: 16),
                        ),
                      )
                    : RefreshIndicator(
                        onRefresh: _loadData,
                        child: ListView.separated(
                          itemCount: _outgoing.length,
                          separatorBuilder: (_, __) => const Divider(color: Colors.white24, height: 1),
                          itemBuilder: (context, idx) {
                            final req = _outgoing[idx];
                            final name = req['display_name'] ?? req['username'] ?? 'لاعب';

                            return ListTile(
                              leading: const CircleAvatar(
                                backgroundColor: Colors.orangeAccent,
                                child: Icon(Icons.arrow_upward, color: Colors.white),
                              ),
                              title: Text(name, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                              subtitle: Text(tr('طلب مرسل قيد الانتظار'), style: const TextStyle(color: Colors.white38)),
                              trailing: const Icon(Icons.more_vert, color: Colors.white54),
                              onTap: () => _showOutgoingActions(req),
                            );
                          },
                        ),
                      ),
              ],
            ),
    );
  }
}

