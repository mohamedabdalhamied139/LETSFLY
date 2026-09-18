import 'package:flutter/material.dart';
import '../../core/app_theme.dart';
import '../../core/localization.dart';
import '../../core/sound_service.dart';
import '../../services/api_service.dart';
import '../../services/ws_service.dart';

class DominoGameView extends StatefulWidget {
  final String roomId;
  final Map<String, dynamic>? initialState;
  final bool isAmerican;

  const DominoGameView({
    super.key,
    required this.roomId,
    this.initialState,
    this.isAmerican = false,
  });

  @override
  State<DominoGameView> createState() => DominoGameViewState();
}

class DominoGameViewState extends State<DominoGameView> {
  List<dynamic> _hand = [];
  List<dynamic> _board = [];
  dynamic _leftEnd;
  dynamic _rightEnd;
  int _boneyardCount = 0;
  bool _canDraw = false;
  bool _canPass = false;
  bool _isMyTurn = false;
  String _lastAction = '';

  @override
  void initState() {
    super.initState();
    if (widget.initialState != null) {
      updateState(widget.initialState!);
    }
  }

  @override
  void didUpdateWidget(DominoGameView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.initialState != null) {
      updateState(widget.initialState!);
    }
  }

  void updateState(Map<String, dynamic> state) {
    setState(() {
      _hand = state['hand'] is List ? state['hand'] : [];
      _board = state['board'] is List ? state['board'] : [];
      _leftEnd = state['left_end'];
      _rightEnd = state['right_end'];
      _boneyardCount = state['boneyard_count'] is int ? state['boneyard_count'] : 0;
      _canDraw = state['can_draw'] == true;
      _canPass = state['can_pass'] == true;
      _isMyTurn = state['is_my_turn'] == true;
      _lastAction = state['last_action']?.toString() ?? '';
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

  void _playTile(int tileIndex, dynamic tile) {
    List<dynamic> validSides = [];
    if (tile is Map && tile['valid_sides'] is List) {
      validSides = tile['valid_sides'];
    }

    if (validSides.contains('left') && validSides.contains('right') && _leftEnd != _rightEnd && _leftEnd != null) {
      _showSidePicker(tileIndex);
    } else {
      final side = validSides.contains('right') ? 'right' : 'left';
      _submitTile(tileIndex, side);
    }
  }

  void _showSidePicker(int tileIndex) {
    showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.surface,
      builder: (ctx) => Container(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              tr('اختر طرف الطاولة للعب القطعة'),
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18, color: Colors.white),
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.card,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
                  ),
                  icon: const Icon(Icons.arrow_back, color: Colors.lightBlueAccent),
                  label: Text('${tr('الطرف الأيسر')} ($_leftEnd)'),
                  onPressed: () {
                    Navigator.of(ctx).pop();
                    _submitTile(tileIndex, 'left');
                  },
                ),
                ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.card,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
                  ),
                  icon: const Icon(Icons.arrow_forward, color: Colors.orangeAccent),
                  label: Text('${tr('الطرف الأيمن')} ($_rightEnd)'),
                  onPressed: () {
                    Navigator.of(ctx).pop();
                    _submitTile(tileIndex, 'right');
                  },
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  void _submitTile(int tileIndex, String side) {
    SoundService.instance.playSound('DOMINO_PLACE');
    _sendAction({
      'action': 'play',
      'card_id': tileIndex.toString(),
      'side': side,
    });
  }

  void _drawTile() {
    SoundService.instance.playSound('DOMINO_DRAW');
    _sendAction({'action': 'draw'});
  }

  void _passTurn() {
    SoundService.instance.playSound('DOMINO_PASS');
    _sendAction({'action': 'pass'});
  }

  String _formatTile(dynamic tile) {
    if (tile is Map) {
      if (tile['label'] != null) return tile['label'].toString();
      if (tile['tile'] is List && (tile['tile'] as List).length >= 2) {
        return '${tile['tile'][0]} / ${tile['tile'][1]}';
      }
    } else if (tile is List && tile.length >= 2) {
      return '${tile[0]} / ${tile[1]}';
    }
    return tile.toString();
  }

  @override
  Widget build(BuildContext context) {
    final endsText = (_leftEnd != null && _rightEnd != null)
        ? '${tr('اليسار')}: $_leftEnd  |  ${tr('اليمين')}: $_rightEnd'
        : tr('طاولة الدومينو فارغة بعد');

    return Column(
      children: [
        // Board Center Area
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
                endsText,
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white),
              ),
              const SizedBox(height: 6),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    '${tr('قطع السحب')}: $_boneyardCount',
                    style: const TextStyle(color: Colors.white70, fontSize: 14),
                  ),
                  const SizedBox(width: 16),
                  Text(
                    '${tr('قطع الطاولة')}: ${_board.length}',
                    style: const TextStyle(color: Colors.white70, fontSize: 14),
                  ),
                ],
              ),
              if (_isMyTurn) ...[
                const SizedBox(height: 8),
                Text(
                  tr('دورك الآن للعب!'),
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

        // Action Buttons Row: Draw Tile or Pass Turn
        if (_canDraw || _canPass)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            child: Row(
              children: [
                if (_canDraw)
                  Expanded(
                    child: ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.card,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                      icon: const Icon(Icons.add_box, color: Colors.orangeAccent),
                      label: Text('${tr('سحب قطعة')} ($_boneyardCount)'),
                      onPressed: _drawTile,
                    ),
                  ),
                if (_canDraw && _canPass) const SizedBox(width: 8),
                if (_canPass)
                  Expanded(
                    child: ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.blueGrey,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                      icon: const Icon(Icons.skip_next),
                      label: Text(tr('تمرير الدور')),
                      onPressed: _passTurn,
                    ),
                  ),
              ],
            ),
          ),

        const SizedBox(height: 4),

        // Hand Tiles List
        Expanded(
          child: _hand.isEmpty
              ? Center(
                  child: Text(
                    tr('يدك لا تحتوي على قطع.'),
                    style: const TextStyle(color: Colors.white60, fontSize: 16),
                  ),
                )
              : ListView.separated(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  itemCount: _hand.length,
                  separatorBuilder: (_, __) => const Divider(height: 1, color: AppColors.divider),
                  itemBuilder: (context, index) {
                    final tile = _hand[index];
                    final tileTitle = _formatTile(tile);
                    final isValid = (tile is Map && tile['is_valid'] == true) || _isMyTurn;

                    return ListTile(
                      tileColor: AppColors.card,
                      leading: const Icon(Icons.view_agenda, color: Colors.amberAccent),
                      title: Text(
                        tileTitle,
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 18,
                          color: isValid ? Colors.white : Colors.white38,
                        ),
                      ),
                      trailing: isValid
                          ? const Icon(Icons.play_arrow, color: Colors.greenAccent)
                          : null,
                      onTap: isValid ? () => _playTile(index, tile) : null,
                    );
                  },
                ),
        ),
      ],
    );
  }
}
