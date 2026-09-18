import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'core/app_theme.dart';
import 'core/localization.dart';
import 'views/auth_view.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await LocalizationService.instance.loadLanguage('ar');
  runApp(const TableVerseApp());
}

class TableVerseApp extends StatelessWidget {
  const TableVerseApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'TableVerse',
      debugShowCheckedModeBanner: false,
      locale: const Locale('ar'),
      supportedLocales: const [
        Locale('ar'),
        Locale('en'),
      ],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      theme: AppTheme.darkTheme,
      home: const AuthView(),
    );
  }
}
