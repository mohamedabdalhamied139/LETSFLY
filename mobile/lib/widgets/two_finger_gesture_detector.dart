import 'package:flutter/material.dart';

/// Global multi-touch gesture detector detecting 4-way two-finger swipes:
/// - Swipe Right: Open Activity Log & Chat
/// - Swipe Left: Announce Top card / Table state (matches 'R' in Windows)
/// - Swipe Up: Announce who has the turn & remaining time (matches 'T' in Windows)
/// - Swipe Down: Spacebar action (draw card, roll dice, draw tile) (matches Space in Windows)
class TwoFingerSwipeDetector extends StatefulWidget {
  final Widget child;
  final VoidCallback? onTwoFingerSwipeRight;
  final VoidCallback? onTwoFingerSwipeLeft;
  final VoidCallback? onTwoFingerSwipeUp;
  final VoidCallback? onTwoFingerSwipeDown;

  const TwoFingerSwipeDetector({
    super.key,
    required this.child,
    this.onTwoFingerSwipeRight,
    this.onTwoFingerSwipeLeft,
    this.onTwoFingerSwipeUp,
    this.onTwoFingerSwipeDown,
  });

  @override
  State<TwoFingerSwipeDetector> createState() => _TwoFingerSwipeDetectorState();
}

class _TwoFingerSwipeDetectorState extends State<TwoFingerSwipeDetector> {
  final Map<int, Offset> _startPositions = {};
  final Map<int, Offset> _currentPositions = {};
  bool _hasTriggered = false;

  static const double _swipeThreshold = 45.0;

  void _handlePointerDown(PointerDownEvent event) {
    _startPositions[event.pointer] = event.position;
    _currentPositions[event.pointer] = event.position;
    if (_startPositions.length != 2) {
      _hasTriggered = false;
    }
  }

  void _handlePointerMove(PointerMoveEvent event) {
    if (_startPositions.containsKey(event.pointer)) {
      _currentPositions[event.pointer] = event.position;
    }

    if (_startPositions.length == 2 && !_hasTriggered) {
      final p1Id = _startPositions.keys.first;
      final p2Id = _startPositions.keys.last;

      if (_currentPositions.containsKey(p1Id) && _currentPositions.containsKey(p2Id)) {
        final start1 = _startPositions[p1Id]!;
        final start2 = _startPositions[p2Id]!;
        final curr1 = _currentPositions[p1Id]!;
        final curr2 = _currentPositions[p2Id]!;

        final dx1 = curr1.dx - start1.dx;
        final dx2 = curr2.dx - start2.dx;
        final dy1 = curr1.dy - start1.dy;
        final dy2 = curr2.dy - start2.dy;

        // Both fingers must move in the same general direction
        final avgDx = (dx1 + dx2) / 2.0;
        final avgDy = (dy1 + dy2) / 2.0;

        if (avgDx.abs() > _swipeThreshold || avgDy.abs() > _swipeThreshold) {
          if (avgDx.abs() > avgDy.abs()) {
            // Horizontal swipe
            if (avgDx > _swipeThreshold && dx1 > 0 && dx2 > 0) {
              _hasTriggered = true;
              widget.onTwoFingerSwipeRight?.call();
            } else if (avgDx < -_swipeThreshold && dx1 < 0 && dx2 < 0) {
              _hasTriggered = true;
              widget.onTwoFingerSwipeLeft?.call();
            }
          } else {
            // Vertical swipe
            if (avgDy > _swipeThreshold && dy1 > 0 && dy2 > 0) {
              _hasTriggered = true;
              widget.onTwoFingerSwipeDown?.call();
            } else if (avgDy < -_swipeThreshold && dy1 < 0 && dy2 < 0) {
              _hasTriggered = true;
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
    return Listener(
      behavior: HitTestBehavior.translucent,
      onPointerDown: _handlePointerDown,
      onPointerMove: _handlePointerMove,
      onPointerUp: _handlePointerUp,
      onPointerCancel: _handlePointerCancel,
      child: widget.child,
    );
  }
}
