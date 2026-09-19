import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import '../core/app_theme.dart';
import '../core/localization.dart';
import '../core/sound_service.dart';
import '../core/accessibility_manager.dart';
import '../games/game_adapter.dart';
import '../games/game_state_engine.dart';
import '../games/dialogs/start_game_dialog.dart';
import '../games/dialogs/table_team_selection_dialog.dart';
import '../services/api_service.dart';
import '../services/auth_storage_service.dart';
import '../services/ws_service.dart';
import '../widgets/two_finger_gesture_detector.dart';
import 'activity_log_widget.dart';
import 'responsive_shell.dart';
import 'table_players_dialog.dart';
import 'game_rules_dialog.dart';

class TableView extends StatefulWidget {
  final Map<String, dynamic> room;

  const TableView({super.key, required this.room});

  @override
  State<TableView> createState() => _TableViewState();
}

class _TableViewState extends State<TableView> {
  late Map<String, dynamic> _room;
  Map<String, dynamic> _gameState = {};
  int _myUserId = 0;
  bool _actionInProgress = false;
  StreamSubscription? _wsSubscription;

  static int? _extractSubFromToken(String? token) {
    if (token == null || token.isEmpty) return null;
    try {
      final parts = token.split('.');
      if (parts.length >= 2) {
        final normalized = base64Url.normalize(parts[1]);
        final payload = utf8.decode(base64Url.decode(normalized));
        final map = json.decode(payload);
        if (map is Map && map.containsKey('sub')) {
          return int.tryParse(map['sub'].toString());
        }
      }
    } catch (_) {}
    return null;
  }

  @override
  void initState() {
    super.initState();
    _room = Map<String, dynamic>.from(widget.room);
    final token = ApiService.instance.token;
    final tokenUid = _extractSubFromToken(token);
    if (tokenUid != null && tokenUid != 0) {
      _myUserId = tokenUid;
    }
    _initUser();
    _fetchRoomDetails();

    // Connect WebSocket to this room's real-time events & gameplay stream
    final roomId = _room['id']?.toString() ?? _room['room_id']?.toString() ?? '';
    if (roomId.isNotEmpty) {
      WebSocketService.instance.connect(
        ApiService.instance.getWsUrl('/ws/room/$roomId'),
        token: ApiService.instance.token,
      );
    }

    _listenToWsEvents();
    if (_isPlaying) {
      _fetchGameState();
    }
  }

  Future<void> _fetchRoomDetails() async {
    final roomId = _room['id']?.toString() ?? _room['room_id']?.toString() ?? '';
    if (roomId.isEmpty) return;
    try {
      final res = await ApiService.instance.getRoom(roomId);
      if (res is Map<String, dynamic> && mounted) {
        setState(() {
          _room = res;
        });
      }
    } catch (_) {}
  }

  @override
  void dispose() {
    _wsSubscription?.cancel();
    // Reconnect WebSocket to lobby events
    final token = ApiService.instance.token;
    if (token != null && token.isNotEmpty) {
      WebSocketService.instance.connect(
        ApiService.instance.getWsUrl('/ws/events'),
        token: token,
      );
    }
    super.dispose();
  }

  Future<void> _initUser() async {
    final user = await AuthStorageService.instance.getActiveUser();
    if (user != null && user.id != 0 && mounted) {
      setState(() => _myUserId = user.id);
    }
  }

