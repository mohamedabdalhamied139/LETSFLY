import 'package:flutter/material.dart';
import '../core/localization.dart';
import '../core/sound_service.dart';
import '../services/api_service.dart';

class SettingsDialog extends StatefulWidget {
  const SettingsDialog({super.key});

  @override
  State<SettingsDialog> createState() => _SettingsDialogState();
}

class _SettingsDialogState extends State<SettingsDialog> with SingleTickerProviderStateMixin {
  late TabController _tabController;

  // General settings
  bool _autoLogin = true;
  bool _keepCredentials = true;
  String _language = 'ar';

  // Audio settings
  bool _autoVoiceJoin = false;
  bool _muteAllSounds = false;
  double _effectsVolume = 1.0;
  double _gameVolume = 1.0;

  // Speech settings
  bool _muteSpeechAll = false;
  final Map<String, String> _speechModes = {
    'friends': 'speech_and_sound',
    'invitations': 'speech_and_sound',
    'table_chat': 'speech_and_sound',
    'private_messages': 'speech_and_sound',
    'game_events': 'speech_and_sound',
  };

  // Privacy settings
  String _pmPolicy = 'everyone';
  String _invitePolicy = 'everyone';
  String _joinPolicy = 'everyone';

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 5, vsync: this);
    _language = LocalizationService.instance.currentLanguage;
    _effectsVolume = SoundService.instance.volume;
    _gameVolume = SoundService.instance.volume;
    _muteAllSounds = SoundService.instance.isMuted;
  }

  Future<void> _saveSettings() async {
    SoundService.instance.setVolume(_effectsVolume);
    SoundService.instance.setMuted(_muteAllSounds);

    if (_language != LocalizationService.instance.currentLanguage) {
      await LocalizationService.instance.loadLanguage(_language);
    }

    try {
      await ApiService.instance.updatePrivacy({
        'pm_policy': _pmPolicy,
        'invite_policy': _invitePolicy,
        'join_policy': _joinPolicy,
      });
    } catch (_) {}

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(tr('تم حفظ الإعدادات بنجاح'))),
      );
      Navigator.of(context).pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF1E1E1E),
      appBar: AppBar(
        title: Text(tr('الإعدادات')),
        backgroundColor: const Color(0xFF2D2D2D),
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          tabs: [
            Tab(text: tr('عام')),
            Tab(text: tr('الصوت')),
            Tab(text: tr('النطق')),
            Tab(text: tr('الخصوصية')),
            Tab(text: tr('الألعاب')),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildGeneralTab(),
          _buildAudioTab(),
          _buildSpeechTab(),
          _buildPrivacyTab(),
          _buildGamesTab(),
        ],
      ),
      bottomNavigationBar: Container(
        color: const Color(0xFF2D2D2D),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.end,
          children: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: Text(tr('إلغاء'), style: const TextStyle(color: Colors.white70)),
            ),
            const SizedBox(width: 8),
            ElevatedButton(
              onPressed: _saveSettings,
              style: ElevatedButton.styleFrom(backgroundColor: Colors.blueAccent),
              child: Text(tr('موافق'), style: const TextStyle(color: Colors.white)),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildGeneralTab() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        SwitchListTile(
          title: Text(tr('تسجيل الدخول تلقائيًا'), style: const TextStyle(color: Colors.white)),
          value: _autoLogin,
          onChanged: (v) => setState(() => _autoLogin = v),
        ),
        SwitchListTile(
          title: Text(tr('حفظ بيانات الدخول'), style: const TextStyle(color: Colors.white)),
          value: _keepCredentials,
          onChanged: (v) => setState(() => _keepCredentials = v),
        ),
        const SizedBox(height: 16),
        ListTile(
          title: Text(tr('اللغة'), style: const TextStyle(color: Colors.white)),
          trailing: DropdownButton<String>(
            value: _language,
            dropdownColor: const Color(0xFF2D2D2D),
            style: const TextStyle(color: Colors.white),
            items: [
              DropdownMenuItem(value: 'ar', child: Text(tr('العربية'))),
              DropdownMenuItem(value: 'en', child: Text(tr('English'))),
              DropdownMenuItem(value: 'fr', child: Text(tr('Français'))),
            ],
            onChanged: (v) {
              if (v != null) setState(() => _language = v);
            },
          ),
        ),
      ],
    );
  }

  Widget _buildAudioTab() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        SwitchListTile(
          title: Text(tr('الانضمام للمحادثة الصوتية تلقائيًا'), style: const TextStyle(color: Colors.white)),
          value: _autoVoiceJoin,
          onChanged: (v) => setState(() => _autoVoiceJoin = v),
        ),
        SwitchListTile(
          title: Text(tr('كتم كل الأصوات'), style: const TextStyle(color: Colors.white)),
          value: _muteAllSounds,
          onChanged: (v) => setState(() => _muteAllSounds = v),
        ),
        const Divider(color: Colors.white24),
        Opacity(
          opacity: _muteAllSounds ? 0.4 : 1.0,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Text(tr('المؤثرات'), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
              ),
              Slider(
                value: _effectsVolume,
                onChanged: _muteAllSounds ? null : (v) => setState(() => _effectsVolume = v),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Text(tr('أصوات اللعبة'), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
              ),
              Slider(
                value: _gameVolume,
                onChanged: _muteAllSounds ? null : (v) => setState(() => _gameVolume = v),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildSpeechTab() {
    final speechEvents = {
      'friends': 'الأصدقاء المتصلين',
      'invitations': 'دعوات اللعب',
      'table_chat': 'دردشة الطاولة',
      'private_messages': 'الرسائل الخاصة',
      'game_events': 'أحداث اللعبة',
    };

    final speechOptions = {
      'speech_and_sound': 'الناطق والصوت',
      'speech': 'الناطق فقط',
      'sound_only': 'الصوت فقط',
      'none': 'لا شيء',
    };

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        SwitchListTile(
          title: Text(tr('كتم الناطق بالكامل'), style: const TextStyle(color: Colors.white)),
          value: _muteSpeechAll,
          onChanged: (v) => setState(() => _muteSpeechAll = v),
        ),
        const Divider(color: Colors.white24),
        ...speechEvents.entries.map((entry) {
          final currentVal = _speechModes[entry.key] ?? 'speech_and_sound';
          return Opacity(
            opacity: _muteSpeechAll ? 0.4 : 1.0,
            child: ListTile(
              title: Text(tr(entry.value), style: const TextStyle(color: Colors.white)),
              trailing: DropdownButton<String>(
                value: currentVal,
                dropdownColor: const Color(0xFF2D2D2D),
                style: const TextStyle(color: Colors.white),
                items: speechOptions.entries.map((opt) {
                  return DropdownMenuItem(value: opt.key, child: Text(tr(opt.value)));
                }).toList(),
                onChanged: _muteSpeechAll
                    ? null
                    : (val) {
                        if (val != null) {
                          setState(() => _speechModes[entry.key] = val);
                        }
                      },
              ),
            ),
          );
        }).toList(),
      ],
    );
  }

  Widget _buildPrivacyTab() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        ListTile(
          title: Text(tr('من يمكنه مراسلتي'), style: const TextStyle(color: Colors.white)),
          trailing: DropdownButton<String>(
            value: _pmPolicy,
            dropdownColor: const Color(0xFF2D2D2D),
            style: const TextStyle(color: Colors.white),
            items: [
              DropdownMenuItem(value: 'everyone', child: Text(tr('الجميع'))),
              DropdownMenuItem(value: 'friends', child: Text(tr('الأصدقاء فقط'))),
              DropdownMenuItem(value: 'nobody', child: Text(tr('لا أحد'))),
            ],
            onChanged: (v) {
              if (v != null) setState(() => _pmPolicy = v);
            },
          ),
        ),
        ListTile(
          title: Text(tr('من يمكنه دعوتي للعب'), style: const TextStyle(color: Colors.white)),
          trailing: DropdownButton<String>(
            value: _invitePolicy,
            dropdownColor: const Color(0xFF2D2D2D),
            style: const TextStyle(color: Colors.white),
            items: [
              DropdownMenuItem(value: 'everyone', child: Text(tr('الجميع'))),
              DropdownMenuItem(value: 'friends', child: Text(tr('الأصدقاء فقط'))),
              DropdownMenuItem(value: 'nobody', child: Text(tr('لا أحد'))),
            ],
            onChanged: (v) {
              if (v != null) setState(() => _invitePolicy = v);
            },
          ),
        ),
        ListTile(
          title: Text(tr('من يمكنه الانضمام لطاولتي'), style: const TextStyle(color: Colors.white)),
          trailing: DropdownButton<String>(
            value: _joinPolicy,
            dropdownColor: const Color(0xFF2D2D2D),
            style: const TextStyle(color: Colors.white),
            items: [
              DropdownMenuItem(value: 'everyone', child: Text(tr('الجميع'))),
              DropdownMenuItem(value: 'friends', child: Text(tr('الأصدقاء فقط'))),
            ],
            onChanged: (v) {
              if (v != null) setState(() => _joinPolicy = v);
            },
          ),
        ),
      ],
    );
  }

  Widget _buildGamesTab() {
    final games = [
      'UNO',
      'DOMINO',
      'AMERICAN_DOMINO',
      'FARKLE',
      'SCOPA',
      'NINETY_NINE',
      'SNAKES_LADDERS',
      'THIEF_HUNT',
      'TENNIS',
    ];

    final gameTitles = {
      'UNO': 'أونو',
      'DOMINO': 'دومينو كلاسيك',
      'AMERICAN_DOMINO': 'دومينو أمريكاني',
      'FARKLE': 'فاركل',
      'SCOPA': 'إسكوبا',
      'NINETY_NINE': 'تسعة وتسعون',
      'SNAKES_LADDERS': 'السلم والثعبان',
      'THIEF_HUNT': 'مطاردة اللص',
      'TENNIS': 'التنس',
    };

    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: games.length,
      separatorBuilder: (_, __) => const Divider(color: Colors.white24),
      itemBuilder: (context, idx) {
        final g = games[idx];
        final title = tr(gameTitles[g] ?? g);

        return ListTile(
          title: Text(title, style: const TextStyle(color: Colors.white)),
          trailing: const Icon(Icons.arrow_forward_ios, color: Colors.white54, size: 16),
          onTap: () {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(tr('إعدادات {title} الافتراضية محددة', {'title': title}))),
            );
          },
        );
      },
    );
  }
}
