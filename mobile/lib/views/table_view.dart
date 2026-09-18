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
import 'table_players_dialog.dart';
import 'activity_log_widget.dart';

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
  final List<Map<String, dynamic>> _activityEvents = [];
  final TextEditingController _chatController = TextEditingController();

  int _myUserId = 0;

  @override
  void initState() {
    super.initState();
    _connectWebSocket();
    _fetchMyUserId();
  }

  Future<void> _fetchMyUserId() async {
    try {
      final me = await ApiService.instance.get('/api/auth/me');
      if (me is Map && me['user'] is Map && mounted) {
        setState(() {
          _myUserId = int.tryParse(me['user']['id'].toString()) ?? 0;
        });
      }
    } catch (_) {}
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
          if (_gameState?['sound_cue'] != null) {
            SoundService.instance.playSound(_gameState!['sound_cue'].toString());
          }
        });
      } else if (type == 'player_joined' || type == 'bot_added') {
        SoundService.instance.playSound('TABLE_JOIN');
      } else if (type == 'player_left' || type == 'bot_removed') {
        SoundService.instance.playSound('TABLE_LEAVE');
      } else if (type == 'game_stopped') {
        SoundService.instance.playSound('GAME_STOPPED');
      } else if (type == 'round_finished' || type == 'round_end') {
        SoundService.instance.playSound('ROUND_END');
      } else if (type == 'match_finished') {
        final won = data['winner_id']?.toString() == _myUserId.toString();
        SoundService.instance.playSound(won ? 'MATCH_WIN' : 'MATCH_LOSS');
      } else if (type == 'chat_message') {
        setState(() {
          _chatMessages.add('${data['sender']}: ${data['text']}');
          _activityEvents.add({
            'text': '${data['sender']}: ${data['text']}',
            'category': 'TABLE_CHAT',
          });
        });
      } else if (type == 'activity_event') {
        setState(() {
          _activityEvents.add({
            'text': data['text'] ?? data['message'] ?? '',
            'category': data['category'] ?? 'GAMEPLAY',
          });
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

  // Exact Windows Room Context Menu (_show_room_context_menu)
  void _showRoomContextMenu() {
    final isHost = _roomState?['is_host'] == true ||
        (_roomState?['host_id'] != null && _roomState?['host_id'].toString() == _myUserId.toString());
    final isCoHost = _roomState?['co_host_id'] != null &&
        _roomState?['co_host_id'].toString() == _myUserId.toString();
    final status = (_roomState?['status'] ?? 'waiting').toString().toLowerCase();
    final isPlaying = status == 'playing';
    final isPrivate = (_roomState?['rules'] as Map?)?['private'] == true || _roomState?['is_locked'] == true;
    final players = (_roomState?['players'] as List?) ?? [];
    final canSave = isPlaying && players.length > 1;

    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF2D2D2D),
      builder: (ctx) => Container(
        padding: const EdgeInsets.symmetric(vertical: 12),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // 1. Start or Stop Game
            if (isPlaying)
              ListTile(
                leading: const Icon(Icons.stop, color: Colors.orangeAccent),
                title: Text(tr('إيقاف اللعبة'), style: const TextStyle(color: Colors.white)),
                enabled: isHost || isCoHost,
                onTap: () {
                  Navigator.of(ctx).pop();
                  WebSocketService.instance.sendJson({'type': 'room_action', 'action': 'stop_game'});
                },
              )
            else
              ListTile(
                leading: const Icon(Icons.play_arrow, color: Colors.greenAccent),
                title: Text(tr('بدء اللعبة'), style: const TextStyle(color: Colors.white)),
                enabled: (isHost || isCoHost) && status == 'waiting',
                onTap: () {
                  Navigator.of(ctx).pop();
                  WebSocketService.instance.sendJson({'type': 'room_action', 'action': 'start_game'});
                },
              ),

            // 2. Players list
            ListTile(
              leading: const Icon(Icons.group, color: Colors.white),
              title: Text(tr('قائمة اللاعبين'), style: const TextStyle(color: Colors.white)),
              onTap: () {
                Navigator.of(ctx).pop();
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => TablePlayersDialog(
                      roomState: _roomState,
                      myUserId: _myUserId,
                      isHost: isHost,
                      isCoHost: isCoHost,
                    ),
                  ),
                );
              },
            ),

            // 3. Spectator mode toggle
            ListTile(
              leading: const Icon(Icons.visibility, color: Colors.lightBlueAccent),
              title: Text(tr('وضع المتفرج'), style: const TextStyle(color: Colors.white)),
              onTap: () {
                Navigator.of(ctx).pop();
                WebSocketService.instance.sendJson({'type': 'room_action', 'action': 'toggle_spectator'});
              },
            ),

            // 4. Save table
            ListTile(
              leading: const Icon(Icons.save, color: Colors.white),
              title: Text(tr('حفظ الطاولة'), style: const TextStyle(color: Colors.white)),
              enabled: canSave,
              onTap: () {
                Navigator.of(ctx).pop();
                WebSocketService.instance.sendJson({'type': 'room_action', 'action': 'save_table'});
              },
            ),

            // 5. Toggle privacy
            ListTile(
              leading: Icon(isPrivate ? Icons.lock_open : Icons.lock, color: Colors.white),
              title: Text(isPrivate ? tr('اجعل الطاولة عامة') : tr('اجعل الطاولة خاصة'),
                  style: const TextStyle(color: Colors.white)),
              enabled: isHost,
              onTap: () {
                Navigator.of(ctx).pop();
                WebSocketService.instance.sendJson({'type': 'room_action', 'action': 'toggle_privacy'});
              },
            ),

            const Divider(color: Colors.white24),

            // 6. Add / Remove Bot
            ListTile(
              leading: const Icon(Icons.smart_toy, color: Colors.tealAccent),
              title: Text(tr('إضافة بوت'), style: const TextStyle(color: Colors.white)),
              enabled: isHost && status == 'waiting',
              onTap: () {
                Navigator.of(ctx).pop();
                WebSocketService.instance.sendJson({'type': 'room_action', 'action': 'add_bot'});
              },
            ),
            ListTile(
              leading: const Icon(Icons.no_sim, color: Colors.teal),
              title: Text(tr('إزالة بوت'), style: const TextStyle(color: Colors.white)),
              enabled: isHost && status == 'waiting',
              onTap: () {
                Navigator.of(ctx).pop();
                WebSocketService.instance.sendJson({'type': 'room_action', 'action': 'remove_bot'});
              },
            ),

            const Divider(color: Colors.white24),

            // 7. Leave table
            ListTile(
              leading: const Icon(Icons.exit_to_app, color: Colors.redAccent),
              title: Text(tr('مغادرة الطاولة'), style: const TextStyle(color: Colors.redAccent)),
              onTap: () {
                Navigator.of(ctx).pop();
                WebSocketService.instance.sendJson({'type': 'room_action', 'action': 'leave_room'});
                Navigator.of(context).pop();
              },
            ),
          ],
        ),
      ),
    );
  }

  void _showActivityLogDrawer() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: const Color(0xFF1E1E1E),
      builder: (ctx) => SizedBox(
        height: MediaQuery.of(context).size.height * 0.75,
        child: ActivityLogWidget(
          events: _activityEvents,
        ),
      ),
    );
  }

  /// Exact scoreboard formatter matching Windows:
  /// e.g. "محمد 0  أحمد 0" together on one single horizontal row.
  Widget _buildHorizontalScoreboard() {
    final Map<String, dynamic> scores = Map<String, dynamic>.from(_gameState?['scores'] ?? _roomState?['scores'] ?? {});
    final players = (_roomState?['players'] as List?) ?? [];

    List<Widget> scoreWidgets = [];

    if (scores.isNotEmpty) {
      scores.forEach((key, val) {
        String playerName = key;
        for (final p in players) {
          if (p is Map && (p['id']?.toString() == key || p['user_id']?.toString() == key)) {
            playerName = p['display_name'] ?? p['name'] ?? p['username'] ?? key;
            break;
          }
        }
        scoreWidgets.add(
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 6.0),
            child: Text(
              '$playerName $val',
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.bold,
                fontSize: 14,
              ),
            ),
          ),
        );
      });
    } else if (players.isNotEmpty) {
      for (final p in players) {
        final name = p is Map ? (p['display_name'] ?? p['name'] ?? p['username'] ?? 'لاعب') : p.toString();
        scoreWidgets.add(
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 6.0),
            child: Text(
              '$name 0',
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.bold,
                fontSize: 14,
              ),
            ),
          ),
        );
      }
    } else {
      scoreWidgets.add(
        Text(
          tr('لا توجد نقاط بعد'),
          style: const TextStyle(color: Colors.white54, fontSize: 13),
        ),
      );
    }

    return Expanded(
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: scoreWidgets,
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
    final gameType = (_roomState?['game_type'] ?? widget.gameType ?? '').toString().toUpperCase();
    final isTennis = gameType == 'TENNIS';
    final isUnoOrDomino = gameType == 'UNO' || gameType.contains('DOMINO');

    return TableGestureDetector(
      isTennis: isTennis,
      isUnoOrDomino: isUnoOrDomino,
      onOpenLog: _showActivityLogDrawer,
      onQueryTable: () {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(tr('استعلام عن كروت وأوراق الطاولة'))),
        );
      },
      onTableInfo: () {
        final playersCount = (_roomState?['players'] as List?)?.length ?? 0;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(tr('عدد اللاعبين الحاليين: {count}', {'count': playersCount}))),
        );
      },
      onSpaceKey: () {
        WebSocketService.instance.sendJson({'type': 'game_action', 'action': 'draw'});
      },
      child: Scaffold(
        backgroundColor: const Color(0xFF1E1E1E),
        appBar: AppBar(
          title: Text(_roomState?['name'] ?? tr('طاولة اللعب')),
          backgroundColor: const Color(0xFF2D2D2D),
          actions: [
            IconButton(
              tooltip: tr('سجل الأحداث'),
              icon: const Icon(Icons.history),
              onPressed: _showActivityLogDrawer,
            ),
          ],
        ),
        body: Column(
          children: [
            // STRICT TOP BAR: Scoreboard with player names on the EXACT same row right next to "خيارات إضافية" (More Options)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              color: const Color(0xFF252526),
              child: Row(
                children: [
                  // Scores right here horizontally
                  _buildHorizontalScoreboard(),
                  const SizedBox(width: 8),
                  // "خيارات إضافية" button opening the 100% full context menu
                  ElevatedButton.icon(
                    onPressed: _showRoomContextMenu,
                    icon: const Icon(Icons.more_horiz, size: 18),
                    label: Text(tr('خيارات إضافية')),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF3E3E42),
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    ),
                  ),
                ],
              ),
            ),

            // Gameplay Central Area (No standalone start button, no fake controls)
            Expanded(
              child: _buildGameWidget(gameType),
            ),

            // Bottom Chat Bar
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 4.0),
              decoration: const BoxDecoration(
                color: Color(0xFF252526),
                border: Border(top: BorderSide(color: Color(0xFF3E3E42))),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _chatController,
                      style: const TextStyle(color: Colors.white),
                      decoration: InputDecoration(
                        hintText: tr('الدردشة...'),
                        hintStyle: const TextStyle(color: Colors.white38),
                        border: InputBorder.none,
                        contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                      ),
                      onSubmitted: (_) => _sendChat(),
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.send, color: Colors.blueAccent),
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
              const Icon(Icons.casino, size: 64, color: Colors.white54),
              const SizedBox(height: 16),
              Text(
                tr('في انتظار بدء اللعبة...'),
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white70),
              ),
            ],
          ),
        );
    }
  }
}
