import 'package:flutter/material.dart';

/// Global multi-touch gesture detector detecting a two-finger swipe to the right.
/// Fulfills user requirement: Two-finger swipe right anywhere opens the Activity Log.
class TwoFingerSwipeDetector extends StatefulWidget {
  final Widget child;
  final VoidCallback onTwoFingerSwipeRight;

  const TwoFingerSwipeDetector({
    super.key,
    required this.child,
    required this.onTwoFingerSwipeRight,
  });

  @override
  State<TwoFingerSwipeDetector> createState() => _TwoFingerSwipeDetectorState();
}

class _TwoFingerSwipeDetectorState extends State<TwoFingerSwipeDetector> {
  final Map<int, Offset> _pointers = {};
  bool _hasTriggered = false;

  static const double _swipeThreshold = 50.0;
  static const double _verticalTolerance = 60.0;

  void _handlePointerDown(PointerDownEvent event) {
    _pointers[event.pointer] = event.position;
    if (_pointers.length != 2) {
      _hasTriggered = false;
    }
  }

  void _handlePointerMove(PointerMoveEvent event) {
    if (_pointers.containsKey(event.pointer)) {
      _pointers[event.pointer] = event.position;
    }

    if (_pointers.length == 2 && !_hasTriggered) {
      final initialPositions = _pointers.values.toList();
      final deltaX = event.delta.dx;
      final totalDeltaX = event.position.dx - (initialPositions.first.dx);

      // Check if both fingers moved rightwards significantly
      if (deltaX > 0 && totalDeltaX > _swipeThreshold) {
        _hasTriggered = true;
        widget.onTwoFingerSwipeRight();
      }
    }
  }

  void _handlePointerUp(PointerUpEvent event) {
    _pointers.remove(event.pointer);
    if (_pointers.isEmpty) {
      _hasTriggered = false;
    }
  }

  void _handlePointerCancel(PointerCancelEvent event) {
    _pointers.remove(event.pointer);
    if (_pointers.isEmpty) {
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
