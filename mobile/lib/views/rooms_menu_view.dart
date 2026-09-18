import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../core/app_theme.dart';
import '../core/localization.dart';
import '../services/api_service.dart';
import 'join_rooms_view.dart';
import 'saved_tables_view.dart';
import 'table_view.dart';
import 'responsive_shell.dart';

class RoomsMenuView extends StatefulWidget {
  const RoomsMenuView({super.key});

  @override
  State<RoomsMenuView> createState() => _RoomsMenuViewState();
}

class _RoomsMenuViewState extends State<RoomsMenuView> {
  // Modes: 'main' (Level 1), 'games' (Level 2), or specific category mode (Level 3)
  String _mode = 'main';
  String? _focusedTag;

  List<Map<String, String>> _getItems() {
    if (_mode == 'cards_games') {
      return [
        {'label': tr('أونو'), 'tag': 'UNO'},
        {'label': tr('إسكوبا'), 'tag': 'SCOPA'},
        {'label': tr('تسعة وتسعون'), 'tag': 'NINETY_NINE'},
      ];
    } else if (_mode == 'dice_games') {
      return [
        {'label': tr('فاركل'), 'tag': 'FARKLE'},
        {'label': tr('السلم والثعبان'), 'tag': 'SNAKES_LADDERS'},
      ];
    } else if (_mode == 'domino_games') {
      return [
        {'label': tr('دومينو'), 'tag': 'DOMINO'},
        {'label': tr('دومينو أمريكي'), 'tag': 'AMERICAN_DOMINO'},
      ];
    } else if (_mode == 'memory_games') {
      return [
        {'label': tr('صيد اللص'), 'tag': 'THIEF_HUNT'},
      ];
    } else if (_mode == 'sports_games') {
      return [
        {'label': tr('تنس'), 'tag': 'TENNIS'},
      ];
    } else if (_mode == 'games') {
      return [
        {'label': tr('ألعاب الكروت'), 'tag': 'category_cards'},
        {'label': tr('ألعاب النرد'), 'tag': 'category_dice'},
        {'label': tr('ألعاب الدومينو'), 'tag': 'category_domino'},
        {'label': tr('ألعاب الذاكرة'), 'tag': 'category_memory'},
        {'label': tr('ألعاب الرياضة'), 'tag': 'category_sports'},
      ];
    } else {
      // Level 1: Main
      return [
        {'label': tr('إنشاء'), 'tag': 'create'},
        {'label': tr('انضمام'), 'tag': 'join'},
        {'label': tr('الطاولات المحفوظة'), 'tag': 'saved_tables'},
      ];
    }
  }

  String _getTitle() {
    if (_mode == 'cards_games') return tr('ألعاب الورق');
    if (_mode == 'dice_games') return tr('ألعاب النرد');
    if (_mode == 'domino_games') return tr('ألعاب الدومينو');
    if (_mode == 'memory_games') return tr('ألعاب الذاكرة والتركيز');
    if (_mode == 'sports_games') return tr('ألعاب رياضية');
    if (_mode == 'games') return tr('تصنيفات الألعاب لإنشاء الطاولة');
    return tr('الطاولات');
  }

  bool _handleBack() {
    final categoryParentMap = {
      'cards_games': 'category_cards',
      'dice_games': 'category_dice',
      'domino_games': 'category_domino',
      'memory_games': 'category_memory',
      'sports_games': 'category_sports',
    };

    if (categoryParentMap.containsKey(_mode)) {
      setState(() {
        _focusedTag = categoryParentMap[_mode];
        _mode = 'games';
      });
      return false; // Handled internally, back to Level 2
    } else if (_mode == 'games') {
      setState(() {
        _focusedTag = 'create';
        _mode = 'main';
      });
      return false; // Handled internally, back to Level 1
    }
    return true; // Pop screen back to HomeView
  }

  void _onBackPressed() {
    if (_handleBack()) {
      Navigator.of(context).pop();
    }
  }

  void _onItemTapped(String tag) async {
    if (tag == 'create') {
      setState(() {
        _mode = 'games';
        _focusedTag = 'category_cards';
      });
    } else if (tag == 'join') {
      Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => const JoinRoomsView()),
      );
    } else if (tag == 'saved_tables') {
      Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => const SavedTablesView()),
      );
    } else if (tag == 'category_cards') {
      setState(() {
        _mode = 'cards_games';
        _focusedTag = 'UNO';
      });
    } else if (tag == 'category_dice') {
      setState(() {
        _mode = 'dice_games';
        _focusedTag = 'FARKLE';
      });
    } else if (tag == 'category_domino') {
      setState(() {
        _mode = 'domino_games';
        _focusedTag = 'DOMINO';
      });
    } else if (tag == 'category_memory') {
      setState(() {
        _mode = 'memory_games';
        _focusedTag = 'THIEF_HUNT';
      });
    } else if (tag == 'category_sports') {
      setState(() {
        _mode = 'sports_games';
        _focusedTag = 'TENNIS';
      });
    } else {
      // Game creation: tag is Game ID
      await _createRoomForGame(tag);
    }
  }

  Future<void> _createRoomForGame(String gameType) async {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const Center(
        child: CircularProgressIndicator(color: AppColors.accent),
      ),
    );
    try {
      final res = await ApiService.instance.createRoom(
        name: 'طاولة $gameType',
        gameType: gameType,
        maxPlayers: 4,
      );
      if (mounted) {
        Navigator.of(context).pop(); // dismiss loading dialog
        final roomId = res['id'] ?? res['room_id'] ?? res['room']?['id'];
        if (roomId != null) {
          Navigator.of(context).pushReplacement(
            MaterialPageRoute(
              builder: (_) => TableView(
                roomId: roomId.toString(),
                gameType: gameType,
              ),
            ),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        Navigator.of(context).pop(); // dismiss loading dialog
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            backgroundColor: AppColors.surface,
            content: Text(
              '${tr('خطأ في إنشاء الطاولة')}: $e',
              style: const TextStyle(color: AppColors.textPrimary),
            ),
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final items = _getItems();

    return Focus(
      autofocus: true,
      onKeyEvent: (node, event) {
        if (event is KeyDownEvent &&
            event.logicalKey == LogicalKeyboardKey.escape) {
          _onBackPressed();
          return KeyEventResult.handled;
        }
        return KeyEventResult.ignored;
      },
      child: WillPopScope(
        onWillPop: () async => _handleBack(),
        child: ResponsiveShell(
          title: _getTitle(),
          leading: IconButton(
            icon: const Icon(Icons.arrow_back, color: AppColors.textPrimary),
            tooltip: tr('رجوع'),
            onPressed: _onBackPressed,
          ),
          child: ListView.separated(
            padding: const EdgeInsets.symmetric(vertical: 8),
            itemCount: items.length,
            separatorBuilder: (_, __) =>
                const Divider(height: 1, color: AppColors.border),
            itemBuilder: (context, idx) {
              final item = items[idx];
              final isFocused = item['tag'] == _focusedTag;

              return Semantics(
                label: item['label']!,
                button: true,
                child: ListTile(
                  tileColor: AppColors.surface,
                  selectedTileColor: AppColors.accent.withOpacity(0.2),
                  selected: isFocused,
                  title: Text(
                    item['label']!,
                    style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 17,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  trailing: const Icon(
                    Icons.arrow_forward_ios,
                    size: 14,
                    color: AppColors.textSecondary,
                  ),
                  onTap: () => _onItemTapped(item['tag']!),
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}
