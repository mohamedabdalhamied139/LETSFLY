import 'package:flutter/material.dart';
import '../core/app_theme.dart';
import '../core/localization.dart';
import '../widgets/two_finger_gesture_detector.dart';
import 'activity_log_widget.dart';

class ResponsiveShell extends StatelessWidget {
  final String title;
  final Widget child;
  final List<Widget>? actions;
  final Widget? floatingActionButton;
  final Widget? leading;
  final PreferredSizeWidget? bottom;

  const ResponsiveShell({
    super.key,
    required this.title,
    required this.child,
    this.actions,
    this.floatingActionButton,
    this.leading,
    this.bottom,
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
      // Two-finger swipe right anywhere opens the Activity Log per explicit user instruction
      body: TwoFingerSwipeDetector(
        onTwoFingerSwipeRight: () => ActivityLogWidget.showAsBottomSheet(context),
        child: child,
      ),
      floatingActionButton: floatingActionButton,
    );
  }
}
