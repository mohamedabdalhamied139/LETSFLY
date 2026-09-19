import 'dart:async';
import '../core/accessibility_manager.dart';
import '../core/haptic_service.dart';
import '../core/localization.dart';
import '../core/sound_service.dart';
import '../services/activity_service.dart';

/// Game State Engine replicating Windows desktop ClientStateEngine (client/table_framework/state_engine.py).
/// Handles:
/// - Monotonic event_id tracking and de-duplication.
/// - In-game activity logging under category 'GAMEPLAY'.
/// - Exact sound cue playback & sequencing.
/// - Victory / defeat detection and speech.
/// - Strict turn announcement gating and tactile haptic vibration (on player turn only).
class GameStateEngine {
  static final GameStateEngine instance = GameStateEngine._();
  GameStateEngine._();

  final Map<String, int> _lastEventIds = {};
  final Map<String, String?> _lastTurnIds = {};
  final Map<String, String?> _lastAnnouncedTurnIds = {};
  final Set<String> _seenGameActivityEvents = {};
  bool _matchResultSoundPlayed = false;

  void resetGameRuntimeState(String? gameType) {
    if (gameType != null) {
      final gt = gameType.toUpperCase();
      _lastEventIds[gt] = 0;
      _lastTurnIds[gt] = null;
      _lastAnnouncedTurnIds[gt] = null;
    } else {
      _lastEventIds.clear();
      _lastTurnIds.clear();
      _lastAnnouncedTurnIds.clear();
    }
    _seenGameActivityEvents.clear();
    _matchResultSoundPlayed = false;
  }

