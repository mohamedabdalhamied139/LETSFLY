import 'package:flutter/material.dart';
import '../../core/app_theme.dart';
import '../../core/accessibility_manager.dart';
import '../../core/localization.dart';

/// Modal dialog for choosing a value adjustment in Ninety-Nine (e.g. +10 or -10 for a 10 card).
/// Replicates show_ninety_nine_choice from client/views/table_view.py.
class NinetyNineChoiceDialog extends StatelessWidget {
  final List<MapEntry<String, String>> options;

  const NinetyNineChoiceDialog({super.key, required this.options});

  static Future<String?> show(
    BuildContext context, {
    required List<MapEntry<String, String>> options,
  }) {
    AccessibilityManager.instance.announce(tr('اختر القيمة'));
    return showModalBottomSheet<String>(
      context: context,
      backgroundColor: AppColors.surface,
      isDismissible: false,
      enableDrag: false,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => NinetyNineChoiceDialog(options: options),
    );
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 16.0, horizontal: 16.0),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Center(
              child: Text(
                tr('اختر القيمة'),
                style: const TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
            ),
            const SizedBox(height: 16),
            ...options.map((entry) {
              return Padding(
                padding: const EdgeInsets.only(bottom: 8.0),
                child: ElevatedButton(
                  onPressed: () => Navigator.of(context).pop(entry.value),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.surfaceLight,
                    minimumSize: const Size.fromHeight(50),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),
                  child: Text(
                    entry.key,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                ),
              );
            }),
          ],
        ),
      ),
    );
  }
}
