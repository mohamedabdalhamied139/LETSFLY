import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter/services.dart';
import '../core/localization.dart';

class _PointerTrack {
  final Offset start;
  Offset current;
  final DateTime time;

  _PointerTrack({
    required this.start,
    required this.current,
    required this.time,
  });
}

/// Accessible and multi-touch gesture detector detecting 4-way two-finger swipes:
/// - Swipe Right: Open Activity Log & Chat (in Shells)
/// - Swipe Left: Top Card / Board Announcement (in Table)
/// - Swipe Up: Announce who has the turn & remaining time (matches 'T' in Windows)
/// - Swipe Down: Spacebar action (draw card, roll dice, draw tile) (matches Space in Windows)
///
/// Also exposes these actions to Screen Readers (TalkBack / VoiceOver) via Semantics
/// so that users can execute them directly via accessibility actions if multi-touch
/// is consumed by the accessibility service.
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
  final Map<int, _PointerTrack> _pointers = {};
  final Map<int, _PointerTrack> _allTracksThisGesture = {};
  int _maxPointers = 0;
  bool _hasTriggered = false;
  DateTime? _lastTriggerTime;

  static const double _swipeThreshold = 25.0;
  static const Duration _cooldown = Duration(milliseconds: 300);

  void _handlePointerDown(PointerDownEvent event) {
    if (_pointers.isEmpty) {
      _hasTriggered = false;
      _maxPointers = 0;
      _allTracksThisGesture.clear();
    }

    final track = _PointerTrack(
      start: event.position,
      current: event.position,
      time: DateTime.now(),
    );

    _pointers[event.pointer] = track;
    _allTracksThisGesture[event.pointer] = track;

    if (_pointers.length > _maxPointers) {
      _maxPointers = _pointers.length;
    }
  }

  void _handlePointerMove(PointerMoveEvent event) {
    if (_pointers.containsKey(event.pointer)) {
      _pointers[event.pointer]!.current = event.position;
    }
    if (_allTracksThisGesture.containsKey(event.pointer)) {
      _allTracksThisGesture[event.pointer]!.current = event.position;
    }

    if (_pointers.isNotEmpty && !_hasTriggered) {
      _evaluateSwipe();
    }
  }

  void _handlePointerUp(PointerUpEvent event) {
    if (_pointers.containsKey(event.pointer)) {
      _pointers[event.pointer]!.current = event.position;
    }
    if (_allTracksThisGesture.containsKey(event.pointer)) {
      _allTracksThisGesture[event.pointer]!.current = event.position;
    }

    // Check on pointer up in case of a quick flick before lifting
    if (!_hasTriggered) {
      _evaluateSwipe();
    }

    _pointers.remove(event.pointer);
    if (_pointers.isEmpty) {
      _hasTriggered = false;
      _maxPointers = 0;
      _allTracksThisGesture.clear();
    }
  }

  void _handlePointerCancel(PointerCancelEvent event) {
    _pointers.remove(event.pointer);
    if (_pointers.isEmpty) {
      _hasTriggered = false;
      _maxPointers = 0;
      _allTracksThisGesture.clear();
    }
  }

  void _evaluateSwipe() {
    if (_hasTriggered) return;
    if (_lastTriggerTime != null && DateTime.now().difference(_lastTriggerTime!) < _cooldown) {
      return;
    }
    if (_pointers.isEmpty && _allTracksThisGesture.isEmpty) return;

    final sourceTracks = _pointers.isNotEmpty ? _pointers.values : _allTracksThisGesture.values;
    if (sourceTracks.isEmpty) return;

    double totalDx = 0.0;
    double totalDy = 0.0;
    int count = 0;

    for (final track in sourceTracks) {
      totalDx += (track.current.dx - track.start.dx);
      totalDy += (track.current.dy - track.start.dy);
      count++;
    }

    if (count == 0) return;

    final avgDx = totalDx / count;
    final avgDy = totalDy / count;

    // Minimum swipe threshold for 1-finger or multi-finger
    final threshold = count == 1 ? 40.0 : _swipeThreshold;
    if (avgDx.abs() < threshold && avgDy.abs() < threshold) {
      return;
    }

    _hasTriggered = true;
    _lastTriggerTime = DateTime.now();

    // Haptic feedback to confirm gesture recognition
    HapticFeedback.mediumImpact();

    if (avgDx.abs() > avgDy.abs()) {
      // Horizontal swipe
      if (avgDx > 0) {
        widget.onTwoFingerSwipeRight?.call();
      } else {
        widget.onTwoFingerSwipeLeft?.call();
      }
    } else {
      // Vertical swipe
      if (avgDy > 0) {
        widget.onTwoFingerSwipeDown?.call();
      } else {
        widget.onTwoFingerSwipeUp?.call();
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final actions = <CustomSemanticsAction, VoidCallback>{};

    if (widget.onTwoFingerSwipeRight != null) {
      actions[CustomSemanticsAction(label: tr('سجل الأحداث والدردشة (سحب بإصبعين لليمين)'))] = () {
        HapticFeedback.selectionClick();
        widget.onTwoFingerSwipeRight?.call();
      };
    }
    if (widget.onTwoFingerSwipeLeft != null) {
      actions[CustomSemanticsAction(label: tr('معرفة المكشوف على الطاولة (سحب بإصبعين لليسار)'))] = () {
        HapticFeedback.selectionClick();
        widget.onTwoFingerSwipeLeft?.call();
      };
    }
    if (widget.onTwoFingerSwipeUp != null) {
      actions[CustomSemanticsAction(label: tr('معرفة الدور (سحب بإصبعين لأعلى)'))] = () {
        HapticFeedback.selectionClick();
        widget.onTwoFingerSwipeUp?.call();
      };
    }
    if (widget.onTwoFingerSwipeDown != null) {
      actions[CustomSemanticsAction(label: tr('مسطرة المسافة (سحب بإصبعين لأسفل)'))] = () {
        HapticFeedback.selectionClick();
        widget.onTwoFingerSwipeDown?.call();
      };
    }

    return Semantics(
      container: true,
      customSemanticsActions: actions,
      child: Listener(
        behavior: HitTestBehavior.translucent,
        onPointerDown: _handlePointerDown,
        onPointerMove: _handlePointerMove,
        onPointerUp: _handlePointerUp,
        onPointerCancel: _handlePointerCancel,
        child: widget.child,
      ),
    );
  }
}
