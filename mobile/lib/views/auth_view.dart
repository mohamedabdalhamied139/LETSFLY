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
  List<Map<String, dynamic>> _savedAccounts = [];

  final TextEditingController _displayNameInput = TextEditingController();
  final TextEditingController _usernameInput = TextEditingController();
  final TextEditingController _passwordInput = TextEditingController();

  @override
  void initState() {
    super.initState();
    _startupCheck();
  }

  @override
  void dispose() {
    _displayNameInput.dispose();
    _usernameInput.dispose();
    _passwordInput.dispose();
    super.dispose();
  }

  /// Startup session check & auto-login
  Future<void> _startupCheck() async {
    try {
      final allAccounts = await AuthStorageService.instance.loadAllAccounts();
      if (mounted) {
        setState(() {
          _savedAccounts = allAccounts;
        });
      }

      final active = await AuthStorageService.instance.loadActiveAccount();
      if (active != null && mounted) {
        final uName = active['username'] ?? '';
        final pwd = active['password'] ?? '';
        final dName = (active['display_name'] ?? uName).toString();
        final token = active['token']?.toString();

        // Prefill credentials if available
        setState(() {
          if (uName.isNotEmpty) _usernameInput.text = uName;
          if (pwd.isNotEmpty) _passwordInput.text = pwd;
        });

        // If active account has a token, validate via ApiService.setToken and auto-navigate
        if (token != null && token.isNotEmpty) {
          ApiService.instance.setToken(token);
          if (mounted) {
            Navigator.of(context).pushReplacement(
              MaterialPageRoute(
                builder: (_) => HomeView(userDisplayName: dName),
              ),
            );
          }
        }
      }
    } catch (_) {}
  }

  Future<void> _reloadAccounts() async {
    try {
      final allAccounts = await AuthStorageService.instance.loadAllAccounts();
      if (mounted) {
        setState(() {
          _savedAccounts = allAccounts;
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
      final token = (res['access_token'] ?? res['token'])?.toString() ?? '';
      final userMap = (res['user'] is Map) ? res['user'] as Map<String, dynamic> : <String, dynamic>{};
      final displayName = (userMap['display_name'] ?? username).toString();
      ApiService.instance.setToken(token);

      if (_rememberCredentials) {
        await AuthStorageService.instance.saveActiveAccount(
          username: username,
          password: password,
          displayName: displayName,
          token: token,
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
      // Auto-login after registration
      final res = await ApiService.instance.login(username, password);
      final token = (res['access_token'] ?? res['token'])?.toString() ?? '';
      ApiService.instance.setToken(token);

      if (_rememberCredentials) {
        await AuthStorageService.instance.saveActiveAccount(
          username: username,
          password: password,
          displayName: displayName,
          token: token,
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
    if (!mounted) return;

    if (accounts.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(tr('لا توجد حسابات محفوظة على هذا الجهاز.')),
          backgroundColor: AppColors.header,
        ),
      );
      return;
    }

    setState(() => _savedAccounts = accounts);

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDialogState) {
          return AlertDialog(
            backgroundColor: AppColors.surface,
            shape: RoundedRectangleBorder(
              side: const BorderSide(color: AppColors.border, width: 1),
              borderRadius: BorderRadius.circular(8),
            ),
            title: Row(
              children: [
                const Icon(Icons.manage_accounts, color: AppColors.accent),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    tr('تبديل الحساب (الحسابات المحفوظة)'),
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ),
            content: SizedBox(
              width: 440,
              child: ListView.separated(
                shrinkWrap: true,
                itemCount: accounts.length,
                separatorBuilder: (_, __) => const Divider(color: AppColors.border, height: 1),
                itemBuilder: (_, idx) {
                  final acc = accounts[idx];
                  final uName = acc['username'] ?? '';
                  final dName = acc['display_name'] ?? uName;
                  final isActive = acc['is_active'] == true;
                  final token = acc['token']?.toString();

                  return ListTile(
                    contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    leading: CircleAvatar(
                      backgroundColor: isActive ? AppColors.accent : AppColors.header,
                      child: Icon(
                        isActive ? Icons.check : Icons.person,
                        color: Colors.white,
                        size: 20,
                      ),
                    ),
                    title: Row(
                      children: [
                        Flexible(
                          child: Text(
                            dName,
                            style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.bold,
                              fontSize: 15,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        if (isActive) ...[
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: AppColors.accent,
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text(
                              '[الحالي]',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                    subtitle: Text(
                      uName,
                      style: const TextStyle(color: AppColors.textSecondary, fontSize: 13),
                    ),
                    onTap: () async {
                      // 1-tap switch & login
                      Navigator.of(ctx).pop();
                      await AuthStorageService.instance.switchActiveAccount(uName);
                      if (!mounted) return;

                      setState(() {
                        _usernameInput.text = uName;
                        _passwordInput.text = acc['password'] ?? '';
                      });

                      if (token != null && token.isNotEmpty) {
                        ApiService.instance.setToken(token);
                        Navigator.of(context).pushReplacement(
                          MaterialPageRoute(
                            builder: (_) => HomeView(userDisplayName: dName),
                          ),
                        );
                      } else {
                        _submitLogin();
                      }
                    },
                    trailing: IconButton(
                      icon: const Icon(Icons.delete_outline, color: Colors.redAccent, size: 20),
                      tooltip: tr('حذف'),
                      onPressed: () async {
                        await AuthStorageService.instance.removeAccount(uName);
                        final updated = await AuthStorageService.instance.loadAllAccounts();
                        if (!mounted) return;
                        _reloadAccounts();
                        if (updated.isEmpty) {
                          Navigator.of(ctx).pop();
                        } else {
                          accounts.clear();
                          accounts.addAll(updated);
                          setDialogState(() {});
                        }
                      },
                    ),
                  );
                },
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(),
                child: Text(
                  tr('إلغاء'),
                  style: const TextStyle(color: AppColors.textSecondary),
                ),
              ),
            ],
          );
        },
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
        backgroundColor: AppColors.header,
        elevation: 0,
        title: Text(
          tr('TableVerse'),
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
        actions: [
          if (_savedAccounts.isNotEmpty)
            IconButton(
              icon: const Icon(Icons.switch_account),
              tooltip: tr('تبديل الحساب (الحسابات المحفوظة)'),
              onPressed: _showSavedAccountsDialog,
            ),
        ],
      ),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 20.0, vertical: 24.0),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 460),
            child: Container(
              padding: const EdgeInsets.all(28.0),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppColors.border, width: 1),
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Semantics(
                    header: true,
                    child: Text(
                      titleText,
                      style: const TextStyle(
                        fontSize: 26,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    modeText,
                    style: const TextStyle(fontSize: 14, color: AppColors.textSecondary),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 24),
                  if (_errorMessage.isNotEmpty) ...[
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: const Color(0xFF7A1D1D),
                        border: Border.all(color: Colors.redAccent, width: 1),
                        borderRadius: BorderRadius.circular(6),
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
                        labelStyle: const TextStyle(color: AppColors.textSecondary),
                        filled: true,
                        fillColor: AppColors.header,
                        border: OutlineInputBorder(
                          borderSide: const BorderSide(color: AppColors.border),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderSide: const BorderSide(color: AppColors.border),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        focusedBorder: OutlineInputBorder(
                          borderSide: const BorderSide(color: AppColors.accent, width: 1.5),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        prefixIcon: const Icon(Icons.badge, color: AppColors.textSecondary),
                      ),
                    ),
                    const SizedBox(height: 16),
                  ],
                  TextField(
                    controller: _usernameInput,
                    style: const TextStyle(color: Colors.white),
                    decoration: InputDecoration(
                      labelText: tr('اسم المستخدم'),
                      labelStyle: const TextStyle(color: AppColors.textSecondary),
                      filled: true,
                      fillColor: AppColors.header,
                      border: OutlineInputBorder(
                        borderSide: const BorderSide(color: AppColors.border),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderSide: const BorderSide(color: AppColors.border),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderSide: const BorderSide(color: AppColors.accent, width: 1.5),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      prefixIcon: const Icon(Icons.person, color: AppColors.textSecondary),
                    ),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: _passwordInput,
                    obscureText: true,
                    style: const TextStyle(color: Colors.white),
                    decoration: InputDecoration(
                      labelText: tr('كلمة المرور'),
                      labelStyle: const TextStyle(color: AppColors.textSecondary),
                      filled: true,
                      fillColor: AppColors.header,
                      border: OutlineInputBorder(
                        borderSide: const BorderSide(color: AppColors.border),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderSide: const BorderSide(color: AppColors.border),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderSide: const BorderSide(color: AppColors.accent, width: 1.5),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      prefixIcon: const Icon(Icons.lock, color: AppColors.textSecondary),
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
                        checkColor: Colors.white,
                      ),
                      GestureDetector(
                        onTap: () => setState(() => _rememberCredentials = !_rememberCredentials),
                        child: Text(
                          tr('حفظ بيانات الدخول'),
                          style: const TextStyle(color: AppColors.textSecondary),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  ElevatedButton(
                    onPressed: _isLoading ? null : (_registerMode ? _submitRegister : _submitLogin),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.accent,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(6),
                      ),
                    ),
                    child: _isLoading
                        ? const SizedBox(
                            height: 20,
                            width: 20,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                          )
                        : Text(
                            titleText,
                            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                          ),
                  ),
                  if (_savedAccounts.isNotEmpty && !_registerMode) ...[
                    const SizedBox(height: 12),
                    OutlinedButton.icon(
                      onPressed: _showSavedAccountsDialog,
                      icon: const Icon(Icons.switch_account, color: AppColors.accent, size: 18),
                      label: Text(
                        tr('تبديل الحساب (الحسابات المحفوظة)'),
                        style: const TextStyle(color: Colors.white, fontSize: 14),
                      ),
                      style: OutlinedButton.styleFrom(
                        backgroundColor: AppColors.header,
                        side: const BorderSide(color: AppColors.border),
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(6),
                        ),
                      ),
                    ),
                  ],
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
      ),
    );
  }
}
