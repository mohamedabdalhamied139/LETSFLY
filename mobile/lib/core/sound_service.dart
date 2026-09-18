import 'package:audioplayers/audioplayers.dart';

class SoundService {
  static final SoundService instance = SoundService._();
  SoundService._() {
    _player.setAudioContext(
      AudioContext(
        android: const AudioContextAndroid(
          isSpeakerphoneOn: false,
          stayAwake: false,
          contentType: AndroidContentType.sonification,
          usageType: AndroidUsageType.game,
          audioFocus: AndroidAudioFocus.gainTransientMayDuck,
        ),
      ),
    );
    _pannedPlayer.setAudioContext(
      AudioContext(
        android: const AudioContextAndroid(
          isSpeakerphoneOn: false,
          stayAwake: false,
          contentType: AndroidContentType.sonification,
          usageType: AndroidUsageType.game,
          audioFocus: AndroidAudioFocus.gainTransientMayDuck,
        ),
      ),
    );
  }

  final AudioPlayer _player = AudioPlayer();
  final AudioPlayer _pannedPlayer = AudioPlayer();

  // Stable cue mapping matching Windows SoundEngine.SOUND_REGISTRY
  static const Map<String, String> _cueMap = {
    'CONNECTING': 'connecting.wav',
    'CONNECTED': 'connected.wav',
    'CONNECTION_LOST': 'connection_lost.wav',
    'MIC_ON': 'mic_on.wav',
    'MIC_OFF': 'mic_off.wav',
    'VOICE_JOINED': 'voice_joined.wav',
    'PLAYER_JOINED': 'player_joined.wav',
    'PLAYER_LEFT': 'player_left.wav',
    'TABLE_JOIN': 'player_joined.wav',
    'TABLE_LEAVE': 'player_left.wav',
    'TURN_START': 'turn_start.wav',
    'ROUND_START': 'round_start.wav',
    'ROUND_END': 'round_end.wav',
    'MATCH_WIN': 'match_win.wav',
    'MATCH_LOSS': 'match_loss.wav',
    'GAME_STOPPED': 'game_stopped.wav',
    'INVALID_ACTION': 'invalid_action.wav',
    // UNO
    'CARD_DRAW': 'uno/draw.wav',
    'CARD_DRAW_TWO': 'uno/draw_two.wav',
    'CARD_WILD_COLOR': 'uno/wild_color.wav',
    'CARD_WILD_DRAW_FOUR': 'uno/wild_draw_four.wav',
    'CARD_SKIP': 'uno/skip.wav',
    'CARD_REVERSE': 'uno/reverse.wav',
    'UNO_DEAL': 'uno/deal.wav',
    'UNO_PLACE': 'uno/place.wav',
    'UNO_PLACE_SPECIAL': 'uno/place_special.wav',
    'UNO_CALLED': 'uno/uno_call.wav',
    'UNO_PENALTY': 'uno/uno_penalty.wav',
    'BLUFF_CHALLENGE': 'uno/bluff_challenge.wav',
    'WILD_COLOR_PROMPT': 'uno/wild_color_prompt.wav',
    // Farkle
    'FARKLE_ROLL': 'farkle/farkle_roll.wav',
    'FARKLE_SCORE': 'farkle/farkle_score.wav',
    'FARKLE_BANK': 'farkle/farkle_bank.wav',
    'FARKLE_BUST': 'farkle/farkle_bust.wav',
    'FARKLE_HOT_DICE': 'farkle/farkle_hot_dice.wav',
    // Thief
    'THIEF_GAME_START': 'thief_hunt/thief_game_start.wav',
    'THIEF_ESCAPE': 'thief_hunt/thief_escape.wav',
    'THIEF_ANSWER_START': 'thief_hunt/thief_answer_start.wav',
    'THIEF_ROUND_END': 'thief_hunt/thief_round_end.wav',
    'THIEF_CAUGHT': 'thief_hunt/thief_caught.wav',
    'THIEF_ROUND_WINNER': 'thief_hunt/thief_round_winner.wav',
    // Domino
    'DOMINO_PLACE': 'domino/domino_place.wav',
    'DOMINO_DRAW': 'domino/domino_draw.wav',
    'DOMINO_PASS': 'domino/domino_pass.wav',
    'DOMINO_BLOCKED': 'domino/domino_blocked.wav',
    'DOMINO_WIN': 'domino/domino_win.wav',
    'DOMINO_SHUFFLE': 'domino/domino_shuffle.wav',
    'DOMINO_SETUP': 'domino/domino_setup.wav',
    'DOMINO_ROUND_START': 'domino/domino_round_start.wav',
    'DOMINO_PLACE_ORIGINAL': 'domino/domino_place_original.wav',
    'DOMINO_DRAW_ORIGINAL': 'domino/domino_draw_original.wav',
    // Snakes & Ladders
    'DICE_ROLL': 'snakes_and_ladders/DICE_ROLL.wav',
    'LADDER_CLIMB': 'snakes_and_ladders/LADDER_CLIMB.wav',
    'SNAKE_BITE': 'snakes_and_ladders/SNAKE_BITE.wav',
    'MYSTERY_BOX': 'snakes_and_ladders/MYSTERY_BOX.wav',
    'PLAYER_BUMP': 'snakes_and_ladders/PLAYER_BUMP.wav',
    'MATCH_WIN_SNAKES': 'snakes_and_ladders/MATCH_WIN.wav',
    'FREEZE_TRAP': 'snakes_and_ladders/FREEZE_TRAP.wav',
    'BONUS_ROLL': 'snakes_and_ladders/BONUS_ROLL.wav',
    'STEP_MOVE': 'snakes_and_ladders/STEP_MOVE.wav',
    // Scopa
    'SCOPA_SWEEP': 'scopa/scopa_sweep.wav',
    'SCOPA_PLAY_CARD': 'scopa/scopa_play.wav',
    'SCOPA_DEAL': 'scopa/scopa_deal.wav',
    'SCOPA_SHUFFLE': 'scopa/scopa_shuffle.wav',
    'SCOPA_CAPTURE': 'scopa/scopa_capture.wav',
    'SCOPA_ROUND_START': 'scopa/scopa_round_start.wav',
    'SCOPA_CARD_THROW': 'scopa/scopa_card_throw.wav',
    'SCOPA_EAT_CARDS': 'scopa/scopa_eat_cards.wav',
    'SCOPA_ANNOUNCEMENT': 'scopa/scopa_announcement.wav',
    // Ninety Nine
    'NINETY_NINE_DRAW': 'ninety_nine/ninety_nine_draw.wav',
    'NINETY_NINE_EXCEED': 'ninety_nine/ninety_nine_exceed.wav',
    'NINETY_NINE_REACH': 'ninety_nine/ninety_nine_reach.wav',
    'NINETY_NINE_DEAL': 'ninety_nine/deal.wav',
    'NINETY_NINE_PLACE': 'ninety_nine/place.wav',
    'NINETY_NINE_REVERSE': 'ninety_nine/reverse.wav',
    'NINETY_NINE_SKIP': 'ninety_nine/skip.wav',
    'NINETY_NINE_PROMPT': 'ninety_nine/prompt.wav',
  };

  Future<void> playSound(String cueOrPath) async {
    try {
      String resolved = _cueMap[cueOrPath.toUpperCase()] ?? cueOrPath;
      if (!resolved.endsWith('.wav') && !resolved.endsWith('.mp3')) {
        resolved = '$resolved.wav';
      }
      // Audioplayers AssetSource resolves relative to flutter assets declared in pubspec
      await _player.stop();
      await _player.play(AssetSource('sounds/$resolved'));
    } catch (_) {}
  }

  /// Play sound with 3D/stereo balance (-1.0 left, 0.0 center, 1.0 right) for Tennis
  Future<void> playPanned(String soundName, double pan) async {
    try {
      String resolved = soundName;
      if (!resolved.endsWith('.wav') && !resolved.endsWith('.mp3')) {
        resolved = '$resolved.wav';
      }
      await _pannedPlayer.setBalance(pan.clamp(-1.0, 1.0));
      await _pannedPlayer.stop();
      await _pannedPlayer.play(AssetSource('sounds/$resolved'));
    } catch (_) {}
  }
}
