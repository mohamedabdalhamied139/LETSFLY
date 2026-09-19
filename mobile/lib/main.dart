import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'core/app_theme.dart';
import 'core/localization.dart';
import 'services/api_service.dart';
import 'services/auth_storage_service.dart';
import 'views/auth_view.dart';
import 'views/home_view.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize API service base URL from storage
  await ApiService.instance.init();

  // Pre-load default Arabic locale dictionary
  await LocalizationService.instance.loadLanguage('ar');

  runApp(const TableVerseMobileApp());
}

class TableVerseMobileApp extends StatelessWidget {
  const TableVerseMobileApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'TableVerse',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      locale: const Locale('ar'),
      supportedLocales: const [
        Locale('ar'),
        Locale('en'),
        Locale('fr'),
      ],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      home: const AuthView(),
    );
  }
}
