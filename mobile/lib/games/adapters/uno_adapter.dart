import 'package:flutter/material.dart';
import '../../core/app_theme.dart';
import '../../core/localization.dart';
import '../../core/sound_service.dart';
import '../../services/api_service.dart';
import '../../services/ws_service.dart';

class UnoGameView extends StatefulWidget {
  final String roomId;
  final Map<String, dynamic>? initialState;

  const UnoGameView({super.key, required this.roomId, this.initialState});

  @override
  State<UnoGameView> createState() => UnoGameViewState();
}

class UnoGameViewState extends State<UnoGameView> {
  List<dynamic> _hand = [];
  Map<String, dynamic>? _topCard;
  String _currentColor = '';
  bool _isMyTurn = false;
  bool _canCallUno = false;

  @override
  void initState() {
    super.initState();
    if (widget.initialState != null) {
      updateState(widget.initialState!);
    }
  }

  @override
  void didUpdateWidget(UnoGameView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.initialState != null) {
      updateState(widget.initialState!);
    }
  }

  void updateState(Map<String, dynamic> state) {
    setState(() {
      _hand = state['hand'] is List ? state['hand'] : [];
      _topCard = state['top_card'] is Map<String, dynamic> ? state['top_card'] : null;
      _currentColor = state['current_color']?.toString() ?? '';
      _isMyTurn = state['is_my_turn'] == true || state['current_player'] == state['my_user_id'];
      _canCallUno = _hand.length == 2 && _isMyTurn;
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

  void _playCard(dynamic card) {
    final cardId = card['id'] ?? card['card_id'];
    final cardType = (card['type'] ?? card['value'] ?? '').toString().toLowerCase();

    if (cardType.contains('wild')) {
      _showColorPicker(cardId);
    } else {
      SoundService.instance.playSound('UNO_PLACE');
      _sendAction({
        'action': 'play',
        'card_id': cardId.toString(),
      });
    }
  }

  void _showColorPicker(dynamic cardId) {
    SoundService.instance.playSound('WILD_COLOR_PROMPT');
    final colors = [
      {'id': 'red', 'title': 'أحمر', 'color': Colors.red},
      {'id': 'yellow', 'title': 'أصفر', 'color': Colors.amber},
      {'id': 'green', 'title': 'أخضر', 'color': Colors.green},
      {'id': 'blue', 'title': 'أزرق', 'color': Colors.blue},
    ];

    showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.surface,
      isDismissible: false,
      builder: (ctx) => Container(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              tr('اختر لون الكرت الجديد'),
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white),
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
                      SoundService.instance.playSound('CARD_WILD_COLOR');
                      _sendAction({
                        'action': 'play',
                        'card_id': cardId.toString(),
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
    SoundService.instance.playSound('CARD_DRAW');
    _sendAction({'action': 'draw'});
  }

  void _callUno() {
    SoundService.instance.playSound('UNO_CALLED');
    _sendAction({'action': 'call_uno'});
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(tr('أونو!'))),
    );
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
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: _isMyTurn ? Colors.greenAccent : AppColors.divider,
              width: 2,
            ),
          ),
          child: Column(
            children: [
              Text(
                '${tr('الكرت الحالي')}: $topCardText' +
                    (_currentColor.isNotEmpty ? ' (${tr(_currentColor)})' : ''),
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white),
              ),
              const SizedBox(height: 6),
              Text(
                _isMyTurn ? tr('دورك الآن للعب!') : tr('في انتظار دور اللاعب التالي...'),
                style: TextStyle(
                  color: _isMyTurn ? Colors.greenAccent : Colors.white60,
                  fontWeight: FontWeight.bold,
                  fontSize: 15,
                ),
              ),
            ],
          ),
        ),

        // Action Buttons Row: Draw Card & Call Uno
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.card,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 12),
                  ),
                  icon: const Icon(Icons.add_card, color: Colors.orangeAccent),
                  label: Text(tr('سحب كرت')),
                  onPressed: _drawCard,
                ),
              ),
              if (_canCallUno || _hand.length <= 2) ...[
                const SizedBox(width: 8),
                ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.redAccent,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  ),
                  icon: const Icon(Icons.campaign),
                  label: Text(tr('أونو!')),
                  onPressed: _callUno,
                ),
              ],
            ],
          ),
        ),

        const SizedBox(height: 8),

        // Hand Cards List
        Expanded(
          child: _hand.isEmpty
              ? Center(
                  child: Text(
                    tr('يدك فارغة.'),
                    style: const TextStyle(color: Colors.white60, fontSize: 16),
                  ),
                )
              : ListView.separated(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  itemCount: _hand.length,
                  separatorBuilder: (_, __) => const Divider(height: 1, color: AppColors.divider),
                  itemBuilder: (context, index) {
                    final card = _hand[index];
                    final cardTitle = _formatCard(card);

                    return ListTile(
                      tileColor: AppColors.card,
                      leading: const Icon(Icons.style, color: Colors.lightBlueAccent),
                      title: Text(
                        cardTitle,
                        style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.white),
                      ),
                      trailing: const Icon(Icons.play_arrow, color: Colors.greenAccent),
                      onTap: () => _playCard(card),
                    );
                  },
                ),
        ),
      ],
    );
  }
}
