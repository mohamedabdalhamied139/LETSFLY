import 'package:flutter/material.dart';
import '../core/app_theme.dart';
import '../core/localization.dart';
import '../core/sound_service.dart';
import '../core/accessibility_manager.dart';
import '../services/api_service.dart';

/// Table Players Dialog & Action Dialogs matching 100% of Windows table_players_dialog.py.
class TablePlayersDialog extends StatefulWidget {
  final Map<String, dynamic> room;
  final int myUserId;
  final VoidCallback onRoomUpdated;

  const TablePlayersDialog({
    super.key,
    required this.room,
    required this.myUserId,
    required this.onRoomUpdated,
  });

  static Future<void> show(
    BuildContext context, {
    required Map<String, dynamic> room,
    required int myUserId,
    required VoidCallback onRoomUpdated,
  }) {
    return showDialog(
      context: context,
      builder: (ctx) => TablePlayersDialog(
        room: room,
        myUserId: myUserId,
        onRoomUpdated: onRoomUpdated,
      ),
    );
  }

  @override
  State<TablePlayersDialog> createState() => _TablePlayersDialogState();
}

class _TablePlayersDialogState extends State<TablePlayersDialog> {
  late Map<String, dynamic> _room;
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    _room = widget.room;
  }

  String _getPlayerName(int uid, int hostId, String hostName, List<dynamic> players, List<dynamic> rawNames, Map<dynamic, dynamic> playersDict) {
    final suid = uid.toString();
    if (playersDict.containsKey(suid) && playersDict[suid] != null && playersDict[suid].toString().isNotEmpty) {
      return playersDict[suid].toString();
    }
    if (rawNames.isNotEmpty) {
      final idx = players.indexOf(uid);
      if (idx >= 0 && idx < rawNames.length && rawNames[idx] != null && rawNames[idx].toString().isNotEmpty) {
        return rawNames[idx].toString();
      }
    }
    if (uid == hostId) {
      return hostName;
    }
    return uid > 0 ? tr('لاعب {0}', {'0': '$uid'}) : 'Bot ${uid.abs()}';
  }

  List<Map<String, dynamic>> _buildPlayersList() {
    final hostId = int.tryParse(_room['host_id']?.toString() ?? '0') ?? 0;
    final hostName = _room['host_name']?.toString() ?? tr('القائد');
    final coHostId = int.tryParse(_room['co_host_id']?.toString() ?? '0');
    final players = List<dynamic>.from(_room['players'] ?? []);
    final spectators = List<dynamic>.from(_room['spectators'] ?? []);
    final rawNames = List<dynamic>.from(_room['player_names'] ?? []);
    final playersDict = Map<dynamic, dynamic>.from(_room['players_dict'] ?? {});

    final List<Map<String, dynamic>> list = [];

    // 1. Captain (always first)
    final hostIsSpectator = spectators.contains(hostId);
    list.add({
      'id': hostId,
      'display_name': hostName,
      'is_host': true,
      'is_co_host': false,
      'is_spectator': hostIsSpectator,
      'is_bot': false,
      'label': hostIsSpectator
          ? '$hostName (${tr('القائد')}) - ${tr('متفرج')}'
          : '$hostName (${tr('القائد')})',
    });

    // 2. Vice-Captain (second if present and not captain)
    if (coHostId != null && coHostId != 0 && coHostId != hostId && (players.contains(coHostId) || spectators.contains(coHostId))) {
      final coName = _getPlayerName(coHostId, hostId, hostName, players, rawNames, playersDict);
      final coIsSpectator = spectators.contains(coHostId);
      list.add({
        'id': coHostId,
        'display_name': coName,
        'is_host': false,
        'is_co_host': true,
        'is_spectator': coIsSpectator,
        'is_bot': false,
        'label': coIsSpectator
            ? '$coName (${tr('نائب القائد')}) - ${tr('متفرج')}'
            : '$coName (${tr('نائب القائد')})',
      });
    }

    // 3. Other Active Players
    for (final rawUid in players) {
      final uid = int.tryParse(rawUid.toString()) ?? 0;
      if (uid == hostId || uid == coHostId || uid < 0) continue;
      final name = _getPlayerName(uid, hostId, hostName, players, rawNames, playersDict);
      list.add({
        'id': uid,
        'display_name': name,
        'is_host': false,
        'is_co_host': false,
        'is_spectator': false,
        'is_bot': false,
        'label': name,
      });
    }

    // 4. Spectators (excluding host and co-host already listed)
    for (final rawUid in spectators) {
      final uid = int.tryParse(rawUid.toString()) ?? 0;
      if (uid == hostId || uid == coHostId) continue;
      final name = _getPlayerName(uid, hostId, hostName, players, rawNames, playersDict);
      list.add({
        'id': uid,
        'display_name': name,
        'is_host': false,
        'is_co_host': false,
        'is_spectator': true,
        'is_bot': false,
        'label': '$name (${tr('متفرج')})',
      });
    }

    // 5. Bots
    for (final rawUid in players) {
      final uid = int.tryParse(rawUid.toString()) ?? 0;
      if (uid >= 0) continue;
      final name = _getPlayerName(uid, hostId, hostName, players, rawNames, playersDict);
      list.add({
        'id': uid,
        'display_name': name,
        'is_host': false,
        'is_co_host': false,
        'is_spectator': false,
        'is_bot': true,
        'label': '$name (Bot)',
      });
    }

    return list;
  }

  void _onPlayerSelected(Map<String, dynamic> user) {
    final hostId = int.tryParse(_room['host_id']?.toString() ?? '0') ?? 0;
    final coHostId = int.tryParse(_room['co_host_id']?.toString() ?? '0') ?? 0;
    final isHost = (widget.myUserId == hostId);
    final isCoHost = (widget.myUserId == coHostId && coHostId != 0);

    TablePlayerActionsDialog.show(
      context,
      targetUser: user,
      isHost: isHost,
      isCoHost: isCoHost,
      myUserId: widget.myUserId,
      room: _room,
      onActionExecuted: () {
        widget.onRoomUpdated();
        Navigator.of(context).pop();
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final players = _buildPlayersList();

    return AlertDialog(
      backgroundColor: AppColors.surface,
      title: Text(
        tr('قائمة اللاعبين'),
        style: const TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold),
      ),
      content: SizedBox(
        width: double.maxFinite,
        child: _loading
            ? const Center(child: CircularProgressIndicator(color: AppColors.primary))
            : ListView.separated(
                shrinkWrap: true,
                itemCount: players.length,
                separatorBuilder: (_, __) => const Divider(color: AppColors.divider, height: 1),
                itemBuilder: (ctx, idx) {
                  final p = players[idx];
                  return ListTile(
                    title: Text(
                      p['label'] ?? '',
                      style: const TextStyle(color: AppColors.textPrimary, fontSize: 16),
                    ),
                    trailing: const Icon(Icons.arrow_forward_ios, size: 14, color: AppColors.textSecondary),
                    onTap: () => _onPlayerSelected(p),
                  );
                },
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

/// Contextual actions dialog for a single table member matching TablePlayerActionsDialog in Windows.
class TablePlayerActionsDialog extends StatelessWidget {
  final Map<String, dynamic> targetUser;
  final bool isHost;
  final bool isCoHost;
  final int myUserId;
  final Map<String, dynamic> room;
  final VoidCallback onActionExecuted;

  const TablePlayerActionsDialog({
    super.key,
    required this.targetUser,
    required this.isHost,
    required this.isCoHost,
    required this.myUserId,
    required this.room,
    required this.onActionExecuted,
  });

  static Future<void> show(
    BuildContext context, {
    required Map<String, dynamic> targetUser,
    required bool isHost,
    required bool isCoHost,
    required int myUserId,
    required Map<String, dynamic> room,
    required VoidCallback onActionExecuted,
  }) {
    return showDialog(
      context: context,
      builder: (ctx) => TablePlayerActionsDialog(
        targetUser: targetUser,
        isHost: isHost,
        isCoHost: isCoHost,
        myUserId: myUserId,
        room: room,
        onActionExecuted: onActionExecuted,
      ),
    );
  }

  List<Map<String, String>> _getAvailableActions() {
    final targetId = int.tryParse(targetUser['id']?.toString() ?? '0') ?? 0;
    final isMe = (targetId == myUserId);
    final isBot = (targetId < 0);
    final isTargetHost = targetUser['is_host'] == true;
    final isTargetCoHost = targetUser['is_co_host'] == true;
    final isSpectator = targetUser['is_spectator'] == true;

    final List<Map<String, String>> actions = [];

    // 1. Host transfer (only host can transfer, to another human player)
    if (isHost && !isMe && !isBot && !isTargetHost) {
      actions.add({'label': tr('تعيينه كقائد'), 'tag': 'transfer_host'});
    }

    // 2. Co-captain / Vice-Captain appointment (only host can appoint/cancel)
    if (isHost && !isMe && !isBot && !isTargetHost) {
      if (isTargetCoHost) {
        actions.add({'label': tr('إلغاء تعيين نائب القائد'), 'tag': 'set_co_host'});
      } else {
        actions.add({'label': tr('تعيين نائب كابتن'), 'tag': 'set_co_host'});
      }
    }

    // 3. Substitute (Host or Co-Host can substitute another player or bot)
    if ((isHost || isCoHost) && !isMe && !isTargetHost) {
      actions.add({'label': tr('استبدال'), 'tag': 'substitute'});
    }

    // 4. Kick and Ban (Host or Co-Host, cannot kick/ban host or another co-host if user is co-host)
    bool canKickBan = false;
    if (isHost && !isMe && !isTargetHost) {
      canKickBan = true;
    } else if (isCoHost && !isMe && !isTargetHost && !isTargetCoHost) {
      canKickBan = true;
    }

    if (canKickBan) {
      actions.add({'label': tr('طرد'), 'tag': 'kick'});
      actions.add({'label': tr('حظر من الطاولة'), 'tag': 'ban'});
    }

    // 5. Make Spectator (Host on active player)
    if (isHost && !isMe && !isTargetHost && !isSpectator) {
      actions.add({'label': tr('تحويل إلى متفرج'), 'tag': 'make_spectator'});
    }

    return actions;
  }

  Future<void> _handleAction(BuildContext context, String tag) async {
    final roomId = room['id']?.toString() ?? room['room_id']?.toString() ?? '';
    final targetId = int.tryParse(targetUser['id']?.toString() ?? '0') ?? 0;
    final targetName = targetUser['display_name'] ?? 'لاعب';

    try {
      if (tag == 'transfer_host') {
        await ApiService.instance.transferHost(roomId, targetId);
        AccessibilityManager.instance.announce(tr('تم تعيين {name} كقائد للطاولة.', {'name': targetName}));
      } else if (tag == 'set_co_host') {
        await ApiService.instance.setCoHost(roomId, targetId);
        AccessibilityManager.instance.announce(tr('تم تحديث منصب نائب الكابتن.'));
      } else if (tag == 'kick') {
        await ApiService.instance.kickPlayer(roomId, targetId);
        AccessibilityManager.instance.announce(tr('تم طرد {name} من الطاولة.', {'name': targetName}));
      } else if (tag == 'ban') {
        await ApiService.instance.banPlayer(roomId, targetId);
        AccessibilityManager.instance.announce(tr('تم حظر {name} من الطاولة.', {'name': targetName}));
      } else if (tag == 'make_spectator') {
        await ApiService.instance.toggleSpectator(roomId, targetUserId: targetId);
        AccessibilityManager.instance.announce(tr('تم تحويل {name} إلى وضع المتفرج.', {'name': targetName}));
      } else if (tag == 'substitute') {
        // Substitute choice dialog
        _showSubstituteChoiceDialog(context, roomId, targetId);
        return;
      }

      await SoundService.instance.playSound('ACTION_CLICK');
      if (context.mounted) {
        Navigator.of(context).pop();
        onActionExecuted();
      }
    } catch (e) {
      await SoundService.instance.playSound('INVALID_ACTION');
      AccessibilityManager.instance.announce(tr('تعذر تنفيذ الإجراء: {error}', {'error': e.toString()}));
    }
  }

  void _showSubstituteChoiceDialog(BuildContext context, String roomId, int targetId) {
    final players = List<dynamic>.from(room['players'] ?? []);
    final spectators = List<dynamic>.from(room['spectators'] ?? []);
    final List<Map<String, dynamic>> candidates = [];

    // Option 1: Replace with bot
    if (targetId > 0) {
      candidates.add({'label': tr('استبدال ببوت'), 'is_bot': true, 'id': null});
    }

    // Option 2: Replace with other human members
    final allCandidates = <int>{};
    for (final uid in [...players, ...spectators]) {
      final parsed = int.tryParse(uid.toString()) ?? 0;
      if (parsed > 0 && parsed != targetId && parsed != myUserId) {
        allCandidates.add(parsed);
      }
    }

    for (final cid in allCandidates) {
      candidates.add({'label': tr('لاعب {0}', {'0': '$cid'}), 'is_bot': false, 'id': cid});
    }

    showDialog(
      context: context,
      builder: (subCtx) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: Text(tr('خيارات الاستبدال'), style: const TextStyle(color: AppColors.textPrimary)),
        content: SizedBox(
          width: double.maxFinite,
          child: ListView.separated(
            shrinkWrap: true,
            itemCount: candidates.length,
            separatorBuilder: (_, __) => const Divider(color: AppColors.divider, height: 1),
            itemBuilder: (c, i) {
              final cand = candidates[i];
              return ListTile(
                title: Text(cand['label'], style: const TextStyle(color: AppColors.textPrimary)),
                onTap: () async {
                  Navigator.of(subCtx).pop();
                  try {
                    await ApiService.instance.substitutePlayer(
                      roomId,
                      targetId,
                      replacementUserId: cand['id'],
                      isBot: cand['is_bot'] == true,
                    );
                    await SoundService.instance.playSound('ACTION_CLICK');
                    AccessibilityManager.instance.announce(tr('تم استبدال اللاعب بنجاح.'));
                    if (context.mounted) {
                      Navigator.of(context).pop();
                      onActionExecuted();
                    }
                  } catch (e) {
                    await SoundService.instance.playSound('INVALID_ACTION');
                    AccessibilityManager.instance.announce(tr('تعذر استبدال اللاعب'));
                  }
                },
              );
            },
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final targetName = targetUser['display_name'] ?? 'لاعب';
    final actions = _getAvailableActions();

    return AlertDialog(
      backgroundColor: AppColors.surface,
      title: Text(
        tr('إجراءات {name}', {'name': targetName}),
        style: const TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold),
      ),
      content: SizedBox(
        width: double.maxFinite,
        child: actions.isEmpty
            ? Padding(
                padding: const EdgeInsets.all(16.0),
                child: Text(
                  tr('لا توجد إجراءات متاحة لهذا اللاعب.'),
                  style: const TextStyle(color: AppColors.textSecondary),
                ),
              )
            : ListView.separated(
                shrinkWrap: true,
                itemCount: actions.length,
                separatorBuilder: (_, __) => const Divider(color: AppColors.divider, height: 1),
                itemBuilder: (ctx, idx) {
                  final act = actions[idx];
                  final isDestructive = act['tag'] == 'kick' || act['tag'] == 'ban';
                  return ListTile(
                    title: Text(
                      act['label'] ?? '',
                      style: TextStyle(
                        color: isDestructive ? AppColors.error : AppColors.textPrimary,
                        fontSize: 16,
                      ),
                    ),
                    onTap: () => _handleAction(context, act['tag'] ?? ''),
                  );
                },
              ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: Text(tr('إلغاء'), style: const TextStyle(color: AppColors.textSecondary)),
        ),
      ],
    );
  }
}
