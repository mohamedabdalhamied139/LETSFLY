import 'package:flutter/material.dart';
import '../../core/localization.dart';
import '../../core/sound_service.dart';
import '../../services/ws_service.dart';

class UnoGameView extends StatefulWidget {
  final Map<String, dynamic>? initialState;

  const UnoGameView({super.key, this.initialState});

  @override
  State<UnoGameView> createState() => UnoGameViewState();
}

class UnoGameViewState extends State<UnoGameView> {
  List<dynamic> _hand = [];
  Map<String, dynamic>? _topCard;
  String _currentColor = '';
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
      _topCard = state['top_card'] is Map<String, dynamic> ? state['top_card'] : null;
      _currentColor = state['current_color'] ?? '';
      _isMyTurn = state['is_my_turn'] == true;
    });
  }

  void _playCard(dynamic card) {
    final cardId = card['id'] ?? card['card_id'];
    final cardType = card['type'] ?? '';

    if (cardType == 'wild' || cardType == 'wild_draw4') {
      _showColorPicker(cardId);
    } else {
      SoundService.instance.playSound('uno/place');
      WebSocketService.instance.sendJson({
        'type': 'game_action',
        'action': 'play_card',
        'card_id': cardId,
      });
    }
  }

  void _showColorPicker(dynamic cardId) {
    SoundService.instance.playSound('uno/wild_color_prompt');
    final colors = [
      {'id': 'red', 'title': 'أحمر', 'color': Colors.red},
      {'id': 'yellow', 'title': 'أصفر', 'color': Colors.amber},
      {'id': 'green', 'title': 'أخضر', 'color': Colors.green},
      {'id': 'blue', 'title': 'أزرق', 'color': Colors.blue},
    ];

    showModalBottomSheet(
      context: context,
      isDismissible: false,
      builder: (ctx) => Container(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              tr('اختر لون الكرت الجديد'),
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: colors.map((c) {
                return Semantics(
                  button: true,
                  label: tr(c['title'] as String),
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: c['color'] as Color,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                    ),
                    onPressed: () {
                      Navigator.of(ctx).pop();
                      SoundService.instance.playSound('uno/wild_color');
                      WebSocketService.instance.sendJson({
                        'type': 'game_action',
                        'action': 'play_card',
                        'card_id': cardId,
                        'chosen_color': c['id'],
                      });
                    },
                    child: Text(tr(c['title'] as String), style: const TextStyle(fontWeight: FontWeight.bold)),
                  ),
                );
              }).toList(),
            ),
          ],
        ),
      ),
    );
  }

  void _drawCard() {
    SoundService.instance.playSound('uno/draw');
    WebSocketService.instance.sendJson({
      'type': 'game_action',
      'action': 'draw_card',
    });
  }

  String _formatCard(dynamic card) {
    if (card is! Map) return card.toString();
    final color = card['color'] ?? '';
    final val = card['value'] ?? card['type'] ?? '';
    return '${tr(color.toString())} ${tr(val.toString())}'.trim();
  }

  @override
  Widget build(BuildContext context) {
    final topCardText = _topCard != null ? _formatCard(_topCard) : tr('لا يوجد');

    return Column(
      children: [
        // Table Center Area
        Container(
          padding: const EdgeInsets.all(16),
          margin: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surface,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: _isMyTurn ? Colors.green : Colors.transparent,
              width: 2,
            ),
          ),
          child: Column(
            children: [
              Text(
                '${tr('الكرت الحالي')}: $topCardText' +
                    (_currentColor.isNotEmpty ? ' (${tr(_currentColor)})' : ''),
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
              if (_isMyTurn) ...[
                const SizedBox(height: 8),
                Text(
                  tr('دورك الآن للعب!'),
                  style: const TextStyle(color: Colors.green, fontWeight: FontWeight.bold),
                ),
              ],
            ],
          ),
        ),
        // Draw Button
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: OutlinedButton.icon(
            icon: const Icon(Icons.add_card),
            label: Text(tr('سحب كرت')),
            onPressed: _drawCard,
          ),
        ),
        const SizedBox(height: 8),
        // Hand Cards List
        Expanded(
          child: _hand.isEmpty
              ? Center(child: Text(tr('يدك فارغة.')))
              : ListView.builder(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  itemCount: _hand.length,
                  itemBuilder: (context, index) {
                    final card = _hand[index];
                    final cardTitle = _formatCard(card);

                    return Card(
                      margin: const EdgeInsets.symmetric(vertical: 4),
                      child: ListTile(
                        leading: const Icon(Icons.crop_portrait),
                        title: Text(
                          cardTitle,
                          style: const TextStyle(fontWeight: FontWeight.bold),
                        ),
                        trailing: const Icon(Icons.play_arrow),
                        onTap: () => _playCard(card),
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }
}
