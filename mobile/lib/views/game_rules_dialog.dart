import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../core/app_theme.dart';
import '../core/localization.dart';
import '../core/accessibility_manager.dart';

/// Accessible Game Rules Viewer Dialog matching Windows TextHelpViewerDialog.
/// Displays game rules in Arabic, English, and French with instant language switching.
class GameRulesDialog extends StatefulWidget {
  final String gameType;

  const GameRulesDialog({
    super.key,
    required this.gameType,
  });

  static Future<void> show(BuildContext context, {required String gameType}) {
    return showDialog(
      context: context,
      builder: (ctx) => GameRulesDialog(gameType: gameType),
    );
  }

  @override
  State<GameRulesDialog> createState() => _GameRulesDialogState();
}

class _GameRulesDialogState extends State<GameRulesDialog> {
  String _selectedLang = 'ar';
  String _rulesContent = '';
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    // Default to app language if supported, else Arabic
    final currentAppLang = LocalizationService.instance.currentLanguageCode;
    if (['ar', 'en', 'fr'].contains(currentAppLang)) {
      _selectedLang = currentAppLang;
    } else {
      _selectedLang = 'ar';
    }
    _loadRules();
  }

  String _getFilePrefix(String gt) {
    switch (gt.toUpperCase()) {
      case 'UNO':
        return 'uno';
      case 'SNAKES_LADDERS':
        return 'snakes_and_ladders';
      case 'FARKLE':
        return 'farkle';
      case 'DOMINO':
        return 'domino';
      case 'AMERICAN_DOMINO':
        return 'american_domino';
      case 'SCOPA':
        return 'scopa';
      case 'THIEF_HUNT':
        return 'thief_hunt';
      case 'TENNIS':
        return 'tennis';
      case 'NINETY_NINE':
      case 'NINETYNINE':
        return 'ninety_nine';
      default:
        return 'game';
    }
  }

  Future<void> _loadRules() async {
    setState(() => _loading = true);
    final prefix = _getFilePrefix(widget.gameType);
    String filename;
    if (_selectedLang == 'en') {
      filename = '${prefix}_rules_accessible_en.txt';
    } else if (_selectedLang == 'fr') {
      filename = '${prefix}_rules_accessible_fr.txt';
    } else {
      filename = '${prefix}_rules_accessible.txt';
    }

    try {
      final content = await rootBundle.loadString('assets/help/$filename');
      if (mounted) {
        setState(() {
          _rulesContent = content;
          _loading = false;
        });
        AccessibilityManager.instance.announce(
          tr('تم عرض قواعد اللعبة.'),
          interrupt: false,
        );
      }
    } catch (_) {
      // Fallback to Arabic if specific language file not found
      try {
        final fallback = await rootBundle.loadString('assets/help/${prefix}_rules_accessible.txt');
        if (mounted) {
          setState(() {
            _rulesContent = fallback;
            _loading = false;
          });
        }
      } catch (e) {
        if (mounted) {
          setState(() {
            _rulesContent = tr('تعذر تحميل قواعد اللعبة.');
            _loading = false;
          });
        }
      }
    }
  }

  void _onLanguageSelected(String lang) {
    if (_selectedLang == lang) return;
    setState(() {
      _selectedLang = lang;
    });
    _loadRules();
  }

  @override
  Widget build(BuildContext context) {
    final isRtl = (_selectedLang == 'ar');

    return AlertDialog(
      backgroundColor: AppColors.surface,
      title: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Expanded(
            child: Text(
              tr('قواعد اللعب'),
              style: const TextStyle(
                color: AppColors.textPrimary,
                fontWeight: FontWeight.bold,
                fontSize: 18,
              ),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.close, color: AppColors.textSecondary),
            tooltip: tr('إغلاق'),
            onPressed: () => Navigator.of(context).pop(),
          ),
        ],
      ),
      content: SizedBox(
        width: double.maxFinite,
        height: 480,
        child: Column(
          children: [
            // Language Selector Chips (Arabic / English / French)
            Padding(
              padding: const EdgeInsets.only(bottom: 12.0),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  _buildLangButton('ar', 'العربية'),
                  const SizedBox(width: 8),
                  _buildLangButton('en', 'English'),
                  const SizedBox(width: 8),
                  _buildLangButton('fr', 'Français'),
                ],
              ),
            ),
            const Divider(color: AppColors.divider, height: 1),
            const SizedBox(height: 8),

            // Scrollable Content
            Expanded(
              child: _loading
                  ? const Center(
                      child: CircularProgressIndicator(color: AppColors.primary),
                    )
                  : Container(
                      decoration: BoxDecoration(
                        color: AppColors.surfaceLight,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      padding: const EdgeInsets.all(12.0),
                      child: Directionality(
                        textDirection: isRtl ? TextDirection.rtl : TextDirection.ltr,
                        child: SingleChildScrollView(
                          child: SelectableText(
                            _rulesContent,
                            style: const TextStyle(
                              color: AppColors.textPrimary,
                              fontSize: 15,
                              height: 1.5,
                            ),
                          ),
                        ),
                      ),
                    ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: Text(tr('إغلاق'), style: const TextStyle(color: AppColors.primary, fontSize: 16)),
        ),
      ],
    );
  }

  Widget _buildLangButton(String langCode, String label) {
    final isSelected = (_selectedLang == langCode);

    return Semantics(
      label: label,
      selected: isSelected,
      button: true,
      excludeSemantics: true,
      child: InkWell(
        onTap: () => _onLanguageSelected(langCode),
        borderRadius: BorderRadius.circular(20),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
          decoration: BoxDecoration(
            color: isSelected ? AppColors.primary : AppColors.surfaceLight,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: isSelected ? AppColors.primary : AppColors.divider,
            ),
          ),
          child: Text(
            label,
            style: TextStyle(
              color: isSelected ? Colors.white : AppColors.textPrimary,
              fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
              fontSize: 13,
            ),
          ),
        ),
      ),
    );
  }
}
