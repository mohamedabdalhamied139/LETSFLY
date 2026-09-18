import 'package:flutter/material.dart';
import '../../core/localization.dart';
import '../../core/sound_service.dart';
import '../../services/ws_service.dart';

class SnakesGameView extends StatefulWidget {
  final Map<String, dynamic>? initialState;

  const SnakesGameView({super.key, this.initialState});

  @override
  State<SnakesGameView> createState() => SnakesGameViewState();
}

class SnakesGameViewState extends State<SnakesGameView> {
  int _position = 1;
  int _lastRoll = 0;
  bool _canRoll = false;

  @override
  void initState() {
    super.initState();
    if (widget.initialState != null) {
      updateState(widget.initialState!);
    }
  }

  void updateState(Map<String, dynamic> state) {
    setState(() {
      _position = state['my_position'] is int ? state['my_position'] : 1;
      _lastRoll = state['last_roll'] is int ? state['last_roll'] : 0;
      _canRoll = state['is_my_turn'] == true;
    });
  }

  void _rollDice() {
    SoundService.instance.playSound('snakes_and_ladders/STEP_MOVE');
    WebSocketService.instance.sendJson({
      'type': 'game_action',
      'action': 'roll',
    });
  }

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.primaryContainer,
                shape: BoxShape.circle,
              ),
              child: Text(
                '$_position',
                style: const TextStyle(fontSize: 48, fontWeight: FontWeight.bold),
              ),
            ),
            const SizedBox(height: 16),
            Text(
              '${tr('المربع الحالي')}: $_position / 100',
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            if (_lastRoll > 0) ...[
              const SizedBox(height: 12),
              Text(
                '${tr('الرمية السابقة')}: $_lastRoll',
                style: const TextStyle(fontSize: 16, color: Colors.amber),
              ),
            ],
            const SizedBox(height: 32),
            ElevatedButton.icon(
              onPressed: _canRoll ? _rollDice : null,
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
                  backgroundColor: Colors.green,
                  foregroundColor: Colors.white,
                ),
                icon: const Icon(Icons.casino, size: 28),
                label: Text(
                  _canRoll ? tr('ارمي النرد الآن!') : tr('انتظر دورك...'),
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
