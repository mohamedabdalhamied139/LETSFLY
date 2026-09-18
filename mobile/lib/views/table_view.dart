import 'package:flutter/material.dart';
import '../core/localization.dart';
import '../services/api_service.dart';
import '../services/ws_service.dart';
import '../widgets/gesture_detector.dart';
import '../games/adapters/uno_adapter.dart';
import '../games/adapters/domino_adapter.dart';
import '../games/adapters/farkle_adapter.dart';
import '../games/adapters/tennis_adapter.dart';
import '../games/adapters/thief_adapter.dart';
import '../games/adapters/snakes_adapter.dart';
import '../games/adapters/scopa_adapter.dart';
import '../games/adapters/ninety_nine_adapter.dart';

class TableView extends StatefulWidget {
  final String roomId;
  final String? gameType;

  const TableView({super.key, required this.roomId, this.gameType});

  @override
  State<TableView> createState() => _TableViewState();
}

class _TableViewState extends State<TableView> {
  Map<String, dynamic>? _roomState;
  Map<String, dynamic>? _gameState;
  final List<String> _chatMessages = [];
  final List<String> _activityLogs = [];
  final TextEditingController _chatController = TextEditingController();
  bool _isReady = false;

  @override
  void initState() {
    super.initState();
    _connectWebSocket();
  }

  void _connectWebSocket() {
    final wsUrl = ApiService.instance.getWsUrl('/ws/room/${widget.roomId}');
    WebSocketService.instance.connect(wsUrl, token: ApiService.instance.authToken);
    WebSocketService.instance.messages.listen((data) {
      final type = data['type'];
      if (type == 'room_snapshot') {
        setState(() {
          _roomState = data['room'];
          final gType = (_roomState?['game_type'] ?? '').toString().toUpperCase();
          if (gType == 'UNO') {
            _gameState = data['uno_state'];
          } else if (gType == 'DOMINO') {
            _gameState = data['domino_state'];
          } else if (gType == 'AMERICAN_DOMINO') {
            _gameState = data['american_domino_state'];
          } else if (gType == 'FARKLE') {
            _gameState = data['farkle_state'];
          } else if (gType == 'TENNIS') {
            _gameState = data['tennis_state'];
          } else if (gType == 'THIEF_HUNT') {
            _gameState = data['thief_state'];
          } else if (gType == 'SNAKES_LADDERS') {
            _gameState = data['snakes_state'];
          } else if (gType == 'SCOPA') {
            _gameState = data['scopa_state'];
          } else if (gType == 'NINETY_NINE') {
            _gameState = data['ninety_nine_state'];
          }
        });
      } else if (type == 'game_state_changed' || type == 'tennis_state_changed') {
        setState(() {
          _gameState = data['state'] ?? data;
        });
      } else if (type == 'chat_message') {
        setState(() {
          _chatMessages.add('${data['sender']}: ${data['text']}');
        });
      } else if (type == 'activity_event') {
        setState(() {
          _activityLogs.add(data['text'] ?? '');
        });
      }
    });
  }

  void _sendChat() {
    final text = _chatController.text.trim();
    if (text.isEmpty) return;
    WebSocketService.instance.sendJson({'type': 'chat', 'text': text});
    _chatController.clear();
  }

  void _toggleReady() {
    setState(() => _isReady = !_isReady);
    WebSocketService.instance.sendJson({
      'type': 'room_action',
      'action': _isReady ? 'ready' : 'unready',
    });
  }

