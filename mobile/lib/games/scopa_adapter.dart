import 'package:flutter/material.dart';
import '../core/app_theme.dart';
import '../core/accessibility_manager.dart';
import '../core/localization.dart';
import '../services/api_service.dart';
import 'card_models.dart';
import 'game_adapter.dart';

/// Scopa Game Adapter providing board UI, table cards, hand interactions, and 4-way gesture handling.
/// Replicates the Windows desktop client Scopa architecture with literal parity.
class ScopaGameAdapter extends GameAdapter {
  @override
  String get gameId => 'SCOPA';

  @override
  String get displayName => tr('إسكوبا');

  @override
  Widget buildBoard(BuildContext context, Map<String, dynamic> state) {
    final roomId = (state['room_id'] ?? '').toString();
    final tableCards = List<dynamic>.from(state['table_cards'] ?? []);
    final hand = List<dynamic>.from(state['my_hand'] ?? []);

    return hand.isEmpty
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
                          onTap: () {
                            ApiService.instance.sendGameAction(roomId, {
                              'action': 'play',
                              'card_id': index.toString(),
                              'data': {'choice_idx': ''},
                            });
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
    // In Scopa, card deal is fully automated in batches of 3. There is no manual draw action.
    announceTop(context, state);
  }

  @override
  void announceTop(BuildContext context, Map<String, dynamic> state) {
    if (state['active'] != true) {
      AccessibilityManager.instance.announce(tr('المباراة لم تبدأ بعد.'));
      return;
    }
    final tableCards = List<dynamic>.from(state['table_cards'] ?? []);
    if (tableCards.isEmpty) {
      AccessibilityManager.instance.announce(tr('الطاولة فارغة.'));
    } else {
      final names = tableCards.map((c) => cardDisplayAr((c is Map) ? Map<String, dynamic>.from(c) : <String, dynamic>{})).join('، ');
      AccessibilityManager.instance.announce(names);
    }
  }

  @override
  void announceTurn(BuildContext context, Map<String, dynamic> state) {
    if (state['active'] != true) {
      AccessibilityManager.instance.announce(tr('المباراة لم تبدأ بعد.'));
      return;
    }
    final curr = (state['current_turn_name'] ?? state['current_player_name'] ?? '').toString();
    AccessibilityManager.instance.announce(curr.isNotEmpty ? tr('دور {name}', {'name': curr}) : tr('غير محدد'));
  }
}
