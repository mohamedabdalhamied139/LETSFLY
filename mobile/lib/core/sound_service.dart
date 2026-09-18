import 'package:audioplayers/audioplayers.dart';

class SoundService {
  static final SoundService instance = SoundService._();
  SoundService._();

  final AudioPlayer _player = AudioPlayer();
  final AudioPlayer _pannedPlayer = AudioPlayer();

  Future<void> playSound(String soundName) async {
    try {
      final fileName = soundName.endsWith('.wav') || soundName.endsWith('.mp3')
          ? soundName
          : '$soundName.wav';
      await _player.stop();
      await _player.play(AssetSource('sounds/$fileName'));
    } catch (_) {}
  }

  /// Play sound with 3D/stereo balance (-1.0 left, 0.0 center, 1.0 right) for Tennis
  Future<void> playPanned(String soundName, double pan) async {
    try {
      final fileName = soundName.endsWith('.wav') || soundName.endsWith('.mp3')
          ? soundName
          : '$soundName.wav';
      await _pannedPlayer.setBalance(pan.clamp(-1.0, 1.0));
      await _pannedPlayer.stop();
      await _pannedPlayer.play(AssetSource('sounds/$fileName'));
    } catch (_) {}
  }
}
