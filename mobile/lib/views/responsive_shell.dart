import 'package:flutter/material.dart';
import '../core/app_theme.dart';
import '../core/localization.dart';
import '../widgets/two_finger_gesture_detector.dart';
import '../widgets/app_navigation_drawer.dart';
import 'activity_log_widget.dart';

class ResponsiveShell extends StatelessWidget {
  final String title;
  final Widget child;
  final List<Widget>? actions;
  final Widget? floatingActionButton;
  final Widget? leading;
  final PreferredSizeWidget? bottom;
  final bool showDrawer;
  final bool showActivityLogAction;

  const ResponsiveShell({
    super.key,
    required this.title,
    required this.child,
    this.actions,
    this.floatingActionButton,
    this.leading,
    this.bottom,
    this.showDrawer = true,
    this.showActivityLogAction = true,
  });

  @override
  Widget build(BuildContext context) {
    final effectiveActions = <Widget>[
      ...?actions,
      if (showActivityLogAction)
        Semantics(
          label: tr('سجل الأحداث والدردشة'),
          button: true,
          excludeSemantics: true,
          child: IconButton(
            icon: const Icon(Icons.forum_outlined),
            tooltip: tr('سجل الأحداث والدردشة'),
            onPressed: () => ActivityLogWidget.showAsBottomSheet(context),
          ),
        ),
    ];

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text(title),
        leading: leading,
        actions: effectiveActions,
        bottom: bottom,
      ),
      drawer: showDrawer ? const AppNavigationDrawer() : null,
      // Two-finger or accessible horizontal swipe anywhere opens the Activity Log
      body: TwoFingerSwipeDetector(
        allowSingleFingerHorizontal: true,
        onTwoFingerSwipeRight: () => ActivityLogWidget.showAsBottomSheet(context),
        onTwoFingerSwipeLeft: () => ActivityLogWidget.showAsBottomSheet(context),
        child: child,
      ),
      floatingActionButton: floatingActionButton,
    );
  }
}
