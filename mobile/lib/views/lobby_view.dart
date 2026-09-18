import 'package:flutter/material.dart';
import '../core/localization.dart';
import '../models/room_models.dart';
import '../services/api_service.dart';
import 'friends_view.dart';
import 'table_view.dart';

class LobbyView extends StatefulWidget {
  const LobbyView({super.key});

  @override
  State<LobbyView> createState() => _LobbyViewState();
}

class _LobbyViewState extends State<LobbyView> {
  List<RoomSummary> _rooms = [];
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _fetchRooms();
  }

  Future<void> _fetchRooms() async {
    setState(() => _isLoading = true);
    try {
      final res = await ApiService.instance.getRooms();
      if (res is List) {
        setState(() {
          _rooms = res.map((item) => RoomSummary.fromJson(item)).toList();
        });
      }
    } catch (_) {
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _showCreateRoomDialog() {
    final nameController = TextEditingController();
    final passwordController = TextEditingController();
    String selectedGame = 'UNO';
    int maxPlayers = 4;

    final gameOptions = [
      {'id': 'UNO', 'title': 'أونو'},
      {'id': 'DOMINO', 'title': 'دومينو'},
      {'id': 'AMERICAN_DOMINO', 'title': 'دومينو أمريكي'},
      {'id': 'FARKLE', 'title': 'فاركل'},
      {'id': 'SNAKES_LADDERS', 'title': 'السلم والثعبان'},
      {'id': 'THIEF_HUNT', 'title': 'صيد اللص'},
      {'id': 'SCOPA', 'title': 'إسكوبا'},
      {'id': 'TENNIS', 'title': 'تنس'},
      {'id': 'NINETY_NINE', 'title': 'تسعة وتسعون'},
    ];

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: Text(tr('إنشاء طاولة جديدة')),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: nameController,
                  decoration: InputDecoration(
                    labelText: tr('اسم الطاولة'),
                    border: const OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: selectedGame,
                  decoration: InputDecoration(
                    labelText: tr('نوع اللعبة'),
                    border: const OutlineInputBorder(),
                  ),
                  items: gameOptions
                      .map((g) => DropdownMenuItem(
                            value: g['id'],
                            child: Text(tr(g['title']!)),
                          ))
                      .toList(),
                  onChanged: (val) {
                    if (val != null) {
                      setDialogState(() {
                        selectedGame = val;
                        if (val == 'TENNIS') maxPlayers = 2;
                      });
                    }
                  },
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: passwordController,
                  obscureText: true,
                  decoration: InputDecoration(
                    labelText: tr('كلمة المرور (اختياري)'),
                    border: const OutlineInputBorder(),
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(),
              child: Text(tr('إلغاء')),
            ),
            ElevatedButton(
              onPressed: () async {
                final name = nameController.text.trim();
                if (name.isEmpty) return;
                Navigator.of(ctx).pop();
                try {
                  final res = await ApiService.instance.createRoom(
                    name: name,
                    gameType: selectedGame,
                    maxPlayers: maxPlayers,
                    password: passwordController.text.trim().isNotEmpty
                        ? passwordController.text.trim()
                        : null,
                  );
                  final roomId = res['room']?['id']?.toString() ?? res['id']?.toString();
                  if (roomId != null && mounted) {
                    _joinRoom(roomId);
                  }
                } catch (_) {}
              },
              child: Text(tr('إنشاء')),
            ),
          ],
        ),
      ),
    );
  }

  void _joinRoom(String roomId, [bool isPasswordProtected = false]) async {
    if (isPasswordProtected) {
      final passController = TextEditingController();
      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text(tr('طاولة محمية بكلمة مرور')),
          content: TextField(
            controller: passController,
            obscureText: true,
            decoration: InputDecoration(
              labelText: tr('كلمة المرور'),
              border: const OutlineInputBorder(),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(),
              child: Text(tr('إلغاء')),
            ),
            ElevatedButton(
              onPressed: () {
                Navigator.of(ctx).pop();
                _enterRoom(roomId, passController.text.trim());
              },
              child: Text(tr('دخول')),
            ),
          ],
        ),
      );
    } else {
      _enterRoom(roomId, null);
    }
  }

  void _enterRoom(String roomId, String? password) async {
    try {
      await ApiService.instance.joinRoom(roomId, password: password);
      if (mounted) {
        Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => TableView(roomId: roomId)),
        );
      }
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(tr('لوبي الطاولات')),
        actions: [
          IconButton(
            tooltip: tr('الأصدقاء'),
            icon: const Icon(Icons.people),
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const FriendsView()),
              );
            },
          ),
          IconButton(
            tooltip: tr('تحديث الطاولات'),
            icon: const Icon(Icons.refresh),
            onPressed: _fetchRooms,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _rooms.isEmpty
              ? Center(
                  child: Text(
                    tr('لا توجد طاولات حالياً. اضغط إنشاء لبدء طاولة جديدة!'),
                    style: const TextStyle(fontSize: 16),
                  ),
                )
              : ListView.builder(
                  itemCount: _rooms.length,
                  itemBuilder: (context, index) {
                    final room = _rooms[index];
                    final roomDescription =
                        '${room.name}، لعبة ${room.gameType}، المضيف ${room.hostName}، ${room.currentPlayers} من ${room.maxPlayers} لاعبين' +
                            (room.hasPassword ? '، محمية بكلمة مرور' : '');

                    return Semantics(
                      button: true,
                      label: roomDescription,
                      hint: tr('انقر مرتين لدخول هذه الطاولة'),
                      child: Card(
                        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                        child: ListTile(
                          leading: Icon(
                            room.hasPassword ? Icons.lock : Icons.table_bar,
                            color: Theme.of(context).colorScheme.primary,
                          ),
                          title: Text(room.name, style: const TextStyle(fontWeight: FontWeight.bold)),
                          subtitle: Text(
                            '${room.gameType} | ${room.hostName} (${room.currentPlayers}/${room.maxPlayers})',
                          ),
                          trailing: const Icon(Icons.arrow_forward_ios, size: 16),
                          onTap: () => _joinRoom(room.id, room.hasPassword),
                        ),
                      ),
                    );
                  },
                ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showCreateRoomDialog,
        icon: const Icon(Icons.add),
        label: Text(tr('إنشاء طاولة')),
      ),
    );
  }
}
