import 'package:flutter/material.dart';
import '../core/app_theme.dart';
import '../core/accessibility_manager.dart';
import '../core/localization.dart';
import '../services/api_service.dart';
import 'card_models.dart';
import 'dialogs/ninety_nine_choice_dialog.dart';
import 'game_adapter.dart';

/// Ninety-Nine (99) Game Adapter providing board UI, pile value, card interactions, and 4-way gesture handling.
/// Replicates the Windows desktop client Ninety-Nine architecture with literal parity.
class NinetyNineGameAdapter extends GameAdapter {
  @override
  String get gameId => 'NINETY_NINE';

  @override
  String get displayName => tr('تسعة وتسعون');

  @override
  Widget buildBoard(BuildContext context, Map<String, dynamic> state) {
    final roomId = (state['room_id'] ?? '').toString();
    final pileValue = state['pile_value'] ?? 0;
    final hand = List<dynamic>.from(state['hand'] ?? state['cards'] ?? []);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Pile Value Display
        Semantics(
          label: tr('المجموع {pile}', {'pile': pileValue.toString()}),
          child: Container(
            padding: const EdgeInsets.all(12.0),
            decoration: BoxDecoration(
              color: AppColors.surfaceLight,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppColors.primary.withOpacity(0.3)),
            ),
            child: Row(
              children: [
                const Icon(Icons.calculate, color: AppColors.primary, size: 26),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        tr('مجموع الكومة'),
                        style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                      ),
                      Text(
                        tr('المجموع {pile}', {'pile': pileValue.toString()}),
                        style: const TextStyle(
                          fontSize: 19,
                          fontWeight: FontWeight.bold,
                          color: AppColors.textPrimary,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 10),

        // Hand Cards Header
        Text(
          tr('أوراقك في اليد ({count})', {'count': '${hand.length}'}),
          style: const TextStyle(
            fontSize: 15,
            fontWeight: FontWeight.bold,
            color: AppColors.textSecondary,
          ),
        ),
        const SizedBox(height: 6),

        // Hand Cards List
        Expanded(
          child: hand.isEmpty
              ? Center(
                  child: Text(
                    tr('لا توجد أوراق في اليد'),
                    style: const TextStyle(fontSize: 15, color: AppColors.textSecondary),
                  ),
                )
              : ListView.builder(
                  itemCount: hand.length,
                  itemBuilder: (ctx, index) {
                    final cardItem = hand[index];
                    final cardMap = (cardItem is Map) ? Map<String, dynamic>.from(cardItem) : <String, dynamic>{};
                    final cardLabel = cardDisplayAr(cardMap);
                    final cardId = (cardMap['id'] ?? index).toString();
                    final val = cardMap['value'];
                    final isTen = val == 10 || val == '10';

                    return Padding(
                      padding: const EdgeInsets.only(bottom: 6.0),
                      child: Card(
                        color: AppColors.surfaceLight,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                        child: ListTile(
                          title: Text(
                            cardLabel,
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
                              color: AppColors.textPrimary,
                            ),
                          ),
                          trailing: const Icon(Icons.play_arrow, size: 20, color: AppColors.primary),
                          onTap: () async {
                            if (isTen) {
                              final choice = await NinetyNineChoiceDialog.show(
                                context,
                                options: const [
                                  MapEntry('+10', '10'),
                                  MapEntry('-10', '-10'),
                                ],
                              );
                              if (choice != null) {
                                ApiService.instance.sendGameAction(roomId, {
                                  'action': 'play',
                                  'card_id': cardId,
                                  'data': {'value': choice},
                                });
                              }
                            } else {
                              ApiService.instance.sendGameAction(roomId, {
                                'action': 'play',
                                'card_id': cardId,
                              });
                            }
                          },
                        ),
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }

  @override
  void onSpaceAction(BuildContext context, Map<String, dynamic> state, String roomId) {
    if (state['active'] != true) return;
    ApiService.instance.sendGameAction(roomId, {'action': 'draw'});
  }

  @override
  void announceTop(BuildContext context, Map<String, dynamic> state) {
    if (state['active'] != true) {
      AccessibilityManager.instance.announce(tr('المباراة لم تبدأ بعد.'));
      return;
    }
    final pile = state['pile_value'] ?? 0;
    AccessibilityManager.instance.announce(tr('المجموع {pile}', {'pile': pile.toString()}));
  }

  @override
  void announceTurn(BuildContext context, Map<String, dynamic> state) {
    if (state['active'] != true) {
      AccessibilityManager.instance.announce(tr('المباراة لم تبدأ بعد.'));
      return;
    }
    final idx = int.tryParse(state['current_turn_index']?.toString() ?? '0') ?? 0;
    final players = List<dynamic>.from(state['players'] ?? []);
    String currName = '';
    if (idx >= 0 && idx < players.length) {
      final p = players[idx];
      if (p is Map) {
        currName = (p['name'] ?? '').toString();
      }
    }
    if (currName.isEmpty) {
      currName = (state['current_player_name'] ?? state['current_turn_name'] ?? '').toString();
    }
    AccessibilityManager.instance.announce(currName.isNotEmpty ? tr('دور {name}', {'name': currName}) : tr('غير محدد'));
  }
}
