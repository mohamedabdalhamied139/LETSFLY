import 'package:flutter/material.dart';
import '../core/app_theme.dart';
import '../core/localization.dart';
import '../services/activity_service.dart';
import '../services/api_service.dart';

/// Activity log and chat widget matching Windows client activity_log_widget.py architecture.
/// Satisfies user rules:
/// 1. Categories with 0 events are dynamically hidden from selection tabs.
/// 2. Announces to screen readers that log is opened in AR, EN, and FR.
class ActivityLogWidget extends StatefulWidget {
  final bool isBottomSheet;
  final VoidCallback? onClose;

  const ActivityLogWidget({
    super.key,
    this.isBottomSheet = false,
    this.onClose,
  });

  static void showAsBottomSheet(BuildContext context) {
    // Announce to screen reader in active language (AR/EN/FR)
    ActivityLogService.instance.announceLogOpened();

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => FractionallySizedBox(
        heightFactor: 0.75,
        child: ActivityLogWidget(
          isBottomSheet: true,
          onClose: () => Navigator.of(ctx).pop(),
        ),
      ),
    );
  }

  @override
  State<ActivityLogWidget> createState() => _ActivityLogWidgetState();
}

class _ActivityLogWidgetState extends State<ActivityLogWidget> {
  final TextEditingController _chatController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  bool _isSending = false;

  static const Map<String, String> _categoryLabels = {
    'TABLE_CHAT': 'دردشة الطاولات',
    'PRIVATE_MESSAGES': 'الرسائل الخاصة',
    'FRIENDS': 'الأصدقاء',
    'GAMEPLAY': 'اللعب',
    'ALL': 'الجميع',
    'FRIEND_REQUESTS': 'طلبات الصداقة',
    'INVITATIONS': 'الدعوات',
    'GIFTS': 'الهدايا',
  };

  @override
  void dispose() {
    _chatController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _sendMessage() async {
    final text = _chatController.text.trim();
    if (text.isEmpty || _isSending) return;

    setState(() => _isSending = true);
    try {
      // Send chat event to current activity service & api
      ActivityLogService.instance.addEvent({
        'category': 'TABLE_CHAT',
        'text': text,
        'time': '',
      });
      _chatController.clear();
    } catch (_) {} finally {
      if (mounted) setState(() => _isSending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: ActivityLogService.instance,
      builder: (context, _) {
        final service = ActivityLogService.instance;
        final visibleCategories = service.visibleCategories;
        final selectedCategory = visibleCategories.contains(service.selectedCategory)
            ? service.selectedCategory
            : 'ALL';
        final filteredEvents = service.filteredEvents;

        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Header Bar
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: const BoxDecoration(
                color: AppColors.header,
                border: Border(bottom: BorderSide(color: AppColors.border)),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    tr('سجل الأحداث والدردشة'),
                    style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  if (widget.isBottomSheet)
                    IconButton(
                      icon: const Icon(Icons.close, color: AppColors.textSecondary),
                      onPressed: widget.onClose,
                      tooltip: tr('إغلاق'),
                    ),
                ],
              ),
            ),

            // Category Selector Tabs (Dynamic: only shows categories with events per user rule)
            if (visibleCategories.length > 1)
              Container(
                height: 48,
                color: AppColors.surface,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  itemCount: visibleCategories.length,
                  separatorBuilder: (_, __) => const SizedBox(width: 8),
                  itemBuilder: (context, index) {
                    final catKey = visibleCategories[index];
                    final isSelected = catKey == selectedCategory;
                    final label = tr(_categoryLabels[catKey] ?? catKey);

                    return Semantics(
                      selected: isSelected,
                      button: true,
                      excludeSemantics: true,
                      label: label,
                      child: ChoiceChip(
                        label: Text(label),
                        selected: isSelected,
                        selectedColor: AppColors.accent,
                        backgroundColor: AppColors.header,
                        labelStyle: TextStyle(
                          color: isSelected ? Colors.white : AppColors.textSecondary,
                          fontSize: 13,
                          fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                        ),
                        onSelected: (selected) {
                          if (selected) {
                            service.selectCategory(catKey);
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
              child: filteredEvents.isEmpty
                  ? Center(
                      child: Text(
                        tr('لا توجد أحداث في هذا القسم.'),
                        style: const TextStyle(color: AppColors.textSecondary),
                      ),
                    )
                  : ListView.separated(
                      controller: _scrollController,
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                      itemCount: filteredEvents.length,
                      separatorBuilder: (_, __) =>
                          const Divider(height: 1, color: AppColors.border),
                      itemBuilder: (context, index) {
                        final event = filteredEvents[index];
                        final rawText = (event['text'] ?? event['message'] ?? '').toString();
                        final text = tr(rawText);
                        final time = (event['time'] ?? event['timestamp'] ?? '').toString();

                        return Semantics(
                          excludeSemantics: true,
                          label: time.isNotEmpty ? '$text، $time' : text,
                          child: Padding(
                            padding: const EdgeInsets.symmetric(vertical: 8),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Expanded(
                                  child: Text(
                                    text,
                                    style: const TextStyle(
                                      color: AppColors.textPrimary,
                                      fontSize: 14,
                                    ),
                                  ),
                                ),
                                if (time.isNotEmpty) ...[
                                  const SizedBox(width: 8),
                                  Text(
                                    time,
                                    style: const TextStyle(
                                      color: AppColors.textSecondary,
                                      fontSize: 11,
                                    ),
                                  ),
                                ],
                              ],
                            ),
                          ),
                        );
                      },
                    ),
            ),

            // Bottom Chat Input Box
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: const BoxDecoration(
                color: AppColors.header,
                border: Border(top: BorderSide(color: AppColors.border)),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _chatController,
                      style: const TextStyle(color: AppColors.textPrimary, fontSize: 14),
                      decoration: InputDecoration(
                        hintText: tr('اكتب رسالة...'),
                        filled: true,
                        fillColor: AppColors.surface,
                        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                      ),
                      onSubmitted: (_) => _sendMessage(),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton(
                    icon: _isSending
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                          )
                        : const Icon(Icons.send, color: AppColors.accent),
                    onPressed: _sendMessage,
                    tooltip: tr('إرسال'),
                  ),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}
