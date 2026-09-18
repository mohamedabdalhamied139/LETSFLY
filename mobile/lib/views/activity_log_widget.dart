import 'package:flutter/material.dart';
import '../core/localization.dart';

const Map<String, String> activityCategoryLabels = {
  'ALL': 'الجميع',
  'TABLE_CHAT': 'دردشة الطاولات',
  'PRIVATE_MESSAGES': 'الرسائل الخاصة',
  'FRIENDS': 'الأصدقاء',
  'GAMEPLAY': 'اللعب',
  'FRIEND_REQUESTS': 'طلبات الصداقة',
  'INVITATIONS': 'الدعوات',
  'GIFTS': 'الهدايا',
};

const List<String> activityCategoryOrder = [
  'ALL',
  'TABLE_CHAT',
  'PRIVATE_MESSAGES',
  'FRIENDS',
  'GAMEPLAY',
  'FRIEND_REQUESTS',
  'INVITATIONS',
  'GIFTS',
];

class ActivityLogWidget extends StatefulWidget {
  final List<Map<String, dynamic>> events;
  final Function(String category)? onCategoryChanged;
  final VoidCallback? onLoadOlder;

  const ActivityLogWidget({
    super.key,
    required this.events,
    this.onCategoryChanged,
    this.onLoadOlder,
  });

  @override
  State<ActivityLogWidget> createState() => _ActivityLogWidgetState();
}

class _ActivityLogWidgetState extends State<ActivityLogWidget> {
  String _selectedCategory = 'ALL';

  List<Map<String, dynamic>> get _filteredEvents {
    if (_selectedCategory == 'ALL') {
      return widget.events;
    }
    return widget.events.where((e) {
      final cat = (e['category'] ?? e['type'] ?? '').toString().toUpperCase();
      return cat == _selectedCategory;
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      color: const Color(0xFF1E1E1E),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Header
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            color: const Color(0xFF2D2D2D),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  tr('سجل الأحداث'),
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 16,
                    color: Colors.white,
                  ),
                ),
                Text(
                  tr(activityCategoryLabels[_selectedCategory] ?? _selectedCategory),
                  style: const TextStyle(
                    color: Colors.lightBlueAccent,
                    fontSize: 14,
                  ),
                ),
              ],
            ),
          ),
          // Category selector scroll
          SizedBox(
            height: 44,
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              itemCount: activityCategoryOrder.length,
              itemBuilder: (context, idx) {
                final catKey = activityCategoryOrder[idx];
                final catLabel = tr(activityCategoryLabels[catKey] ?? catKey);
                final isSelected = catKey == _selectedCategory;

                return Padding(
                  padding: const EdgeInsets.only(right: 6.0),
                  child: ChoiceChip(
                    label: Text(
                      catLabel,
                      style: TextStyle(
                        fontSize: 12,
                        color: isSelected ? Colors.white : Colors.white70,
                      ),
                    ),
                    selected: isSelected,
                    selectedColor: Colors.blueAccent,
                    backgroundColor: const Color(0xFF252526),
                    onSelected: (selected) {
                      if (selected) {
                        setState(() => _selectedCategory = catKey);
                        widget.onCategoryChanged?.call(catKey);
                      }
                    },
                  ),
                );
              },
            ),
          ),
          const Divider(height: 1, color: Color(0xFF3E3E42)),
          // Events List
          Expanded(
            child: _filteredEvents.isEmpty
                ? Center(
                    child: Text(
                      tr('لا توجد أحداث في هذا القسم.'),
                      style: const TextStyle(color: Colors.white54),
                    ),
                  )
                : ListView.separated(
                    itemCount: _filteredEvents.length,
                    separatorBuilder: (_, __) => const Divider(
                      height: 1,
                      color: Color(0xFF2D2D2D),
                    ),
                    itemBuilder: (context, idx) {
                      final item = _filteredEvents[idx];
                      final text = item['text'] ?? item['message'] ?? item.toString();
                      final time = item['time'] ?? '';

                      return Semantics(
                        label: text.toString(),
                        child: ListTile(
                          dense: true,
                          title: Text(
                            text.toString(),
                            style: const TextStyle(color: Colors.white, fontSize: 14),
                          ),
                          subtitle: time.toString().isNotEmpty
                              ? Text(
                                  time.toString(),
                                  style: const TextStyle(color: Colors.white38, fontSize: 11),
                                )
                              : null,
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}
