import 'package:flutter/material.dart';
import '../core/app_theme.dart';
import '../core/accessibility_manager.dart';
import '../core/localization.dart';
import '../core/sound_service.dart';
import '../services/api_service.dart';
import 'game_adapter.dart';

/// Farkle Game Adapter providing board UI, dice display, scoring combinations,
/// and 4-way gesture handling replicating Windows client/views/table_view.py.
class FarkleGameAdapter extends GameAdapter {
  @override
  String get gameId => 'FARKLE';

  @override
  String get displayName => tr('فاركل');

  @override
  Widget buildBoard(BuildContext context, Map<String, dynamic> state) {
    final roomId = (state['room_id'] ?? '').toString();
    final dice = List<dynamic>.from(state['dice'] ?? state['last_roll'] ?? []);
    final turnScore = int.tryParse(state['turn_score']?.toString() ?? '0') ?? 0;
    final isMyTurn = state['is_my_turn'] == true;
    final canRoll = isMyTurn && state['can_roll'] == true && state['must_score_before_roll'] != true;
    final availableCombos = List<dynamic>.from(state['available_combinations'] ?? []);
    final minBank = int.tryParse(state['min_bank']?.toString() ?? '30') ?? 30;
    final mustScoreBeforeRoll = state['must_score_before_roll'] == true;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Score & Dice Summary Card
        Semantics(
          excludeSemantics: true,
          label: tr('نقاط الدور الحالي: {score}', {'score': '$turnScore'}),
          child: Container(
            padding: const EdgeInsets.all(12.0),
            decoration: BoxDecoration(
              color: AppColors.surfaceLight,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppColors.primary.withOpacity(0.3)),
            ),
            child: Row(
              children: [
                const Icon(Icons.casino, color: AppColors.primary, size: 26),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        tr('نقاط الدور الحالي: {score}', {'score': '$turnScore'}),
                        style: const TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: AppColors.textPrimary,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        dice.isEmpty
                            ? tr('لا توجد رمية سابقة.')
                            : tr('النرد: {dice}', {'dice': dice.join('، ')}),
                        style: const TextStyle(fontSize: 14, color: AppColors.textSecondary),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 10),

        // Actions Header
        Text(
          isMyTurn ? tr('الإجراءات المتاحة') : tr('في انتظار انتهاء دور اللاعب'),
          style: const TextStyle(
            fontSize: 15,
            fontWeight: FontWeight.bold,
            color: AppColors.textSecondary,
          ),
        ),
        const SizedBox(height: 6),

        // Actions List
        Expanded(
          child: ListView(
            children: [
              if (isMyTurn) ...[
                // 1. Available winning combinations from the roll
                for (final comboItem in availableCombos)
                  if (comboItem is Map)
                    Builder(builder: (ctx) {
                      final labelAr = (comboItem['label'] ?? '').toString();
                      final labelEn = (comboItem['label_en'] ?? '').toString();
                      final itemText = labelAr.isNotEmpty ? tr(labelAr) : labelEn;
                      final indices = List<dynamic>.from(comboItem['indices'] ?? []);

                      return Padding(
                        padding: const EdgeInsets.only(bottom: 6.0),
                        child: Card(
                          color: AppColors.surfaceLight,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                          child: ListTile(
                            leading: const Icon(Icons.check_circle_outline, color: AppColors.success),
                            title: Text(
                              itemText,
                              style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w600,
                                color: AppColors.textPrimary,
                              ),
                            ),
                            trailing: const Icon(Icons.add, color: AppColors.primary),
                            onTap: () {
                              final indicesStr = (List<int>.from(indices.map((x) => int.tryParse(x.toString()) ?? 0))..sort()).join(',');
                              ApiService.instance.sendGameAction(roomId, {
                                'action': 'score',
                                'data': {'indices': indicesStr},
                              });
                            },
                          ),
                        ),
                      );
                    }),

                // 2. Roll Dice Option
                Builder(builder: (ctx) {
                  final numDice = dice.isNotEmpty ? dice.length : 6;
                  final rollText = tr('ارمِ {count} نرد', {'count': '$numDice'});

                  return Padding(
                    padding: const EdgeInsets.only(bottom: 6.0),
                    child: Card(
                      color: canRoll ? AppColors.surfaceLight : AppColors.surfaceLight.withOpacity(0.5),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                      child: ListTile(
                        leading: const Icon(Icons.refresh, color: AppColors.primary),
                        title: Text(
                          rollText,
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                            color: canRoll ? AppColors.textPrimary : AppColors.textSecondary,
                          ),
                        ),
                        onTap: () {
                          if (mustScoreBeforeRoll) {
                            AccessibilityManager.instance.announce(
                              tr('يجب عليك اختيار وتثبيت مجموعة رابحة أولًا قبل الرمي مجددًا.'),
                            );
                            SoundService.instance.playSound('INVALID_ACTION');
                            return;
                          }
                          ApiService.instance.sendGameAction(roomId, {'action': 'roll'});
                        },
                      ),
                    ),
                  );
                }),

                // 3. Bank Points Option
                Builder(builder: (ctx) {
                  final bankText = tr('تثبيت {score} نقطة لهذا الدور', {'score': '$turnScore'});

                  return Padding(
                    padding: const EdgeInsets.only(bottom: 6.0),
                    child: Card(
                      color: AppColors.surfaceLight,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                      child: ListTile(
                        leading: const Icon(Icons.save_alt, color: AppColors.success),
                        title: Text(
                          bankText,
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                            color: AppColors.success,
                          ),
                        ),
                        onTap: () {
                          if (mustScoreBeforeRoll) {
                            AccessibilityManager.instance.announce(
                              tr('يجب عليك اختيار مجموعة رابحة أولًا قبل تثبيت النقاط.'),
                            );
                            SoundService.instance.playSound('INVALID_ACTION');
                            return;
                          }
                          if (turnScore < minBank) {
                            AccessibilityManager.instance.announce(
                              tr('لا يمكنك التثبيت الآن. الحد الأدنى للتثبيت هو {min} نقطة.', {'min': '$minBank'}),
                            );
                            SoundService.instance.playSound('INVALID_ACTION');
                            return;
                          }
                          ApiService.instance.sendGameAction(roomId, {'action': 'bank'});
                        },
                      ),
                    ),
                  );
                }),
              ] else ...[
                Center(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 24.0),
                    child: Text(
                      tr('في انتظار دورك...'),
                      style: const TextStyle(fontSize: 16, color: AppColors.textSecondary),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }

  @override
  void onSpaceAction(BuildContext context, Map<String, dynamic> state, String roomId) {
    // Replicates on_draw_shortcut for Farkle from client/client_app.py:1675
    if (state['active'] != true) return;
    final roll = state['last_roll'] ?? state['dice'];
    if (roll is List && roll.isNotEmpty) {
      AccessibilityManager.instance.announce(roll.join('، '));
    } else {
      AccessibilityManager.instance.announce(tr('لا توجد رمية سابقة.'));
    }
  }

  @override
  void announceTop(BuildContext context, Map<String, dynamic> state) {
    // Replicates on_announce_top for Farkle from client/client_app.py:296
    onSpaceAction(context, state, (state['room_id'] ?? '').toString());
  }

  @override
  void announceTurn(BuildContext context, Map<String, dynamic> state) {
    // Replicates on_announce_turn for Farkle from client/client_app.py:2391
    if (state['active'] != true) {
      AccessibilityManager.instance.announce(tr('المباراة لم تبدأ بعد.'));
      return;
    }
    final curr = (state['current_player_name'] ?? '').toString();
    AccessibilityManager.instance.announce(curr.isNotEmpty ? tr('دور {name}', {'name': curr}) : tr('غير محدد'));
  }
}