  void _listenToWsEvents() {
    _wsSubscription = WebSocketService.instance.events.listen((event) {
      if (!mounted) return;
      final type = event['type']?.toString();
      final roomId = _room['id']?.toString() ?? _room['room_id']?.toString() ?? '';
      final eventRoomId = event['room_id']?.toString();

      // Only handle events for this room or relevant table lifecycle events
      if (eventRoomId != null && eventRoomId != roomId) return;

      if (type == 'player_joined' || type == 'bot_added') {
        final name = event['name']?.toString() ?? tr('لاعب');
        final uid = event['user_id'];
        if (uid != null && uid.toString() != _myUserId.toString()) {
          SoundService.instance.playSound('TABLE_JOIN');
          AccessibilityManager.instance.announce(tr('{name} انضم للطاولة', {'name': name}));
        }
        setState(() {
          if (uid != null) {
            final intUid = int.tryParse(uid.toString()) ?? 0;
            final currentPlayers = List<dynamic>.from(_room['players'] ?? []);
            final toAdd = intUid != 0 ? intUid : uid;
            if (!currentPlayers.contains(intUid) && !currentPlayers.contains(uid)) {
              currentPlayers.add(toAdd);
              _room['players'] = currentPlayers;
            }
            final pdict = Map<String, dynamic>.from(_room['players_dict'] ?? {});
            pdict[uid.toString()] = name;
            _room['players_dict'] = pdict;

            final pnames = List<dynamic>.from(_room['player_names'] ?? []);
            if (!pnames.contains(name)) {
              pnames.add(name);
              _room['player_names'] = pnames;
            }
          }
          if (event['players'] is List) {
            _room['players'] = event['players'];
          }
          if (event['player_names'] is List) {
            _room['player_names'] = event['player_names'];
          }
          if (event['players_dict'] is Map) {
            _room['players_dict'] = event['players_dict'];
          }
        });
        _fetchRoomDetails();
      } else if (type == 'player_left' || type == 'bot_removed') {
        final name = event['name']?.toString() ?? tr('لاعب');
        final uid = event['user_id'];
        if (uid != null && uid.toString() != _myUserId.toString()) {
          SoundService.instance.playSound('TABLE_LEAVE');
          AccessibilityManager.instance.announce(tr('{name} غادر الطاولة', {'name': name}));
        }
        setState(() {
          if (uid != null) {
            final intUid = int.tryParse(uid.toString()) ?? 0;
            final currentPlayers = List<dynamic>.from(_room['players'] ?? []);
            currentPlayers.remove(intUid);
            currentPlayers.remove(uid);
            _room['players'] = currentPlayers;

            final pnames = List<dynamic>.from(_room['player_names'] ?? []);
            pnames.remove(name);
            _room['player_names'] = pnames;
          }
          if (event['players'] is List) {
            _room['players'] = event['players'];
          }
          if (event['player_names'] is List) {
            _room['player_names'] = event['player_names'];
          }
          if (event['players_dict'] is Map) {
            _room['players_dict'] = event['players_dict'];
          }
        });
        _fetchRoomDetails();
      } else if (type == 'room_updated') {
        _fetchRoomDetails();
      } else if (type == 'player_kicked' || type == 'player_banned') {
        final name = event['name']?.toString() ?? tr('لاعب');
        final uid = event['user_id'];
        if (uid != null && uid.toString() == _myUserId.toString()) {
          final msg = (type == 'player_banned')
              ? tr('تم حظرك من الطاولة بواسطة القائد.')
              : tr('تم طردك من الطاولة بواسطة القائد.');
          AccessibilityManager.instance.announce(msg);
          Navigator.of(context).pop();
        } else {
          final msg = (type == 'player_banned')
              ? tr('تم حظر {name} من الطاولة.', {'name': name})
              : tr('تم طرد {name} من الطاولة بواسطة القائد.', {'name': name});
          AccessibilityManager.instance.announce(msg);
          _fetchRoomDetails();
        }
      } else if (type == 'game_started') {
        setState(() => _room['status'] = 'playing');
        SoundService.instance.playSound('ROUND_START');
        AccessibilityManager.instance.announce(tr('بدأت اللعبة.'));
        _fetchGameState();
      } else if (type == 'game_stopped') {
        setState(() {
          _room['status'] = 'waiting';
          _gameState = {'active': false};
        });
        final gameType = _room['game']?.toString().toUpperCase() ?? 'UNO';
        GameStateEngine.instance.resetGameRuntimeState(gameType);
        SoundService.instance.playSound('GAME_STOPPED');
        AccessibilityManager.instance.announce(tr('توقفت اللعبة.'));
      } else if (type == 'captain_changed') {
        final newHostId = event['host_id'];
        final newHostName = event['host_name'];
        setState(() {
          if (newHostId != null) _room['host_id'] = newHostId;
          if (newHostName != null) _room['host_name'] = newHostName;
        });
      } else if (type == 'co_captain_changed') {
        setState(() => _room['co_host_id'] = event['co_host_id']);
      } else if (type == 'player_connection_lost') {
        final name = event['name']?.toString() ?? tr('لاعب');
        final uid = event['user_id'];
        if (uid != null && uid.toString() != _myUserId.toString()) {
          SoundService.instance.playSound('CONNECTION_LOST');
          AccessibilityManager.instance.announce(tr('{name} فقد الاتصال', {'name': name}));
        }
      } else if (type == 'player_reconnected') {
        final name = event['name']?.toString() ?? tr('لاعب');
        final uid = event['user_id'];
        if (uid != null && uid.toString() != _myUserId.toString()) {
          SoundService.instance.playSound('CONNECTED');
          AccessibilityManager.instance.announce(tr('{name} أعاد الاتصال مجددا', {'name': name}));
        }
      } else if ([
        'uno_state_changed',
        'game_state_changed',
        'ninety_nine_state_changed',
        'thief_state_changed',
        'farkle_state_changed',
        'domino_state_changed',
        'american_domino_state_changed',
        'snakes_state_changed',
        'scopa_state_changed'
      ].contains(type)) {
        final state = event['state'];
        if (state is Map<String, dynamic>) {
          _processGameState(state);
        } else if (state is Map) {
          _processGameState(Map<String, dynamic>.from(state));
        } else {
          _fetchGameState();
        }
      }
    });
  }

