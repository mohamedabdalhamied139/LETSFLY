import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../core/app_theme.dart';
import '../core/localization.dart';
import '../services/activity_service.dart';

const Map<String, String> activityCategoryLabels = {
  'TABLE_CHAT': 'دردشة الطاولات',
  'PRIVATE_MESSAGES': 'الرسائل الخاصة',
  'FRIENDS': 'الأصدقاء',
  'GAMEPLAY': 'اللعب',
  'ALL': 'الجميع',
  'FRIEND_REQUESTS': 'طلبات الصداقة',
  'INVITATIONS': 'الدعوات',
  'GIFTS': 'الهدايا',
};

const List<String> activityCategoryOrder = [
  'TABLE_CHAT',
  'PRIVATE_MESSAGES',
  'FRIENDS',
  'GAMEPLAY',
  'ALL',
  'FRIEND_REQUESTS',
  'INVITATIONS',
  'GIFTS',
];

/// Synchronized Activity Log Widget displaying real-time events categorized across the
/// 8 canonical categories in desktop Windows order.
class ActivityLogWidget extends StatefulWidget {
  final List<Map<String, dynamic>>? events;
  final void Function(String category)? onCategoryChanged;
  final void Function(Map<String, dynamic> event)? onEventActivated;
  final VoidCallback? onLoadOlder;
  final ActivityLogService? service;

  const ActivityLogWidget({
    super.key,
    this.events,
    this.onCategoryChanged,
    this.onEventActivated,
    this.onLoadOlder,
    this.service,
  });

  @override
  State<ActivityLogWidget> createState() => _ActivityLogWidgetState();
}

class _ActivityLogWidgetState extends State<ActivityLogWidget> {
  final FocusNode _focusNode = FocusNode();

  ActivityLogService get _service => widget.service ?? ActivityLogService.instance;

  @override
  void dispose() {
    _focusNode.dispose();
    super.dispose();
  }

  void _moveCategory(int delta) {
    final current = _service.selectedCategory;
    final currentIndex = activityCategoryOrder.indexOf(current);
    if (currentIndex == -1) return;
    final newIndex = (currentIndex + delta).clamp(0, activityCategoryOrder.length - 1);
    final newCat = activityCategoryOrder[newIndex];
    if (newCat != current) {
      _service.selectCategory(newCat);
      widget.onCategoryChanged?.call(newCat);
    }
  }

  List<Map<String, dynamic>> _getEventsToDisplay() {
    // If external events are passed and service is empty, filter external events for backwards compatibility
    if (widget.events != null && widget.events!.isNotEmpty && _service.events.isEmpty) {
      final selected = _service.selectedCategory;
      if (selected == 'ALL') {
        return widget.events!;
      }
      return widget.events!.where((Map<String, dynamic> e) {
        final cat = (e['category'] ?? e['type'] ?? '').toString().trim().toUpperCase();
        return cat == selected;
      }).toList();
    }
    return _service.filteredEvents;
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: _service,
      builder: (BuildContext context, Widget? _) {
        final selectedCat = _service.selectedCategory;
        final eventsToDisplay = _getEventsToDisplay();

        return Focus(
          focusNode: _focusNode,
          onKeyEvent: (FocusNode node, KeyEvent event) {
            if (event is KeyDownEvent) {
              if (event.logicalKey == LogicalKeyboardKey.arrowLeft) {
                _moveCategory(-1);
                return KeyEventResult.handled;
              } else if (event.logicalKey == LogicalKeyboardKey.arrowRight) {
                _moveCategory(1);
                return KeyEventResult.handled;
              }
            }
            return KeyEventResult.ignored;
          },
          child: Container(
            color: AppColors.background,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Header Bar
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  color: AppColors.header,
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        tr('سجل الأحداث'),
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 16,
                          color: AppColors.textPrimary,
                        ),
                      ),
                      Text(
                        tr(activityCategoryLabels[selectedCat] ?? selectedCat),
                        style: const TextStyle(
                          color: Colors.lightBlueAccent,
                          fontSize: 14,
                        ),
                      ),
                    ],
                  ),
                ),
                // Category Chips Selector
                SizedBox(
                  height: 44,
                  child: ListView.builder(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    itemCount: activityCategoryOrder.length,
                    itemBuilder: (BuildContext context, int idx) {
                      final catKey = activityCategoryOrder[idx];
                      final catLabel = tr(activityCategoryLabels[catKey] ?? catKey);
                      final isSelected = catKey == selectedCat;

                      return Padding(
                        padding: const EdgeInsets.only(right: 6.0),
                        child: ChoiceChip(
                          label: Text(
                            catLabel,
                            style: TextStyle(
                              fontSize: 12,
                              color: isSelected ? Colors.white : AppColors.textSecondary,
                            ),
                          ),
                          selected: isSelected,
                          selectedColor: AppColors.accent,
                          backgroundColor: AppColors.surface,
                          side: const BorderSide(color: AppColors.border),
                          onSelected: (bool selected) {
                            if (selected) {
                              _service.selectCategory(catKey);
                              widget.onCategoryChanged?.call(catKey);
                            }
                          },
                        ),
                      );
                    },
                  ),
                ),
                const Divider(height: 1, color: AppColors.border),
                // Events List
                Expanded(
                  child: eventsToDisplay.isEmpty
                      ? Center(
                          child: Text(
                            tr('لا توجد أحداث في هذا القسم.'),
                            style: const TextStyle(
                              color: AppColors.textSecondary,
                              fontSize: 14,
                            ),
                          ),
                        )
                      : ListView.separated(
                          itemCount: eventsToDisplay.length,
                          separatorBuilder: (BuildContext _, int __) => const Divider(
                            height: 1,
                            color: AppColors.header,
                          ),
                          itemBuilder: (BuildContext context, int idx) {
                            final item = eventsToDisplay[idx];
                            final rawText = item['text'] ?? item['message'] ?? item.toString();
                            final text = tr(rawText.toString());
                            final time = (item['time'] ?? item['created_at'] ?? '').toString();

                            return ListTile(
                              dense: true,
                              title: Text(
                                text,
                                style: const TextStyle(
                                  color: AppColors.textPrimary,
                                  fontSize: 14,
                                ),
                              ),
                              subtitle: time.isNotEmpty
                                  ? Text(
                                      time,
                                      style: const TextStyle(
                                        color: AppColors.textSecondary,
                                        fontSize: 11,
                                      ),
                                    )
                                  : null,
                              onTap: widget.onEventActivated != null
                                  ? () => widget.onEventActivated!(item)
                                  : null,
                            );
                          },
                        ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
