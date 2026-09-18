import 'package:flutter/material.dart';

abstract class GameWidgetAdapter extends Widget {
  const GameWidgetAdapter({super.key});

  void handleEvent(Map<String, dynamic> event);
}