  Future<void> _fetchGameState() async {
    final roomId = _room['id']?.toString() ?? _room['room_id']?.toString() ?? '';
    if (roomId.isEmpty) return;
    try {
      final res = await ApiService.instance.getGameState(roomId);
      if (res is Map<String, dynamic> && mounted) {
        _processGameState(res);
      } else if (res is Map && mounted) {
        _processGameState(Map<String, dynamic>.from(res));
      }
    } catch (_) {}
  }

  void _processGameState(Map<String, dynamic> state) {
    final gameType = _room['game']?.toString().toUpperCase() ?? 'UNO';
    final roomId = _room['id']?.toString() ?? _room['room_id']?.toString() ?? '';
    state['room_id'] = roomId;

    GameStateEngine.instance.processCommonState(
      gameType: gameType,
      state: state,
      roomId: roomId,
      myUserId: _myUserId,
      onStateProcessed: (isPlaying, isRoundFinished) {
        if (mounted) {
          setState(() {
            _gameState = state;
            _room['status'] = isPlaying ? 'playing' : 'waiting';
          });
        }
      },
    );
  }

  // Directional 2-finger gesture handlers replacing keyboard shortcuts
  void _onSwipeLeftTopAnnouncement() {
    final gameType = _room['game']?.toString().toUpperCase() ?? 'UNO';
    final adapter = GameAdapterRegistry.instance.get(gameType);
    if (adapter != null) {
      adapter.announceTop(context, _gameState);
    } else {
      _defaultAnnounceTop(gameType, _gameState);
    }
  }

  void _onSwipeUpTurnAnnouncement() {
    final gameType = _room['game']?.toString().toUpperCase() ?? 'UNO';
    final adapter = GameAdapterRegistry.instance.get(gameType);
    if (adapter != null) {
      adapter.announceTurn(context, _gameState);
    } else {
      _defaultAnnounceTurn(_gameState);
    }
  }

  void _onSwipeDownSpaceAction() {
    final gameType = _room['game']?.toString().toUpperCase() ?? 'UNO';
    final roomId = _room['id']?.toString() ?? _room['room_id']?.toString() ?? '';
    final adapter = GameAdapterRegistry.instance.get(gameType);
    if (adapter != null) {
      adapter.onSpaceAction(context, _gameState, roomId);
    } else {
      _defaultSpaceAction(gameType, _gameState, roomId);
    }
  }

  void _defaultAnnounceTurn(Map<String, dynamic> state) {
    if (state['active'] != true && !_isPlaying) {
      AccessibilityManager.instance.announce(tr('المباراة لم تبدأ بعد.'));
      return;
    }
    final name = (state['current_player_name'] ?? state['current_turn_name'] ?? '').toString();
    if (name.isNotEmpty) {
      AccessibilityManager.instance.announce(tr('دور {name}', {'name': name}));
    } else {
      AccessibilityManager.instance.announce(tr('غير محدد'));
    }
  }

  void _defaultAnnounceTop(String gameType, Map<String, dynamic> state) {
    if (state['active'] != true && !_isPlaying) {
      AccessibilityManager.instance.announce(tr('المباراة لم تبدأ بعد.'));
      return;
    }
    if (gameType == 'NINETY_NINE') {
      final pile = state['pile_value'] ?? 0;
      AccessibilityManager.instance.announce(tr('المجموع {pile}', {'pile': pile.toString()}));
    } else if (gameType == 'SCOPA') {
      final tableCards = state['table_cards'];
      if (tableCards is List && tableCards.isNotEmpty) {
        final names = tableCards.map((c) => c.toString()).join('، ');
        AccessibilityManager.instance.announce(names);
      } else {
        AccessibilityManager.instance.announce(tr('الطاولة فارغة.'));
      }
    } else if (gameType == 'UNO') {
      final top = state['top_card'];
      if (top != null) {
        AccessibilityManager.instance.announce(top.toString());
      } else {
        AccessibilityManager.instance.announce(tr('لا توجد ورقة مكشوفة.'));
      }
    } else if (gameType == 'FARKLE') {
      final roll = state['last_roll'] ?? state['dice'];
      if (roll is List && roll.isNotEmpty) {
        AccessibilityManager.instance.announce(roll.join('، '));
      } else {
        AccessibilityManager.instance.announce(tr('لا توجد رمية سابقة.'));
      }
    } else if (gameType == 'SNAKES_LADDERS') {
      final roll = state['last_roll'] ?? 0;
      if (roll > 0) {
        AccessibilityManager.instance.announce(tr('آخر نرد: {roll}', {'roll': roll.toString()}));
      } else {
        AccessibilityManager.instance.announce(tr('لا توجد رمية سابقة.'));
      }
    } else {
      AccessibilityManager.instance.announce(tr('لا توجد معلومات حالة متاحة.'));
    }
  }

