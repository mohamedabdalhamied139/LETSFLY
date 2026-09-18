import 'dart:async';
import 'package:flutter/material.dart';
import '../core/app_theme.dart';
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
import '../core/sound_service.dart';

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
  final GlobalKey<TennisGameViewState> _tennisKey = GlobalKey();

  int _myUserId = 0;
  Timer? _pollTimer;

  @override
  void initState() {
    super.initState();
    _connectWebSocket();
    _fetchMyUserId();
    _pollGameState();
    _pollTimer = Timer.periodic(const Duration(milliseconds: 1500), (_) => _pollGameState());
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

  Future<void> _pollGameState() async {
    if (!mounted) return;
    try {
      final res = await ApiService.instance.getGameState(widget.roomId);
      if (res is Map && mounted) {
        setState(() {
          if (res['room'] is Map) {
            _roomState = res['room'] as Map<String, dynamic>;
          }
          if (res['game_state'] is Map) {
            _gameState = res['game_state'] as Map<String, dynamic>;
          } else if (res['state'] is Map) {
            _gameState = res['state'] as Map<String, dynamic>;
          }
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
        _pollGameState();
      } else if (type == 'player_left' || type == 'bot_removed') {
        SoundService.instance.playSound('TABLE_LEAVE');
        _pollGameState();
      } else if (type == 'game_stopped') {
        SoundService.instance.playSound('GAME_STOPPED');
        _pollGameState();
      } else if (type == 'round_finished' || type == 'round_end') {
        SoundService.instance.playSound('ROUND_END');
        _pollGameState();
      } else if (type == 'match_finished') {
        final won = data['winner_id']?.toString() == _myUserId.toString();
        SoundService.instance.playSound(won ? 'MATCH_WIN' : 'MATCH_LOSS');
        _pollGameState();
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

  Future<void> _startGame() async {
    try {
      await ApiService.instance.startGame(widget.roomId);
      await _pollGameState();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    }
  }

  Future<void> _stopGame() async {
    try {
      await ApiService.instance.stopGame(widget.roomId);
      await _pollGameState();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    }
  }

  Future<void> _addBot() async {
    try {
      await ApiService.instance.addBot(widget.roomId);
      await _pollGameState();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    }
  }

  Future<void> _removeBot() async {
    try {
      await ApiService.instance.removeBot(widget.roomId);
      await _pollGameState();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    }
  }

  Future<void> _saveTable() async {
    try {
      await ApiService.instance.saveTable(widget.roomId);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(tr('تم حفظ الطاولة بنجاح'))));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    }
  }

  Future<void> _togglePrivacy() async {
    try {
      await ApiService.instance.togglePrivacy(widget.roomId);
      await _pollGameState();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    }
  }

  Future<void> _toggleSpectator() async {
    try {
      await ApiService.instance.toggleSpectator(widget.roomId);
      await _pollGameState();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    }
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
                  _stopGame();
                },
              )
            else
              ListTile(
                leading: const Icon(Icons.play_arrow, color: Colors.greenAccent),
                title: Text(tr('بدء اللعبة'), style: const TextStyle(color: Colors.white)),
                enabled: (isHost || isCoHost) && status == 'waiting',
                onTap: () {
                  Navigator.of(ctx).pop();
                  _startGame();
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
                _toggleSpectator();
              },
            ),

            // 4. Save table
            ListTile(
              leading: const Icon(Icons.save, color: Colors.white),
              title: Text(tr('حفظ الطاولة'), style: const TextStyle(color: Colors.white)),
              enabled: canSave,
              onTap: () {
                Navigator.of(ctx).pop();
                _saveTable();
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
                _togglePrivacy();
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
                _addBot();
              },
            ),
            ListTile(
              leading: const Icon(Icons.no_sim, color: Colors.teal),
              title: Text(tr('إزالة بوت'), style: const TextStyle(color: Colors.white)),
              enabled: isHost && status == 'waiting',
              onTap: () {
                Navigator.of(ctx).pop();
                _removeBot();
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

  void _handleSpaceKey(String gameType) {
    final g = gameType.toUpperCase();
    if (g == 'TENNIS') {
      _tennisKey.currentState?.hitOrServe();
    } else if (g == 'FARKLE' || g == 'SNAKES_LADDERS') {
      final reqId = 'req_${DateTime.now().millisecondsSinceEpoch}';
      WebSocketService.instance.sendJson({
        'type': 'game_action',
        'request_id': reqId,
        'payload': {'action': 'roll'},
      });
      ApiService.instance.sendGameAction(widget.roomId, {'action': 'roll'});
    } else {
      // UNO, DOMINO, AMERICAN_DOMINO, NINETY_NINE
      final reqId = 'req_${DateTime.now().millisecondsSinceEpoch}';
      WebSocketService.instance.sendJson({
        'type': 'game_action',
        'request_id': reqId,
        'payload': {'action': 'draw'},
      });
      ApiService.instance.sendGameAction(widget.roomId, {'action': 'draw'});
    }
  }

  void _announceTableQuery(String gameType) {
    final g = gameType.toUpperCase();
    String queryText = '';

    if (g == 'UNO') {
      final top = _gameState?['top_card'];
      final col = _gameState?['current_color'] ?? '';
      queryText = '${tr('الكرت الحالي')}: ${top != null ? top.toString() : tr('لا يوجد')} ${col.isNotEmpty ? '($col)' : ''}';
    } else if (g == 'DOMINO' || g == 'AMERICAN_DOMINO') {
      final l = _gameState?['left_end'] ?? '-';
      final r = _gameState?['right_end'] ?? '-';
      queryText = '${tr('أطراف الدومينو')}: ${tr('يسار')} $l | ${tr('يمين')} $r';
    } else if (g == 'FARKLE') {
      final dice = (_gameState?['dice'] as List?)?.join('، ') ?? '';
      final tScore = _gameState?['turn_score'] ?? 0;
      queryText = '${tr('النرد الحالي')}: $dice | ${tr('نقاط الدور')}: $tScore';
    } else if (g == 'SNAKES_LADDERS') {
      final pos = _gameState?['my_position'] ?? _gameState?['position'] ?? 1;
      queryText = '${tr('موقعك')}: $pos / 100';
    } else if (g == 'NINETY_NINE') {
      final total = _gameState?['pile_value'] ?? _gameState?['total'] ?? 0;
      queryText = '${tr('مجموع الطاولة')}: $total / 99';
    } else if (g == 'SCOPA') {
      final count = (_gameState?['table_cards'] as List?)?.length ?? 0;
      queryText = '${tr('عدد كروت الطاولة')}: $count';
    } else if (g == 'THIEF_HUNT') {
      final phase = _gameState?['phase'] ?? 'waiting';
      queryText = '${tr('حالة اللعبة')}: $phase';
    } else {
      queryText = tr('استعلام عن حالة الطاولة');
    }

    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(queryText)));
  }

  void _announceTableInfo() {
    final name = _roomState?['name'] ?? tr('طاولة اللعب');
    final players = (_roomState?['players'] as List?)?.length ?? 0;
    final spectators = (_roomState?['spectators'] as List?)?.length ?? 0;
    final status = _roomState?['status'] ?? 'waiting';

    final infoText = '$name — $players لاعبين — $spectators متفرجين — الحالة: $status';
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(infoText)));
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
    _pollTimer?.cancel();
    WebSocketService.instance.disconnect();
    _chatController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final gameType = (_roomState?['game_type'] ?? widget.gameType ?? '').toString().toUpperCase();
    final isTennis = gameType == 'TENNIS';
    final isUnoOrDomino = gameType == 'UNO' || gameType.contains('DOMINO') || gameType == 'FARKLE' || gameType == 'SNAKES_LADDERS';

    return TableGestureDetector(
      isTennis: isTennis,
      isUnoOrDomino: isUnoOrDomino,
      onOpenLog: _showActivityLogDrawer,
      onQueryTable: () => _announceTableQuery(gameType),
      onTableInfo: _announceTableInfo,
      onSpaceKey: () => _handleSpaceKey(gameType),
      onTennisLeft: () => _tennisKey.currentState?.moveLeft(),
      onTennisRight: () => _tennisKey.currentState?.moveRight(),
      onTennisUp: () => _tennisKey.currentState?.hitOrServe(),
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
                  _buildHorizontalScoreboard(),
                  const SizedBox(width: 8),
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

            // Gameplay Central Area
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
    final status = (_roomState?['status'] ?? 'waiting').toString().toLowerCase();
    final isHost = _roomState?['is_host'] == true ||
        (_roomState?['host_id'] != null && _roomState?['host_id'].toString() == _myUserId.toString());

    // If game is in pre-game waiting state, display functional lobby with quick start & add bot buttons
    if (status == 'waiting') {
      final players = (_roomState?['players'] as List?) ?? [];
      final botsCount = players.where((p) => p is Map && (p['is_bot'] == true || (int.tryParse(p['id']?.toString() ?? '0') ?? 0) < 0)).length;

      return Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.meeting_room, size: 56, color: Colors.tealAccent),
              const SizedBox(height: 12),
              Text(
                _roomState?['name'] ?? tr('طاولة اللعب'),
                style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.white),
              ),
              const SizedBox(height: 4),
              Text(
                '${tr('اللعبة')}: ${tr(gameType)}',
                style: const TextStyle(fontSize: 16, color: Colors.amberAccent),
              ),
              const SizedBox(height: 16),

              // Players Count & List
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppColors.divider),
                ),
                child: Column(
                  children: [
                    Text(
                      '${tr('اللاعبون في الطاولة')} (${players.length}):',
                      style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.white70),
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      alignment: WrapAlignment.center,
                      children: players.map((p) {
                        final name = p is Map ? (p['display_name'] ?? p['name'] ?? 'لاعب') : p.toString();
                        final isBot = p is Map && (p['is_bot'] == true || (int.tryParse(p['id']?.toString() ?? '0') ?? 0) < 0);

                        return Chip(
                          backgroundColor: isBot ? Colors.teal.shade900 : AppColors.card,
                          avatar: Icon(isBot ? Icons.smart_toy : Icons.person, size: 18, color: Colors.white),
                          label: Text(name, style: const TextStyle(color: Colors.white)),
                        );
                      }).toList(),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 20),

              // Host controls or waiting indicator
              if (isHost) ...[
                ElevatedButton.icon(
                  onPressed: _startGame,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.green.shade700,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 14),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  icon: const Icon(Icons.play_arrow, size: 24),
                  label: Text(tr('بدء اللعبة الآن'), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                ),
                const SizedBox(height: 10),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    OutlinedButton.icon(
                      onPressed: _addBot,
                      style: OutlinedButton.styleFrom(
                        foregroundColor: Colors.tealAccent,
                        side: const BorderSide(color: Colors.tealAccent),
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                      ),
                      icon: const Icon(Icons.add),
                      label: Text(tr('إضافة بوت')),
                    ),
                    if (botsCount > 0) ...[
                      const SizedBox(width: 12),
                      OutlinedButton.icon(
                        onPressed: _removeBot,
                        style: OutlinedButton.styleFrom(
                          foregroundColor: Colors.redAccent,
                          side: const BorderSide(color: Colors.redAccent),
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                        ),
                        icon: const Icon(Icons.remove),
                        label: Text(tr('إزالة بوت')),
                      ),
                    ],
                  ],
                ),
              ] else ...[
                Text(
                  tr('في انتظار بدء المضيف للعبة...'),
                  style: const TextStyle(color: Colors.white60, fontSize: 16),
                ),
              ],
            ],
          ),
        ),
      );
    }

    switch (gameType.toUpperCase()) {
      case 'UNO':
        return UnoGameView(roomId: widget.roomId, initialState: _gameState);
      case 'DOMINO':
        return DominoGameView(roomId: widget.roomId, initialState: _gameState, isAmerican: false);
      case 'AMERICAN_DOMINO':
        return DominoGameView(roomId: widget.roomId, initialState: _gameState, isAmerican: true);
      case 'FARKLE':
        return FarkleGameView(roomId: widget.roomId, initialState: _gameState);
      case 'TENNIS':
        return TennisGameView(key: _tennisKey, roomId: widget.roomId, initialState: _gameState);
      case 'THIEF_HUNT':
        return ThiefGameView(roomId: widget.roomId, initialState: _gameState);
      case 'SNAKES_LADDERS':
        return SnakesGameView(roomId: widget.roomId, initialState: _gameState);
      case 'SCOPA':
        return ScopaGameView(roomId: widget.roomId, initialState: _gameState);
      case 'NINETY_NINE':
        return NinetyNineGameView(roomId: widget.roomId, initialState: _gameState);
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

