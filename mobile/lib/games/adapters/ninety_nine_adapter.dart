import 'package:flutter/material.dart';
import '../../core/localization.dart';
import '../../core/sound_service.dart';
import '../../services/ws_service.dart';

class NinetyNineGameView extends StatefulWidget {
  final Map<String, dynamic>? initialState;

  const NinetyNineGameView({super.key, this.initialState});

  @override
  State<NinetyNineGameView> createState() => NinetyNineGameViewState();
}

class NinetyNineGameViewState extends State<NinetyNineGameView> {
  List<dynamic> _hand = [];
  int _currentTotal = 0;
  int _tokens = 3;
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
      _currentTotal = state['total'] is int ? state['total'] : 0;
      _tokens = state['tokens'] is int ? state['tokens'] : 3;
      _isMyTurn = state['is_my_turn'] == true;
    });
  }

  void _playCard(dynamic card) {
    final cardId = card['id'] ?? card.toString();
    final cardVal = card['value']?.toString() ?? '';

    // If card is a 10 (can be +10 or -10), prompt the player
    if (cardVal == '10') {
      _promptTenChoice(cardId);
    } else {
      _submitCard(cardId, null);
    }
  }

  void _promptTenChoice(dynamic cardId) {
    showModalBottomSheet(
      context: context,
      builder: (ctx) => Container(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(tr('اختر قيمة الكرت 10'), style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                ElevatedButton(
                  onPressed: () {
                    Navigator.of(ctx).pop();
                    _submitCard(cardId, 10);
                  },
                  child: Text(tr('إضافة 10 (+10)')),
                ),
                ElevatedButton(
                  onPressed: () {
                    Navigator.of(ctx).pop();
                    _submitCard(cardId, -10);
                  },
                  child: Text(tr('طرح 10 (-10)')),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  void _submitCard(dynamic cardId, int? choice) {
    SoundService.instance.playSound('uno/place');
    WebSocketService.instance.sendJson({
      'type': 'game_action',
      'action': 'play_card',
      'card_id': cardId,
      'choice': choice,
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
    return Column(
      children: [
        // Table Total & Tokens
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
                liveRegion: true,
                label: 'مجموع الطاولة الحالي $_currentTotal من 99، ولديك $_tokens عملات متبقية',
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    Column(
                      children: [
                        Text(tr('مجموع الطاولة'), style: const TextStyle(fontSize: 14)),
                        Text('$_currentTotal / 99', style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold, color: _currentTotal >= 90 ? Colors.red : Colors.green)),
                      ],
                    ),
                    Column(
                      children: [
                        Text(tr('العملات'), style: const TextStyle(fontSize: 14)),
                        Text('$_tokens', style: const TextStyle(fontSize: 26, fontWeight: FontWeight.bold, color: Colors.amber)),
                      ],
                    ),
                  ],
                ),
              ),
              if (_isMyTurn) ...[
                const SizedBox(height: 8),
                Text(
                  tr('دورك الآن للعب! احذر تجاوز 99'),
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
                      label: 'كرت $title',
                      hint: tr('انقر مرتين للعب هذا الكرت'),
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
