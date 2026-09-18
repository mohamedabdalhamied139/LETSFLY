import 'package:flutter/material.dart';
import '../core/localization.dart';
import '../services/api_service.dart';
import '../services/ws_service.dart';

class TablePlayersDialog extends StatelessWidget {
  final Map<String, dynamic>? roomState;
  final int myUserId;
  final bool isHost;
  final bool isCoHost;
  final VoidCallback? onRefresh;

  const TablePlayersDialog({
    super.key,
    required this.roomState,
    required this.myUserId,
    required this.isHost,
    this.isCoHost = false,
    this.onRefresh,
  });

  void _showPlayerActions(BuildContext context, Map<String, dynamic> player) {
    final name = player['display_name'] ?? player['name'] ?? player['username'] ?? 'لاعب';
    final targetId = player['id'] ?? player['user_id'];
    final isTargetHost = player['is_host'] == true;
    final isTargetCoHost = player['is_co_host'] == true;
    final isMe = targetId == myUserId;
    final isBot = targetId != null && int.tryParse(targetId.toString()) != null && int.parse(targetId.toString()) < 0;

    final roomId = roomState?['id']?.toString() ?? '';

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
            if (isHost && !isMe && !isBot && !isTargetHost) ...[
              ListTile(
                leading: const Icon(Icons.star, color: Colors.amber),
                title: Text(tr('تعيينه كقائد'), style: const TextStyle(color: Colors.white)),
                onTap: () {
                  Navigator.of(ctx).pop();
                  WebSocketService.instance.sendJson({
                    'type': 'room_action',
                    'action': 'transfer_host',
                    'target_user_id': targetId,
                  });
                },
              ),
              ListTile(
                leading: const Icon(Icons.shield, color: Colors.blueAccent),
                title: Text(
                  isTargetCoHost ? tr('إلغاء تعيين نائب القائد') : tr('تعيين نائب كابتن'),
                  style: const TextStyle(color: Colors.white),
                ),
                onTap: () {
                  Navigator.of(ctx).pop();
                  WebSocketService.instance.sendJson({
                    'type': 'room_action',
                    'action': 'set_co_host',
                    'target_user_id': targetId,
                  });
                },
              ),
            ],
            if ((isHost || isCoHost) && !isMe && !isTargetHost) ...[
              ListTile(
                leading: const Icon(Icons.swap_horiz, color: Colors.orange),
                title: Text(tr('استبدال ببوت'), style: const TextStyle(color: Colors.white)),
                onTap: () {
                  Navigator.of(ctx).pop();
                  WebSocketService.instance.sendJson({
                    'type': 'room_action',
                    'action': 'substitute',
                    'target_user_id': targetId,
                    'is_bot': true,
                  });
                },
              ),
              ListTile(
                leading: const Icon(Icons.exit_to_app, color: Colors.redAccent),
                title: Text(tr('طرد'), style: const TextStyle(color: Colors.redAccent)),
                onTap: () {
                  Navigator.of(ctx).pop();
                  WebSocketService.instance.sendJson({
                    'type': 'room_action',
                    'action': 'kick',
                    'target_user_id': targetId,
                  });
                },
              ),
              ListTile(
                leading: const Icon(Icons.block, color: Colors.red),
                title: Text(tr('حظر من الطاولة'), style: const TextStyle(color: Colors.red)),
                onTap: () {
                  Navigator.of(ctx).pop();
                  WebSocketService.instance.sendJson({
                    'type': 'room_action',
                    'action': 'ban',
                    'target_user_id': targetId,
                  });
                },
              ),
            ],
            if (!isBot && !isMe) ...[
              ListTile(
                leading: const Icon(Icons.person_add, color: Colors.green),
                title: Text(tr('إضافة صديق'), style: const TextStyle(color: Colors.white)),
                onTap: () async {
                  Navigator.of(ctx).pop();
                  try {
                    if (targetId != null) {
                      await ApiService.instance.sendFriendRequest(int.parse(targetId.toString()));
                    }
                  } catch (_) {}
                },
              ),
            ],
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final players = (roomState?['players'] as List?) ?? [];
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
          ...players.map((p) {
            final pMap = p is Map ? Map<String, dynamic>.from(p) : {'name': p.toString()};
            final name = pMap['display_name'] ?? pMap['name'] ?? pMap['username'] ?? 'لاعب';
            final isPlayerHost = pMap['is_host'] == true;
            final isPlayerCoHost = pMap['is_co_host'] == true;

            String role = '';
            if (isPlayerHost) role = ' (${tr('القائد')})';
            else if (isPlayerCoHost) role = ' (${tr('نائب القائد')})';

            return ListTile(
              leading: CircleAvatar(
                backgroundColor: isPlayerHost ? Colors.amber : Colors.blueGrey,
                child: Icon(isPlayerHost ? Icons.star : Icons.person, color: Colors.white),
              ),
              title: Text('$name$role', style: const TextStyle(color: Colors.white)),
              trailing: const Icon(Icons.more_vert, color: Colors.white54),
              onTap: () => _showPlayerActions(context, pMap),
            );
          }).toList(),
          if (spectators.isNotEmpty) ...[
            const Divider(color: Colors.white24),
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Text(
                '${tr('المتفرجون')} (${spectators.length})',
                style: const TextStyle(color: Colors.white70, fontWeight: FontWeight.bold, fontSize: 16),
              ),
            ),
            ...spectators.map((s) {
              final sMap = s is Map ? Map<String, dynamic>.from(s) : {'name': s.toString()};
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
            }).toList(),
          ],
        ],
      ),
    );
  }
}