  void _defaultSpaceAction(String gameType, Map<String, dynamic> state, String roomId) {
    if (state['active'] != true && !_isPlaying) {
      return;
    }
    if (gameType == 'UNO') {
      ApiService.instance.sendGameAction(roomId, {'action': 'draw'});
    } else if (gameType == 'DOMINO' || gameType == 'AMERICAN_DOMINO') {
      if (state['can_draw'] == true) {
        ApiService.instance.sendGameAction(roomId, {'action': 'draw'});
      } else if (state['can_pass'] == true) {
        ApiService.instance.sendGameAction(roomId, {'action': 'pass'});
      }
    }
  }

  String _getGameTitle() {
    final game = _room['game']?.toString().toUpperCase() ?? 'UNO';
    final map = {
      'UNO': 'أونو',
      'SCOPA': 'إسكوبا',
      'NINETY_NINE': 'تسعة وتسعون',
      'FARKLE': 'فاركل',
      'SNAKES_LADDERS': 'السلم والثعبان',
      'DOMINO': 'دومينو كلاسيك',
      'AMERICAN_DOMINO': 'دومينو أمريكاني',
      'THIEF_HUNT': 'مطاردة اللص',
      'TENNIS': 'التنس',
    };
    return tr(map[game] ?? _room['game_label'] ?? game);
  }

  bool get _isHost {
    if (_room['is_host'] == true || _room['role'] == 'captain') return true;
    final hostId = int.tryParse(_room['host_id']?.toString() ?? '0') ?? 0;
    if (_myUserId != 0 && hostId != 0 && _myUserId == hostId) return true;
    return false;
  }

  bool get _isCoHost {
    if (_room['is_co_host'] == true || _room['role'] == 'co_host') return true;
    final coHostId = int.tryParse(_room['co_host_id']?.toString() ?? '0') ?? 0;
    if (_myUserId != 0 && coHostId != 0 && _myUserId == coHostId) return true;
    return false;
  }

  bool get _isPlaying => _room['status'] == 'playing';

