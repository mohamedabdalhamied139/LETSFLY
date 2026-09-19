import 'dart:async';
import 'package:flutter/material.dart';
import '../core/app_theme.dart';
import '../core/accessibility_manager.dart';
import '../core/haptic_service.dart';
import '../core/localization.dart';
import '../core/sound_service.dart';
import '../services/api_service.dart';
import 'game_adapter.dart';

/// Snakes and Ladders Game Adapter providing board UI, radar information,
/// step-by-step token movement audio sequence, and 4-way gesture handling
/// replicating Windows client/client_app.py and client/views/table_view.py.
class SnakesGameAdapter extends GameAdapter {
  @override
  String get gameId => 'SNAKES_LADDERS';

  @override
  String get displayName => tr('السلم والثعبان');

  int _lastStepEventId = 0;
  bool _isStepping = false;
  Timer? _stepTimer;

  void _processSnakesState(Map<String, dynamic> state) {
    if (state['active'] != true) {
      _isStepping = false;
      _stepTimer?.cancel();
      return;
    }

    final et = (state['event_type'] ?? '').toString().toUpperCase();
    final roll = int.tryParse(state['last_roll']?.toString() ?? '0') ?? 0;
    final eventId = int.tryParse(state['event_id']?.toString() ?? '0') ?? 0;

    if (['DICE_ROLLED', 'BONUS_ROLL', 'MATCH_FINISHED'].contains(et) &&
        roll > 0 &&
        eventId != _lastStepEventId) {
      _lastStepEventId = eventId;
      _isStepping = true;
      _stepTimer?.cancel();

      final rollAction = (state['roll_action'] ?? '').toString();
      if (rollAction.isNotEmpty) {
        AccessibilityManager.instance.announce(tr(rollAction), interrupt: true);
      }

      final arrivalAnnouncement =
          (state['arrival_action'] ?? state['last_action'] ?? '').toString();
      final rawCues = List<dynamic>.from(state['sound_cues'] ?? []);
      final arrivalCues = rawCues
          .map((c) => c.toString())
          .where((c) => [
                'SNAKE_BITE',
                'LADDER_CLIMB',
                'FREEZE_TRAP',
                'MYSTERY_BOX',
                'PLAYER_BUMP',
                'MATCH_WIN',
              ].contains(c))
          .toList();

      _playSteps(roll, 1, arrivalCues, arrivalAnnouncement, state);
    } else if (['CANNOT_MOVE', 'MATCH_WON', 'PLAYER_FROZEN'].contains(et)) {
      _isStepping = false;
      _stepTimer?.cancel();
      if (['CANNOT_MOVE', 'PLAYER_FROZEN'].contains(et)) {
        final lastAction = (state['last_action'] ?? '').toString();
        if (lastAction.isNotEmpty) {
          AccessibilityManager.instance.announce(tr(lastAction), interrupt: true);
        }
      }
    }
  }

  void _playSteps(
    int roll,
    int currentStep,
    List<String> arrivalCues,
    String arrivalAnnouncement,
    Map<String, dynamic> state,
  ) {
    if (currentStep > roll) {
      for (final cue in arrivalCues) {
        SoundService.instance.playSound(cue);
      }

      if (arrivalAnnouncement.isNotEmpty) {
        Timer(const Duration(milliseconds: 80), () {
          AccessibilityManager.instance.announce(tr(arrivalAnnouncement), interrupt: true);
        });
      }

      final et = (state['event_type'] ?? '').toString().toUpperCase();
      final isMatchFinished = ['MATCH_FINISHED', 'MATCH_WON'].contains(et) ||
          state['winner_id'] != null;

      if (isMatchFinished) {
        _isStepping = false;
        return;
      }

      final delay = arrivalAnnouncement.isNotEmpty ? 500 : 100;
      Timer(Duration(milliseconds: delay), () {
        _isStepping = false;
        final isMyTurn = state['is_my_turn'] == true;
        final currentName = (state['current_player_name'] ??
                state['current_turn_name'] ??
                tr('غير معروف'))
            .toString();

        if (isMyTurn) {
          SoundService.instance.playSound('TURN_START');
          HapticService.instance.playTurnHaptic();
          AccessibilityManager.instance.announce(tr('دورك'), interrupt: false);
        } else {
          AccessibilityManager.instance.announce(
            tr('دور {name}', {'name': currentName}),
            interrupt: false,
          );
        }
      });
      return;
    }

    SoundService.instance.playSound('STEP_MOVE');
    _stepTimer = Timer(const Duration(milliseconds: 320), () {
      _playSteps(roll, currentStep + 1, arrivalCues, arrivalAnnouncement, state);
    });
  }

