import 'package:flutter/material.dart';
import '../core/localization.dart';
import '../services/api_service.dart';
import 'home_view.dart';

class AuthView extends StatefulWidget {
  const AuthView({super.key});

  @override
  State<AuthView> createState() => _AuthViewState();
}

class _AuthViewState extends State<AuthView> {
  bool _registerMode = false;
  bool _isLoading = false;
  String _errorMessage = '';

  final _displayNameInput = TextEditingController();
  final _usernameInput = TextEditingController();
  final _passwordInput = TextEditingController();

  Future<void> _submitLogin() async {
    final username = _usernameInput.text.trim();
    final password = _passwordInput.text.trim();

    if (username.isEmpty || password.isEmpty) {
      setState(() => _errorMessage = tr('يرجى كتابة اسم المستخدم وكلمة المرور'));
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = '';
    });

    try {
      final res = await ApiService.instance.login(username, password);
      final token = res['access_token'] ?? res['token'];
      final userMap = res['user'] ?? {};
      final displayName = userMap['display_name'] ?? username;
      ApiService.instance.setToken(token);

      if (mounted) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => HomeView(userDisplayName: displayName)),
        );
      }
    } catch (e) {
      setState(() {
        _errorMessage = e.toString().replaceFirst('Exception: ', '');
      });
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _submitRegister() async {
    final displayName = _displayNameInput.text.trim();
    final username = _usernameInput.text.trim();
    final password = _passwordInput.text.trim();

    if (displayName.isEmpty || username.isEmpty || password.isEmpty) {
      setState(() => _errorMessage = tr('يرجى ملء جميع الحقول'));
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = '';
    });

    try {
      await ApiService.instance.register(username, displayName, password);
      // Auto login after register
      final res = await ApiService.instance.login(username, password);
      final token = res['access_token'] ?? res['token'];
      ApiService.instance.setToken(token);

      if (mounted) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => HomeView(userDisplayName: displayName)),
        );
      }
    } catch (e) {
      setState(() {
        _errorMessage = e.toString().replaceFirst('Exception: ', '');
      });
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _toggleMode() {
    setState(() {
      _registerMode = !_registerMode;
      _errorMessage = '';
    });
  }

  @override
  Widget build(BuildContext context) {
    final titleText = _registerMode ? tr('إنشاء حساب') : tr('تسجيل الدخول');
    final modeText = _registerMode ? tr('وضع إنشاء الحساب') : tr('وضع تسجيل الدخول');
    final toggleButtonText = _registerMode ? tr('الانتقال إلى تسجيل الدخول') : tr('الانتقال إلى إنشاء حساب');

    return Scaffold(
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24.0),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 460),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Semantics(
                  header: true,
                  label: tr('عنوان الشاشة'),
                  child: Text(
                    titleText,
                    style: const TextStyle(fontSize: 26, fontWeight: FontWeight.bold),
                    textAlign: TextAlign.center,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  modeText,
                  style: const TextStyle(fontSize: 14, color: Colors.grey),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 24),
                if (_errorMessage.isNotEmpty) ...[
                  Semantics(
                    liveRegion: true,
                    child: Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.red.shade900,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        _errorMessage,
                        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                ],
                if (_registerMode) ...[
                  Semantics(
                    label: tr('الاسم'),
                    child: TextField(
                      controller: _displayNameInput,
                      decoration: InputDecoration(
                        labelText: tr('الاسم'),
                        hintText: tr('اكتب الاسم'),
                        border: const OutlineInputBorder(),
                        prefixIcon: const Icon(Icons.badge),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                ],
                Semantics(
                  label: tr('اسم المستخدم'),
                  child: TextField(
                    controller: _usernameInput,
                    decoration: InputDecoration(
                      labelText: tr('اسم المستخدم'),
                      hintText: tr('اكتب اسم المستخدم'),
                      border: const OutlineInputBorder(),
                      prefixIcon: const Icon(Icons.person),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                Semantics(
                  label: tr('كلمة المرور'),
                  child: TextField(
                    controller: _passwordInput,
                    obscureText: true,
                    decoration: InputDecoration(
                      labelText: tr('كلمة المرور'),
                      hintText: tr('اكتب كلمة المرور'),
                      border: const OutlineInputBorder(),
                      prefixIcon: const Icon(Icons.lock),
                    ),
                  ),
                ),
                const SizedBox(height: 24),
                if (!_registerMode) ...[
                  Semantics(
                    button: true,
                    label: tr('تسجيل الدخول'),
                    child: ElevatedButton(
                      onPressed: _isLoading ? null : _submitLogin,
                      style: ElevatedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        backgroundColor: Theme.of(context).colorScheme.primary,
                        foregroundColor: Colors.white,
                      ),
                      child: _isLoading
                          ? const CircularProgressIndicator(color: Colors.white)
                          : Text(tr('تسجيل الدخول'), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                    ),
                  ),
                  const SizedBox(height: 12),
                ],
                if (_registerMode) ...[
                  Semantics(
                    button: true,
                    label: tr('إنشاء حساب'),
                    child: ElevatedButton(
                      onPressed: _isLoading ? null : _submitRegister,
                      style: ElevatedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        backgroundColor: Theme.of(context).colorScheme.primary,
                        foregroundColor: Colors.white,
                      ),
                      child: _isLoading
                          ? const CircularProgressIndicator(color: Colors.white)
                          : Text(tr('إنشاء حساب'), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                    ),
                  ),
                  const SizedBox(height: 12),
                ],
                Semantics(
                  button: true,
                  label: toggleButtonText,
                  child: OutlinedButton(
                    onPressed: _toggleMode,
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                    child: Text(toggleButtonText, style: const TextStyle(fontSize: 16)),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
