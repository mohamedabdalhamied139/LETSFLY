import 'package:flutter/material.dart';
import '../../core/app_theme.dart';
import '../../core/localization.dart';
import '../../core/sound_service.dart';
import '../../services/api_service.dart';
import '../../services/ws_service.dart';

class NinetyNineGameView extends StatefulWidget {
  final String roomId;
  final Map<String, dynamic>? initialState;

  const NinetyNineGameView({
    super.key,
    required this.roomId,
    this.initialState,
  });

  @override
  State<NinetyNineGameView> createState() => NinetyNineGameViewState();
}

class NinetyNineGameViewState extends State<NinetyNineGameView> {
  List<dynamic> _hand = [];
  int _pileValue = 0;
  int _tokens = 3;
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
  void didUpdateWidget(NinetyNineGameView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.initialState != null) {
      updateState(widget.initialState!);
    }
  }

  void updateState(Map<String, dynamic> state) {
    setState(() {
      _hand = state['hand'] is List ? state['hand'] : [];
      _pileValue = state['pile_value'] is int
          ? state['pile_value']
          : (state['total'] is int ? state['total'] : 0);

      final myUid = state['my_user_id']?.toString() ?? '';
      if (state['tokens'] is Map && myUid.isNotEmpty && state['tokens'][myUid] != null) {
        _tokens = int.tryParse(state['tokens'][myUid].toString()) ?? 3;
      } else if (state['tokens'] is int) {
        _tokens = state['tokens'];
      }

      _isMyTurn = state['is_my_turn'] == true ||
          (state['current_turn_id'] != null &&
              state['current_turn_id'].toString() == myUid) ||
          (state['current_player_id'] != null &&
              state['current_player_id'].toString() == myUid);

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

  void _playCard(dynamic card) {
    final cardId = card['id'] ?? card.toString();
    final cardVal = card['value']?.toString() ?? '';

    if (cardVal == '10') {
      _promptTenChoice(cardId);
    } else {
      SoundService.instance.playSound('NINETY_NINE_PLACE');
      _sendAction({
        'action': 'play',
        'card_id': cardId.toString(),
      });
    }
  }

  void _promptTenChoice(dynamic cardId) {
    showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.surface,
      builder: (ctx) => Container(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              tr('اختر قيمة الكرت 10'),
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18, color: Colors.white),
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.green.shade700,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
                  ),
                  onPressed: () {
                    Navigator.of(ctx).pop();
                    SoundService.instance.playSound('NINETY_NINE_PLACE');
                    _sendAction({
                      'action': 'choose',
                      'card_id': '+10',
                    });
                  },
                  child: Text(tr('إضافة 10 (+10)'), style: const TextStyle(fontWeight: FontWeight.bold)),
                ),
                ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.red.shade700,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
                  ),
                  onPressed: () {
                    Navigator.of(ctx).pop();
                    SoundService.instance.playSound('NINETY_NINE_PLACE');
                    _sendAction({
                      'action': 'choose',
                      'card_id': '-10',
                    });
                  },
                  child: Text(tr('طرح 10 (-10)'), style: const TextStyle(fontWeight: FontWeight.bold)),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  String _formatCard(dynamic card) {
    if (card is Map) {
      final suit = card['suit']?.toString() ?? '';
      final val = card['value'] ?? '';
      return '${tr(suit)} $val'.trim();
    }
    return card.toString();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Table Total & Tokens Area
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
              Semantics(
                liveRegion: true,
                label: 'مجموع الطاولة الحالي $_pileValue من 99، ولديك $_tokens عملات متبقية',
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    Column(
                      children: [
                        Text(tr('مجموع الطاولة'), style: const TextStyle(fontSize: 14, color: Colors.white70)),
                        const SizedBox(height: 4),
                        Text(
                          '$_pileValue / 99',
                          style: TextStyle(
                            fontSize: 28,
                            fontWeight: FontWeight.bold,
                            color: _pileValue >= 90 ? Colors.redAccent : Colors.greenAccent,
                          ),
                        ),
                      ],
                    ),
                    Column(
                      children: [
                        Text(tr('العملات المتبقية'), style: const TextStyle(fontSize: 14, color: Colors.white70)),
                        const SizedBox(height: 4),
                        Text(
                          '$_tokens',
                          style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Colors.amberAccent),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              if (_isMyTurn) ...[
                const SizedBox(height: 8),
                Text(
                  tr('دورك الآن للعب! احذر تجاوز 99'),
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
                      leading: const Icon(Icons.style, color: Colors.cyanAccent),
                      title: Text(
                        title,
                        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18, color: Colors.white),
                      ),
                      trailing: _isMyTurn
                          ? const Icon(Icons.play_arrow, color: Colors.greenAccent)
                          : null,
                      onTap: _isMyTurn ? () => _playCard(card) : null,
                    );
                  },
                ),
        ),
      ],
    );
  }
}
