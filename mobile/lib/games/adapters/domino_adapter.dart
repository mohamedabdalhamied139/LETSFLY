import 'package:flutter/material.dart';
import '../../core/localization.dart';
import '../../core/sound_service.dart';
import '../../services/ws_service.dart';

class DominoGameView extends StatefulWidget {
  final Map<String, dynamic>? initialState;
  final bool isAmerican;

  const DominoGameView({super.key, this.initialState, this.isAmerican = false});

  @override
  State<DominoGameView> createState() => DominoGameViewState();
}

class DominoGameViewState extends State<DominoGameView> {
  List<dynamic> _hand = [];
  dynamic _leftEnd;
  dynamic _rightEnd;
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
      final board = state['board'] is Map ? state['board'] : {};
      _leftEnd = board['left_end'] ?? state['left_end'];
      _rightEnd = board['right_end'] ?? state['right_end'];
      _isMyTurn = state['is_my_turn'] == true;
    });
  }

  void _playDomino(dynamic tile) {
    final tileId = tile['id'] ?? tile.toString();
    // Choose side if board has two open ends
    if (_leftEnd != null && _rightEnd != null && _leftEnd != _rightEnd) {
      _showSidePicker(tileId);
    } else {
      _submitTile(tileId, 'left');
    }
  }

  void _showSidePicker(dynamic tileId) {
    showModalBottomSheet(
      context: context,
      builder: (ctx) => Container(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(tr('اختر طرف الطاولة للعب القطعة'), style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                ElevatedButton(
                  onPressed: () {
                    Navigator.of(ctx).pop();
                    _submitTile(tileId, 'left');
                  },
                  child: Text('${tr('الطرف الأيسر')} ($_leftEnd)'),
                ),
                ElevatedButton(
                  onPressed: () {
                    Navigator.of(ctx).pop();
                    _submitTile(tileId, 'right');
                  },
                  child: Text('${tr('الطرف الأيمن')} ($_rightEnd)'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  void _submitTile(dynamic tileId, String side) {
    SoundService.instance.playSound('domino/place');
    WebSocketService.instance.sendJson({
      'type': 'game_action',
      'action': 'play_tile',
      'tile_id': tileId,
      'side': side,
    });
  }

  void _drawOrPass() {
    SoundService.instance.playSound('domino/draw');
    WebSocketService.instance.sendJson({
      'type': 'game_action',
      'action': 'draw_or_pass',
    });
  }

  String _formatTile(dynamic tile) {
    if (tile is Map) {
      return '${tile['left']} / ${tile['right']}';
    } else if (tile is List && tile.length >= 2) {
      return '${tile[0]} / ${tile[1]}';
    }
    return tile.toString();
  }

  @override
  Widget build(BuildContext context) {
    final endsText = (_leftEnd != null && _rightEnd != null)
        ? '${tr('اليمين')}: $_rightEnd | ${tr('اليسار')}: $_leftEnd'
        : tr('طاولة الدومينو فارغة بعد');

    return Column(
      children: [
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
                label: 'أطراف الطاولة: $endsText',
                child: Text(
                  endsText,
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
              ),
              if (_isMyTurn) ...[
                const SizedBox(height: 8),
                Text(
                  tr('دورك الآن للعب قطعة دومينو!'),
                  style: const TextStyle(color: Colors.green, fontWeight: FontWeight.bold),
                ),
              ],
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: OutlinedButton.icon(
            icon: const Icon(Icons.download),
            label: Text(tr('سحب قطعة / تمرير (أو اسحب لأسفل)')),
            onPressed: _drawOrPass,
          ),
        ),
        const SizedBox(height: 8),
        Expanded(
          child: _hand.isEmpty
              ? Center(child: Text(tr('يدك لا تحتوي على قطع.')))
              : ListView.builder(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  itemCount: _hand.length,
                  itemBuilder: (context, index) {
                    final tile = _hand[index];
                    final tileTitle = _formatTile(tile);

                    return Semantics(
                      button: true,
                      label: 'قطعة دومينو $tileTitle',
                      hint: tr('انقر مرتين للعب هذه القطعة'),
                      child: Card(
                        child: ListTile(
                          leading: const Icon(Icons.filter_2),
                          title: Text(
                            tileTitle,
                            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
                          ),
                          trailing: const Icon(Icons.play_arrow),
                          onTap: () => _playDomino(tile),
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
