import 'package:flutter/material.dart';
import '../../core/localization.dart';
import '../../core/sound_service.dart';
import '../../services/ws_service.dart';

class ThiefGameView extends StatefulWidget {
  final Map<String, dynamic>? initialState;

  const ThiefGameView({super.key, this.initialState});

  @override
  State<ThiefGameView> createState() => ThiefGameViewState();
}

class ThiefGameViewState extends State<ThiefGameView> {
  String _phase = 'WAITING';
  String _targetWord = '';
  final TextEditingController _inputController = TextEditingController();
  bool _canAnswer = false;

  @override
  void initState() {
    super.initState();
    if (widget.initialState != null) {
      updateState(widget.initialState!);
    }
  }

  void updateState(Map<String, dynamic> state) {
    setState(() {
      _phase = state['phase'] ?? 'WAITING';
      _targetWord = state['target_word'] ?? '';
      _canAnswer = state['can_answer'] == true;
    });

    if (_phase == 'NARRATION') {
      SoundService.instance.playSound('thief_hunt/thief_game_start');
    } else if (_phase == 'ANSWER') {
      SoundService.instance.playSound('thief_hunt/thief_answer_start');
    }
  }

  void _submitAnswer() {
    final ans = _inputController.text.trim();
    if (ans.isEmpty) return;
    WebSocketService.instance.sendJson({
      'type': 'game_action',
      'action': 'answer',
      'text': ans,
    });
    _inputController.clear();
  }

  @override
  void dispose() {
    _inputController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            _phase == 'ANSWER' ? Icons.alarm : Icons.security,
            size: 64,
            color: _phase == 'ANSWER' ? Colors.red : Theme.of(context).colorScheme.primary,
          ),
          Text(
            _phase == 'ANSWER'
                ? tr('اكتب الكلمة بأقصى سرعة!')
                : tr('استمع لتفاصيل الجولة...'),
            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 24),
          if (_canAnswer || _phase == 'ANSWER') ...[
            TextField(
              controller: _inputController,
              autofocus: true,
              decoration: InputDecoration(
                labelText: tr('الكلمة المستهدفة'),
                border: const OutlineInputBorder(),
                suffixIcon: IconButton(
                  icon: const Icon(Icons.send),
                  onPressed: _submitAnswer,
                ),
              ),
              onSubmitted: (_) => _submitAnswer(),
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _submitAnswer,
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.red.shade700,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 14),
              ),
              child: Text(tr('صيد اللص!'), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            ),
          ],
        ],
      ),
    );
  }
}
