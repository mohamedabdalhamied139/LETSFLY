import 'package:flutter/material.dart';
import '../../core/app_theme.dart';
import '../../core/localization.dart';
import '../../core/sound_service.dart';
import '../../services/api_service.dart';
import '../../services/ws_service.dart';

class SnakesGameView extends StatefulWidget {
  final String roomId;
  final Map<String, dynamic>? initialState;

  const SnakesGameView({
    super.key,
    required this.roomId,
    this.initialState,
  });

  @override
  State<SnakesGameView> createState() => SnakesGameViewState();
}

class SnakesGameViewState extends State<SnakesGameView> {
  int _position = 1;
  int _lastRoll = 0;
  bool _canRoll = false;
  bool _extraRoll = false;
  Map<String, dynamic>? _radar;
  List<dynamic> _players = [];
  String _lastAction = '';

  @override
  void initState() {
    super.initState();
    if (widget.initialState != null) {
      updateState(widget.initialState!);
    }
  }

  @override
  void didUpdateWidget(SnakesGameView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.initialState != null) {
      updateState(widget.initialState!);
    }
  }

  void updateState(Map<String, dynamic> state) {
    setState(() {
      _position = state['my_position'] is int
          ? state['my_position']
          : (state['position'] is int ? state['position'] : 1);
      _lastRoll = state['last_roll'] is int ? state['last_roll'] : 0;
      _canRoll = state['is_my_turn'] == true;
      _extraRoll = state['extra_roll'] == true;
      _radar = state['radar'] is Map<String, dynamic> ? state['radar'] : null;
      _players = state['players'] is List ? state['players'] : [];
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

  void _rollDice() {
    SoundService.instance.playSound('DICE_ROLL');
    _sendAction({'action': 'roll'});
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        children: [
          // Current Position Badge
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: _canRoll ? Colors.greenAccent : AppColors.divider,
                width: 2,
              ),
            ),
            child: Column(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 14),
                  decoration: BoxDecoration(
                    color: AppColors.card,
                    borderRadius: BorderRadius.circular(32),
                    border: Border.all(color: Colors.amberAccent, width: 2),
                  ),
                  child: Text(
                    '$_position',
                    style: const TextStyle(fontSize: 44, fontWeight: FontWeight.bold, color: Colors.amberAccent),
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  '${tr('المربع الحالي')}: $_position / 100',
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white),
                ),
                if (_lastRoll > 0) ...[
                  const SizedBox(height: 6),
                  Text(
                    '${tr('الرمية السابقة')}: $_lastRoll' + (_extraRoll ? ' (${tr('رمية إضافية!')})' : ''),
                    style: const TextStyle(fontSize: 15, color: Colors.lightGreenAccent),
                  ),
                ],
                if (_lastAction.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text(
                    _lastAction,
                    style: const TextStyle(color: Colors.white70, fontSize: 13),
                    textAlign: TextAlign.center,
                  ),
                ],
              ],
            ),
          ),

          const SizedBox(height: 12),

          // Radar Info Area (if available)
          if (_radar != null)
            Container(
              padding: const EdgeInsets.all(12),
              margin: const EdgeInsets.only(bottom: 12),
              decoration: BoxDecoration(
                color: AppColors.card,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: AppColors.divider),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceAround,
                children: [
                  if (_radar!['nearest_ladder'] != null)
                    Row(
                      children: [
                        const Icon(Icons.upgrade, color: Colors.greenAccent, size: 20),
                        const SizedBox(width: 4),
                        Text(
                          '${tr('سلم')}: +${_radar!['nearest_ladder'][2]}',
                          style: const TextStyle(color: Colors.greenAccent, fontWeight: FontWeight.bold, fontSize: 13),
                        ),
                      ],
                    ),
                  if (_radar!['nearest_snake'] != null)
                    Row(
                      children: [
                        const Icon(Icons.warning, color: Colors.redAccent, size: 18),
                        const SizedBox(width: 4),
                        Text(
                          '${tr('ثعبان')}: +${_radar!['nearest_snake'][2]}',
                          style: const TextStyle(color: Colors.redAccent, fontWeight: FontWeight.bold, fontSize: 13),
                        ),
                      ],
                    ),
                  Text(
                    '${tr('متبقي للفوز')}: ${100 - _position}',
                    style: const TextStyle(color: Colors.white70, fontSize: 13),
                  ),
                ],
              ),
            ),

          // Roll Dice Action Button
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: _canRoll ? _rollDice : null,
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 14),
                backgroundColor: _canRoll ? Colors.green.shade700 : AppColors.card,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              ),
              icon: const Icon(Icons.casino, size: 28),
              label: Text(
                _canRoll ? tr('ارمي النرد الآن!') : tr('انتظر دورك...'),
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
            ),
          ),

          const SizedBox(height: 16),

          // Players Leaderboard on the Board
          if (_players.isNotEmpty) ...[
            Align(
              alignment: Alignment.centerRight,
              child: Text(
                tr('مواقع المتسابقين:'),
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: Colors.white),
              ),
            ),
            const SizedBox(height: 8),
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: _players.length,
              separatorBuilder: (_, __) => const Divider(height: 1, color: AppColors.divider),
              itemBuilder: (context, index) {
                final p = _players[index];
                final name = p is Map ? (p['name'] ?? 'لاعب') : p.toString();
                final pos = p is Map ? (p['position'] ?? 0) : 0;
                final isFrozen = p is Map && p['is_frozen'] == true;

                return ListTile(
                  tileColor: AppColors.surface,
                  leading: CircleAvatar(
                    backgroundColor: index == 0 ? Colors.amber : Colors.blueGrey,
                    foregroundColor: Colors.black,
                    radius: 14,
                    child: Text('${index + 1}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12)),
                  ),
                  title: Text(name, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                  trailing: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (isFrozen)
                        const Padding(
                          padding: EdgeInsets.only(right: 6),
                          child: Icon(Icons.ac_unit, color: Colors.lightBlueAccent, size: 18),
                        ),
                      Text(
                        '$pos / 100',
                        style: const TextStyle(color: Colors.amberAccent, fontWeight: FontWeight.bold, fontSize: 15),
                      ),
                    ],
                  ),
                );
              },
            ),
          ],
        ],
      ),
    );
  }
}
