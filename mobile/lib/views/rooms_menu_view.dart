import 'package:flutter/material.dart';
import '../core/app_theme.dart';
import '../core/localization.dart';
import '../core/sound_service.dart';
import '../core/accessibility_manager.dart';
import '../services/api_service.dart';
import '../services/auth_storage_service.dart';
import 'responsive_shell.dart';
import 'join_rooms_view.dart';
import 'saved_tables_view.dart';
import 'table_view.dart';

class RoomsMenuView extends StatefulWidget {
  const RoomsMenuView({super.key});

  @override
  State<RoomsMenuView> createState() => _RoomsMenuViewState();
}

class _RoomsMenuViewState extends State<RoomsMenuView> {
  // Modes: 'main', 'games', 'cards_games', 'dice_games', 'domino_games', 'memory_games', 'sports_games'
  String _mode = 'main';
  bool _creating = false;

  String _getTitle() {
    switch (_mode) {
      case 'cards_games':
        return tr('ألعاب الكروت');
      case 'dice_games':
        return tr('ألعاب النرد');
      case 'domino_games':
        return tr('ألعاب الدومينو');
      case 'memory_games':
        return tr('ألعاب الذاكرة والتركيز');
      case 'sports_games':
        return tr('ألعاب رياضية');
      case 'games':
        return tr('تصنيفات الألعاب لإنشاء الطاولة');
      default:
        return tr('الطاولات');
    }
  }

  List<Map<String, String>> _getItems() {
    switch (_mode) {
      case 'cards_games':
        return [
          {'label': tr('أونو'), 'tag': 'create_uno', 'game': 'UNO'},
          {'label': tr('إسكوبا'), 'tag': 'create_scopa', 'game': 'SCOPA'},
          {'label': tr('تسعة وتسعون'), 'tag': 'create_ninety_nine', 'game': 'NINETY_NINE'},
        ];
      case 'dice_games':
        return [
          {'label': tr('فاركل'), 'tag': 'create_farkle', 'game': 'FARKLE'},
          {'label': tr('السلم والثعبان'), 'tag': 'create_snakes_ladders', 'game': 'SNAKES_LADDERS'},
        ];
      case 'domino_games':
        return [
          {'label': tr('دومينو كلاسيك'), 'tag': 'create_domino', 'game': 'DOMINO'},
          {'label': tr('دومينو أمريكاني'), 'tag': 'create_american_domino', 'game': 'AMERICAN_DOMINO'},
        ];
      case 'memory_games':
        return [
          {'label': tr('مطاردة اللص'), 'tag': 'create_thief_hunt', 'game': 'THIEF_HUNT'},
        ];
      case 'sports_games':
        return [
          {'label': tr('التنس'), 'tag': 'create_tennis', 'game': 'TENNIS'},
        ];
      case 'games':
        return [
          {'label': tr('ألعاب الكروت'), 'tag': 'category_cards'},
          {'label': tr('ألعاب النرد'), 'tag': 'category_dice'},
          {'label': tr('ألعاب الدومينو'), 'tag': 'category_domino'},
          {'label': tr('ألعاب الذاكرة'), 'tag': 'category_memory'},
          {'label': tr('ألعاب الرياضة'), 'tag': 'category_sports'},
        ];
      default:
        return [
          {'label': tr('إنشاء'), 'tag': 'create'},
          {'label': tr('انضمام'), 'tag': 'join'},
          {'label': tr('الطاولات المحفوظة'), 'tag': 'saved_tables'},
        ];
    }
  }

  bool _handleBack() {
    final subCategories = [
      'cards_games',
      'dice_games',
      'domino_games',
      'memory_games',
      'sports_games'
    ];
    if (subCategories.contains(_mode)) {
      setState(() => _mode = 'games');
      AccessibilityManager.instance.announce(tr('تصنيفات الألعاب لإنشاء الطاولة'));
      return false; // Don't pop route
    } else if (_mode == 'games') {
      setState(() => _mode = 'main');
      AccessibilityManager.instance.announce(tr('الطاولات'));
      return false; // Don't pop route
    }
    return true; // Pop route back to home
  }

  void _onItemTapped(Map<String, String> item) {
    final tag = item['tag'] ?? '';
    if (tag == 'create') {
      setState(() => _mode = 'games');
      AccessibilityManager.instance.announce(tr('نوع اللعبة.'));
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
      AccessibilityManager.instance.announce(tr('ألعاب الكروت'));
    } else if (tag == 'category_dice') {
      setState(() => _mode = 'dice_games');
      AccessibilityManager.instance.announce(tr('ألعاب النرد'));
    } else if (tag == 'category_domino') {
      setState(() => _mode = 'domino_games');
      AccessibilityManager.instance.announce(tr('ألعاب الدومينو'));
    } else if (tag == 'category_memory') {
      setState(() => _mode = 'memory_games');
      AccessibilityManager.instance.announce(tr('ألعاب الذاكرة والذكاء'));
    } else if (tag == 'category_sports') {
      setState(() => _mode = 'sports_games');
      AccessibilityManager.instance.announce(tr('ألعاب الرياضة'));
    } else if (item.containsKey('game')) {
      _createNewRoom(item['game']!);
    }
  }

  Future<void> _createNewRoom(String game) async {
    if (_creating) return;
    setState(() => _creating = true);

    try {
      final res = await ApiService.instance.createRoom(game: game);
      final roomData = res is Map<String, dynamic> ? res : Map<String, dynamic>.from(res as Map);

      await SoundService.instance.playSound('TABLE_JOIN');
      final activeUser = await AuthStorageService.instance.getActiveUser();
      final myName = activeUser?.displayName.isNotEmpty == true
          ? activeUser!.displayName
          : (roomData['host_name'] ?? 'محمد');
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
      AccessibilityManager.instance.announce(tr('تعذر إنشاء الطاولة: {error}', {'error': e.toString()}));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(tr('تعذر إنشاء الطاولة')),
            backgroundColor: AppColors.error,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _creating = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final items = _getItems();

    return PopScope(
      canPop: _mode == 'main',
      onPopInvoked: (didPop) {
        if (!didPop) {
          _handleBack();
        }
      },
      child: ResponsiveShell(
        title: _getTitle(),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () {
            if (_handleBack()) {
              Navigator.of(context).pop();
            }
          },
        ),
        child: _creating
            ? const Center(
                child: CircularProgressIndicator(color: AppColors.primary),
              )
            : ListView.separated(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                itemCount: items.length,
                separatorBuilder: (_, __) => const SizedBox(height: 10),
                itemBuilder: (ctx, idx) {
                  final item = items[idx];
                  return Semantics(
                    button: true,
                    label: item['label'],
                    child: Card(
                      color: AppColors.surface,
                      elevation: 2,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10),
                        side: const BorderSide(color: AppColors.divider, width: 1),
                      ),
                      child: InkWell(
                        onTap: () => _onItemTapped(item),
                        borderRadius: BorderRadius.circular(10),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
                          child: Row(
                            children: [
                              Expanded(
                                child: Text(
                                  item['label'] ?? '',
                                  style: const TextStyle(
                                    fontSize: 18,
                                    fontWeight: FontWeight.w600,
                                    color: AppColors.textPrimary,
                                  ),
                                ),
                              ),
                              const Icon(
                                Icons.arrow_forward_ios,
                                size: 18,
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
