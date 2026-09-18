import 'package:flutter/material.dart';
import '../../core/app_theme.dart';
import '../../core/localization.dart';
import '../../core/sound_service.dart';
import '../../services/api_service.dart';
import '../../services/ws_service.dart';

class ThiefGameView extends StatefulWidget {
  final String roomId;
  final Map<String, dynamic>? initialState;

  const ThiefGameView({
    super.key,
    required this.roomId,
    this.initialState,
  });

  @override
  State<ThiefGameView> createState() => ThiefGameViewState();
}

class ThiefGameViewState extends State<ThiefGameView> {
  String _phase = 'waiting';
  bool _isThief = false;
  int? _startFloor;
  int? _finalFloor;
  List<dynamic> _directions = [];
  int _answerSeconds = 0;
  List<dynamic> _answers = [];
  List<dynamic> _roundWinners = [];
  String _roundWinnerName = '';
  String _lastAction = '';
  int? _myAnswer;

  @override
  void initState() {
    super.initState();
    if (widget.initialState != null) {
      updateState(widget.initialState!);
    }
  }

  @override
  void didUpdateWidget(ThiefGameView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.initialState != null) {
      updateState(widget.initialState!);
    }
  }

  void updateState(Map<String, dynamic> state) {
    setState(() {
      _phase = (state['phase'] ?? 'waiting').toString();
      _isThief = state['is_thief'] == true;
      _startFloor = state['start_floor'] is int ? state['start_floor'] : null;
      _finalFloor = state['final_floor'] is int ? state['final_floor'] : null;
      _directions = state['directions'] is List ? state['directions'] : [];
      _answerSeconds = state['answer_seconds_remaining'] is int
          ? state['answer_seconds_remaining']
          : 0;
      _answers = state['answers'] is List ? state['answers'] : [];
      _roundWinners = state['round_winners'] is List ? state['round_winners'] : [];
      _roundWinnerName = state['round_winner_name']?.toString() ?? '';
      _lastAction = state['last_action']?.toString() ?? '';

      final myUid = state['my_user_id'];
      if (_answers.isNotEmpty && myUid != null) {
        for (final ans in _answers) {
          if (ans is Map && ans['user_id']?.toString() == myUid.toString()) {
            _myAnswer = ans['floor'] is int ? ans['floor'] : null;
            break;
          }
        }
      }
    });

    if (state['sound_cue'] != null && state['sound_cue'].toString().isNotEmpty) {
      SoundService.instance.playSound(state['sound_cue'].toString());
    } else if (_phase == 'escape') {
      SoundService.instance.playSound('THIEF_ESCAPE');
    } else if (_phase == 'answering') {
      SoundService.instance.playSound('THIEF_ANSWER_START');
    } else if (_phase == 'round_result') {
      SoundService.instance.playSound('THIEF_ROUND_END');
    }
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

  void _chooseStartFloor(int floor) {
    SoundService.instance.playSound('THIEF_GAME_START');
    _sendAction({
      'action': 'choose_floor',
      'card_id': floor.toString(),
    });
  }

  void _submitAnswer(int floor) {
    setState(() => _myAnswer = floor);
    SoundService.instance.playSound('THIEF_ANSWER_START');
    _sendAction({
      'action': 'answer',
      'card_id': floor.toString(),
    });
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        children: [
          // Phase Header Card
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: _phase == 'answering' ? Colors.redAccent : AppColors.divider,
                width: 2,
              ),
            ),
            child: Column(
              children: [
                Icon(
                  _phase == 'answering'
                      ? Icons.timer
                      : (_phase == 'escape' ? Icons.directions_run : Icons.security),
                  size: 48,
                  color: _phase == 'answering'
                      ? Colors.redAccent
                      : (_phase == 'escape' ? Colors.amberAccent : Colors.lightBlueAccent),
                ),
                const SizedBox(height: 8),
                Text(
                  _phaseTitle(),
                  style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.white),
                  textAlign: TextAlign.center,
                ),
                if (_lastAction.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text(
                    _lastAction,
                    style: const TextStyle(color: Colors.white70, fontSize: 13),
                    textAlign: TextAlign.center,
                  ),
                ],
                if (_phase == 'answering' && _answerSeconds > 0) ...[
                  const SizedBox(height: 8),
                  Text(
                    '${tr('الوقت المتبقي')}: $_answerSeconds ${tr('ثواني')}',
                    style: const TextStyle(color: Colors.redAccent, fontWeight: FontWeight.bold, fontSize: 16),
                  ),
                ],
              ],
            ),
          ),

          const SizedBox(height: 16),

          // Phase 1: Thief chooses starting floor (1..10)
          if (_phase == 'choose_floor' && _isThief) ...[
            Text(
              tr('اختر الطابق الذي ستبدأ منه الهروب سرًا:'),
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.amberAccent),
            ),
            const SizedBox(height: 12),
            _buildFloorsGrid(onTap: _chooseStartFloor),
          ],

          // Phase 2: Escape Narration
          if (_phase == 'escape') ...[
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.card,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                children: [
                  if (_startFloor != null)
                    Text(
                      '${tr('الطابق الأولي')}: $_startFloor',
                      style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white),
                    ),
                  const SizedBox(height: 8),
                  Text(
                    '${tr('الاتجاهات')}: ${_directions.isEmpty ? tr('جاري التحرك...') : _directions.join(' ← ')}',
                    style: const TextStyle(fontSize: 16, color: Colors.lightGreenAccent),
                    textAlign: TextAlign.center,
                  ),
                ],
              ),
            ),
          ],

          // Phase 3: Answering window (Investigator guesses floor 1..10)
          if (_phase == 'answering' && !_isThief) ...[
            Text(
              _myAnswer == null
                  ? tr('اختر الطابق الذي وصل إليه اللص:')
                  : '${tr('إجابتك المسجلة')}: ${tr('الطابق')} $_myAnswer',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: _myAnswer == null ? Colors.white : Colors.greenAccent,
              ),
            ),
            const SizedBox(height: 12),
            _buildFloorsGrid(
              selectedFloor: _myAnswer,
              onTap: _myAnswer == null ? _submitAnswer : null,
            ),
          ],

          // Phase 4: Round Results
          if (_phase == 'round_result' || _phase == 'match_finished') ...[
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.card,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.greenAccent),
              ),
              child: Column(
                children: [
                  if (_finalFloor != null)
                    Text(
                      '${tr('الطابق الفعلي للص')}: $_finalFloor',
                      style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.amberAccent),
                    ),
                  const SizedBox(height: 8),
                  Text(
                    _roundWinnerName.isNotEmpty
                        ? '${tr('فائز الجولة')}: $_roundWinnerName'
                        : tr('هرب اللص دون أن يُمسك به أحد!'),
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  String _phaseTitle() {
    switch (_phase) {
      case 'choose_floor':
        return _isThief ? tr('أنت اللص! اختر طابق البداية') : tr('اللص يختار طابق البداية سرًا...');
      case 'escape':
        return tr('اللص يتحرك بين الطوابق...');
      case 'answering':
        return _isThief ? tr('المحققون يبحثون عنك!') : tr('حدد طابق اللص بأقصى سرعة!');
      case 'round_result':
        return tr('نتيجة الجولة');
      case 'match_finished':
        return tr('نهاية المباراة');
      default:
        return tr('في انتظار بدء الجولة...');
    }
  }

  Widget _buildFloorsGrid({int? selectedFloor, ValueChanged<int>? onTap}) {
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 5,
        childAspectRatio: 1.1,
        crossAxisSpacing: 10,
        mainAxisSpacing: 10,
      ),
      itemCount: 10,
      itemBuilder: (context, index) {
        final floor = index + 1;
        final isSelected = selectedFloor == floor;

        return ElevatedButton(
          style: ElevatedButton.styleFrom(
            backgroundColor: isSelected ? Colors.green.shade700 : AppColors.card,
            foregroundColor: Colors.white,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(10),
              side: BorderSide(
                color: isSelected ? Colors.greenAccent : AppColors.divider,
                width: isSelected ? 2 : 1,
              ),
            ),
          ),
          onPressed: onTap != null ? () => onTap(floor) : null,
          child: Text(
            '$floor',
            style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
          ),
        );
      },
    );
  }
}
