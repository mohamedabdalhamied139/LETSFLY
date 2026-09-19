import 'package:flutter/material.dart';
import '../core/app_theme.dart';
import '../core/localization.dart';
import '../core/sound_service.dart';
import '../core/accessibility_manager.dart';
import '../services/api_service.dart';
import 'responsive_shell.dart';

class TableView extends StatefulWidget {
  final Map<String, dynamic> room;

  const TableView({super.key, required this.room});

  @override
  State<TableView> createState() => _TableViewState();
}

class _TableViewState extends State<TableView> {
  late Map<String, dynamic> _room;
  bool _leaving = false;

  @override
  void initState() {
    super.initState();
    _room = widget.room;
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

  Future<void> _leaveRoom() async {
    if (_leaving) return;
    setState(() => _leaving = true);
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
    final players = _room['players'] is List ? (_room['players'] as List) : [];
    final status = _room['status'] == 'playing' ? tr('جارية') : tr('في الانتظار');

    return ResponsiveShell(
      title: tr('طاولة {game}', {'game': _getGameTitle()}),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Card(
              color: AppColors.surface,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _getGameTitle(),
                      style: const TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                        color: AppColors.primary,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      tr('المضيف: {name}', {'name': hostName}),
                      style: const TextStyle(fontSize: 16, color: AppColors.textPrimary),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      tr('الحالة: {status}', {'status': status}),
                      style: const TextStyle(fontSize: 16, color: AppColors.textSecondary),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      tr('عدد اللاعبين: {count}', {'count': '${players.length}'}),
                      style: const TextStyle(fontSize: 16, color: AppColors.textSecondary),
                    ),
                    if (roomId.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        tr('معرف الطاولة: {id}', {'id': roomId}),
                        style: const TextStyle(fontSize: 13, color: AppColors.textMuted),
                      ),
                    ],
                  ],
                ),
              ),
            ),
            const Spacer(),
            ElevatedButton.icon(
              onPressed: _leaving ? null : _leaveRoom,
              icon: const Icon(Icons.exit_to_app, color: Colors.white),
              label: Text(
                _leaving ? tr('جاري المغادرة...') : tr('مغادرة الطاولة'),
                style: const TextStyle(fontSize: 18, color: Colors.white),
              ),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.error,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
