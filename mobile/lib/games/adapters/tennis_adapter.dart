import 'package:flutter/material.dart';
import '../../core/localization.dart';
import '../../core/sound_service.dart';
import '../../services/ws_service.dart';

class TennisGameView extends StatefulWidget {
  final Map<String, dynamic>? initialState;

  const TennisGameView({super.key, this.initialState});

  @override
  State<TennisGameView> createState() => TennisGameViewState();
}

class TennisGameViewState extends State<TennisGameView> {
  int _currentLane = 0; // -1: Left, 0: Center, 1: Right
  String _scoreText = '0 - 0';
  bool _isPlaying = false;
  String _announcement = '';

  @override
  void initState() {
    super.initState();
    if (widget.initialState != null) {
      updateState(widget.initialState!);
    }
  }

  void updateState(Map<String, dynamic> state) {
    setState(() {
      _scoreText = state['score_text'] ?? _scoreText;
      _isPlaying = state['state'] == 'PLAYING';
      _announcement = state['umpire_call'] ?? '';
    });
    if (_announcement.isNotEmpty) {
      SoundService.instance.playSound('tennis/arabic_umpire/$_announcement');
    }
  }

  void moveLeft() {
    setState(() => _currentLane = -1);
    SoundService.instance.playPanned('tennis/jm_left', -0.9);
    WebSocketService.instance.sendJson({
      'type': 'tennis_action',
      'action': 'move',
      'lane': -1,
    });
  }

  void moveRight() {
    setState(() => _currentLane = 1);
    SoundService.instance.playPanned('tennis/jm_right', 0.9);
    WebSocketService.instance.sendJson({
      'type': 'tennis_action',
      'action': 'move',
      'lane': 1,
    });
  }

  void hitOrServe() {
    double pan = _currentLane == -1 ? -0.8 : (_currentLane == 1 ? 0.8 : 0.0);
    SoundService.instance.playPanned('tennis/hit_1_center', pan);
    WebSocketService.instance.sendJson({
      'type': 'tennis_action',
      'action': 'hit',
      'lane': _currentLane,
    });
  }

  @override
  Widget build(BuildContext context) {
    final laneNames = {-1: tr('الممر الأيسر'), 0: tr('الممر الأوسط'), 1: tr('الممر الأيمن')};
    final currentLaneName = laneNames[_currentLane] ?? tr('الوسط');

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Semantics(
              liveRegion: true,
              label: 'النتيجة: $_scoreText',
              child: Text(
                '$_scoreText',
                style: const TextStyle(fontSize: 36, fontWeight: FontWeight.bold),
              ),
            ),
            const SizedBox(height: 24),
            Semantics(
              label: 'موقعك الحالي: $currentLaneName',
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.primaryContainer,
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Text(
                  '${tr('الموقع')}: $currentLaneName',
                  style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                ),
              ),
            ),
            const SizedBox(height: 32),
            Text(
              tr('إيماءات التنس باللمس:'),
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
            ),
            const SizedBox(height: 8),
            Text(tr('• سحب لليسار: الانتقال لليسار')),
            Text(tr('• سحب لليمين: الانتقال لليمين')),
            Text(tr('• سحب للأعلى: ضرب الكرة / الإرسال')),
            Text(tr('• سحب للأسفل: فتح سجل النشاط والأحداث')),
            const SizedBox(height: 32),
            // On-screen touch buttons as accessibility alternative to gestures
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                ElevatedButton.icon(
                  onPressed: moveLeft,
                  icon: const Icon(Icons.arrow_back),
                  label: Text(tr('يسار')),
                ),
                ElevatedButton.icon(
                  onPressed: hitOrServe,
                  style: ElevatedButton.styleFrom(backgroundColor: Colors.green, foregroundColor: Colors.white),
                  icon: const Icon(Icons.sports_tennis),
                  label: Text(tr('ضرب / إرسال')),
                ),
                ElevatedButton.icon(
                  onPressed: moveRight,
                  icon: const Icon(Icons.arrow_forward),
                  label: Text(tr('يمين')),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
