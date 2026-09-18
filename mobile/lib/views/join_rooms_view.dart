import 'package:flutter/material.dart';
import '../core/localization.dart';
import '../services/api_service.dart';
import 'table_view.dart';

class JoinRoomsView extends StatefulWidget {
  const JoinRoomsView({super.key});

  @override
  State<JoinRoomsView> createState() => _JoinRoomsViewState();
}

class _JoinRoomsViewState extends State<JoinRoomsView> {
  bool _isLoading = true;
  List<dynamic> _rooms = [];
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadRooms();
  }

  Future<void> _loadRooms() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final res = await ApiService.instance.getRooms();
      if (mounted) {
        setState(() {
          _rooms = (res is List) ? res : (res['rooms'] ?? []);
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = e.toString().replaceFirst('Exception: ', '');
          _isLoading = false;
        });
      }
    }
  }

  void _joinRoom(Map<String, dynamic> room) {
    final roomId = room['id']?.toString() ?? '';
    final gameType = room['game_type'] ?? room['game'] ?? 'GAME';
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => TableView(
          roomId: roomId,
          gameType: gameType,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(tr('الطاولات المتاحة حاليًا')),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: tr('تحديث'),
            onPressed: _loadRooms,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _errorMessage != null
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(_errorMessage!, style: const TextStyle(color: Colors.redAccent)),
                      const SizedBox(height: 12),
                      ElevatedButton(
                        onPressed: _loadRooms,
                        child: Text(tr('إعادة المحاولة')),
                      ),
                    ],
                  ),
                )
              : _rooms.isEmpty
                  ? Center(
                      child: Text(
                        tr('لا توجد طاولات متاحة حاليًا.'),
                        style: const TextStyle(fontSize: 16, color: Colors.grey),
                      ),
                    )
                  : ListView.separated(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      itemCount: _rooms.length,
                      separatorBuilder: (_, __) => const Divider(height: 1),
                      itemBuilder: (context, idx) {
                        final r = _rooms[idx] as Map<String, dynamic>;
                        final host = r['host_name'] ?? tr('مجهول');
                        final players = (r['players'] as List?)?.length ?? 1;
                        final status = r['status'] == 'playing' ? tr('جارية') : tr('في الانتظار');
                        final gameLabel = r['game_label'] ?? r['game_type'] ?? r['game'] ?? tr('لعبة');

                        // Matching Windows exact format: "{game_raw} — {host} — {count}/10 لاعبين — {raw_status}"
                        final titleText = '$gameLabel — $host — $players/10 لاعبين — $status';

                        return ListTile(
                          title: Text(
                            titleText,
                            style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 16),
                          ),
                          subtitle: Text('رقم الطاولة: ${r['id']}'),
                          trailing: ElevatedButton(
                            onPressed: () => _joinRoom(r),
                            child: Text(tr('انضمام')),
                          ),
                          onTap: () => _joinRoom(r),
                        );
                      },
                    ),
    );
  }
}
