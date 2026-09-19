import 'package:flutter/material.dart';
import '../../core/app_theme.dart';
import '../../core/accessibility_manager.dart';
import '../../core/localization.dart';
import '../../services/game_preferences_service.dart';
import '../game_settings_registry.dart';

class StartGameResult {
  final int targetScore;
  final Map<String, dynamic> rules;

  const StartGameResult({required this.targetScore, required this.rules});
}

/// Dialog replicating _choose_start_mode and _open_settings_list from client/client_app.py.
/// Prompt: "هل تريد اللعب بالاعدادات الافتراضية؟"
/// - "نعم": starts immediately with saved/default settings.
/// - "لا": opens the customized settings sheet.
class StartGameDialog {
  static Future<StartGameResult?> show(
    BuildContext context, {
    required String gameType,
    Map<String, dynamic>? currentRoom,
  }) async {
    final definition = GAME_SETTINGS_REGISTRY[gameType.toUpperCase()];
    if (definition == null) {
      return const StartGameResult(targetScore: 500, rules: {});
    }

    final saved = await GamePreferencesService.instance.load(
      gameType,
      definition.defaultTargetScore,
      definition.defaultRules,
    );

    AccessibilityManager.instance.announce(tr('هل تريد اللعب بالاعدادات الافتراضية؟'));

    // Step 1: Prompt default vs custom
    final choice = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: Text(
          tr('هل تريد اللعب بالاعدادات الافتراضية؟'),
          style: const TextStyle(color: AppColors.textPrimary, fontSize: 18),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop('custom'),
            child: Text(tr('لا'), style: const TextStyle(color: AppColors.textSecondary, fontSize: 16)),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(ctx).pop('default'),
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.success),
            child: Text(tr('نعم'), style: const TextStyle(color: Colors.white, fontSize: 16)),
          ),
        ],
      ),
    );

    if (choice == null) return null;

    if (choice == 'default') {
      return StartGameResult(targetScore: saved.key, rules: saved.value);
    }

    // Step 2: Custom settings sheet
    return await _showCustomSettingsSheet(context, definition, saved.key, saved.value, currentRoom);
  }

  static Future<StartGameResult?> _showCustomSettingsSheet(
    BuildContext context,
    GameSettingsDefinition definition,
    int initialTarget,
    Map<String, dynamic> initialRules,
    Map<String, dynamic>? currentRoom,
  ) {
    return showModalBottomSheet<StartGameResult>(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => _CustomGameSettingsSheet(
        definition: definition,
        initialTarget: initialTarget,
        initialRules: initialRules,
        currentRoom: currentRoom,
      ),
    );
  }
}

class _CustomGameSettingsSheet extends StatefulWidget {
  final GameSettingsDefinition definition;
  final int initialTarget;
  final Map<String, dynamic> initialRules;
  final Map<String, dynamic>? currentRoom;

  const _CustomGameSettingsSheet({
    required this.definition,
    required this.initialTarget,
    required this.initialRules,
    this.currentRoom,
  });

  @override
  State<_CustomGameSettingsSheet> createState() => _CustomGameSettingsSheetState();
}

class _CustomGameSettingsSheetState extends State<_CustomGameSettingsSheet> {
  late Map<String, dynamic> _values;

  @override
  void initState() {
    super.initState();
    _values = {};

    // Initialize values from fields
    for (final field in widget.definition.customFields) {
      final dict = field.toDict(widget.currentRoom);
      dynamic val = dict['value'];

      if (field.key == 'target_score') {
        val = widget.initialTarget;
      } else if (widget.initialRules.containsKey(field.key)) {
        val = widget.initialRules[field.key];
      }

      _values[field.key] = val ?? field.defaultValue;
    }
  }

  void _onBoolChanged(SettingField field, bool value) {
    setState(() {
      _values[field.key] = value;

      // Check conflict logic matching Windows
      if (field.conflictsWith.isNotEmpty && value) {
        for (final conflictingKey in field.conflictsWith.keys) {
          _values[conflictingKey] = false;
        }
      }

      // Group radio logic
      if (field.group != null && value) {
        for (final other in widget.definition.customFields) {
          if (other.group == field.group && other.key != field.key) {
            _values[other.key] = false;
          }
        }
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final title = tr('تخصيص {title}', {'title': tr(widget.definition.title)});

    return SafeArea(
      child: FractionallySizedBox(
        heightFactor: 0.85,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Header
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 14.0),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      title,
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close, color: AppColors.textSecondary),
                    onPressed: () => Navigator.of(context).pop(null),
                  ),
                ],
              ),
            ),
            const Divider(height: 1, color: AppColors.divider),

