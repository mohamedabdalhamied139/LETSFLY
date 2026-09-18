import 'package:flutter/material.dart';
import '../core/localization.dart';
import '../services/api_service.dart';
import '../services/ws_service.dart';

class TablePlayersDialog extends StatelessWidget {
  final String roomId;
  final Map<String, dynamic>? roomState;
  final int myUserId;
  final bool isHost;
  final bool isCoHost;
  final VoidCallback? onRefresh;

  const TablePlayersDialog({
    super.key,
    this.roomId = '',
    required this.roomState,
    required this.myUserId,
    required this.isHost,
    this.isCoHost = false,
    this.onRefresh,
  });

  void _showPlayerActions(BuildContext context, Map<String, dynamic> player) {
    final name = (player['display_name'] ?? player['name'] ?? player['username'] ?? 'لاعب').toString();
    final rawId = player['id'] ?? player['user_id'];
    final targetId = rawId != null ? int.tryParse(rawId.toString()) ?? 0 : 0;
    final isTargetHost = player['is_host'] == true ||
        (roomState?['host_id'] != null && roomState?['host_id'].toString() == targetId.toString());
    final isTargetCoHost = player['is_co_host'] == true ||
        (roomState?['co_host_id'] != null && roomState?['co_host_id'].toString() == targetId.toString());
    final isMe = targetId == myUserId;
    final isBot = targetId < 0;
    final isSpectator = player['is_spectator'] == true;
    final effectiveRoomId = roomId.isNotEmpty
        ? roomId
        : (roomState?['id']?.toString() ?? roomState?['room_id']?.toString() ?? '');

    bool canKickBan = false;
    if (isHost && !isMe && !isTargetHost) {
      canKickBan = true;
    } else if (isCoHost && !isMe && !isTargetHost && !isTargetCoHost) {
      canKickBan = true;
    }

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

              // 1. Transfer Host
              if (isHost && !isMe && !isBot && !isTargetHost)
                ListTile(
                  leading: const Icon(Icons.star, color: Colors.amber),
                  title: Text(tr('تعيينه كقائد'), style: const TextStyle(color: Colors.white)),
                  onTap: () async {
                    Navigator.of(ctx).pop();
                    try {
                      await ApiService.instance.transferHost(effectiveRoomId, targetId);
                      onRefresh?.call();
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text(tr('تم نقل القيادة بنجاح.'))),
                        );
                      }
                    } catch (e) {
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
                      }
                    }
                  },
                ),

              // 2. Co-Captain
              if (isHost && !isMe && !isBot && !isTargetHost)
                ListTile(
                  leading: const Icon(Icons.shield, color: Colors.blueAccent),
                  title: Text(
                    isTargetCoHost ? tr('إلغاء تعيين نائب القائد') : tr('تعيين نائب كابتن'),
                    style: const TextStyle(color: Colors.white),
                  ),
                  onTap: () async {
                    Navigator.of(ctx).pop();
                    try {
                      await ApiService.instance.setCoHost(effectiveRoomId, targetId);
                      onRefresh?.call();
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text(isTargetCoHost ? tr('تم إلغاء تعيين نائب القائد.') : tr('تم تعيين نائب القائد بنجاح.'))),
                        );
                      }
                    } catch (e) {
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
                      }
                    }
                  },
                ),

              // 3. Substitute
              if ((isHost || isCoHost) && !isMe && !isTargetHost)
                ListTile(
                  leading: const Icon(Icons.swap_horiz, color: Colors.orangeAccent),
                  title: Text(tr('استبدال ببوت'), style: const TextStyle(color: Colors.white)),
                  onTap: () async {
                    Navigator.of(ctx).pop();
                    try {
                      await ApiService.instance.substitutePlayer(effectiveRoomId, targetId, isBot: true);
                      onRefresh?.call();
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text(tr('تم استبدال اللاعب بنجاح.'))),
                        );
                      }
                    } catch (e) {
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
                      }
                    }
                  },
                ),

              // 4. Kick
              if (canKickBan)
                ListTile(
                  leading: const Icon(Icons.exit_to_app, color: Colors.redAccent),
                  title: Text(tr('طرد من الطاولة'), style: const TextStyle(color: Colors.redAccent)),
                  onTap: () async {
                    Navigator.of(ctx).pop();
                    try {
                      await ApiService.instance.kickPlayer(effectiveRoomId, targetId);
                      onRefresh?.call();
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text(tr('تم طرد اللاعب من الطاولة.'))),
                        );
                      }
                    } catch (e) {
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
                      }
                    }
                  },
                ),

              // 5. Ban
              if (canKickBan)
                ListTile(
                  leading: const Icon(Icons.block, color: Colors.red),
                  title: Text(tr('حظر من الطاولة'), style: const TextStyle(color: Colors.red)),
                  onTap: () async {
                    Navigator.of(ctx).pop();
                    try {
                      await ApiService.instance.banPlayer(effectiveRoomId, targetId);
                      onRefresh?.call();
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text(tr('تم حظر اللاعب من الطاولة.'))),
                        );
                      }
                    } catch (e) {
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
                      }
                    }
                  },
                ),

              // 6. Voice Controls
              if (isHost && !isBot && !isMe) ...[
                ListTile(
                  leading: const Icon(Icons.mic_off, color: Colors.amberAccent),
                  title: Text(tr('كتم / إلغاء كتم الميكروفون'), style: const TextStyle(color: Colors.white)),
                  onTap: () async {
                    Navigator.of(ctx).pop();
                    try {
                      await ApiService.instance.voiceMutePlayer(effectiveRoomId, targetId);
                      onRefresh?.call();
                    } catch (e) {
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
                      }
                    }
                  },
                ),
                ListTile(
                  leading: const Icon(Icons.phone_disabled, color: Colors.redAccent),
                  title: Text(tr('إزالة من المحادثة الصوتية'), style: const TextStyle(color: Colors.redAccent)),
                  onTap: () async {
                    Navigator.of(ctx).pop();
                    try {
                      await ApiService.instance.voiceKickPlayer(effectiveRoomId, targetId);
                      onRefresh?.call();
                    } catch (e) {
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
                      }
                    }
                  },
                ),
              ],

              // 7. Make spectator
              if (isHost && !isMe && !isTargetHost && !isSpectator)
                ListTile(
                  leading: const Icon(Icons.visibility, color: Colors.cyanAccent),
                  title: Text(tr('تحويل إلى متفرج'), style: const TextStyle(color: Colors.white)),
                  onTap: () async {
                    Navigator.of(ctx).pop();
                    try {
                      await ApiService.instance.toggleSpectator(effectiveRoomId, targetUserId: targetId);
                      onRefresh?.call();
                    } catch (e) {
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
                      }
                    }
                  },
                ),

              // 8. Social Actions for Human Players
              if (!isBot) ...[
                const Divider(color: Colors.white24),
                ListTile(
                  leading: const Icon(Icons.account_circle, color: Colors.white70),
                  title: Text(tr('زيارة الملف الشخصي'), style: const TextStyle(color: Colors.white)),
                  onTap: () {
                    Navigator.of(ctx).pop();
                    _showProfileDialog(context, targetId, name);
                  },
                ),
                if (!isMe) ...[
                  ListTile(
                    leading: const Icon(Icons.person_add, color: Colors.greenAccent),
                    title: Text(tr('إرسال طلب صداقة'), style: const TextStyle(color: Colors.white)),
                    onTap: () async {
                      Navigator.of(ctx).pop();
                      try {
                        await ApiService.instance.sendFriendRequest(targetId);
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text(tr('تم إرسال طلب الصداقة بنجاح.'))),
                          );
                        }
                      } catch (e) {
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
                        }
                      }
                    },
                  ),
                  ListTile(
                    leading: const Icon(Icons.message, color: Colors.blueAccent),
                    title: Text(tr('إرسال رسالة خاصة'), style: const TextStyle(color: Colors.white)),
                    onTap: () {
                      Navigator.of(ctx).pop();
                      _showPrivateMessageInput(context, targetId, name);
                    },
                  ),
                ],
              ],
            ],
          ),
        ),
      ),
    );
  }

  void _showProfileDialog(BuildContext context, int userId, String fallbackName) {
    showDialog(
      context: context,
      builder: (ctx) => FutureBuilder(
        future: ApiService.instance.getUserProfile(userId),
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          final data = snapshot.data is Map ? Map<String, dynamic>.from(snapshot.data as Map) : <String, dynamic>{};
          final name = data['display_name'] ?? fallbackName;
          final bio = data['bio'] ?? tr('لا يوجد بايو');
          final gender = data['gender'] ?? tr('غير محدد');
          final isOnline = data['online'] == true;

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

  void _showPrivateMessageInput(BuildContext context, int userId, String name) {
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
                  await ApiService.instance.sendPrivateMessage(userId, txt);
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

  @override
  Widget build(BuildContext context) {
    final players = (roomState?['players'] as List?) ?? [];
    final playerNames = (roomState?['player_names'] as List?) ?? [];
    final playersDict = (roomState?['players_dict'] as Map?) ?? {};
    final spectators = (roomState?['spectators'] as List?) ?? [];

    return Scaffold(
      backgroundColor: const Color(0xFF1E1E1E),
      appBar: AppBar(
        title: Text(tr('قائمة اللاعبين')),
        backgroundColor: const Color(0xFF2D2D2D),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Text(
              '${tr('اللاعبون')} (${players.length})',
              style: const TextStyle(color: Colors.white70, fontWeight: FontWeight.bold, fontSize: 16),
            ),
          ),
          ...players.asMap().entries.map((entry) {
            final idx = entry.key;
            final p = entry.value;
            Map<String, dynamic> pMap = {};
            if (p is Map) {
              pMap = Map<String, dynamic>.from(p);
            } else if (p is int) {
              final dName = playersDict[p.toString()] ?? (idx < playerNames.length ? playerNames[idx] : 'لاعب');
              pMap = {'id': p, 'display_name': dName};
            } else {
              pMap = {'name': p.toString()};
            }

            final rawId = pMap['id'] ?? pMap['user_id'];
            final isPlayerHost = pMap['is_host'] == true ||
                (roomState?['host_id'] != null && roomState?['host_id'].toString() == rawId?.toString());
            final isPlayerCoHost = pMap['is_co_host'] == true ||
                (roomState?['co_host_id'] != null && roomState?['co_host_id'].toString() == rawId?.toString());
            final name = pMap['display_name'] ?? pMap['name'] ?? pMap['username'] ?? 'لاعب';

            String role = '';
            if (isPlayerHost) {
              role = ' (${tr('القائد')})';
            } else if (isPlayerCoHost) {
              role = ' (${tr('نائب القائد')})';
            }

            return ListTile(
              leading: CircleAvatar(
                backgroundColor: isPlayerHost ? Colors.amber : (isPlayerCoHost ? Colors.blueAccent : Colors.blueGrey),
                child: Icon(isPlayerHost ? Icons.star : (isPlayerCoHost ? Icons.shield : Icons.person), color: Colors.white),
              ),
              title: Text('$name$role', style: const TextStyle(color: Colors.white)),
              trailing: const Icon(Icons.more_vert, color: Colors.white54),
              onTap: () => _showPlayerActions(context, pMap),
            );
          }),
          if (spectators.isNotEmpty) ...[
            const Divider(color: Colors.white24, height: 32),
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Text(
                '${tr('المتفرجون')} (${spectators.length})',
                style: const TextStyle(color: Colors.white70, fontWeight: FontWeight.bold, fontSize: 16),
              ),
            ),
            ...spectators.map((s) {
              Map<String, dynamic> sMap = {};
              if (s is Map) {
                sMap = Map<String, dynamic>.from(s);
              } else if (s is int) {
                final dName = playersDict[s.toString()] ?? 'متفرج';
                sMap = {'id': s, 'display_name': dName, 'is_spectator': true};
              } else {
                sMap = {'name': s.toString(), 'is_spectator': true};
              }
              final name = sMap['display_name'] ?? sMap['name'] ?? sMap['username'] ?? 'متفرج';

              return ListTile(
                leading: const CircleAvatar(
                  backgroundColor: Colors.grey,
                  child: Icon(Icons.visibility, color: Colors.white),
                ),
                title: Text('$name (${tr('متفرج')})', style: const TextStyle(color: Colors.white)),
                trailing: const Icon(Icons.more_vert, color: Colors.white54),
                onTap: () => _showPlayerActions(context, sMap),
              );
            }),
          ],
        ],
      ),
    );
  }
}
