import 'package:flutter/material.dart';
import '../core/app_theme.dart';
import '../core/localization.dart';
import '../widgets/two_finger_gesture_detector.dart';
import 'activity_log_widget.dart';

/// Responsive shell wrapping mobile views with the two-finger swipe right gesture
/// and top AppBar with an Activity Log toggle action.
class ResponsiveShell extends StatelessWidget {
  final String title;
  final Widget child;
  final List<Widget>? actions;
  final Widget? floatingActionButton;
  final bool showActivityLogAction;
  final Widget? leading;
  final PreferredSizeWidget? bottom;

  const ResponsiveShell({
    super.key,
    required this.title,
    required this.child,
    this.actions,
    this.floatingActionButton,
    this.showActivityLogAction = true,
    this.leading,
    this.bottom,
  });

  @override
  Widget build(BuildContext context) {
    final List<Widget> effectiveActions = [];
    if (actions != null) {
      effectiveActions.addAll(actions!);
    }

    if (showActivityLogAction) {
      effectiveActions.add(
        IconButton(
          icon: const Icon(Icons.chat_bubble_outline, color: AppColors.textPrimary),
          tooltip: tr('سجل الأحداث والدردشة'),
          onPressed: () => ActivityLogWidget.showAsBottomSheet(context),
        ),
      );
    }

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text(title),
        leading: leading,
        actions: effectiveActions,
        bottom: bottom,
      ),
      // Two-finger swipe right anywhere opens the Activity Log per explicit user instruction
      body: TwoFingerSwipeDetector(
        onTwoFingerSwipeRight: () => ActivityLogWidget.showAsBottomSheet(context),
        child: child,
      ),
      floatingActionButton: floatingActionButton,
    );
  }
}