  void processCommonState({
    required String gameType,
    required Map<String, dynamic> state,
    required String roomId,
    required int myUserId,
    required void Function(bool isPlaying, bool isRoundFinished) onStateProcessed,
  }) {
    if (state.isEmpty) return;

    final gt = gameType.toUpperCase();
    bool isActive = state['active'] == true;
    final bool isRoundFinished = state['round_finished'] == true;

    if (gt == 'TENNIS') {
      final s = (state['state'] ?? '').toString().toUpperCase();
      isActive = s.isNotEmpty && s != 'WAITING' && s != 'FINISHED';
    }

    final String et = (state['event_type'] ?? '').toString().toUpperCase();
    final String phase = (state['phase'] ?? '').toString().toLowerCase();

    final bool isMatchOver = state['winner_id'] != null ||
        state['winning_team'] != null ||
        state['match_winner_id'] != null ||
        state['match_finished'] == true ||
        et == 'MATCH_WON' ||
        et == 'MATCH_FINISHED' ||
        phase == 'match_finished';

    final bool keepScopaHand = (gt == 'SCOPA' &&
        !isActive &&
        !isMatchOver &&
        state['final_play_action'] != null);

    final bool isPlayingMode = ((isActive && !isRoundFinished) || keepScopaHand) && !isMatchOver;

    onStateProcessed(isPlayingMode, isRoundFinished);

    if (isMatchOver) {
      _lastTurnIds[gt] = null;
      _lastAnnouncedTurnIds[gt] = null;
    }

    final int eventId = int.tryParse(state['event_id']?.toString() ?? '0') ?? 0;
    int lastId = _lastEventIds[gt] ?? 0;

    // Reset lastId if server started a new match and eventId wrapped around to 1
    if (eventId == 1 && lastId > 1) {
      lastId = 0;
      _matchResultSoundPlayed = false;
    }

    final String actionText = (state['last_action'] ?? '').toString().trim();
    bool spokeEvent = false;

    if (eventId > lastId) {
      _lastEventIds[gt] = eventId;

      // 1. Activity Log
      final String logicalKey = 'game:$roomId:$et:$eventId';
      if (actionText.isNotEmpty && !_seenGameActivityEvents.contains(logicalKey)) {
        _seenGameActivityEvents.add(logicalKey);
        if (_seenGameActivityEvents.length > 512) {
          final keep = _seenGameActivityEvents.toList().sublist(_seenGameActivityEvents.length - 256);
          _seenGameActivityEvents.clear();
          _seenGameActivityEvents.addAll(keep);
        }

        ActivityLogService.instance.addEvent({
          'category': 'GAMEPLAY',
          'text': actionText,
          'event_type': et,
          'game_event_id': eventId,
          'room_id': roomId,
        });
      }

      if (['GAME_STARTED', 'ROUND_START', 'ROUND_STARTED'].contains(et)) {
        _matchResultSoundPlayed = false;
      }

      // 2. Sound Cues
      final String singleCue = (state['sound_cue'] ?? '').toString().trim();
      final dynamic rawCues = state['sound_cues'];
      List<String> eventCues = [];
      if (rawCues is List) {
        eventCues = rawCues.map((e) => e.toString().trim()).where((c) => c.isNotEmpty).toList();
      } else if (singleCue.isNotEmpty) {
        eventCues = [singleCue];
      }

      // Handle Scopa round finished
      if (gt == 'SCOPA' && ['ROUND_FINISHED', 'ROUND_END', 'ROUND_WON'].contains(et)) {
        eventCues = [];
      } else if (gt == 'SNAKES_LADDERS') {
        if (!['MATCH_WON', 'MATCH_FINISHED'].contains(et)) {
          eventCues = eventCues.where((c) => !['SNAKE_BITE', 'LADDER_CLIMB', 'FREEZE_TRAP', 'MYSTERY_BOX', 'PLAYER_BUMP'].contains(c)).toList();
        }
      }

      // Play Sound Cues (sequenced if multiple cues e.g. Domino or 99)
      if (['NINETY_NINE', 'DOMINO', 'AMERICAN_DOMINO'].contains(gt) && eventCues.length > 1) {
        for (int i = 0; i < eventCues.length; i++) {
          final cue = eventCues[i];
          if (i == 0) {
            SoundService.instance.playSound(cue);
          } else {
            Timer(Duration(milliseconds: i * 180), () {
              SoundService.instance.playSound(cue);
            });
          }
        }
      } else {
        for (final cue in eventCues) {
          SoundService.instance.playSound(cue);
        }
      }

      // 3. Event Speech Announcement
      if (['MATCH_WON', 'MATCH_FINISHED'].contains(et)) {
        final winnerId = state['winner_id'] ?? state['match_winner_id'];
        final winningTeam = state['winning_team'];
        final teams = state['teams'];
        bool isMe = false;

        if (winningTeam != null && teams is Map && myUserId != 0 && teams[myUserId.toString()] != null) {
          isMe = (teams[myUserId.toString()] == winningTeam);
        } else if (winnerId != null && myUserId != 0) {
          isMe = (winnerId.toString() == myUserId.toString());
        } else if (state['winning_ids'] is List && myUserId != 0) {
          isMe = (state['winning_ids'] as List).any((w) => w.toString() == myUserId.toString());
        }

        if (!_matchResultSoundPlayed) {
          SoundService.instance.playSound(isMe ? 'MATCH_WIN' : 'MATCH_LOSS');
          _matchResultSoundPlayed = true;
        }

        final localizedAction = tr(actionText);
        final msg = isMe
            ? '${tr("مبروك! لقد فزت.")} $localizedAction'
            : '${tr("حظ أوفر!")} $localizedAction';
        AccessibilityManager.instance.announce(msg, interrupt: (gt != 'SCOPA'));
        spokeEvent = true;
      } else if (['ROUND_FINISHED', 'ROUND_END', 'ROUND_WON'].contains(et)) {
        if (gt != 'SCOPA' && actionText.isNotEmpty) {
          AccessibilityManager.instance.announce(tr(actionText), interrupt: true);
          spokeEvent = true;
        }
      } else if (['ROUND_START', 'ROUND_STARTED', 'GAME_STARTED'].contains(et)) {
        if (actionText.isNotEmpty) {
          AccessibilityManager.instance.announce(tr(actionText), interrupt: true);
          spokeEvent = true;
        }
      } else {
        if (['UNO', 'NINETY_NINE'].contains(gt)) {
          if ([
            'CARD_DRAWN', 'CARD_DRAWN_AND_PASSED', 'DRAW_PENALTY',
            'CARD_PLAYED', 'SPECIAL_CARD_PLAYED', 'BLUFF_CAUGHT',
            'BLUFF_FALSE', 'UNO_CAUGHT', 'SEVEN_EXCHANGE',
            'BUZZER_PENALTY', 'PLAYER_ELIMINATED',
            'PENDING_CHOICE', 'CHOICE_CANCELLED'
          ].contains(et)) {
            AccessibilityManager.instance.announce(tr(actionText), interrupt: true);
            spokeEvent = true;
          } else if (et == 'UNO_CALLED') {
            AccessibilityManager.instance.announce('UNO', interrupt: true);
            spokeEvent = true;
          }
        } else if (gt == 'FARKLE') {
          if (actionText.isNotEmpty) {
            AccessibilityManager.instance.announce(tr(actionText), interrupt: false);
            spokeEvent = true;
          }
        } else if (gt == 'SCOPA') {
          if (['CARD_PLAYED', 'CARD_CAPTURED', 'SCOPA_SCORED', 'SCOPA_SWEEP'].contains(et)) {
            AccessibilityManager.instance.announce(tr(actionText), interrupt: false);
            spokeEvent = true;
          }
        } else if (!['THIEF_HUNT', 'SNAKES_LADDERS'].contains(gt)) {
          if (actionText.isNotEmpty) {
            AccessibilityManager.instance.announce(tr(actionText), interrupt: false);
            spokeEvent = true;
          }
        }
      }
    }

    // 4. Canonical Turn Announcement & Haptic Feedback
    final currentName = (state['current_player_name'] ?? state['current_turn_name'] ?? tr('غير معروف')).toString();
    dynamic currId = state['current_turn_id'] ?? state['current_player_id'];

    final int snakesRoll = int.tryParse(state['last_roll']?.toString() ?? '0') ?? 0;
    final bool isSnakesStepping = gt == 'SNAKES_LADDERS' && ['DICE_ROLLED', 'BONUS_ROLL'].contains(et) && snakesRoll > 0;

    final bool isTurnAllowed = isPlayingMode &&
        state['pending_deal_batch'] != true &&
        state['pending_round_finalize'] != true &&
        !isSnakesStepping &&
        !['MATCH_WON', 'MATCH_FINISHED', 'ROUND_FINISHED', 'ROUND_END'].contains(et);

    if (isTurnAllowed && currId != null) {
      final currIdStr = currId.toString();
      final lastAnnouncedTurn = _lastAnnouncedTurnIds[gt];
      final isMyTurn = (myUserId != 0 && currIdStr == myUserId.toString());

      if (currIdStr != lastAnnouncedTurn) {
        _lastAnnouncedTurnIds[gt] = currIdStr;
        _lastTurnIds[gt] = currIdStr;

        if (isMyTurn) {
          // Strictly trigger tactile haptic vibration when it becomes my turn
          HapticService.instance.playTurnHaptic();
          SoundService.instance.playSound('TURN_START');
        }
      }
    } else if (['MATCH_WON', 'MATCH_FINISHED', 'ROUND_FINISHED', 'ROUND_END'].contains(et)) {
      _lastTurnIds[gt] = null;
      _lastAnnouncedTurnIds[gt] = null;
    }
  }
}
