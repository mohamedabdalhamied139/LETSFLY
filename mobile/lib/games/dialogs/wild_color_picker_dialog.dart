import 'package:flutter/material.dart';
import '../../core/app_theme.dart';
import '../../core/accessibility_manager.dart';
import '../../core/localization.dart';

/// Modal dialog for choosing a wild card color in UNO.
/// Replicates show_wild_colors from client/views/table_view.py.
class WildColorPickerDialog extends StatefulWidget {
  final bool darkSide;

  const WildColorPickerDialog({super.key, this.darkSide = false});

  static Future<String?> show(BuildContext context, {bool darkSide = false}) {
    AccessibilityManager.instance.announce(tr('اختر اللون'));
    return showModalBottomSheet<String>(
      context: context,
      backgroundColor: AppColors.surface,
      isDismissible: false,
      enableDrag: false,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => WildColorPickerDialog(darkSide: darkSide),
    );
  }

  @override
  State<WildColorPickerDialog> createState() => _WildColorPickerDialogState();
}

class _WildColorPickerDialogState extends State<WildColorPickerDialog> {
  static const Map<String, String> _colorCodes = {
    'أحمر': 'red',
    'أصفر': 'yellow',
    'أخضر': 'green',
    'أزرق': 'blue',
    'برتقالي': 'orange',
    'وردي': 'pink',
    'بنفسجي': 'purple',
    'تركوازي': 'teal',
  };

  static const Map<String, Color> _visualColors = {
    'red': Colors.red,
    'yellow': Colors.amber,
    'green': Colors.green,
    'blue': Colors.blue,
    'orange': Colors.deepOrange,
    'pink': Colors.pink,
    'purple': Colors.purple,
    'teal': Colors.teal,
  };

  List<String> get _options {
    if (widget.darkSide) {
      return ['برتقالي', 'وردي', 'بنفسجي', 'تركوازي'];
    }
    return ['أحمر', 'أصفر', 'أخضر', 'أزرق'];
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
                tr('اختر اللون'),
                style: const TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
            ),
            const SizedBox(height: 16),
            ...List.generate(_options.length, (index) {
              final colorName = _options[index];
              final code = _colorCodes[colorName] ?? 'red';
              final visualColor = _visualColors[code] ?? Colors.grey;

              return Padding(
                padding: const EdgeInsets.only(bottom: 8.0),
                child: ElevatedButton.icon(
                  onPressed: () => Navigator.of(context).pop(code),
                  icon: Container(
                    width: 20,
                    height: 20,
                    decoration: BoxDecoration(
                      color: visualColor,
                      shape: BoxShape.circle,
                      border: Border.all(color: Colors.white, width: 2),
                    ),
                  ),
                  label: Text(
                    tr(colorName),
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.surfaceLight,
                    minimumSize: const Size.fromHeight(50),
                    alignment: Alignment.centerLeft,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
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