            // Scrollable Fields List
            Expanded(
              child: ListView(
                padding: const EdgeInsets.all(16.0),
                children: widget.definition.customFields.map((field) {
                  if (field.kind == 'number') {
                    final currentVal = int.tryParse(_values[field.key]?.toString() ?? '') ?? field.minimum;

                    return Card(
                      color: AppColors.surfaceLight,
                      margin: const EdgeInsets.only(bottom: 12.0),
                      child: Padding(
                        padding: const EdgeInsets.all(12.0),
                        child: Row(
                          children: [
                            Expanded(
                              child: Text(
                                tr(field.label),
                                style: const TextStyle(fontSize: 16, color: AppColors.textPrimary),
                              ),
                            ),
                            IconButton(
                              icon: const Icon(Icons.remove_circle_outline),
                              color: AppColors.primary,
                              onPressed: () {
                                final next = currentVal - field.step;
                                if (next >= field.minimum) {
                                  setState(() => _values[field.key] = next);
                                }
                              },
                            ),
                            Text(
                              '$currentVal',
                              style: const TextStyle(
                                fontSize: 17,
                                fontWeight: FontWeight.bold,
                                color: AppColors.textPrimary,
                              ),
                            ),
                            IconButton(
                              icon: const Icon(Icons.add_circle_outline),
                              color: AppColors.primary,
                              onPressed: () {
                                final next = currentVal + field.step;
                                if (field.maximum == null || next <= field.maximum!) {
                                  setState(() => _values[field.key] = next);
                                }
                              },
                            ),
                          ],
                        ),
                      ),
                    );
                  } else if (field.kind == 'choice') {
                    final currentVal = _values[field.key]?.toString() ?? 'none';

                    return Card(
                      color: AppColors.surfaceLight,
                      margin: const EdgeInsets.only(bottom: 12.0),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 12.0, vertical: 8.0),
                        child: Row(
                          children: [
                            Expanded(
                              child: Text(
                                tr(field.label),
                                style: const TextStyle(fontSize: 16, color: AppColors.textPrimary),
                              ),
                            ),
                            DropdownButton<String>(
                              value: field.options.contains(currentVal) ? currentVal : field.options.first,
                              dropdownColor: AppColors.surfaceLight,
                              underline: const SizedBox(),
                              items: field.options.map((opt) {
                                final label = field.labels[opt] ?? opt;
                                return DropdownMenuItem(
                                  value: opt,
                                  child: Text(
                                    tr(label),
                                    style: const TextStyle(color: AppColors.textPrimary),
                                  ),
                                );
                              }).toList(),
                              onChanged: (val) {
                                if (val != null) {
                                  setState(() => _values[field.key] = val);
                                }
                              },
                            ),
                          ],
                        ),
                      ),
                    );
                  } else if (field.kind == 'bool') {
                    final currentVal = _values[field.key] == true;

                    return Card(
                      color: AppColors.surfaceLight,
                      margin: const EdgeInsets.only(bottom: 8.0),
                      child: SwitchListTile(
                        title: Text(
                          tr(field.label),
                          style: const TextStyle(fontSize: 15, color: AppColors.textPrimary),
                        ),
                        subtitle: field.description != null
                            ? Text(
                                tr(field.description!),
                                style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                              )
                            : null,
                        value: currentVal,
                        activeColor: AppColors.primary,
                        onChanged: (v) => _onBoolChanged(field, v),
                      ),
                    );
                  }
                  return const SizedBox();
                }).toList(),
              ),
            ),

            // Bottom Actions: بدء اللعبة / إلغاء
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => Navigator.of(context).pop(null),
                      style: OutlinedButton.styleFrom(
                        minimumSize: const Size.fromHeight(48),
                        side: const BorderSide(color: AppColors.textSecondary),
                      ),
                      child: Text(tr('إلغاء'), style: const TextStyle(color: AppColors.textSecondary)),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () async {
                        final extracted = widget.definition.extractTargetAndRules(_values);
                        // Persist to user preferences matching Windows save()
                        await GamePreferencesService.instance.save(
                          widget.definition.gameType,
                          extracted.key,
                          extracted.value,
                        );

                        Navigator.of(context).pop(
                          StartGameResult(
                            targetScore: extracted.key,
                            rules: extracted.value,
                          ),
                        );
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.success,
                        minimumSize: const Size.fromHeight(48),
                      ),
                      child: Text(tr('بدء اللعبة'), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
