import 'package:flutter/material.dart';

/// Callback signatures for TableVerse gestures
typedef GestureActionCallback = void Function();

/// Custom gesture recognizer wrapper implementing the user's explicit touch mapping:
/// - Two-finger swipe Left: Query table cards/dice ('R')
/// - Two-finger swipe Up: Table/time info ('T')
/// - Single swipe Right: Open Activity Log (all tables EXCEPT Tennis)
/// - Single swipe Down: Space key (UNO & Domino only)
///
/// For Tennis:
/// - Single swipe Left: Move to Left Lane
/// - Single swipe Right: Move to Right Lane
/// - Single swipe Up: Hit / Serve ball
/// - Single swipe Down: Open Activity Log
class TableGestureDetector extends StatefulWidget {
  final Widget child;
  final bool isTennis;
  final bool isUnoOrDomino;
  final GestureActionCallback? onQueryTable; // Two-finger swipe Left ('R')
  final GestureActionCallback? onTableInfo;  // Two-finger swipe Up ('T')
  final GestureActionCallback? onOpenLog;    // Swipe Right (or Down in Tennis)
  final GestureActionCallback? onSpaceKey;   // Swipe Down (UNO/Domino)
  final GestureActionCallback? onTennisLeft; // Tennis Left
  final GestureActionCallback? onTennisRight;// Tennis Right
  final GestureActionCallback? onTennisUp;   // Tennis Hit / Serve

  const TableGestureDetector({
    super.key,
    required this.child,
    this.isTennis = false,
    this.isUnoOrDomino = false,
    this.onQueryTable,
    this.onTableInfo,
    this.onOpenLog,
    this.onSpaceKey,
    this.onTennisLeft,
    this.onTennisRight,
    this.onTennisUp,
  });

  @override
  State<TableGestureDetector> createState() => _TableGestureDetectorState();
}

class _TableGestureDetectorState extends State<TableGestureDetector> {
  int _pointerCount = 0;
  Offset? _startOffset;

  @override
  Widget build(BuildContext context) {
    return Listener(
      onPointerDown: (event) {
        _pointerCount++;
        _startOffset ??= event.position;
      },
      onPointerUp: (event) {
        if (_startOffset != null) {
          final delta = event.position - _startOffset!;
          _handleGesture(delta, _pointerCount);
        }
        _pointerCount = (_pointerCount - 1).clamp(0, 10);
        if (_pointerCount == 0) {
          _startOffset = null;
        }
      },
      onPointerCancel: (event) {
        _pointerCount = (_pointerCount - 1).clamp(0, 10);
        if (_pointerCount == 0) {
          _startOffset = null;
        }
      },
      child: widget.child,
    );
  }

  void _handleGesture(Offset delta, int pointerCount) {
    const double minDistance = 50.0;
    final double dx = delta.dx;
    final double dy = delta.dy;

    if (dx.abs() < minDistance && dy.abs() < minDistance) {
      return;
    }

    final bool isHorizontal = dx.abs() > dy.abs();

    if (pointerCount >= 2) {
      // Two-finger gestures
      if (isHorizontal && dx < -minDistance) {
        // Two-finger swipe Left -> R (استعلام عن الأرض)
        widget.onQueryTable?.call();
      } else if (!isHorizontal && dy < -minDistance) {
        // Two-finger swipe Up -> T (معلومات الطاولة)
        widget.onTableInfo?.call();
      }
      return;
    }

    // Single-finger gestures
    if (widget.isTennis) {
      if (isHorizontal) {
        if (dx < -minDistance) {
          widget.onTennisLeft?.call();
        } else if (dx > minDistance) {
          widget.onTennisRight?.call();
        }
      } else {
        if (dy < -minDistance) {
          widget.onTennisUp?.call();
        } else if (dy > minDistance) {
          // In Tennis: Swipe Down opens Activity Log
          widget.onOpenLog?.call();
        }
      }
      return;
    }

    // Standard Games (Non-Tennis)
    if (isHorizontal) {
      if (dx > minDistance) {
        // Single swipe Right -> Open Activity Log
        widget.onOpenLog?.call();
      }
    } else {
      if (dy > minDistance && widget.isUnoOrDomino) {
        // Single swipe Down -> Space Key (UNO & Domino only)
        widget.onSpaceKey?.call();
      }
    }
  }
}
