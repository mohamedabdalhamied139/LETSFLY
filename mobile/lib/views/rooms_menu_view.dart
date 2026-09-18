import 'package:flutter/material.dart';
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
  // modes: 'main', 'games', 'cards_games', 'dice_games', 'domino_games', 'memory_games', 'sports_games'
  String _mode = 'main';

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
    final categoryMap = {
      'cards_games': 'games',
      'dice_games': 'games',
      'domino_games': 'games',
      'memory_games': 'games',
      'sports_games': 'games',
    };
    if (categoryMap.containsKey(_mode)) {
      setState(() => _mode = 'games');
      return false; // handled internally
    } else if (_mode == 'games') {
      setState(() => _mode = 'main');
      return false;
    }
    return true; // pop screen back to HomeView
  }

  void _onItemTapped(String tag) async {
    if (tag == 'create') {
      setState(() => _mode = 'games');
    } else if (tag == 'join') {
      Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => const JoinRoomsView()),
      );
    } else if (tag == 'saved_tables') {
      Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => const SavedTablesView()),
      );
    } else if (tag == 'category_cards') {
      setState(() => _mode = 'cards_games');
    } else if (tag == 'category_dice') {
      setState(() => _mode = 'dice_games');
    } else if (tag == 'category_domino') {
      setState(() => _mode = 'domino_games');
    } else if (tag == 'category_memory') {
      setState(() => _mode = 'memory_games');
    } else if (tag == 'category_sports') {
      setState(() => _mode = 'sports_games');
    } else {
      // Game creation: tag is Game ID
      await _createRoomForGame(tag);
    }
  }

  Future<void> _createRoomForGame(String gameType) async {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const Center(child: CircularProgressIndicator()),
    );
    try {
      final res = await ApiService.instance.createRoom(
        name: 'طاولة $gameType',
        gameType: gameType,
        maxPlayers: 4,
      );
      if (mounted) {
        Navigator.of(context).pop(); // dismiss loading
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
        Navigator.of(context).pop(); // dismiss loading
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('${tr('خطأ في إنشاء الطاولة')}: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final items = _getItems();
    return WillPopScope(
      onWillPop: () async => _handleBack(),
      child: ResponsiveShell(
        title: _getTitle(),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          tooltip: tr('رجوع'),
          onPressed: () {
            if (_handleBack()) {
              Navigator.of(context).pop();
            }
          },
        ),
        child: ListView.separated(
          padding: const EdgeInsets.symmetric(vertical: 8),
          itemCount: items.length,
          separatorBuilder: (_, __) => const Divider(height: 1, color: AppColors.divider),
          itemBuilder: (context, idx) {
            final item = items[idx];
            return ListTile(
              tileColor: AppColors.card,
              title: Text(
                item['label']!,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 17,
                  fontWeight: FontWeight.w600,
                ),
              ),
              trailing: const Icon(Icons.arrow_forward_ios, size: 14, color: Colors.white54),
              onTap: () => _onItemTapped(item['tag']!),
            );
          },
        ),
      ),
    );
  }
}
