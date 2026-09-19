import 'package:flutter/material.dart';
import '../../core/app_theme.dart';
import '../../core/localization.dart';

/// Accessible dialog for host to select teammate in team games (e.g. Scopa with teams).
/// Replicates TableTeamSelectionDialog from client/views/table_players_dialog.py.
class TableTeamSelectionDialog extends StatelessWidget {
  final List<Map<String, dynamic>> players;
  final int currentUserId;

  const TableTeamSelectionDialog({
    super.key,
    required this.players,
    required this.currentUserId,
  });

  static Future<Map<String, int>?> show(
    BuildContext context, {
    required List<Map<String, dynamic>> players,
    required int currentUserId,
  }) {
    return showDialog<Map<String, int>>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => TableTeamSelectionDialog(
        players: players,
        currentUserId: currentUserId,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    // Candidates are other players (excluding host)
    final candidatePlayers = players.where((p) {
      final uid = int.tryParse(p['id']?.toString() ?? '0') ?? 0;
      return uid != currentUserId;
    }).toList();

    return AlertDialog(
      backgroundColor: AppColors.surface,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      title: Text(
        tr('اختيار الفريق'),
        style: const TextStyle(
          fontSize: 20,
          fontWeight: FontWeight.bold,
          color: AppColors.textPrimary,
        ),
      ),
      content: SizedBox(
        width: double.maxFinite,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              tr('اختر زميلك في الفريق:'),
              style: const TextStyle(fontSize: 15, color: AppColors.textSecondary),
            ),
            const SizedBox(height: 12),
            Flexible(
              child: ListView.builder(
                shrinkWrap: true,
                itemCount: candidatePlayers.length,
                itemBuilder: (ctx, index) {
                  final p = candidatePlayers[index];
                  final uid = int.tryParse(p['id']?.toString() ?? '0') ?? 0;
                  final name = (p['name'] ?? p['username'] ?? 'لاعب $uid').toString();

                  return Padding(
                    padding: const EdgeInsets.only(bottom: 6.0),
                    child: Card(
                      color: AppColors.surfaceLight,
                      child: ListTile(
                        leading: const Icon(Icons.person, color: AppColors.primary),
                        title: Text(
                          name,
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w600,
                            color: AppColors.textPrimary,
                          ),
                        ),
                        onTap: () {
                          // Build team assignments:
                          // Team 0: Host and chosen partner
                          // Team 1: Remaining players
                          final teamAssignments = <String, int>{};
                          teamAssignments[currentUserId.toString()] = 0;
                          teamAssignments[uid.toString()] = 0;

                          for (final other in players) {
                            final otherUid = int.tryParse(other['id']?.toString() ?? '0') ?? 0;
                            if (otherUid != currentUserId && otherUid != uid) {
                              teamAssignments[otherUid.toString()] = 1;
                            }
                          }

                          Navigator.of(context).pop(teamAssignments);
                        },
                      ),
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(null),
          child: Text(tr('إلغاء'), style: const TextStyle(color: AppColors.textSecondary)),
        ),
      ],
    );
  }
}
