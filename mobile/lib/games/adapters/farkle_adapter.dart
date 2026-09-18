import 'package:flutter/material.dart';
import '../../core/app_theme.dart';
import '../../core/localization.dart';
import '../../core/sound_service.dart';
import '../../services/api_service.dart';
import '../../services/ws_service.dart';

class FarkleGameView extends StatefulWidget {
  final String roomId;
  final Map<String, dynamic>? initialState;

  const FarkleGameView({
    super.key,
    required this.roomId,
    this.initialState,
  });

  @override
  State<FarkleGameView> createState() => FarkleGameViewState();
}

class FarkleGameViewState extends State<FarkleGameView> {
  List<int> _currentDice = [];
  final Set<int> _selectedIndices = {};
  int _turnScore = 0;
  bool _canRoll = false;
  bool _canBank = false;
  bool _mustScore = false;
  bool _isMyTurn = false;
  String _lastAction = '';
  List<dynamic> _availableCombinations = [];

  @override
  void initState() {
    super.initState();
    if (widget.initialState != null) {
      updateState(widget.initialState!);
    }
  }

  @override
  void didUpdateWidget(FarkleGameView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.initialState != null) {
      updateState(widget.initialState!);
    }
  }

  void updateState(Map<String, dynamic> state) {
    setState(() {
      _currentDice = (state['dice'] as List?)
              ?.map((e) => int.tryParse(e.toString()) ?? 1)
              .toList() ??
          [];
      _turnScore = state['turn_score'] is int
          ? state['turn_score']
          : (state['round_score'] is int ? state['round_score'] : 0);
      _canRoll = state['can_roll'] == true;
      _mustScore = state['must_score_before_roll'] == true;
      _isMyTurn = state['is_my_turn'] == true;
      _canBank = _turnScore >= (state['min_bank'] ?? 30) && _isMyTurn;
      _lastAction = state['last_action']?.toString() ?? '';
      _availableCombinations = state['available_combinations'] is List
          ? state['available_combinations']
          : [];
      _selectedIndices.clear();
    });
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

  void _rollDice() {
    SoundService.instance.playSound('FARKLE_ROLL');
    _sendAction({'action': 'roll'});
  }

  void _scoreSelectedDice() {
    if (_selectedIndices.isEmpty) return;
    SoundService.instance.playSound('FARKLE_SCORE');
    final indicesStr = _selectedIndices.toList()..sort();
    _sendAction({
      'action': 'score',
      'card_id': indicesStr.join(','),
      'value': indicesStr,
    });
  }

  void _bankScore() {
    SoundService.instance.playSound('FARKLE_BANK');
    _sendAction({'action': 'bank'});
  }

  void _toggleDie(int index) {
    setState(() {
      if (_selectedIndices.contains(index)) {
        _selectedIndices.remove(index);
      } else {
        _selectedIndices.add(index);
      }
    });
    SoundService.instance.playSound('FARKLE_SCORE');
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Score banner
        Container(
          padding: const EdgeInsets.all(16),
          margin: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: _isMyTurn ? Colors.greenAccent : AppColors.divider,
              width: 2,
            ),
          ),
          child: Column(
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceAround,
                children: [
                  Semantics(
                    label: 'نقاط الدور الحالية $_turnScore',
                    child: Column(
                      children: [
                        Text(tr('نقاط الدور الحالي'), style: const TextStyle(fontSize: 14, color: Colors.white70)),
                        const SizedBox(height: 4),
                        Text(
                          '$_turnScore',
                          style: const TextStyle(fontSize: 26, fontWeight: FontWeight.bold, color: Colors.amberAccent),
                        ),
                      ],
                    ),
                  ),
                  Column(
                    children: [
                      Text(tr('الحالة'), style: const TextStyle(fontSize: 14, color: Colors.white70)),
                      const SizedBox(height: 4),
                      Text(
                        _isMyTurn
                            ? (_mustScore ? tr('يجب اختيار نرد رابح') : tr('دورك للعب'))
                            : tr('في انتظار دورك'),
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: _isMyTurn ? Colors.greenAccent : Colors.white60,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              if (_lastAction.isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(
                  _lastAction,
                  style: const TextStyle(color: Colors.white70, fontSize: 13),
                  textAlign: TextAlign.center,
                ),
              ],
            ],
          ),
        ),

        // Action Buttons Row: Roll, Score, Bank
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
          child: Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.card,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 12),
                  ),
                  icon: const Icon(Icons.casino, color: Colors.orangeAccent),
                  label: Text(tr('ارمي النرد')),
                  onPressed: (_canRoll && _isMyTurn) ? _rollDice : null,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _selectedIndices.isNotEmpty ? Colors.amber.shade800 : AppColors.card,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 12),
                  ),
                  icon: const Icon(Icons.check_circle, color: Colors.greenAccent),
                  label: Text(tr('تسجيل')),
                  onPressed: (_selectedIndices.isNotEmpty && _isMyTurn) ? _scoreSelectedDice : null,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _canBank ? Colors.green.shade700 : AppColors.card,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 12),
                  ),
                  icon: const Icon(Icons.account_balance),
                  label: Text(tr('تثبيت')),
                  onPressed: (_canBank && _isMyTurn) ? _bankScore : null,
                ),
              ),
            ],
          ),
        ),

        const SizedBox(height: 8),

        // Available Combinations Hint
        if (_availableCombinations.isNotEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: AppColors.card,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                '${tr('التركيبات المتاحة')}: ${_availableCombinations.map((c) => c is Map ? (c['name_ar'] ?? c['name'] ?? '') : c.toString()).join('، ')}',
                style: const TextStyle(color: Colors.amberAccent, fontSize: 13),
              ),
            ),
          ),

        const SizedBox(height: 8),

        // Dice Grid
        Expanded(
          child: _currentDice.isEmpty
              ? Center(
                  child: Text(
                    tr('اضغط ارمي النرد لبدء جولة الفاركل'),
                    style: const TextStyle(color: Colors.white60, fontSize: 16),
                  ),
                )
              : GridView.builder(
                  padding: const EdgeInsets.all(16),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 3,
                    childAspectRatio: 1.1,
                    crossAxisSpacing: 14,
                    mainAxisSpacing: 14,
                  ),
                  itemCount: _currentDice.length,
                  itemBuilder: (context, index) {
                    final value = _currentDice[index];
                    final isSelected = _selectedIndices.contains(index);

                    return Semantics(
                      button: true,
                      label: 'نرد رقم $value ${isSelected ? 'محدد' : 'غير محدد'}',
                      hint: tr('انقر لتحديد أو إلغاء تحديد هذا النرد'),
                      child: InkWell(
                        onTap: () => _toggleDie(index),
                        borderRadius: BorderRadius.circular(12),
                        child: Container(
                          decoration: BoxDecoration(
                            color: isSelected ? Colors.amber.shade900 : AppColors.card,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(
                              color: isSelected ? Colors.amberAccent : AppColors.divider,
                              width: isSelected ? 3 : 1,
                            ),
                          ),
                          child: Center(
                            child: Text(
                              '$value',
                              style: TextStyle(
                                fontSize: 36,
                                fontWeight: FontWeight.bold,
                                color: isSelected ? Colors.white : Colors.white70,
                              ),
                            ),
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
}
