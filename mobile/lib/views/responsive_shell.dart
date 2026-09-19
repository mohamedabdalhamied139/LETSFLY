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
  final VoidCallback? onTwoFingerSwipeRight;
  final VoidCallback? onTwoFingerSwipeLeft;
  final VoidCallback? onTwoFingerSwipeUp;
  final VoidCallback? onTwoFingerSwipeDown;

  const ResponsiveShell({
    super.key,
    required this.title,
    required this.child,
    this.actions,
    this.floatingActionButton,
    this.leading,
    this.bottom,
    this.showDrawer = true,
    this.onTwoFingerSwipeRight,
    this.onTwoFingerSwipeLeft,
    this.onTwoFingerSwipeUp,
    this.onTwoFingerSwipeDown,
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
      // Two-finger swipe detector wrapping the entire body
      body: TwoFingerSwipeDetector(
        onTwoFingerSwipeRight: onTwoFingerSwipeRight ?? () => ActivityLogWidget.showAsBottomSheet(context),
        onTwoFingerSwipeLeft: onTwoFingerSwipeLeft,
        onTwoFingerSwipeUp: onTwoFingerSwipeUp,
        onTwoFingerSwipeDown: onTwoFingerSwipeDown,
        child: child,
      ),
      floatingActionButton: floatingActionButton,
    );
  }
}
