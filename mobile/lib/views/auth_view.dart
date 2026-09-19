import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import '../core/accessibility_manager.dart';
import '../core/app_theme.dart';
import '../core/localization.dart';
import '../core/sound_service.dart';
import '../services/api_service.dart';
import '../services/auth_storage_service.dart';
import '../widgets/two_finger_gesture_detector.dart';
import 'activity_log_widget.dart';
import 'home_view.dart';

/// Accessible dialog to switch between stored accounts or remove saved accounts.
/// 100% parity with Windows AccountSwitcherDialog in client/views/auth_view.py.
class AccountSwitcherDialog extends StatefulWidget {
  const AccountSwitcherDialog({super.key});

  @override
  State<AccountSwitcherDialog> createState() => _AccountSwitcherDialogState();
}

class _AccountSwitcherDialogState extends State<AccountSwitcherDialog> {
  List<Map<String, dynamic>> _profiles = [];
  Map<String, dynamic>? _selectedAccount;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadProfiles();
  }

  Future<void> _loadProfiles() async {
    setState(() => _isLoading = true);
    try {
      final profiles = await AuthStorageService.instance.loadAllAccounts();
      setState(() {
        _profiles = profiles;
        if (profiles.isNotEmpty) {
          _selectedAccount = profiles.firstWhere(
            (p) => p['is_active'] == true,
            orElse: () => profiles.first,
          );
        }
      });
    } catch (_) {} finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _removeAccount(String username) async {
    await AuthStorageService.instance.removeAccount(username);
    await AccessibilityManager.instance.announce(tr('تم حذف الحساب {name} من الجهاز.', {'name': username}));
    await _loadProfiles();
    if (_profiles.isEmpty && mounted) {
      Navigator.of(context).pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: AppColors.surface,
      shape: RoundedRectangleBorder(
        side: const BorderSide(color: AppColors.border),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Container(
        padding: const EdgeInsets.all(16),
        constraints: const BoxConstraints(maxWidth: 420, maxHeight: 480),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              tr('تبديل الحساب'),
              style: const TextStyle(
                color: AppColors.textPrimary,
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              tr('اختر حسابًا لتسجيل الدخول به:'),
              style: const TextStyle(color: AppColors.textSecondary, fontSize: 13),
            ),
            const Divider(color: AppColors.border, height: 24),
            Expanded(
              child: _isLoading
                  ? const Center(child: CircularProgressIndicator())
                  : _profiles.isEmpty
                      ? Center(
                          child: Text(
                            tr('لا توجد حسابات محفوظة على هذا الجهاز.'),
                            style: const TextStyle(color: AppColors.textSecondary),
                          ),
                        )
                      : ListView.separated(
                          itemCount: _profiles.length,
                          separatorBuilder: (_, __) =>
                              const Divider(height: 1, color: AppColors.border),
                          itemBuilder: (context, index) {
                            final p = _profiles[index];
                            final u = p['username'] ?? '';
                            final d = p['display_name'] ?? u;
                            final isAct = p['is_active'] == true;
                            final isSelected = _selectedAccount?['username'] == u;
                            final tagStr = isAct ? '[${tr('[الحالي]')}] ' : '';
                            final title = '$tagStr$d ($u)';

                            return Semantics(
                              label: title,
                              selected: isSelected,
                              button: true,
                              excludeSemantics: true,
                              child: ListTile(
                                tileColor: isSelected ? AppColors.accent.withOpacity(0.2) : AppColors.surface,
                                title: Text(
                                  title,
                                  style: TextStyle(
                                    color: isAct ? Colors.greenAccent : AppColors.textPrimary,
                                    fontWeight: isAct ? FontWeight.bold : FontWeight.normal,
                                    fontSize: 14,
                                  ),
                                ),
                                trailing: IconButton(
                                  icon: const Icon(Icons.delete_outline, color: Colors.redAccent, size: 20),
                                  tooltip: tr('حذف الحساب من القائمة'),
                                  onPressed: () => _removeAccount(u),
                                ),
                                onTap: () {
                                  setState(() => _selectedAccount = p);
                                },
                              ),
                            );
                          },
                        ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: ElevatedButton(
                    onPressed: _selectedAccount == null
                        ? null
                        : () => Navigator.of(context).pop(_selectedAccount),
                    child: Text(tr('تسجيل الدخول بهذا الحساب')),
                  ),
                ),
                const SizedBox(width: 8),
                TextButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: Text(tr('إلغاء')),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Accessible, clearly separated Login and Registration screen.
/// 100% parity with Windows client client/views/auth_view.py.
class AuthView extends StatefulWidget {
  const AuthView({super.key});

  @override
  State<AuthView> createState() => _AuthViewState();
}

class _AuthViewState extends State<AuthView> {
  final TextEditingController _usernameController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  final TextEditingController _displayNameController = TextEditingController();

  bool _registerMode = false;
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _checkAutoLogin();
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    _displayNameController.dispose();
    super.dispose();
  }

  Future<void> _checkAutoLogin() async {
    final activeAccount = await AuthStorageService.instance.loadActiveAccount();
    if (activeAccount != null) {
      final token = activeAccount['token']?.toString();
      final username = activeAccount['username']?.toString() ?? '';
      final password = activeAccount['password']?.toString() ?? '';
      final displayName = activeAccount['display_name']?.toString() ?? username;

      _usernameController.text = username;
      _passwordController.text = password;

      if (token != null && token.isNotEmpty) {
        ApiService.instance.setToken(token);
        if (mounted) {
          Navigator.of(context).pushReplacement(
            MaterialPageRoute(
              builder: (_) => HomeView(userDisplayName: displayName),
            ),
          );
        }
      }
    }
  }

  void _toggleMode() {
    setState(() {
      _registerMode = !_registerMode;
    });
    final modeAnnouncement = _registerMode ? tr('شاشة إنشاء الحساب.') : tr('شاشة تسجيل الدخول.');
    AccessibilityManager.instance.announce(modeAnnouncement);
  }

  Future<void> _handleLogin() async {
    final u = _usernameController.text.trim();
    final p = _passwordController.text;

    if (u.isEmpty || p.isEmpty) {
      await AccessibilityManager.instance.announce(tr('اكتب اسم المستخدم ثم كلمة المرور.'));
      return;
    }

    setState(() => _isLoading = true);
    SoundService.instance.playLooping('CONNECTING');
    try {
      final res = await ApiService.instance.login(u, p);
      SoundService.instance.stopLooping('CONNECTING');
      SoundService.instance.playSound('CONNECTED');

      final token = (res is Map) ? (res['access_token'] ?? res['token'])?.toString() ?? '' : '';
      final displayName = res['user']?['display_name'] ?? res['display_name'] ?? u;
      final userId = int.tryParse((res['user']?['id'] ?? res['id'])?.toString() ?? '0');

      await AuthStorageService.instance.saveActiveAccount(
        id: userId,
        username: u,
        password: p,
        displayName: displayName,
        token: token,
      );

      if (mounted) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(
            builder: (_) => HomeView(userDisplayName: displayName),
          ),
        );
      }
    } catch (e) {
      SoundService.instance.stopLooping('CONNECTING');
      String msg = tr('فشل تسجيل الدخول. تأكد من صحة البيانات.');
      if (e is DioException) {
        if (e.type == DioExceptionType.connectionTimeout ||
            e.type == DioExceptionType.sendTimeout ||
            e.type == DioExceptionType.receiveTimeout ||
            e.type == DioExceptionType.connectionError) {
          msg = tr('تعذر الاتصال بالخادم. يرجى التحقق من اتصال الإنترنت أو إعدادات الخادم.');
        } else if (e.response?.statusCode == 401) {
          msg = tr('اسم المستخدم أو كلمة المرور غير صحيحة.');
        } else if (e.response?.data is Map && (e.response!.data as Map).containsKey('detail')) {
          final detail = (e.response!.data as Map)['detail'];
          if (detail != null && detail.toString().isNotEmpty) {
            msg = detail.toString();
          }
        }
      }
      await AccessibilityManager.instance.announce(msg);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(msg), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _handleRegister() async {
    final d = _displayNameController.text.trim();
    final u = _usernameController.text.trim();
    final p = _passwordController.text;

    if (d.isEmpty || u.isEmpty || p.isEmpty) {
      await AccessibilityManager.instance.announce(tr('اكتب الاسم واسم المستخدم وكلمة المرور.'));
      return;
    }

    setState(() => _isLoading = true);
    SoundService.instance.playLooping('CONNECTING');
    try {
      final res = await ApiService.instance.register(u, p, d);
      SoundService.instance.stopLooping('CONNECTING');
      SoundService.instance.playSound('CONNECTED');

      final token = (res is Map) ? (res['access_token'] ?? res['token'])?.toString() ?? '' : '';
      final displayName = res['user']?['display_name'] ?? res['display_name'] ?? d;
      final userId = int.tryParse((res['user']?['id'] ?? res['id'])?.toString() ?? '0');

      await AuthStorageService.instance.saveActiveAccount(
        id: userId,
        username: u,
        password: p,
        displayName: displayName,
        token: token,
      );

      if (mounted) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(
            builder: (_) => HomeView(userDisplayName: displayName),
          ),
        );
      }
    } catch (e) {
      SoundService.instance.stopLooping('CONNECTING');
      String msg = tr('فشل إنشاء الحساب. قد يكون اسم المستخدم مستخدمًا بالفعل.');
      if (e is DioException) {
        if (e.type == DioExceptionType.connectionTimeout ||
            e.type == DioExceptionType.sendTimeout ||
            e.type == DioExceptionType.receiveTimeout ||
            e.type == DioExceptionType.connectionError) {
          msg = tr('تعذر الاتصال بالخادم. يرجى التحقق من اتصال الإنترنت أو إعدادات الخادم.');
        } else if (e.response?.statusCode == 409) {
          msg = tr('اسم المستخدم مستخدم بالفعل.');
        } else if (e.response?.data is Map && (e.response!.data as Map).containsKey('detail')) {
          final detail = (e.response!.data as Map)['detail'];
          if (detail != null && detail.toString().isNotEmpty) {
            msg = detail.toString();
          }
        }
      }
      await AccessibilityManager.instance.announce(msg);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(msg), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _showAccountSwitcher() async {
    final selected = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => const AccountSwitcherDialog(),
    );

    if (selected != null) {
      final u = selected['username']?.toString() ?? '';
      final p = selected['password']?.toString() ?? '';
      _usernameController.text = u;
      _passwordController.text = p;
      await _handleLogin();
    }
  }

  Future<void> _showServerSettings() async {
    final controller = TextEditingController(text: ApiService.instance.baseUrl);
    final changed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: Text(tr('إعدادات الخادم'), style: const TextStyle(color: AppColors.textPrimary)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              tr('عنوان خادم اللعبة:'),
              style: const TextStyle(color: AppColors.textSecondary, fontSize: 13),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: controller,
              style: const TextStyle(color: AppColors.textPrimary),
              decoration: const InputDecoration(
                hintText: ApiService.defaultBaseUrl,
              ),
            ),
            const SizedBox(height: 12),
            TextButton(
              onPressed: () {
                controller.text = ApiService.defaultBaseUrl;
              },
              child: Text(tr('استعادة العنوان الافتراضي')),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(tr('إلغاء')),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(tr('حفظ')),
          ),
        ],
      ),
    );

    if (changed == true) {
      final newUrl = controller.text.trim();
      if (newUrl.isNotEmpty) {
        await ApiService.instance.saveBaseUrl(newUrl);
        await AccessibilityManager.instance.announce(tr('تم حفظ عنوان الخادم.'));
      }
    }
    controller.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.dns_outlined, color: AppColors.textSecondary),
            tooltip: tr('إعدادات الخادم'),
            onPressed: _showServerSettings,
          ),
        ],
      ),
      body: TwoFingerSwipeDetector(
        onTwoFingerSwipeRight: () => ActivityLogWidget.showAsBottomSheet(context),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 440),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    // Title
                    Text(
                      tr(_registerMode ? 'إنشاء حساب' : 'تسجيل الدخول'),
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        color: AppColors.textPrimary,
                        fontSize: 26,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      tr(_registerMode ? 'وضع إنشاء الحساب' : 'وضع تسجيل الدخول'),
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: AppColors.textSecondary, fontSize: 13),
                    ),
                    const SizedBox(height: 24),

                    // Display Name (Registration mode only)
                    if (_registerMode) ...[
                      TextField(
                        controller: _displayNameController,
                        style: const TextStyle(color: AppColors.textPrimary),
                        decoration: InputDecoration(
                          labelText: tr('الاسم'),
                          hintText: tr('اكتب الاسم'),
                          prefixIcon: const Icon(Icons.badge_outlined, color: AppColors.textSecondary),
                        ),
                      ),
                      const SizedBox(height: 14),
                    ],

                    // Username Input
                    TextField(
                      controller: _usernameController,
                      style: const TextStyle(color: AppColors.textPrimary),
                      decoration: InputDecoration(
                        labelText: tr('اسم المستخدم'),
                        hintText: tr('اكتب اسم المستخدم'),
                        prefixIcon: const Icon(Icons.person_outline, color: AppColors.textSecondary),
                      ),
                    ),
                    const SizedBox(height: 14),

                    // Password Input
                    TextField(
                      controller: _passwordController,
                      obscureText: true,
                      style: const TextStyle(color: AppColors.textPrimary),
                      decoration: InputDecoration(
                        labelText: tr('كلمة المرور'),
                        hintText: tr('اكتب كلمة المرور'),
                        prefixIcon: const Icon(Icons.lock_outline, color: AppColors.textSecondary),
                      ),
                      onSubmitted: (_) => _registerMode ? _handleRegister() : _handleLogin(),
                    ),
                    const SizedBox(height: 22),

                    // Primary Action Button
                    ElevatedButton(
                      onPressed: _isLoading ? null : (_registerMode ? _handleRegister : _handleLogin),
                      style: ElevatedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                      child: _isLoading
                          ? const SizedBox(
                              height: 20,
                              width: 20,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                            )
                          : Text(
                              tr(_registerMode ? 'إنشاء حساب' : 'تسجيل الدخول'),
                              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                            ),
                    ),
                    const SizedBox(height: 12),

                    // Switch Stored Accounts Button (Login mode only)
                    if (!_registerMode) ...[
                      OutlinedButton(
                        onPressed: _isLoading ? null : _showAccountSwitcher,
                        style: OutlinedButton.styleFrom(
                          side: const BorderSide(color: AppColors.border),
                          padding: const EdgeInsets.symmetric(vertical: 13),
                        ),
                        child: Text(
                          tr('تبديل الحساب (الحسابات المحفوظة)'),
                          style: const TextStyle(color: AppColors.textPrimary),
                        ),
                      ),
                      const SizedBox(height: 12),
                    ],

                    // Toggle Mode Button
                    TextButton(
                      onPressed: _isLoading ? null : _toggleMode,
                      child: Text(
                        tr(_registerMode ? 'الانتقال إلى تسجيل الدخول' : 'الانتقال إلى إنشاء حساب'),
                        style: const TextStyle(color: AppColors.accent, fontSize: 14),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
