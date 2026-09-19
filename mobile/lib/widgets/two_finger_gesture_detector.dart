import 'package:flutter/material.dart';

/// Global multi-touch and accessibility-friendly gesture detector detecting 4-way swipes:
/// - Swipe Right / Left: Open Activity Log & Chat (in Shells) or Top Card Announcement (in Table)
/// - Swipe Up: Announce who has the turn & remaining time (matches 'T' in Windows)
/// - Swipe Down: Spacebar action (draw card, roll dice, draw tile) (matches Space in Windows)
class TwoFingerSwipeDetector extends StatefulWidget {
  final Widget child;
  final VoidCallback? onTwoFingerSwipeRight;
  final VoidCallback? onTwoFingerSwipeLeft;
  final VoidCallback? onTwoFingerSwipeUp;
  final VoidCallback? onTwoFingerSwipeDown;
  final bool allowSingleFingerHorizontal;

  const TwoFingerSwipeDetector({
    super.key,
    required this.child,
    this.onTwoFingerSwipeRight,
    this.onTwoFingerSwipeLeft,
    this.onTwoFingerSwipeUp,
    this.onTwoFingerSwipeDown,
    this.allowSingleFingerHorizontal = false,
  });

  @override
  State<TwoFingerSwipeDetector> createState() => _TwoFingerSwipeDetectorState();
}

class _TwoFingerSwipeDetectorState extends State<TwoFingerSwipeDetector> {
  final Map<int, Offset> _startPositions = {};
  final Map<int, Offset> _currentPositions = {};
  bool _hasTriggered = false;

  static const double _swipeThreshold = 30.0;

  void _handlePointerDown(PointerDownEvent event) {
    _startPositions[event.pointer] = event.position;
    _currentPositions[event.pointer] = event.position;
    if (_startPositions.length < 2) {
      _hasTriggered = false;
    }
  }

  void _handlePointerMove(PointerMoveEvent event) {
    if (_startPositions.containsKey(event.pointer)) {
      _currentPositions[event.pointer] = event.position;
    }

    if (_startPositions.length >= 2 && !_hasTriggered) {
      double totalDx = 0.0;
      double totalDy = 0.0;
      int activeCount = 0;

      for (final entry in _startPositions.entries) {
        final pid = entry.key;
        if (_currentPositions.containsKey(pid)) {
          totalDx += (_currentPositions[pid]!.dx - entry.value.dx);
          totalDy += (_currentPositions[pid]!.dy - entry.value.dy);
          activeCount++;
        }
      }

      if (activeCount >= 2) {
        final avgDx = totalDx / activeCount;
        final avgDy = totalDy / activeCount;

        if (avgDx.abs() > _swipeThreshold || avgDy.abs() > _swipeThreshold) {
          _hasTriggered = true;
          if (avgDx.abs() > avgDy.abs()) {
            // Horizontal swipe
            if (avgDx > _swipeThreshold) {
              widget.onTwoFingerSwipeRight?.call();
            } else if (avgDx < -_swipeThreshold) {
              widget.onTwoFingerSwipeLeft?.call();
            }
          } else {
            // Vertical swipe
            if (avgDy > _swipeThreshold) {
              widget.onTwoFingerSwipeDown?.call();
            } else if (avgDy < -_swipeThreshold) {
              widget.onTwoFingerSwipeUp?.call();
            }
          }
        }
      }
    }
  }

  void _handlePointerUp(PointerUpEvent event) {
    _startPositions.remove(event.pointer);
    _currentPositions.remove(event.pointer);
    if (_startPositions.isEmpty) {
      _hasTriggered = false;
    }
  }

  void _handlePointerCancel(PointerCancelEvent event) {
    _startPositions.remove(event.pointer);
    _currentPositions.remove(event.pointer);
    if (_startPositions.isEmpty) {
      _hasTriggered = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final listener = Listener(
      behavior: HitTestBehavior.translucent,
      onPointerDown: _handlePointerDown,
      onPointerMove: _handlePointerMove,
      onPointerUp: _handlePointerUp,
      onPointerCancel: _handlePointerCancel,
      child: widget.child,
    );

    if (widget.allowSingleFingerHorizontal) {
      return GestureDetector(
        behavior: HitTestBehavior.translucent,
        onHorizontalDragEnd: (details) {
          if (_hasTriggered) return;
          final vx = details.primaryVelocity ?? 0.0;
          if (vx > 250) {
            widget.onTwoFingerSwipeRight?.call();
          } else if (vx < -250) {
            widget.onTwoFingerSwipeLeft?.call();
          }
        },
        child: listener,
      );
    }

    return listener;
  }
}
