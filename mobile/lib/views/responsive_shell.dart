import 'package:flutter/material.dart';
import '../core/app_theme.dart';
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

  const ResponsiveShell({
    super.key,
    required this.title,
    required this.child,
    this.actions,
    this.floatingActionButton,
    this.leading,
    this.bottom,
    this.showDrawer = true,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text(title),
        leading: leading,
        actions: actions,
        bottom: bottom,
      ),
      drawer: showDrawer ? const AppNavigationDrawer() : null,
      // Two-finger swipe right anywhere opens the Activity Log per explicit user instruction
      body: TwoFingerSwipeDetector(
        onTwoFingerSwipeRight: () => ActivityLogWidget.showAsBottomSheet(context),
        child: child,
      ),
      floatingActionButton: floatingActionButton,
    );
  }
}
