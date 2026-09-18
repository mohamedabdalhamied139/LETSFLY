import 'package:flutter/material.dart';
import '../core/localization.dart';
import '../services/api_service.dart';
import 'lobby_view.dart';

class AuthView extends StatefulWidget {
  const AuthView({super.key});

  @override
  State<AuthView> createState() => _AuthViewState();
}

class _AuthViewState extends State<AuthView> {
  bool _isLoginMode = true;
  bool _isLoading = false;
  String _errorMessage = '';

  final _usernameController = TextEditingController();
  final _displayNameController = TextEditingController();
  final _passwordController = TextEditingController();

  Future<void> _submit() async {
    final username = _usernameController.text.trim();
    final password = _passwordController.text.trim();
    final displayName = _displayNameController.text.trim();

    if (username.isEmpty || password.isEmpty || (!_isLoginMode && displayName.isEmpty)) {
      setState(() {
        _errorMessage = tr('يرجى ملء جميع الحقول المطلوبة');
      });
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = '';
    });

    try {
      if (_isLoginMode) {
        final res = await ApiService.instance.login(username, password);
        final token = res['access_token'] ?? res['token'];
        ApiService.instance.setToken(token);
      } else {
        await ApiService.instance.register(username, displayName, password);
        // Automatically login after successful registration
        final res = await ApiService.instance.login(username, password);
        final token = res['access_token'] ?? res['token'];
        ApiService.instance.setToken(token);
      }

      if (mounted) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const LobbyView()),
        );
      }
    } catch (e) {
      setState(() {
        _errorMessage = e.toString().replaceFirst('Exception: ', '');
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final title = _isLoginMode ? tr('تسجيل الدخول') : tr('إنشاء حساب جديد');

    return Scaffold(
      appBar: AppBar(
        title: Text(title),
        centerTitle: true,
      ),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
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
              Semantics(
                label: tr('اسم المستخدم'),
                hint: tr('أدخل اسم المستخدم بالإنجليزية'),
                child: TextField(
                  controller: _usernameController,
                  decoration: InputDecoration(
                    labelText: tr('اسم المستخدم'),
                    border: const OutlineInputBorder(),
                    prefixIcon: const Icon(Icons.person),
                  ),
                ),
              ),
              if (!_isLoginMode) ...[
                const SizedBox(height: 16),
                Semantics(
                  label: tr('الاسم الظاهر'),
                  hint: tr('الاسم الذي يراه الآخرون في الطاولة'),
                  child: TextField(
                    controller: _displayNameController,
                    decoration: InputDecoration(
                      labelText: tr('الاسم الظاهر'),
                      border: const OutlineInputBorder(),
                      prefixIcon: const Icon(Icons.badge),
                    ),
                  ),
                ),
              ],
              const SizedBox(height: 16),
              Semantics(
                label: tr('كلمة المرور'),
                hint: tr('أدخل كلمة المرور الخاصة بك'),
                child: TextField(
                  controller: _passwordController,
                  obscureText: true,
                  decoration: InputDecoration(
                    labelText: tr('كلمة المرور'),
                    border: const OutlineInputBorder(),
                    prefixIcon: const Icon(Icons.lock),
                  ),
                ),
              ),
              const SizedBox(height: 24),
              Semantics(
                button: true,
                label: title,
                child: ElevatedButton(
                  onPressed: _isLoading ? null : _submit,
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    backgroundColor: Theme.of(context).colorScheme.primary,
                    foregroundColor: Colors.white,
                  ),
                  child: _isLoading
                      ? const CircularProgressIndicator(color: Colors.white)
                      : Text(title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                ),
              ),
              const SizedBox(height: 16),
              TextButton(
                onPressed: () {
                  setState(() {
                    _isLoginMode = !_isLoginMode;
                    _errorMessage = '';
                  });
                },
                child: Text(
                  _isLoginMode
                      ? tr('ليس لديك حساب؟ إنشاء حساب جديد')
                      : tr('لديك حساب بالفعل؟ تسجيل الدخول'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
