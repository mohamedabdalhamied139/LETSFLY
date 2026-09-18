import 'package:flutter/material.dart';
import '../../core/app_theme.dart';
import '../../core/localization.dart';
import '../../core/sound_service.dart';
import '../../services/api_service.dart';
import '../../services/ws_service.dart';

class TennisGameView extends StatefulWidget {
  final String roomId;
  final Map<String, dynamic>? initialState;

  const TennisGameView({
    super.key,
    required this.roomId,
    this.initialState,
  });

  @override
  State<TennisGameView> createState() => TennisGameViewState();
}

class TennisGameViewState extends State<TennisGameView> {
  int _currentLane = 0; // -1: Left, 0: Center, 1: Right
  String _scoreText = '0 - 0';
  String _stateStatus = 'WAITING';
  int _serverIdx = 0;
  String _lastAction = '';

  @override
  void initState() {
    super.initState();
    if (widget.initialState != null) {
      updateState(widget.initialState!);
    }
  }

  @override
  void didUpdateWidget(TennisGameView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.initialState != null) {
      updateState(widget.initialState!);
    }
  }

  void updateState(Map<String, dynamic> state) {
    setState(() {
      _stateStatus = (state['state'] ?? 'WAITING').toString();
      _lastAction = state['last_action']?.toString() ?? '';

      if (state['score'] is Map) {
        final score = state['score'] as Map;
        final p0Pts = _formatPoints(score['points']?['0'] ?? score['points']?[0] ?? 0);
        final p1Pts = _formatPoints(score['points']?['1'] ?? score['points']?[1] ?? 0);
        final p0Games = score['games']?['0'] ?? score['games']?[0] ?? 0;
        final p1Games = score['games']?['1'] ?? score['games']?[1] ?? 0;
        final p0Sets = score['sets']?['0'] ?? score['sets']?[0] ?? 0;
        final p1Sets = score['sets']?['1'] ?? score['sets']?[1] ?? 0;
        _serverIdx = int.tryParse(score['server_idx']?.toString() ?? '0') ?? 0;

        _scoreText = 'المجموعات: $p0Sets - $p1Sets | أشواط: $p0Games - $p1Games | نقاط: $p0Pts - $p1Pts';
      } else if (state['score_text'] != null) {
        _scoreText = state['score_text'].toString();
      }

      if (state['player_positions'] is Map) {
        final myUid = state['my_user_id']?.toString();
        if (myUid != null && state['player_positions'][myUid] != null) {
          _currentLane = int.tryParse(state['player_positions'][myUid].toString()) ?? _currentLane;
        }
      }
    });

    if (state['sound_cue'] != null && state['sound_cue'].toString().isNotEmpty) {
      SoundService.instance.playSound(state['sound_cue'].toString());
    }
  }

  String _formatPoints(dynamic pt) {
    final v = int.tryParse(pt.toString()) ?? 0;
    if (v == 0) return '0';
    if (v == 1) return '15';
    if (v == 2) return '30';
    if (v == 3) return '40';
    if (v >= 4) return 'AD';
    return v.toString();
  }

  void _sendAction(Map<String, dynamic> actionPayload) {
    final reqId = 'req_${DateTime.now().millisecondsSinceEpoch}';
    WebSocketService.instance.sendJson({
      'type': 'game_action',
      'request_id': reqId,
      'payload': actionPayload,
    });
    ApiService.instance.sendGameAction(widget.roomId, actionPayload);
  }

  void moveLeft() {
    setState(() => _currentLane = -1);
    SoundService.instance.playPanned('tennis/jm_left', -0.9);
    _sendAction({
      'action': 'position',
      'data': {'lane': -1},
    });
  }

  void moveCenter() {
    setState(() => _currentLane = 0);
    SoundService.instance.playPanned('tennis/jm_center', 0.0);
    _sendAction({
      'action': 'position',
      'data': {'lane': 0},
    });
  }

  void moveRight() {
    setState(() => _currentLane = 1);
    SoundService.instance.playPanned('tennis/jm_right', 0.9);
    _sendAction({
      'action': 'position',
      'data': {'lane': 1},
    });
  }

  void hitOrServe() {
    double pan = _currentLane == -1 ? -0.85 : (_currentLane == 1 ? 0.85 : 0.0);
    SoundService.instance.playPanned('tennis/hit_1_center', pan);
    _sendAction({
      'action': _stateStatus == 'SERVING' ? 'serve' : 'hit',
      'data': {'lane': _currentLane},
    });
  }

  @override
  Widget build(BuildContext context) {
    final laneNames = {
      -1: tr('الممر الأيسر'),
      0: tr('الممر الأوسط'),
      1: tr('الممر الأيمن'),
    };
    final currentLaneName = laneNames[_currentLane] ?? tr('الوسط');

    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Tennis Court Score Banner
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppColors.divider, width: 2),
              ),
              child: Column(
                children: [
                  Text(
                    _scoreText,
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '${tr('الإرسال')}: ${_serverIdx == 0 ? tr('اللاعب 1') : tr('اللاعب 2')}',
                    style: const TextStyle(color: Colors.amberAccent, fontWeight: FontWeight.bold, fontSize: 14),
                  ),
                  if (_lastAction.isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Text(
                      _lastAction,
                      style: const TextStyle(color: Colors.white70, fontSize: 13),
                      textAlign: TextAlign.center,
                    ),
                  ],
                ],
              ),
            ),

            const SizedBox(height: 20),

            // Current Position on Court
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
              decoration: BoxDecoration(
                color: AppColors.card,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.lightBlueAccent, width: 2),
              ),
              child: Text(
                '${tr('موقعك')}: $currentLaneName',
                style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.white),
              ),
            ),

            const SizedBox(height: 20),

            // 3-Lane Visual Court Representation
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                _buildLaneIndicator(-1, tr('يسار')),
                const SizedBox(width: 8),
                _buildLaneIndicator(0, tr('وسط')),
                const SizedBox(width: 8),
                _buildLaneIndicator(1, tr('يمين')),
              ],
            ),

            const SizedBox(height: 24),

            // On-screen touch buttons
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                ElevatedButton.icon(
                  onPressed: moveLeft,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _currentLane == -1 ? Colors.lightBlue.shade800 : AppColors.card,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  ),
                  icon: const Icon(Icons.arrow_back),
                  label: Text(tr('يسار')),
                ),
                ElevatedButton.icon(
                  onPressed: hitOrServe,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.green.shade700,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
                  ),
                  icon: const Icon(Icons.sports_tennis),
                  label: Text(
                    _stateStatus == 'SERVING' ? tr('إرسال!') : tr('ضرب الكرة!'),
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                  ),
                ),
                ElevatedButton.icon(
                  onPressed: moveRight,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _currentLane == 1 ? Colors.lightBlue.shade800 : AppColors.card,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  ),
                  icon: const Icon(Icons.arrow_forward),
                  label: Text(tr('يمين')),
                ),
              ],
            ),

            const SizedBox(height: 24),

            // Gestures Guide
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.card,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: AppColors.divider),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    tr('إيماءات التنس باللمس:'),
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: Colors.amberAccent),
                  ),
                  const SizedBox(height: 4),
                  Text(tr('• سحب لليسار: الانتقال للممر الأيسر'), style: const TextStyle(color: Colors.white70, fontSize: 13)),
                  Text(tr('• سحب لليمين: الانتقال للممر الأيمن'), style: const TextStyle(color: Colors.white70, fontSize: 13)),
                  Text(tr('• سحب للأعلى: ضرب الكرة / الإرسال'), style: const TextStyle(color: Colors.white70, fontSize: 13)),
                  Text(tr('• سحب للأسفل: فتح سجل النشاط والأحداث'), style: const TextStyle(color: Colors.white70, fontSize: 13)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLaneIndicator(int lane, String label) {
    final isCurrent = _currentLane == lane;

    return InkWell(
      onTap: () {
        if (lane == -1) moveLeft();
        if (lane == 0) moveCenter();
        if (lane == 1) moveRight();
      },
      borderRadius: BorderRadius.circular(8),
      child: Container(
        width: 70,
        height: 60,
        decoration: BoxDecoration(
          color: isCurrent ? Colors.lightBlue.shade900 : AppColors.surface,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: isCurrent ? Colors.lightBlueAccent : AppColors.divider,
            width: isCurrent ? 2.5 : 1,
          ),
        ),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                isCurrent ? Icons.person_pin_circle : Icons.sports_tennis,
                color: isCurrent ? Colors.lightBlueAccent : Colors.white38,
                size: 22,
              ),
              const SizedBox(height: 2),
              Text(
                label,
                style: TextStyle(
                  color: isCurrent ? Colors.white : Colors.white54,
                  fontWeight: isCurrent ? FontWeight.bold : FontWeight.normal,
                  fontSize: 12,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