  void _showRoomOptionsMenu() {
    final isHost = _isHost;
    final isCoHost = _isCoHost;
    final isPlaying = _isPlaying;
    final players = List<dynamic>.from(_room['players'] ?? []);
    final rules = Map<String, dynamic>.from(_room['rules'] ?? {});
    final isPrivate = rules['private'] == true;

    showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => SafeArea(
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 14),
                child: Text(
                  tr('قائمة خيارات الطاولة'),
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: AppColors.textPrimary,
                  ),
                ),
              ),
              const Divider(color: AppColors.divider, height: 1),

              // 1. Start Game / Stop Game
              if (isPlaying)
                ListTile(
                  leading: const Icon(Icons.stop, color: AppColors.error),
                  title: Text(tr('إيقاف اللعبة'), style: const TextStyle(color: AppColors.textPrimary)),
                  onTap: () {
                    Navigator.of(ctx).pop();
                    if (!isHost && !isCoHost) {
                      AccessibilityManager.instance.announce(tr('إيقاف اللعبة متاح للقائد أو نائب القائد فقط.'));
                      return;
                    }
                    _stopGame();
                  },
                )
              else
                ListTile(
                  leading: const Icon(Icons.play_arrow, color: AppColors.success),
                  title: Text(tr('بدء اللعبة'), style: const TextStyle(color: AppColors.textPrimary)),
                  onTap: () {
                    Navigator.of(ctx).pop();
                    _startGame();
                  },
                ),

              // 2. Players List
              ListTile(
                leading: const Icon(Icons.people, color: AppColors.primary),
                title: Text(tr('قائمة اللاعبين'), style: const TextStyle(color: AppColors.textPrimary)),
                onTap: () {
                  Navigator.of(ctx).pop();
                  _openPlayersDialog();
                },
              ),

              // 3. Spectator Mode
              ListTile(
                leading: const Icon(Icons.visibility, color: AppColors.textSecondary),
                title: Text(tr('وضع المتفرج'), style: const TextStyle(color: AppColors.textPrimary)),
                onTap: () {
                  Navigator.of(ctx).pop();
                  _toggleSpectator();
                },
              ),

              // 4. Game Rules (قواعد اللعب)
              ListTile(
                leading: const Icon(Icons.menu_book, color: AppColors.primary),
                title: Text(tr('قواعد اللعب'), style: const TextStyle(color: AppColors.textPrimary)),
                onTap: () {
                  Navigator.of(ctx).pop();
                  final gameType = _room['game']?.toString().toUpperCase() ?? 'UNO';
                  GameRulesDialog.show(context, gameType: gameType);
                },
              ),

              // 4. Save Table
              ListTile(
                leading: const Icon(Icons.save, color: AppColors.textSecondary),
                title: Text(tr('حفظ الطاولة'), style: const TextStyle(color: AppColors.textPrimary)),
                onTap: () {
                  Navigator.of(ctx).pop();
                  if (!isPlaying || players.length <= 1) {
                    AccessibilityManager.instance.announce(tr('حفظ الطاولة متاح فقط أثناء اللعب النشط مع لاعبين اثنين على الأقل.'));
                    return;
                  }
                  _saveTable();
                },
              ),

              // 5. Privacy Toggle
              ListTile(
                leading: Icon(isPrivate ? Icons.lock_open : Icons.lock, color: AppColors.textSecondary),
                title: Text(
                  isPrivate ? tr('اجعل الطاولة عامة') : tr('اجعل الطاولة خاصة'),
                  style: const TextStyle(color: AppColors.textPrimary),
                ),
                onTap: () {
                  Navigator.of(ctx).pop();
                  if (!isHost) {
                    AccessibilityManager.instance.announce(tr('تغيير خصوصية الطاولة متاح للقائد فقط.'));
                    return;
                  }
                  _togglePrivacy();
                },
              ),

              // 6. Add Bot
              ListTile(
                leading: const Icon(Icons.smart_toy, color: AppColors.primary),
                title: Text(tr('إضافة بوت'), style: const TextStyle(color: AppColors.textPrimary)),
                onTap: () {
                  Navigator.of(ctx).pop();
                  if (!isHost) {
                    AccessibilityManager.instance.announce(tr('إضافة بوت متاح لمضيف الطاولة فقط.'));
                    return;
                  }
                  if (isPlaying) {
                    AccessibilityManager.instance.announce(tr('لا يمكن إضافة بوت أثناء اللعب.'));
                    return;
                  }
                  _addBot();
                },
              ),

              // 7. Remove Bot
              ListTile(
                leading: const Icon(Icons.remove_circle_outline, color: AppColors.textSecondary),
                title: Text(tr('إزالة بوت'), style: const TextStyle(color: AppColors.textPrimary)),
                onTap: () {
                  Navigator.of(ctx).pop();
                  if (!isHost) {
                    AccessibilityManager.instance.announce(tr('إزالة بوت متاح لمضيف الطاولة فقط.'));
                    return;
                  }
                  if (isPlaying) {
                    AccessibilityManager.instance.announce(tr('لا يمكن إزالة بوت أثناء اللعب.'));
                    return;
                  }
                  _removeBot();
                },
              ),

              const Divider(color: AppColors.divider, height: 1),

              // 8. Leave Table
              ListTile(
                leading: const Icon(Icons.exit_to_app, color: AppColors.error),
                title: Text(tr('مغادرة الطاولة'), style: const TextStyle(color: AppColors.error)),
                onTap: () {
                  Navigator.of(ctx).pop();
                  _confirmLeaveRoom();
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _startGame() async {
    if (!_isHost && !_isCoHost) {
      AccessibilityManager.instance.announce(tr('بدء اللعبة متاح للقائد أو نائب القائد فقط.'));
      return;
    }
    final roomId = _room['id']?.toString() ?? _room['room_id']?.toString() ?? '';
    final gameType = _room['game']?.toString().toUpperCase() ?? 'UNO';
    final players = List<dynamic>.from(_room['players'] ?? []);

    if (players.length < 2) {
      AccessibilityManager.instance.announce(tr('يجب وجود لاعبين اثنين على الأقل لبدء اللعبة. أضف بوتاً للبدء فوراً.'));
      if (mounted) {
        final addBotConfirm = await showDialog<bool>(
          context: context,
          builder: (ctx) => AlertDialog(
            backgroundColor: AppColors.surface,
            title: Text(tr('لاعب واحد في الطاولة'), style: const TextStyle(color: AppColors.textPrimary)),
            content: Text(
              tr('يجب وجود لاعبين اثنين على الأقل لبدء اللعبة. هل تريد إضافة بوت لبدء اللعبة فوراً؟'),
              style: const TextStyle(color: AppColors.textSecondary),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(false),
                child: Text(tr('إلغاء')),
              ),
              ElevatedButton(
                onPressed: () => Navigator.of(ctx).pop(true),
                style: ElevatedButton.styleFrom(backgroundColor: AppColors.primary),
                child: Text(tr('إضافة بوت'), style: const TextStyle(color: Colors.white)),
              ),
            ],
          ),
        );
        if (addBotConfirm == true) {
          await _addBot();
        }
      }
      return;
    }

    // Prompt default vs custom settings matching Windows _choose_start_mode
    final startResult = await StartGameDialog.show(
      context,
      gameType: gameType,
      currentRoom: _room,
    );
    if (startResult == null) return; // Cancelled

    final targetScore = startResult.targetScore;
    final rules = Map<String, dynamic>.from(startResult.rules);

    // Scopa team selection: If teams are enabled and 4 or 6 players, host chooses teams
    if (gameType == 'SCOPA' && rules['teams_enabled'] == true && (players.length == 4 || players.length == 6)) {
      final teamMap = await TableTeamSelectionDialog.show(
        context,
        players: players.map((p) {
          if (p is Map) return Map<String, dynamic>.from(p);
          final uid = int.tryParse(p.toString()) ?? 0;
          return {'id': uid, 'name': 'لاعب $uid'};
        }).toList(),
        currentUserId: _myUserId,
      );
      if (teamMap == null) return; // Cancelled
      rules['custom_teams'] = teamMap;
    }

    try {
      await ApiService.instance.startGame(roomId, targetScore: targetScore, rules: rules);
      setState(() => _room['status'] = 'playing');
      await SoundService.instance.playSound('ROUND_START');
      AccessibilityManager.instance.announce(tr('بدأت اللعبة.'));
      _fetchGameState();
    } catch (e) {
      await SoundService.instance.playSound('INVALID_ACTION');
      AccessibilityManager.instance.announce(tr('تعذر بدء اللعبة: {error}', {'error': e.toString()}));
    }
  }

  Future<void> _stopGame() async {
    final roomId = _room['id']?.toString() ?? _room['room_id']?.toString() ?? '';
    try {
      await ApiService.instance.stopGame(roomId);
      setState(() {
        _room['status'] = 'waiting';
        _gameState = {'active': false};
      });
      final gameType = _room['game']?.toString().toUpperCase() ?? 'UNO';
      GameStateEngine.instance.resetGameRuntimeState(gameType);
      await SoundService.instance.playSound('GAME_STOPPED');
      AccessibilityManager.instance.announce(tr('توقفت اللعبة.'));
    } catch (e) {
      await SoundService.instance.playSound('INVALID_ACTION');
      AccessibilityManager.instance.announce(tr('تعذر إيقاف اللعبة: {error}', {'error': e.toString()}));
    }
  }

  void _openPlayersDialog() {
    TablePlayersDialog.show(
      context,
      room: _room,
      myUserId: _myUserId,
      onRoomUpdated: () async {
        await _fetchRoomDetails();
        if (_isPlaying) {
          await _fetchGameState();
        }
      },
    );
  }

  Future<void> _toggleSpectator() async {
    final roomId = _room['id']?.toString() ?? _room['room_id']?.toString() ?? '';
    try {
      final res = await ApiService.instance.toggleSpectator(roomId);
      if (res is Map && res['is_spectator'] != null) {
        final isSpec = res['is_spectator'] == true;
        final msg = isSpec ? tr('أنت الآن في وضع المتفرج.') : tr('أنت الآن في وضع اللعب.');
        AccessibilityManager.instance.announce(msg);
      }
    } catch (e) {
      await SoundService.instance.playSound('INVALID_ACTION');
      AccessibilityManager.instance.announce(tr('تعذر تغيير وضع المتفرج: {error}', {'error': e.toString()}));
    }
  }

  Future<void> _saveTable() async {
    final roomId = _room['id']?.toString() ?? _room['room_id']?.toString() ?? '';
    AccessibilityManager.instance.announce(tr('جاري حفظ الطاولة...'));
    try {
      final res = await ApiService.instance.saveTable(roomId);
      await SoundService.instance.playSound('CONNECTED');
      final msg = res is Map && res['message'] != null
          ? res['message'].toString()
          : tr('تم حفظ الطاولة بنجاح مقابل عملتين.');
      AccessibilityManager.instance.announce(tr(msg));
      _leaveRoomInternal();
    } catch (e) {
      await SoundService.instance.playSound('INVALID_ACTION');
      AccessibilityManager.instance.announce(e.toString());
    }
  }

  Future<void> _togglePrivacy() async {
    final roomId = _room['id']?.toString() ?? _room['room_id']?.toString() ?? '';
    try {
      final res = await ApiService.instance.togglePrivacy(roomId);
      final isPriv = res is Map && res['is_private'] == true;
      setState(() {
        final r = Map<String, dynamic>.from(_room['rules'] ?? {});
        r['private'] = isPriv;
        _room['rules'] = r;
      });
      final msg = isPriv ? tr('تم تغيير الطاولة إلى خاصة.') : tr('تم تغيير الطاولة إلى عامة.');
      AccessibilityManager.instance.announce(msg);
    } catch (e) {
      await SoundService.instance.playSound('INVALID_ACTION');
      AccessibilityManager.instance.announce(tr('تعذر تغيير خصوصية الطاولة: {error}', {'error': e.toString()}));
    }
  }

  Future<void> _addBot() async {
    final roomId = _room['id']?.toString() ?? _room['room_id']?.toString() ?? '';
    try {
      final res = await ApiService.instance.addBot(roomId);
      if (res is Map<String, dynamic> && mounted) {
        setState(() => _room = res);
      }
    } catch (e) {
      await SoundService.instance.playSound('INVALID_ACTION');
      AccessibilityManager.instance.announce(e.toString());
    }
  }

  Future<void> _removeBot() async {
    final players = List<dynamic>.from(_room['players'] ?? []);
    final botIds = players.where((uid) => (int.tryParse(uid.toString()) ?? 0) < 0).toList();
    if (botIds.isEmpty) {
      AccessibilityManager.instance.announce(tr('لا يوجد بوت'));
      return;
    }
    final roomId = _room['id']?.toString() ?? _room['room_id']?.toString() ?? '';
    try {
      final res = await ApiService.instance.removeBot(roomId);
      if (res is Map && res['room'] is Map && mounted) {
        setState(() => _room = Map<String, dynamic>.from(res['room'] as Map));
      }
    } catch (e) {
      await SoundService.instance.playSound('INVALID_ACTION');
      AccessibilityManager.instance.announce(e.toString());
    }
  }

  void _confirmLeaveRoom() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: Text(
          tr('هل تريد الخروج من الطاولة'),
          style: const TextStyle(color: AppColors.textPrimary),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: Text(tr('لا'), style: const TextStyle(color: AppColors.textSecondary)),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.of(ctx).pop();
              _leaveRoomInternal();
            },
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.error),
            child: Text(tr('نعم'), style: const TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  Future<void> _leaveRoomInternal() async {
    if (_actionInProgress) return;
    setState(() => _actionInProgress = true);
    final roomId = _room['id']?.toString() ?? _room['room_id']?.toString() ?? '';
    try {
      if (roomId.isNotEmpty) {
        await ApiService.instance.leaveRoom(roomId);
      }
    } catch (_) {}

    await SoundService.instance.playSound('TABLE_LEAVE');
    AccessibilityManager.instance.announce(tr('تمت مغادرة الطاولة والرجوع لقائمة الطاولات.'));

    if (mounted) {
      Navigator.of(context).pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    final roomId = _room['id']?.toString() ?? _room['room_id']?.toString() ?? '';
    final hostName = _room['host_name']?.toString() ?? tr('مجهول');
    final players = List<dynamic>.from(_room['players'] ?? []);
    final isPlaying = _isPlaying;
    final statusText = isPlaying ? tr('جارية') : tr('في الانتظار');
    final gameType = _room['game']?.toString().toUpperCase() ?? 'UNO';
    final adapter = GameAdapterRegistry.instance.get(gameType);

    return ResponsiveShell(
      title: tr('طاولة {game}', {'game': _getGameTitle()}),
      actions: [
        Semantics(
          label: tr('قائمة خيارات الطاولة'),
          button: true,
          excludeSemantics: true,
          child: IconButton(
            icon: const Icon(Icons.more_vert),
            tooltip: tr('قائمة خيارات الطاولة'),
            onPressed: _showRoomOptionsMenu,
          ),
        ),
      ],
      onTwoFingerSwipeRight: () => ActivityLogWidget.showAsBottomSheet(context),
      onTwoFingerSwipeLeft: _onSwipeLeftTopAnnouncement,
      onTwoFingerSwipeUp: _onSwipeUpTurnAnnouncement,
      onTwoFingerSwipeDown: _onSwipeDownSpaceAction,
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
              // Status Card
              Card(
                color: AppColors.surface,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              _getGameTitle(),
                              style: const TextStyle(
                                fontSize: 22,
                                fontWeight: FontWeight.bold,
                                color: AppColors.primary,
                              ),
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: isPlaying ? AppColors.success.withOpacity(0.2) : Colors.orange.withOpacity(0.2),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text(
                              statusText,
                              style: TextStyle(
                                color: isPlaying ? AppColors.success : Colors.orange,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Text(
                        tr('المضيف: {name}', {'name': hostName}),
                        style: const TextStyle(fontSize: 16, color: AppColors.textPrimary),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        tr('عدد اللاعبين: {count}', {'count': '${players.length}'}),
                        style: const TextStyle(fontSize: 16, color: AppColors.textSecondary),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Waiting Lobby or Active Gameplay Area
              Expanded(
                child: Card(
                  color: AppColors.surface,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  child: Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          isPlaying ? tr('مجريات اللعبة') : tr('قائمة الانتظار'),
                          style: const TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                            color: AppColors.textPrimary,
                          ),
                        ),
                        const Divider(color: AppColors.divider),
                        Expanded(
                          child: isPlaying && adapter != null
                              ? adapter.buildBoard(context, _gameState)
                              : _buildWaitingLobby(context, players),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
    );
  }

  Widget _buildWaitingLobby(BuildContext context, List<dynamic> players) {
    final hostId = int.tryParse(_room['host_id']?.toString() ?? '0') ?? 0;
    final hostName = _room['host_name']?.toString() ?? tr('القائد');
    final coHostId = int.tryParse(_room['co_host_id']?.toString() ?? '0');
    final spectators = List<dynamic>.from(_room['spectators'] ?? []);
    final rawNames = List<dynamic>.from(_room['player_names'] ?? []);
    final playersDict = Map<dynamic, dynamic>.from(_room['players_dict'] ?? {});

    String getPlayerName(int uid) {
      final suid = uid.toString();
      if (playersDict.containsKey(suid) && playersDict[suid] != null && playersDict[suid].toString().isNotEmpty) {
        return playersDict[suid].toString();
      }
      if (rawNames.isNotEmpty) {
        final idx = players.indexOf(uid);
        if (idx >= 0 && idx < rawNames.length && rawNames[idx] != null && rawNames[idx].toString().isNotEmpty) {
          return rawNames[idx].toString();
        }
      }
      if (uid == hostId) return hostName;
      return uid > 0 ? tr('لاعب {0}', {'0': '$uid'}) : 'Bot ${uid.abs()}';
    }

    final List<Map<String, dynamic>> participantItems = [];

    // 1. Host / Captain
    final hostIsSpec = spectators.contains(hostId);
    participantItems.add({
      'id': hostId,
      'name': hostName,
      'role': tr('القائد'),
      'is_host': true,
      'is_co_host': false,
      'is_spectator': hostIsSpec,
      'is_bot': false,
    });

    // 2. Co-Host
    if (coHostId != null && coHostId != 0 && coHostId != hostId && (players.contains(coHostId) || spectators.contains(coHostId))) {
      final coName = getPlayerName(coHostId);
      final coIsSpec = spectators.contains(coHostId);
      participantItems.add({
        'id': coHostId,
        'name': coName,
        'role': tr('نائب القائد'),
        'is_host': false,
        'is_co_host': true,
        'is_spectator': coIsSpec,
        'is_bot': false,
      });
    }

    // 3. Other players
    for (final p in players) {
      final uid = int.tryParse(p.toString()) ?? 0;
      if (uid == hostId || uid == coHostId || uid == 0) continue;
      final isBot = uid < 0;
      final pName = getPlayerName(uid);
      participantItems.add({
        'id': uid,
        'name': pName,
        'role': isBot ? tr('روبوت') : tr('لاعب'),
        'is_host': false,
        'is_co_host': false,
        'is_spectator': false,
        'is_bot': isBot,
      });
    }

    // 4. Spectators (excluding host and co-host)
    for (final s in spectators) {
      final uid = int.tryParse(s.toString()) ?? 0;
      if (uid == hostId || uid == coHostId || uid == 0) continue;
      final sName = getPlayerName(uid);
      participantItems.add({
        'id': uid,
        'name': sName,
        'role': tr('متفرج'),
        'is_host': false,
        'is_co_host': false,
        'is_spectator': true,
        'is_bot': false,
      });
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 4.0),
          child: Text(
            tr('اللاعبون في الطاولة ({count}):', {'count': '${participantItems.length}'}),
            style: const TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.bold,
              color: AppColors.textSecondary,
            ),
          ),
        ),
        Expanded(
          child: ListView.separated(
            padding: const EdgeInsets.symmetric(vertical: 4),
            itemCount: participantItems.length,
            separatorBuilder: (_, __) => const SizedBox(height: 6),
            itemBuilder: (ctx, idx) {
              final item = participantItems[idx];
              final name = item['name'] as String;
              final role = item['role'] as String;
              final isHost = item['is_host'] == true;
              final isCoHost = item['is_co_host'] == true;
              final isBot = item['is_bot'] == true;
              final isSpec = item['is_spectator'] == true;
              final semanticLabel = '$name، $role';

              return Semantics(
                label: semanticLabel,
                button: true,
                excludeSemantics: true,
                child: Card(
                  color: AppColors.surfaceLight,
                  margin: EdgeInsets.zero,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  child: ListTile(
                    contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
                    leading: CircleAvatar(
                      radius: 18,
                      backgroundColor: isHost
                          ? AppColors.primary
                          : isCoHost
                              ? Colors.teal
                              : isBot
                                  ? Colors.grey
                                  : AppColors.surface,
                      child: isBot
                          ? const Icon(Icons.smart_toy, size: 18, color: Colors.white)
                          : Text(
                              name.isNotEmpty ? name[0].toUpperCase() : 'U',
                              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                            ),
                    ),
                    title: Text(
                      name,
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 15,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    trailing: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: isHost
                            ? AppColors.primary.withOpacity(0.2)
                            : isCoHost
                                ? Colors.teal.withOpacity(0.2)
                                : isSpec
                                    ? Colors.purple.withOpacity(0.2)
                                    : AppColors.surface,
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        role,
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: isHost
                              ? AppColors.primary
                              : isCoHost
                                  ? Colors.tealAccent
                                  : isSpec
                                      ? Colors.purpleAccent
                                      : AppColors.textSecondary,
                        ),
                      ),
                    ),
                    onTap: _openPlayersDialog,
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
