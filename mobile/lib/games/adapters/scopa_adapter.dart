import 'package:flutter/material.dart';
import '../../core/localization.dart';
import '../../core/sound_service.dart';
import '../../services/ws_service.dart';

class ScopaGameView extends StatefulWidget {
  final Map<String, dynamic>? initialState;

  const ScopaGameView({super.key, this.initialState});

  @override
  State<ScopaGameView> createState() => ScopaGameViewState();
}

class ScopaGameViewState extends State<ScopaGameView> {
  List<dynamic> _hand = [];
  List<dynamic> _tableCards = [];
  bool _isMyTurn = false;

  @override
  void initState() {
    super.initState();
    if (widget.initialState != null) {
      updateState(widget.initialState!);
    }
  }

  void updateState(Map<String, dynamic> state) {
    setState(() {
      _hand = state['hand'] is List ? state['hand'] : [];
      _tableCards = state['table_cards'] is List ? state['table_cards'] : [];
      _isMyTurn = state['is_my_turn'] == true;
    });
  }

  void _playCard(dynamic card) {
    final cardId = card['id'] ?? card.toString();
    SoundService.instance.playSound('uno/place');
    WebSocketService.instance.sendJson({
      'type': 'game_action',
      'action': 'play_card',
      'card_id': cardId,
    });
  }

  String _formatCard(dynamic card) {
    if (card is Map) {
      return '${tr(card['suit']?.toString() ?? '')} ${card['value'] ?? ''}'.trim();
    }
    return card.toString();
  }

  @override
  Widget build(BuildContext context) {
    final tableDesc = _tableCards.isEmpty
        ? tr('الطاولة فارغة')
        : _tableCards.map(_formatCard).join('، ');

    return Column(
      children: [
        // Table Cards
        Container(
          padding: const EdgeInsets.all(16),
          margin: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surface,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: _isMyTurn ? Colors.green : Colors.transparent, width: 2),
          ),
          child: Column(
            children: [
              Semantics(
                label: 'كروت الطاولة الحالية: $tableDesc',
                child: Text(
                  '${tr('كروت الطاولة')}: $tableDesc',
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  textAlign: TextAlign.center,
                ),
              ),
              if (_isMyTurn) ...[
                const SizedBox(height: 8),
                Text(
                  tr('دورك الآن للعب كرت إسكوبا!'),
                  style: const TextStyle(color: Colors.green, fontWeight: FontWeight.bold),
                ),
              ],
            ],
          ),
        ),
        // Hand Cards
        Expanded(
          child: _hand.isEmpty
              ? Center(child: Text(tr('يدك فارغة.')))
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: _hand.length,
                  itemBuilder: (context, index) {
                    final card = _hand[index];
                    final title = _formatCard(card);

                    return Semantics(
                      button: true,
                      label: 'كرت إسكوبا $title',
                      hint: tr('انقر مرتين لرمي هذا الكرت على الطاولة'),
                      child: Card(
                        child: ListTile(
                          leading: const Icon(Icons.style),
                          title: Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
                          trailing: const Icon(Icons.play_arrow),
                          onTap: () => _playCard(card),
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
