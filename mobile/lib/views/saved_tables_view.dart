import 'package:flutter/material.dart';
import '../core/app_theme.dart';
import '../core/localization.dart';
import '../core/sound_service.dart';
import '../core/accessibility_manager.dart';
import '../services/api_service.dart';
import 'responsive_shell.dart';
import 'table_view.dart';

class SavedTablesView extends StatefulWidget {
  const SavedTablesView({super.key});

  @override
  State<SavedTablesView> createState() => _SavedTablesViewState();
}

class _SavedTablesViewState extends State<SavedTablesView> {
  List<Map<String, dynamic>> _tables = [];
  bool _loading = true;
  bool _actionInProgress = false;

  @override
  void initState() {
    super.initState();
    _fetchSavedTables();
  }

  Future<void> _fetchSavedTables() async {
    setState(() => _loading = true);
    try {
      final res = await ApiService.instance.getSavedTables();
      if (mounted) {
        setState(() {
          _tables = res;
          _loading = false;
        });
        AccessibilityManager.instance.announce(tr('قائمة الطاولات المحفوظة.'));
      }
    } catch (e) {
      if (mounted) {
        setState(() => _loading = false);
        AccessibilityManager.instance.announce(tr('تعذر تحميل الطاولات المحفوظة'));
      }
    }
  }

  String _formatDateTime(dynamic dt) {
    if (dt == null) return '';
    final str = dt.toString();
    if (str.isEmpty) return '';
    try {
      final parsed = DateTime.tryParse(str.replaceAll('Z', '+00:00'));
      if (parsed != null) {
        final year = parsed.year.toString().padLeft(4, '0');
        final month = parsed.month.toString().padLeft(2, '0');
        final day = parsed.day.toString().padLeft(2, '0');
        final hour = parsed.hour.toString().padLeft(2, '0');
        final min = parsed.minute.toString().padLeft(2, '0');
        return '$year-$month-$day $hour:$min';
      }
    } catch (_) {}
    if (str.length >= 16) {
      return str.substring(0, 16).replaceAll('T', ' ');
    }
    return str;
  }

  String _getGameLabel(String? game) {
    const gameMap = {
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
    final key = game?.toUpperCase() ?? '';
    return tr(gameMap[key] ?? game ?? 'طاولة');
  }

  String _formatTableLine(Map<String, dynamic> t) {
    final gname = _getGameLabel(t['game']?.toString());
    final opponents = t['opponents_summary']?.toString() ?? tr('لا يوجد');
    final savedTime = _formatDateTime(t['saved_at']);
    final expiresTime = _formatDateTime(t['expires_at']);

    final againstText = tr('ضد: {0}', {'0': opponents});
    final savedText = tr('تاريخ الحفظ: {0}', {'0': savedTime});
    final expiresText = tr('تنتهي في: {0}', {'0': expiresTime});

    return '$gname — $againstText — $savedText — $expiresText';
  }

  Future<void> _restoreTable(int savedId) async {
    if (_actionInProgress) return;
    setState(() => _actionInProgress = true);

    AccessibilityManager.instance.announce(tr('استعادة الطاولة...'));

    try {
      final res = await ApiService.instance.restoreSavedTable(savedId);
      final roomData = res.containsKey('room') && res['room'] is Map
          ? Map<String, dynamic>.from(res['room'] as Map)
          : res;

      await SoundService.instance.playSound('TABLE_JOIN');
      AccessibilityManager.instance.announce(tr('تم استرجاع الطاولة بنجاح.'));

      if (mounted) {
        Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => TableView(room: roomData)),
        );
      }
    } catch (e) {
      await SoundService.instance.playSound('INVALID_ACTION');
      AccessibilityManager.instance.announce(tr('تعذر استرجاع الطاولة: {error}', {'error': e.toString()}));
    } finally {
      if (mounted) {
        setState(() => _actionInProgress = false);
      }
    }
  }

  Future<void> _deleteTable(int savedId) async {
    if (_actionInProgress) return;
    setState(() => _actionInProgress = true);

    try {
      await ApiService.instance.deleteSavedTable(savedId);
      await SoundService.instance.playSound('ACTION_CLICK');
      AccessibilityManager.instance.announce(tr('تم حذف الطاولة المحفوظة.'));
      await _fetchSavedTables();
    } catch (e) {
      await SoundService.instance.playSound('INVALID_ACTION');
      AccessibilityManager.instance.announce(tr('تعذر حذف الطاولة المحفوظة'));
    } finally {
      if (mounted) {
        setState(() => _actionInProgress = false);
      }
    }
  }

  void _confirmDelete(int savedId) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: Text(
          tr('تأكيد الحذف'),
          style: const TextStyle(color: AppColors.textPrimary),
        ),
        content: Text(
          tr('هل أنت متأكد من حذف هذه الطاولة المحفوظة؟'),
          style: const TextStyle(color: AppColors.textSecondary),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: Text(tr('إلغاء'), style: const TextStyle(color: AppColors.textSecondary)),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.of(ctx).pop();
              _deleteTable(savedId);
            },
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.error),
            child: Text(tr('حذف'), style: const TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return ResponsiveShell(
      title: tr('الطاولات المحفوظة'),
      child: _loading
          ? const Center(child: CircularProgressIndicator(color: AppColors.primary))
          : RefreshIndicator(
              onRefresh: _fetchSavedTables,
              color: AppColors.primary,
              child: _tables.isEmpty
                  ? ListView(
                      physics: const AlwaysScrollableScrollPhysics(),
                      children: [
                        SizedBox(
                          height: MediaQuery.of(context).size.height * 0.5,
                          child: Center(
                            child: Text(
                              tr('لا توجد طاولات محفوظة.'),
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
                      itemCount: _tables.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 10),
                      itemBuilder: (ctx, idx) {
                        final table = _tables[idx];
                        final savedId = table['id'] is int
                            ? table['id'] as int
                            : int.tryParse(table['id']?.toString() ?? '0') ?? 0;
                        final lineText = _formatTableLine(table);

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
                              onTap: _actionInProgress ? null : () => _restoreTable(savedId),
                              borderRadius: BorderRadius.circular(10),
                              child: Padding(
                                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                                child: Row(
                                  children: [
                                    Expanded(
                                      child: Text(
                                        lineText,
                                        style: const TextStyle(
                                          fontSize: 15,
                                          fontWeight: FontWeight.w500,
                                          color: AppColors.textPrimary,
                                        ),
                                      ),
                                    ),
                                    const SizedBox(width: 8),
                                    IconButton(
                                      icon: const Icon(Icons.delete_outline, color: AppColors.error),
                                      tooltip: tr('حذف'),
                                      onPressed: _actionInProgress ? null : () => _confirmDelete(savedId),
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