  void _showPlayersDialog() {
    final players = (_roomState?['players'] as List?) ?? [];
    showModalBottomSheet(
      context: context,
      builder: (ctx) => Container(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              '${tr('اللاعبون في الطاولة')} (${players.length})',
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            ...players.map((p) {
              final name = p is Map ? (p['name'] ?? p['username'] ?? 'لاعب') : p.toString();
              final isReady = p is Map ? p['ready'] == true : false;
              final isHost = p is Map ? p['is_host'] == true : false;

              return ListTile(
                leading: CircleAvatar(
                  backgroundColor: isReady ? Colors.green : Colors.grey,
                  child: Icon(isHost ? Icons.star : Icons.person, color: Colors.white),
                ),
                title: Text(name),
                trailing: Text(
                  isReady ? tr('جاهز') : tr('غير جاهز'),
                  style: TextStyle(color: isReady ? Colors.green : Colors.orange, fontWeight: FontWeight.bold),
                ),
              );
            }).toList(),
          ],
        ),
      ),
    );
  }

  void _showActivityLogDialog() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => DraggableScrollableSheet(
        expand: false,
        builder: (_, scrollController) => Scaffold(
          appBar: AppBar(
            title: Text(tr('سجل النشاط والأحداث')),
            leading: IconButton(
              icon: const Icon(Icons.close),
              onPressed: () => Navigator.of(ctx).pop(),
            ),
          ),
          body: _activityLogs.isEmpty
              ? Center(child: Text(tr('لا توجد أحداث مسجلة بعد.')))
              : ListView.builder(
                  controller: scrollController,
                  itemCount: _activityLogs.length,
                  itemBuilder: (_, idx) => ListTile(
                    title: Text(_activityLogs[idx]),
                  ),
                ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    WebSocketService.instance.disconnect();
    _chatController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final gameType = _roomState?['game_type'] ?? '';
    final isTennis = gameType == 'TENNIS';
    final isUnoOrDomino = gameType == 'UNO' || gameType.toString().contains('DOMINO');

    return TableGestureDetector(
      isTennis: isTennis,
      isUnoOrDomino: isUnoOrDomino,
      onOpenLog: _showActivityLogDialog,
      onQueryTable: () {
        // R key equivalent
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(tr('استعلام عن كروت وأوراق الطاولة'))),
        );
      },
      onTableInfo: () {
        // T key equivalent
        final playersCount = (_roomState?['players'] as List?)?.length ?? 0;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(tr('عدد اللاعبين الحاليين: {count}', {'count': playersCount}))),
        );
      },
      onSpaceKey: () {
        // Space key equivalent
        WebSocketService.instance.sendJson({'type': 'game_action', 'action': 'draw'});
      },
      child: Scaffold(
        appBar: AppBar(
          title: Text(_roomState?['name'] ?? tr('طاولة اللعب')),
          actions: [
            IconButton(
              tooltip: tr('اللاعبون'),
              icon: const Icon(Icons.group),
              onPressed: _showPlayersDialog,
            ),
            IconButton(
              tooltip: tr('سجل النشاط'),
              icon: const Icon(Icons.history),
              onPressed: _showActivityLogDialog,
            ),
          ],
        ),
        body: Column(
          children: [
            // Status Banner
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              color: Theme.of(context).colorScheme.surfaceVariant,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    '${tr('اللعبة')}: $gameType',
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                  Row(
                    children: [
                      if (_roomState?['is_host'] == true && _roomState?['status'] != 'playing')
                        Padding(
                          padding: const EdgeInsets.only(left: 8.0),
                          child: ElevatedButton(
                            onPressed: () {
                              WebSocketService.instance.sendJson({'type': 'room_action', 'action': 'start_game'});
                            },
                            style: ElevatedButton.styleFrom(backgroundColor: Colors.blue, foregroundColor: Colors.white),
                            child: Text(tr('بدء اللعبة')),
                          ),
                        ),
                      ElevatedButton(
                        onPressed: _toggleReady,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: _isReady ? Colors.green : Colors.orange,
                          foregroundColor: Colors.white,
                        ),
                        child: Text(_isReady ? tr('جاهز') : tr('غير جاهز')),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            // Shared Dynamic Game Play Area
            Expanded(
              child: _buildGameWidget(gameType),
            ),
            // Chat Input & Live Area
            Container(
              padding: const EdgeInsets.all(8.0),
              decoration: BoxDecoration(
                border: Border(top: BorderSide(color: DividerTheme.of(context).color ?? Colors.grey)),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _chatController,
                      decoration: InputDecoration(
                        hintText: tr('اكتب رسالة في الشات...'),
                        border: const OutlineInputBorder(),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                      ),
                      onSubmitted: (_) => _sendChat(),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton(
                    icon: const Icon(Icons.send),
                    onPressed: _sendChat,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildGameWidget(String gameType) {
    switch (gameType.toUpperCase()) {
      case 'UNO':
        return UnoGameView(initialState: _gameState);
      case 'DOMINO':
        return DominoGameView(initialState: _gameState, isAmerican: false);
      case 'AMERICAN_DOMINO':
        return DominoGameView(initialState: _gameState, isAmerican: true);
      case 'FARKLE':
        return FarkleGameView(initialState: _gameState);
      case 'TENNIS':
        return TennisGameView(initialState: _gameState);
      case 'THIEF_HUNT':
        return ThiefGameView(initialState: _gameState);
      case 'SNAKES_LADDERS':
        return SnakesGameView(initialState: _gameState);
      case 'SCOPA':
        return ScopaGameView(initialState: _gameState);
      case 'NINETY_NINE':
        return NinetyNineGameView(initialState: _gameState);
      default:
        return Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.casino, size: 64),
              const SizedBox(height: 16),
              Text(
                tr('في انتظار بدء اللعبة...'),
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
            ],
          ),
        );
    }
  }
}
