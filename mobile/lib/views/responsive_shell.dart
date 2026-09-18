import 'package:flutter/material.dart';
import '../core/app_theme.dart';
import '../core/localization.dart';
import 'activity_log_widget.dart';

/// Responsive master-detail shell matching the Windows desktop layout architecture.
/// Displays dual-pane (side-by-side) on wide viewports (>= 720dp) and stacked
/// collapsible layout on compact viewports (< 720dp).
class ResponsiveShell extends StatefulWidget {
  final String title;
  final Widget child;
  final List<Widget>? actions;
  final Widget? floatingActionButton;
  final bool showActivityLog;
  final Widget? leading;
  final PreferredSizeWidget? bottom;

  const ResponsiveShell({
    super.key,
    required this.title,
    required this.child,
    this.actions,
    this.floatingActionButton,
    this.showActivityLog = true,
    this.leading,
    this.bottom,
  });

  @override
  State<ResponsiveShell> createState() => _ResponsiveShellState();
}

class _ResponsiveShellState extends State<ResponsiveShell> {
  bool _isLogExpanded = true;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text(widget.title),
        leading: widget.leading,
        actions: widget.actions,
        bottom: widget.bottom,
      ),
      body: LayoutBuilder(
        builder: (BuildContext context, BoxConstraints constraints) {
          final isWide = constraints.maxWidth >= 720;

          if (!widget.showActivityLog) {
            return widget.child;
          }

          if (isWide) {
            // Wide Viewport (>= 720dp): Side-by-side dual-pane matching Windows QHBoxLayout
            return Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Expanded(
                  flex: 6,
                  child: widget.child,
                ),
                const VerticalDivider(
                  width: 1,
                  thickness: 1,
                  color: AppColors.border,
                ),
                const Expanded(
                  flex: 4,
                  child: ActivityLogWidget(),
                ),
              ],
            );
          }

          // Compact Viewport (< 720dp): Content on top and collapsible bottom ActivityLogWidget
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Expanded(
                flex: _isLogExpanded ? 6 : 1,
                child: widget.child,
              ),
              // Collapsible Divider / Toggle Bar
              InkWell(
                onTap: () {
                  setState(() {
                    _isLogExpanded = !_isLogExpanded;
                  });
                },
                child: Container(
                  height: 36,
                  color: AppColors.header,
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Row(
                        children: [
                          Icon(
                            _isLogExpanded
                                ? Icons.keyboard_arrow_down
                                : Icons.keyboard_arrow_up,
                            color: AppColors.textSecondary,
                            size: 20,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            tr('سجل الأحداث'),
                            style: const TextStyle(
                              color: AppColors.textPrimary,
                              fontSize: 13,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                      Text(
                        _isLogExpanded ? tr('طي') : tr('توسيع'),
                        style: const TextStyle(
                          color: AppColors.textSecondary,
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              if (_isLogExpanded)
                const Expanded(
                  flex: 4,
                  child: ActivityLogWidget(),
                ),
            ],
          );
        },
      ),
      floatingActionButton: widget.floatingActionButton,
    );
  }
}
