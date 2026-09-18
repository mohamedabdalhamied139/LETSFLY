import 'package:flutter/material.dart';
import '../../core/localization.dart';
import '../../core/sound_service.dart';
import '../../services/ws_service.dart';

class FarkleGameView extends StatefulWidget {
  final Map<String, dynamic>? initialState;

  const FarkleGameView({super.key, this.initialState});

  @override
  State<FarkleGameView> createState() => FarkleGameViewState();
}

class FarkleGameViewState extends State<FarkleGameView> {
  List<int> _currentDice = [];
  final Set<int> _selectedIndices = {};
  int _roundScore = 0;
  int _totalScore = 0;
  bool _canRoll = false;
  bool _canBank = false;

  @override
  void initState() {
    super.initState();
    if (widget.initialState != null) {
      updateState(widget.initialState!);
    }
  }

  void updateState(Map<String, dynamic> state) {
    setState(() {
      _currentDice = (state['dice'] as List?)?.map((e) => int.tryParse(e.toString()) ?? 1).toList() ?? [];
      _roundScore = state['round_score'] is int ? state['round_score'] : 0;
      _totalScore = state['total_score'] is int ? state['total_score'] : 0;
      _canRoll = state['can_roll'] == true;
      _canBank = state['can_bank'] == true;
      _selectedIndices.clear();
    });
  }

  void _rollDice() {
    SoundService.instance.playSound('farkle/dice_roll');
    WebSocketService.instance.sendJson({
      'type': 'game_action',
      'action': 'roll',
    });
  }

  void _bankScore() {
    SoundService.instance.playSound('farkle/bank');
    WebSocketService.instance.sendJson({
      'type': 'game_action',
      'action': 'bank',
    });
  }

  void _toggleDie(int index) {
    setState(() {
      if (_selectedIndices.contains(index)) {
        _selectedIndices.remove(index);
      } else {
        _selectedIndices.add(index);
      }
    });
    SoundService.instance.playSound('farkle/select');
    WebSocketService.instance.sendJson({
      'type': 'game_action',
      'action': 'select_dice',
      'indices': _selectedIndices.toList(),
    });
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Score summary
        Container(
          padding: const EdgeInsets.all(16),
          margin: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surface,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              Semantics(
                label: 'مجموع النقاط الكلي $_totalScore',
                child: Column(
                  children: [
                    Text(tr('المجموع الكلي'), style: const TextStyle(fontSize: 14)),
                    Text('$_totalScore', style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
                  ],
                ),
              ),
              Semantics(
                label: 'نقاط الجولة الحالية $_roundScore',
                child: Column(
                  children: [
                    Text(tr('نقاط الجولة'), style: const TextStyle(fontSize: 14)),
                    Text('$_roundScore', style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.amber)),
                  ],
                ),
              ),
            ],
          ),
        ),
        // Action Buttons
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
          children: [
            ElevatedButton.icon(
              onPressed: _canRoll ? _rollDice : null,
              icon: const Icon(Icons.casino),
              label: Text(tr('ارمي النرد')),
            ),
            ElevatedButton.icon(
              onPressed: _canBank ? _bankScore : null,
              style: ElevatedButton.styleFrom(backgroundColor: Colors.green, foregroundColor: Colors.white),
              icon: const Icon(Icons.account_balance),
              label: Text(tr('احفظ النقاط')),
            ),
          ],
        ),
        const SizedBox(height: 16),
        // Dice Grid
        Expanded(
          child: _currentDice.isEmpty
              ? Center(child: Text(tr('اضغط ارمي النرد لبدء جولة الفاركل')))
              : GridView.builder(
                  padding: const EdgeInsets.all(16),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 3,
                    childAspectRatio: 1.2,
                    crossAxisSpacing: 12,
                    mainAxisSpacing: 12,
                  ),
                  itemCount: _currentDice.length,
                  itemBuilder: (context, index) {
                    final value = _currentDice[index];
                    final isSelected = _selectedIndices.contains(index);

                    return Semantics(
                      button: true,
                      label: 'النرد ${index + 1}، القيمة $value' + (isSelected ? '، محدد' : ''),
                      hint: tr('انقر مرتين لتحديد أو إلغاء تحديد هذا النرد'),
                      child: InkWell(
                        onTap: () => _toggleDie(index),
                        borderRadius: BorderRadius.circular(12),
                        child: Container(
                          decoration: BoxDecoration(
                            color: isSelected ? Colors.amber.shade800 : Theme.of(context).colorScheme.primaryContainer,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(
                              color: isSelected ? Colors.white : Colors.transparent,
                              width: 2,
                            ),
                          ),
                          child: Center(
                            child: Text(
                              '$value',
                              style: const TextStyle(fontSize: 32, fontWeight: FontWeight.bold),
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
