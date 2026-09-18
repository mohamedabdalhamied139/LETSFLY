import 'package:flutter/material.dart';
import '../core/localization.dart';
import '../services/api_service.dart';
import '../services/ws_service.dart';
import '../widgets/gesture_detector.dart';

class TableView extends StatefulWidget {
  final String roomId;

  const TableView({super.key, required this.roomId});

  @override
  State<TableView> createState() => _TableViewState();
}

class _TableViewState extends State<TableView> {
  Map<String, dynamic>? _roomState;
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
            ),
            // Shared Game Play Area Placeholder (for Stage 3 & 4 Adapters)
            Expanded(
              child: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.casino, size: 64, color: Theme.of(context).colorScheme.primary),
                    const SizedBox(height: 16),
                    Text(
                      tr('منطقة اللعب المشتركة جاهزة للاستقبال'),
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    ),
                  ],
                ),
              ),
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
}
