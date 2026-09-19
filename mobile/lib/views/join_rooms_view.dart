import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import '../core/app_theme.dart';
import '../core/localization.dart';
import '../core/sound_service.dart';
import '../core/accessibility_manager.dart';
import '../services/api_service.dart';
import '../services/auth_storage_service.dart';
import 'responsive_shell.dart';
import 'table_view.dart';

class JoinRoomsView extends StatefulWidget {
  const JoinRoomsView({super.key});

  @override
  State<JoinRoomsView> createState() => _JoinRoomsViewState();
}

class _JoinRoomsViewState extends State<JoinRoomsView> {
  List<Map<String, dynamic>> _rooms = [];
  bool _loading = true;
  bool _joining = false;

  @override
  void initState() {
    super.initState();
    _fetchRooms();
  }

  Future<void> _fetchRooms() async {
    setState(() => _loading = true);
    try {
      final res = await ApiService.instance.getRooms();
      List<Map<String, dynamic>> parsed = [];
      if (res is List) {
        parsed = res.map((e) => Map<String, dynamic>.from(e as Map)).toList();
      } else if (res is Map && res['rooms'] is List) {
        parsed = (res['rooms'] as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
      }
      if (mounted) {
        setState(() {
          _rooms = parsed;
          _loading = false;
        });
        AccessibilityManager.instance.announce(tr('قائمة الطاولات المتاحة.'));
      }
    } catch (e) {
      if (mounted) {
        setState(() => _loading = false);
        AccessibilityManager.instance.announce(tr('تعذر تحميل الطاولات'));
      }
    }
  }

  String _formatRoomLine(Map<String, dynamic> r) {
    final gameRaw = r['game_label']?.toString() ?? r['game']?.toString() ?? tr('لعبة');
    final host = r['host_name']?.toString() ?? tr('مجهول');
    final players = r['players'] is List ? (r['players'] as List) : [];
    final count = players.length;
    final rawStatus = r['status'] == 'playing' ? tr('جارية') : tr('في الانتظار');
    return '$gameRaw — $host — $count/10 ${tr('لاعبين')} — $rawStatus';
  }

  Future<void> _joinRoom(Map<String, dynamic> room) async {
    if (_joining) return;
    setState(() => _joining = true);
    final roomId = room['id']?.toString() ?? '';

    try {
      final res = await ApiService.instance.joinRoom(roomId, asSpectator: false);
      final roomData = res.containsKey('room') && res['room'] is Map
          ? Map<String, dynamic>.from(res['room'] as Map)
          : room;

      await SoundService.instance.playSound('TABLE_JOIN');
      final activeUser = await AuthStorageService.instance.getActiveUser();
      final myName = activeUser?.displayName.isNotEmpty == true
          ? activeUser!.displayName
          : 'محمد';
      AccessibilityManager.instance.announce(
        tr('{name} انضم للطاولة', {'name': myName}),
      );

      if (mounted) {
        Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => TableView(room: roomData)),
        );
      }
    } catch (e) {
      await SoundService.instance.playSound('INVALID_ACTION');
      String errorMsg = tr('تعذر الانضمام للطاولة');
      if (e is DioException && e.response?.data is Map && (e.response!.data as Map).containsKey('detail')) {
        errorMsg = (e.response!.data as Map)['detail']?.toString() ?? errorMsg;
      }
      AccessibilityManager.instance.announce(errorMsg);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(errorMsg),
            backgroundColor: AppColors.error,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _joining = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return ResponsiveShell(
      title: tr('الطاولات المتاحة حاليًا'),
      child: _loading
          ? const Center(child: CircularProgressIndicator(color: AppColors.primary))
          : RefreshIndicator(
              onRefresh: _fetchRooms,
              color: AppColors.primary,
              child: _rooms.isEmpty
                  ? ListView(
                      physics: const AlwaysScrollableScrollPhysics(),
                      children: [
                        SizedBox(
                          height: MediaQuery.of(context).size.height * 0.5,
                          child: Center(
                            child: Text(
                              tr('لا توجد طاولات متاحة حاليًا.'),
                              style: const TextStyle(
                                fontSize: 18,
                                color: AppColors.textSecondary,
                              ),
                            ),
                          ),
                        ),
                      ],
                    )
                  : ListView.separated(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      itemCount: _rooms.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 10),
                      itemBuilder: (ctx, idx) {
                        final room = _rooms[idx];
                        final lineText = _formatRoomLine(room);

                        return Semantics(
                          button: true,
                          excludeSemantics: true,
                          label: lineText,
                          child: Card(
                            color: AppColors.surface,
                            elevation: 2,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(10),
                              side: const BorderSide(color: AppColors.divider, width: 1),
                            ),
                            child: InkWell(
                              onTap: _joining ? null : () => _joinRoom(room),
                              borderRadius: BorderRadius.circular(10),
                              child: Padding(
                                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
                                child: Row(
                                  children: [
                                    Expanded(
                                      child: Text(
                                        lineText,
                                        style: const TextStyle(
                                          fontSize: 16,
                                          fontWeight: FontWeight.w500,
                                          color: AppColors.textPrimary,
                                        ),
                                      ),
                                    ),
                                    const SizedBox(width: 8),
                                    const Icon(
                                      Icons.arrow_forward_ios,
                                      size: 16,
                                      color: AppColors.textSecondary,
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        );
                      },
                    ),
            ),
    );
  }
}
