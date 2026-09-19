import 'package:flutter/material.dart';
import '../core/app_theme.dart';
import '../core/accessibility_manager.dart';
import '../core/localization.dart';
import '../services/api_service.dart';
import 'card_models.dart';
import 'dialogs/wild_color_picker_dialog.dart';
import 'game_adapter.dart';

/// UNO Game Adapter providing board UI, card interactions, and 4-way gesture handling.
/// Replicates the Windows desktop client UNO architecture with literal parity.
class UnoGameAdapter extends GameAdapter {
  @override
  String get gameId => 'UNO';

  @override
  String get displayName => tr('أونو');

  @override
  Widget buildBoard(BuildContext context, Map<String, dynamic> state) {
    final roomId = (state['room_id'] ?? '').toString();
    final topCard = state['top_card'] as Map<String, dynamic>?;
    final topCardText = cardDisplayAr(topCard);
    final chosenColor = (state['current_color'] ?? topCard?['chosen_color'] ?? '').toString();
    final chosenColorAr = COLOR_NAMES_AR[chosenColor] ?? chosenColor;
    final effectiveTopText = (topCard != null && (WILD_TYPES.contains(topCard['type']) || topCard['color'] == 'wild') && chosenColor.isNotEmpty)
        ? '$topCardText $chosenColorAr'
        : topCardText;

    final hand = List<dynamic>.from(state['hand'] ?? state['cards'] ?? []);
    final isDarkSide = state['dark_side'] == true;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Top Card Display
        Semantics(
          excludeSemantics: true,
          label: tr('الورقة المكشوفة: {card}', {'card': effectiveTopText}),
          child: Container(
            padding: const EdgeInsets.all(12.0),
            decoration: BoxDecoration(
              color: AppColors.surfaceLight,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppColors.primary.withOpacity(0.3)),
            ),
            child: Row(
              children: [
                const Icon(Icons.style, color: AppColors.primary, size: 24),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        tr('الورقة المكشوفة'),
                        style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                      ),
                      Text(
                        effectiveTopText,
                        style: const TextStyle(
                          fontSize: 17,
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
                    final isWild = WILD_TYPES.contains(cardMap['type']) || cardMap['color'] == 'wild';

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
                          trailing: const Icon(Icons.arrow_forward_ios, size: 14, color: AppColors.textSecondary),
                          onTap: () async {
                            if (isWild) {
                              final color = await WildColorPickerDialog.show(context, darkSide: isDarkSide);
                              if (color != null && color.isNotEmpty) {
                                ApiService.instance.sendGameAction(roomId, {
                                  'action': 'play',
                                  'card_id': cardId,
                                  'chosen_color': color,
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
    final top = state['top_card'] as Map<String, dynamic>?;
    if (top == null || top.isEmpty) {
      AccessibilityManager.instance.announce(tr('لا توجد ورقة مكشوفة.'));
      return;
    }
    var topName = cardDisplayAr(top);
    if (WILD_TYPES.contains(top['type']) || top['card_type'] == 'wild' || top['color'] == 'wild') {
      final chosenColor = (state['current_color'] ?? top['chosen_color'] ?? '').toString();
      if (chosenColor.isNotEmpty) {
        final colorAr = COLOR_NAMES_AR[chosenColor] ?? chosenColor;
        topName = '$topName $colorAr';
      }
    }
    AccessibilityManager.instance.announce(tr(topName));
  }

  @override
  void announceTurn(BuildContext context, Map<String, dynamic> state) {
    if (state['active'] != true) {
      AccessibilityManager.instance.announce(tr('المباراة لم تبدأ بعد.'));
      return;
    }
    final curr = (state['current_player_name'] ?? state['current_turn_name'] ?? '').toString();
    AccessibilityManager.instance.announce(curr.isNotEmpty ? tr('دور {name}', {'name': curr}) : tr('غير محدد'));
  }
}
