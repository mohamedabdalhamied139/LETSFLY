import 'dart:async';
import 'package:flutter/material.dart';
import '../core/accessibility_manager.dart';
import '../core/localization.dart';
import '../services/activity_service.dart';
import '../services/api_service.dart';
import 'rooms_menu_view.dart';

/// Landing Home screen hosting RoomsMenuView with global Navigation Drawer access.
class HomeView extends StatefulWidget {
  final String userDisplayName;

  const HomeView({super.key, required this.userDisplayName});

  @override
  State<HomeView> createState() => _HomeViewState();
}

class _HomeViewState extends State<HomeView> {
  @override
  void initState() {
    super.initState();

    final greeting = tr('مرحبًا بعودتك {name}.', {'name': widget.userDisplayName});

    // 1. Announce return greeting to screen reader on startup
    AccessibilityManager.instance.announce(greeting);

    // 2. Add return greeting to ActivityLogService matching Windows client
    ActivityLogService.instance.addEvent({
      'category': 'GAMEPLAY',
      'text': greeting,
      'time': '',
    });

    _fetchRecentActivity();
  }

  Future<void> _fetchRecentActivity() async {
    try {
      final evts = await ApiService.instance.getRecentEvents();
      if (evts is List) {
        for (final e in evts) {
          if (e is Map<String, dynamic>) {
            ActivityLogService.instance.addEvent(e);
          }
        }
      }
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    // RoomsMenuView is now the direct primary home screen
    return const RoomsMenuView();
  }
}