  @override
  Widget buildBoard(BuildContext context, Map<String, dynamic> state) {
    _processSnakesState(state);

    final roomId = (state['room_id'] ?? '').toString();
    final isMyTurn = state['is_my_turn'] == true;
    final lastRoll = int.tryParse(state['last_roll']?.toString() ?? '0') ?? 0;
    final radar = state['radar'] as Map? ?? {};
    final pos = int.tryParse(radar['position']?.toString() ?? '0') ?? 0;
    final ladder = radar['nearest_ladder'] as List?;
    final snake = radar['nearest_snake'] as List?;
    final dist = int.tryParse(radar['distance_to_finish']?.toString() ?? '${100 - pos}') ?? (100 - pos);
    final players = List<dynamic>.from(state['players'] ?? []);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // 1. Radar & Position Card
        Semantics(
          excludeSemantics: true,
          label: _buildRadarSpeech(radar),
          child: Container(
            padding: const EdgeInsets.all(12.0),
            decoration: BoxDecoration(
              color: AppColors.surfaceLight,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppColors.primary.withOpacity(0.3)),
            ),
            child: Row(
              children: [
                const Icon(Icons.explore, color: AppColors.primary, size: 28),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        tr('المربع {position}', {'position': '$pos'}),
                        style: const TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: AppColors.textPrimary,
                        ),
                      ),
                      const SizedBox(height: 4),
                      if (ladder != null && ladder.length >= 2)
                        Text(
                          tr('سلم في {base} إلى {top}', {'base': '${ladder[0]}', 'top': '${ladder[1]}'}),
                          style: const TextStyle(fontSize: 13, color: AppColors.success),
                        ),
                      if (snake != null && snake.length >= 2)
                        Text(
                          tr('ثعبان في {head} إلى {tail}', {'head': '${snake[0]}', 'tail': '${snake[1]}'}),
                          style: const TextStyle(fontSize: 13, color: AppColors.error),
                        ),
                      Text(
                        tr('المتبقي للنهاية: {dist} مربع', {'dist': '$dist'}),
                        style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                      ),
                    ],
                  ),
                ),
                if (lastRoll > 0)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(
                      color: AppColors.primary.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Column(
                      children: [
                        const Icon(Icons.casino, color: AppColors.primary, size: 20),
                        const SizedBox(height: 2),
                        Text(
                          '$lastRoll',
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                            color: AppColors.primary,
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

        // 2. Action Button (Matches Windows SnakesActionList "ارمي النرد")
        Card(
          color: (isMyTurn && !_isStepping)
              ? AppColors.surfaceLight
              : AppColors.surfaceLight.withOpacity(0.5),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
          child: ListTile(
            leading: Icon(
              Icons.play_circle_fill,
              color: (isMyTurn && !_isStepping) ? AppColors.primary : AppColors.textSecondary,
              size: 28,
            ),
            title: Text(
              tr('ارمي النرد'),
              style: TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.bold,
                color: (isMyTurn && !_isStepping)
                    ? AppColors.textPrimary
                    : AppColors.textSecondary,
              ),
            ),
            subtitle: Text(
              isMyTurn
                  ? tr('دورك الآن! اضغط للرمي أو اسحب بإصبعين للأسفل')
                  : tr('في انتظار دور اللاعب...'),
              style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
            ),
            onTap: () {
              if (_isStepping || !isMyTurn) {
                AccessibilityManager.instance.announce(tr('ليس دورك الآن.'), interrupt: true);
                SoundService.instance.playSound('INVALID_ACTION');
                return;
              }
              ApiService.instance.sendGameAction(roomId, {'action': 'roll'});
            },
          ),
        ),
        const SizedBox(height: 10),

        // 3. Player Positions Header & List
        Text(
          tr('مواقع اللاعبين'),
          style: const TextStyle(
            fontSize: 15,
            fontWeight: FontWeight.bold,
            color: AppColors.textSecondary,
          ),
        ),
        const SizedBox(height: 6),
        Expanded(
          child: ListView.builder(
            itemCount: players.length,
            itemBuilder: (context, index) {
              final p = players[index];
              if (p is! Map) return const SizedBox.shrink();
              final rank = index + 1;
              final name = (p['name'] ?? tr('لاعب')).toString();
              final position = int.tryParse(p['position']?.toString() ?? '0') ?? 0;
              final isFrozen = p['is_frozen'] == true;
              final hasShield = p['has_shield'] == true;

              final statusParts = <String>[];
              if (isFrozen) statusParts.add(tr('مجمد'));
              if (hasShield) statusParts.add(tr('مع درع'));
              final statusStr = statusParts.isNotEmpty ? ' (${statusParts.join('، ')})' : '';

              final itemSemantic = tr(
                'المركز {rank}: {name} في المربع {position}{status}',
                {'rank': '$rank', 'name': name, 'position': '$position', 'status': statusStr},
              );

              return Semantics(
                excludeSemantics: true,
                label: itemSemantic,
                child: Card(
                  color: AppColors.surfaceLight,
                  margin: const EdgeInsets.only(bottom: 6.0),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  child: ListTile(
                    leading: CircleAvatar(
                      backgroundColor: rank == 1
                          ? AppColors.primary
                          : AppColors.surface,
                      foregroundColor: rank == 1
                          ? Colors.white
                          : AppColors.textPrimary,
                      child: Text('$rank', style: const TextStyle(fontWeight: FontWeight.bold)),
                    ),
                    title: Text(
                      name,
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    subtitle: Text(
                      tr('المربع {position}', {'position': '$position'}) + statusStr,
                      style: TextStyle(
                        fontSize: 13,
                        color: isFrozen ? AppColors.error : AppColors.textSecondary,
                      ),
                    ),
                    trailing: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        if (hasShield)
                          const Padding(
                            padding: EdgeInsets.only(right: 4.0),
                            child: Icon(Icons.shield, color: AppColors.primary, size: 20),
                          ),
                        if (isFrozen)
                          const Icon(Icons.ac_unit, color: AppColors.info, size: 20),
                      ],
                    ),
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  String _buildRadarSpeech(Map radar) {
    final pos = radar['position'] ?? 0;
    final ladder = radar['nearest_ladder'] as List?;
    final snake = radar['nearest_snake'] as List?;

    final parts = [tr('المربع {position}', {'position': '$pos'})];
    if (ladder != null && ladder.length >= 2) {
      parts.add(tr('سلم في {base} إلى {top}', {'base': '${ladder[0]}', 'top': '${ladder[1]}'}));
    }
    if (snake != null && snake.length >= 2) {
      parts.add(tr('ثعبان في {head} إلى {tail}', {'head': '${snake[0]}', 'tail': '${snake[1]}'}));
    }
    return parts.join('، ');
  }

  @override
  void onSpaceAction(BuildContext context, Map<String, dynamic> state, String roomId) {
    // Replicates on_snakes_roll_shortcut from client/client_app.py:2331
    if (state['active'] != true) return;
    if (_isStepping || state['is_my_turn'] != true) {
      AccessibilityManager.instance.announce(tr('ليس دورك الآن.'), interrupt: true);
      SoundService.instance.playSound('INVALID_ACTION');
      return;
    }
    ApiService.instance.sendGameAction(roomId, {'action': 'roll'});
  }

  @override
  void announceTop(BuildContext context, Map<String, dynamic> state) {
    // Replicates on_snakes_radar_shortcut from client/client_app.py:2353
    if (state['active'] != true) return;
    final radar = state['radar'] as Map? ?? {};
    final speech = _buildRadarSpeech(radar);
    AccessibilityManager.instance.announce(speech, interrupt: true);
  }

  @override
  void announceTurn(BuildContext context, Map<String, dynamic> state) {
    // Replicates on_announce_turn for SNAKES_LADDERS from client/client_app.py:2407
    if (state['active'] != true) {
      AccessibilityManager.instance.announce(tr('المباراة لم تبدأ بعد.'), interrupt: true);
      return;
    }
    final curr = (state['current_player_name'] ?? '').toString();
    AccessibilityManager.instance.announce(
      curr.isNotEmpty ? tr('دور {name}', {'name': curr}) : tr('غير محدد'),
      interrupt: true,
    );
  }
}
