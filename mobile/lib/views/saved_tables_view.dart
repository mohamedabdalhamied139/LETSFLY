import 'dart:math';
import 'package:flutter/material.dart';
import '../core/app_theme.dart';
import '../core/localization.dart';
import '../core/sound_service.dart';
import '../services/api_service.dart';
import 'responsive_shell.dart';
import 'table_view.dart';

class SavedTablesView extends StatefulWidget {
  const SavedTablesView({super.key});

  @override
  State<SavedTablesView> createState() => _SavedTablesViewState();
}

class _SavedTablesViewState extends State<SavedTablesView> {
  bool _isLoading = true;
  List<Map<String, dynamic>> _tables = [];
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadSavedTables();
  }

  Future<void> _loadSavedTables() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final res = await ApiService.instance.getSavedTables();
      if (mounted) {
        final List<dynamic> list = (res is List)
            ? res
            : ((res is Map && res['saved_tables'] is List)
                ? res['saved_tables']
                : []);
        setState(() {
          _tables = list.map((e) => Map<String, dynamic>.from(e as Map)).toList();
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

  static String formatDatetime(String isoStr) {
    if (isoStr.isEmpty) return '';
    try {
      final cleanStr = isoStr.endsWith('Z') ? isoStr.replaceAll('Z', '') : isoStr;
      final dt = DateTime.parse(cleanStr);
      final year = dt.year.toString().padLeft(4, '0');
      final month = dt.month.toString().padLeft(2, '0');
      final day = dt.day.toString().padLeft(2, '0');
      final hour = dt.hour.toString().padLeft(2, '0');
      final minute = dt.minute.toString().padLeft(2, '0');
      return '$year-$month-$day $hour:$minute';
    } catch (_) {
      final sub = isoStr.substring(0, min(16, isoStr.length));
      return sub.replaceAll('T', ' ');
    }
  }

  static String gameLabel(String game) {
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
    return tr(gameMap[game] ?? game);
  }

  static String formatRowText(Map<String, dynamic> t) {
    final gname = gameLabel(t['game']?.toString() ?? '');
    final opponents = t['opponents_summary'] ?? t['opponents'] ?? tr('لا يوجد');
    final savedTime = formatDatetime(t['saved_at']?.toString() ?? '');
    final expiresTime = formatDatetime(t['expires_at']?.toString() ?? '');

    return '$gname — ${tr('ضد')}: $opponents — ${tr('تاريخ الحفظ')}: $savedTime — ${tr('تنتهي في')}: $expiresTime';
  }

  Future<void> _restoreTable(int savedId, String game) async {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const Center(child: CircularProgressIndicator()),
    );

    try {
      final res = await ApiService.instance.restoreSavedTable(savedId);
      if (mounted) {
        Navigator.of(context).pop(); // dismiss loading
        SoundService.instance.playSound('TABLE_JOIN');
        final roomId = res['room_id'] ?? res['id'] ?? res['room']?['id'];
        if (roomId != null) {
          Navigator.of(context).pushReplacement(
            MaterialPageRoute(
              builder: (_) => TableView(
                roomId: roomId.toString(),
                gameType: game,
              ),
            ),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        Navigator.of(context).pop(); // dismiss loading
        SoundService.instance.playSound('INVALID_ACTION');
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('${tr('خطأ في استعادة الطاولة')}: $e')),
        );
      }
    }
  }

  Future<void> _confirmDeleteTable(int savedId) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: Text(tr('تأكيد الحذف'), style: const TextStyle(color: Colors.white)),
        content: Text(
          tr('هل أنت متأكد من حذف هذه الطاولة المحفوظة؟'),
          style: const TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(tr('إلغاء'), style: const TextStyle(color: Colors.white70)),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: Text(tr('حذف'), style: const TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      try {
        await ApiService.instance.deleteSavedTable(savedId);
        SoundService.instance.playSound('ACTION_CLICK');
        setState(() {
          _tables.removeWhere((t) => t['id'] == savedId);
        });
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(tr('تم حذف الطاولة المحفوظة بنجاح.'))),
          );
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('${tr('فشل الحذف')}: $e')),
          );
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return ResponsiveShell(
      title: tr('الطاولات المحفوظة'),
      actions: [
        IconButton(
          icon: const Icon(Icons.refresh),
          tooltip: tr('تحديث'),
          onPressed: _loadSavedTables,
        ),
      ],
      child: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _errorMessage != null
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(_errorMessage!, style: const TextStyle(color: Colors.redAccent)),
                      const SizedBox(height: 12),
                      ElevatedButton(
                        onPressed: _loadSavedTables,
                        child: Text(tr('إعادة المحاولة')),
                      ),
                    ],
                  ),
                )
              : _tables.isEmpty
                  ? Center(
                      child: Text(
                        tr('لا توجد طاولات محفوظة.'),
                        style: const TextStyle(fontSize: 16, color: Colors.grey),
                      ),
                    )
                  : ListView.separated(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      itemCount: _tables.length,
                      separatorBuilder: (_, __) => const Divider(height: 1, color: AppColors.divider),
                      itemBuilder: (context, idx) {
                        final t = _tables[idx];
                        final savedId = int.tryParse(t['id']?.toString() ?? '0') ?? 0;
                        final game = t['game']?.toString() ?? 'GAME';
                        final rowText = formatRowText(t);

                        return Semantics(
                          label: rowText,
                          customSemanticsActions: {
                            CustomSemanticsAction(label: tr('استعادة')): () => _restoreTable(savedId, game),
                            CustomSemanticsAction(label: tr('حذف')): () => _confirmDeleteTable(savedId),
                          },
                          child: ListTile(
                            tileColor: AppColors.card,
                            title: Text(
                              rowText,
                              style: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.w500,
                                fontSize: 15,
                              ),
                            ),
                            trailing: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                ElevatedButton(
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: AppColors.accent,
                                    foregroundColor: Colors.white,
                                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                                  ),
                                  onPressed: () => _restoreTable(savedId, game),
                                  child: Text(tr('استعادة')),
                                ),
                                const SizedBox(width: 6),
                                IconButton(
                                  icon: const Icon(Icons.delete_outline, color: Colors.redAccent),
                                  tooltip: tr('حذف'),
                                  onPressed: () => _confirmDeleteTable(savedId),
                                ),
                              ],
                            ),
                            onTap: () => _restoreTable(savedId, game),
                          ),
                        );
                      },
                    ),
    );
  }
}
