import 'package:flutter/material.dart';
import '../core/app_theme.dart';
import '../core/localization.dart';
import '../services/api_service.dart';
import '../services/auth_storage_service.dart';
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
  bool _rememberCredentials = true;

  final _displayNameInput = TextEditingController();
  final _usernameInput = TextEditingController();
  final _passwordInput = TextEditingController();

  @override
  void initState() {
    super.initState();
    _checkSavedAccount();
  }

  Future<void> _checkSavedAccount() async {
    try {
      final active = await AuthStorageService.instance.loadActiveAccount();
      if (active != null && mounted) {
        setState(() {
          _usernameInput.text = active['username'] ?? '';
          _passwordInput.text = active['password'] ?? '';
        });
      }
    } catch (_) {}
  }

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

      if (_rememberCredentials) {
        await AuthStorageService.instance.saveActiveAccount(
          username: username,
          password: password,
          displayName: displayName,
          token: token ?? '',
        );
      }

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

      if (_rememberCredentials) {
        await AuthStorageService.instance.saveActiveAccount(
          username: username,
          password: password,
          displayName: displayName,
          token: token ?? '',
        );
      }

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

  void _showSavedAccountsDialog() async {
    final accounts = await AuthStorageService.instance.loadAllAccounts();
    if (!mounted || accounts.isEmpty) return;

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: Text(tr('الحسابات المحفوظة'), style: const TextStyle(color: Colors.white)),
        content: SizedBox(
          width: double.maxFinite,
          child: ListView.builder(
            shrinkWrap: true,
            itemCount: accounts.length,
            itemBuilder: (_, idx) {
              final acc = accounts[idx];
              final uName = acc['username'] ?? '';
              final dName = acc['display_name'] ?? uName;
              return ListTile(
                leading: const Icon(Icons.person, color: AppColors.accent),
                title: Text(dName, style: const TextStyle(color: Colors.white)),
                subtitle: Text(uName, style: const TextStyle(color: Colors.white60)),
                onTap: () {
                  Navigator.of(ctx).pop();
                  setState(() {
                    _usernameInput.text = uName;
                    _passwordInput.text = acc['password'] ?? '';
                  });
                },
                trailing: IconButton(
                  icon: const Icon(Icons.close, color: Colors.redAccent, size: 18),
                  onPressed: () async {
                    await AuthStorageService.instance.removeAccount(uName);
                    Navigator.of(ctx).pop();
                    _showSavedAccountsDialog();
                  },
                ),
              );
            },
          ),
        ),
      ),
    );
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
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text(tr('TableVerse')),
        actions: [
          IconButton(
            icon: const Icon(Icons.switch_account),
            tooltip: tr('الحسابات المحفوظة'),
            onPressed: _showSavedAccountsDialog,
          ),
        ],
      ),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24.0),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 460),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  titleText,
                  style: const TextStyle(fontSize: 26, fontWeight: FontWeight.bold, color: Colors.white),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 4),
                Text(
                  modeText,
                  style: const TextStyle(fontSize: 14, color: Colors.white60),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 24),
                if (_errorMessage.isNotEmpty) ...[
                  Container(
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
                  const SizedBox(height: 16),
                ],
                if (_registerMode) ...[
                  TextField(
                    controller: _displayNameInput,
                    style: const TextStyle(color: Colors.white),
                    decoration: InputDecoration(
                      labelText: tr('الاسم'),
                      labelStyle: const TextStyle(color: Colors.white70),
                      border: const OutlineInputBorder(),
                      prefixIcon: const Icon(Icons.badge, color: Colors.white70),
                    ),
                  ),
                  const SizedBox(height: 16),
                ],
                TextField(
                  controller: _usernameInput,
                  style: const TextStyle(color: Colors.white),
                  decoration: InputDecoration(
                    labelText: tr('اسم المستخدم'),
                    labelStyle: const TextStyle(color: Colors.white70),
                    border: const OutlineInputBorder(),
                    prefixIcon: const Icon(Icons.person, color: Colors.white70),
                  ),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _passwordInput,
                  obscureText: true,
                  style: const TextStyle(color: Colors.white),
                  decoration: InputDecoration(
                    labelText: tr('كلمة المرور'),
                    labelStyle: const TextStyle(color: Colors.white70),
                    border: const OutlineInputBorder(),
                    prefixIcon: const Icon(Icons.lock, color: Colors.white70),
                  ),
                  onSubmitted: (_) {
                    if (!_isLoading) {
                      _registerMode ? _submitRegister() : _submitLogin();
                    }
                  },
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Checkbox(
                      value: _rememberCredentials,
                      onChanged: (val) => setState(() => _rememberCredentials = val ?? true),
                      activeColor: AppColors.accent,
                    ),
                    Text(tr('حفظ بيانات الدخول'), style: const TextStyle(color: Colors.white70)),
                  ],
                ),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: _isLoading ? null : (_registerMode ? _submitRegister : _submitLogin),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.accent,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                  child: _isLoading
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : Text(titleText, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                ),
                const SizedBox(height: 16),
                TextButton(
                  onPressed: _toggleMode,
                  child: Text(
                    toggleButtonText,
                    style: const TextStyle(color: Colors.lightBlueAccent),
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
