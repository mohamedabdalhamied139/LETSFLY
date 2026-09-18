import 'package:flutter/material.dart';
import '../../core/app_theme.dart';
import '../../core/localization.dart';
import '../../core/sound_service.dart';
import '../../services/api_service.dart';
import '../../services/ws_service.dart';

class ScopaGameView extends StatefulWidget {
  final String roomId;
  final Map<String, dynamic>? initialState;

  const ScopaGameView({
    super.key,
    required this.roomId,
    this.initialState,
  });

  @override
  State<ScopaGameView> createState() => ScopaGameViewState();
}

class ScopaGameViewState extends State<ScopaGameView> {
  List<dynamic> _hand = [];
  List<dynamic> _tableCards = [];
  int _myCapturedCount = 0;
  int _deckCount = 0;
  bool _isMyTurn = false;
  dynamic _pendingChoice;
  String _lastAction = '';

  @override
  void initState() {
    super.initState();
    if (widget.initialState != null) {
      updateState(widget.initialState!);
    }
  }

  @override
  void didUpdateWidget(ScopaGameView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.initialState != null) {
      updateState(widget.initialState!);
    }
  }

  void updateState(Map<String, dynamic> state) {
    setState(() {
      _hand = state['my_hand'] is List
          ? state['my_hand']
          : (state['hand'] is List ? state['hand'] : []);
      _tableCards = state['table_cards'] is List ? state['table_cards'] : [];
      _myCapturedCount = state['my_captured_count'] is int ? state['my_captured_count'] : 0;
      _deckCount = state['deck_count'] is int ? state['deck_count'] : 0;
      _isMyTurn = state['is_my_turn'] == true ||
          (state['current_turn_id'] != null &&
              state['current_turn_id'].toString() == state['my_user_id']?.toString());
      _pendingChoice = state['pending_choice'];
      _lastAction = state['last_action']?.toString() ?? '';
    });

    if (state['sound_cue'] != null && state['sound_cue'].toString().isNotEmpty) {
      SoundService.instance.playSound(state['sound_cue'].toString());
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

  void _playCard(int index, dynamic card) {
    SoundService.instance.playSound('SCOPA_PLAY_CARD');
    _sendAction({
      'action': 'play',
      'card_id': index.toString(),
    });
  }

  String _formatCard(dynamic card) {
    if (card is Map) {
      final suit = card['suit']?.toString() ?? '';
      final val = card['value'] ?? card['rank'] ?? '';
      return '${tr(suit)} $val'.trim();
    }
    return card.toString();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Table Cards & Stats Area
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
                  Text(
                    '${tr('كروت السحب')}: $_deckCount',
                    style: const TextStyle(color: Colors.white70, fontSize: 14),
                  ),
                  Text(
                    '${tr('كروتك المأكولة')}: $_myCapturedCount',
                    style: const TextStyle(color: Colors.white70, fontSize: 14),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Text(
                tr('كروت الطاولة:'),
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: Colors.white),
              ),
              const SizedBox(height: 8),
              _tableCards.isEmpty
                  ? Text(
                      tr('الطاولة فارغة'),
                      style: const TextStyle(color: Colors.white54, fontStyle: FontStyle.italic),
                    )
                  : Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      alignment: WrapAlignment.center,
                      children: _tableCards.map((c) {
                        return Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                          decoration: BoxDecoration(
                            color: AppColors.card,
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: Colors.lightBlueAccent, width: 1.5),
                          ),
                          child: Text(
                            _formatCard(c),
                            style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.white),
                          ),
                        );
                      }).toList(),
                    ),
              if (_isMyTurn) ...[
                const SizedBox(height: 10),
                Text(
                  tr('دورك الآن للعب كرت إسكوبا!'),
                  style: const TextStyle(color: Colors.greenAccent, fontWeight: FontWeight.bold, fontSize: 15),
                ),
              ],
              if (_lastAction.isNotEmpty) ...[
                const SizedBox(height: 6),
                Text(
                  _lastAction,
                  style: const TextStyle(color: Colors.amberAccent, fontSize: 13),
                  textAlign: TextAlign.center,
                ),
              ],
            ],
          ),
        ),

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
                    final title = _formatCard(card);

                    return ListTile(
                      tileColor: AppColors.card,
                      leading: const Icon(Icons.style, color: Colors.amberAccent),
                      title: Text(
                        title,
                        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18, color: Colors.white),
                      ),
                      trailing: _isMyTurn
                          ? const Icon(Icons.play_arrow, color: Colors.greenAccent)
                          : null,
                      onTap: _isMyTurn ? () => _playCard(index, card) : null,
                    );
                  },
                ),
        ),
      ],
    );
  }
}
