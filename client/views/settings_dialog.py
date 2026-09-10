from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QStackedWidget,
    QWidget, QLabel, QCheckBox, QComboBox, QPushButton, QSlider,
    QListWidgetItem
)
from PySide6.QtCore import Qt
from client import settings_store
from client.audio.sound_engine import sound_engine
from client.table_framework.settings_registry import GAME_SETTINGS_REGISTRY
from client.game_preferences import load, save
from client.localization import tr, subscribe, unsubscribe, localize_widget_tree, language
from client.views.list_menu import SettingsListMenu

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("الإعدادات"))
        self.setAccessibleName(tr("الإعدادات"))
        self.resize(600, 450)
        self.settings = settings_store.load_settings()
        
        main_layout = QHBoxLayout(self)
        
        # Left navigation
        self.nav_list = QListWidget()
        self.nav_list.setAccessibleName(tr("أقسام الإعدادات"))
        self.nav_list.addItems(["عام", "الصوت", "النطق", "الخصوصية", "الألعاب"])
        self.nav_list.setMaximumWidth(150)
        
        # Right content
        self.stack = QStackedWidget()
        
        self.stack.addWidget(self._create_general_tab())
        self.stack.addWidget(self._create_audio_tab())
        self.stack.addWidget(self._create_speech_tab())
        self.stack.addWidget(self._create_privacy_tab())
        self.stack.addWidget(self._create_games_tab())
        
        self.nav_list.currentRowChanged.connect(self.stack.setCurrentIndex)
        
        # Buttons
        btn_layout = QVBoxLayout()
        self.btn_ok = QPushButton(tr("موافق"))
        self.btn_cancel = QPushButton(tr("إلغاء"))
        self.btn_apply = QPushButton(tr("تطبيق"))
        
        self.btn_ok.clicked.connect(self.accept_settings)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_apply.clicked.connect(self.apply_settings)
        
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_apply)
        btn_layout.addStretch()
        
        main_layout.addWidget(self.nav_list)
        main_layout.addWidget(self.stack)
        main_layout.addLayout(btn_layout)
        
        self.nav_list.setCurrentRow(0)
        subscribe(self._on_language_changed)
        localize_widget_tree(self)

    def _create_general_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        
        gen = self.settings.get("general", {})
        
        self.chk_auto_login = QCheckBox(tr("تسجيل الدخول تلقائيًا"))
        self.chk_auto_login.setChecked(gen.get("auto_login", True))
        
        self.chk_keep_creds = QCheckBox(tr("حفظ بيانات الدخول"))
        self.chk_keep_creds.setChecked(gen.get("keep_credentials", True))
        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel(tr("اللغة")))
        self.language_combo = QComboBox()
        self.language_combo.setAccessibleName(tr("اللغة"))
        self.language_combo.addItem(tr("لغة الجهاز"), "system")
        self.language_combo.addItem(tr("العربية"), "ar")
        self.language_combo.addItem(tr("English"), "en")
        current_lang = str(gen.get("language", "system") or "system")
        self.language_combo.setCurrentIndex({"system": 0, "ar": 1, "en": 2}.get(current_lang, 0))
        lang_row.addWidget(self.language_combo)

        l.addWidget(self.chk_auto_login)
        l.addWidget(self.chk_keep_creds)
        l.addLayout(lang_row)
        l.addStretch()
        return w

    def _create_audio_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        
        audio = self.settings.get("audio", {})
        vols = audio.get("volumes", {})
        
        self.sliders = {}
        self.chk_auto_voice_join = QCheckBox(tr("الانضمام للمحادثة الصوتية تلقائيًا"))
        self.chk_auto_voice_join.setChecked(bool(audio.get("voice_auto_join", False)))
        l.addWidget(self.chk_auto_voice_join)
        self.chk_mute_all_sounds = QCheckBox(tr("كتم كل الأصوات"))
        self.chk_mute_all_sounds.setChecked(bool(audio.get("mute_all", False)))
        self.chk_mute_all_sounds.toggled.connect(self._set_audio_options_enabled)
        l.addWidget(self.chk_mute_all_sounds)
        labels = {"effects": tr("المؤثرات"), "game": tr("أصوات اللعبة")}
        
        for k, name in labels.items():
            hl = QHBoxLayout()
            lbl = QLabel(name)
            slider = QSlider(Qt.Horizontal)
            slider.setAccessibleName(name)
            slider.setMinimum(0)
            slider.setMaximum(100)
            slider.setValue(int(vols.get(k, 1.0) * 100))
            hl.addWidget(lbl)
            hl.addWidget(slider)
            l.addLayout(hl)
            self.sliders[k] = slider
            
        self._set_audio_options_enabled(self.chk_mute_all_sounds.isChecked())
        l.addStretch()
        return w

    def _set_audio_options_enabled(self, muted: bool):
        available = not bool(muted)
        for slider in getattr(self, "sliders", {}).values():
            slider.setEnabled(available)
            base = slider.accessibleName()
            unavailable_suffix = " - " + tr("غير متاح")
            english_suffix = " - Unavailable"
            if not available and unavailable_suffix not in base and english_suffix not in base:
                slider.setAccessibleName(base + unavailable_suffix)
            elif available:
                slider.setAccessibleName(base.replace(unavailable_suffix, "").replace(english_suffix, ""))

    def _create_speech_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        
        sp = self.settings.get("speech", {})
        modes = sp.get("modes", {})
        
        self.chk_mute_all = QCheckBox(tr("كتم الناطق بالكامل"))
        self.chk_mute_all.setChecked(sp.get("mute_all", False))
        self.chk_mute_all.toggled.connect(self._set_speech_options_enabled)
        l.addWidget(self.chk_mute_all)
        
        self.speech_combos = {}
        events = {
            "friends": tr("الأصدقاء المتصلين"),
            "invitations": tr("دعوات اللعب"),
            "table_chat": tr("دردشة الطاولة"),
            "private_messages": tr("الرسائل الخاصة"),
            "game_events": tr("أحداث اللعبة")
        }
        
        options = [tr("الناطق والصوت"), tr("الناطق فقط"), tr("الصوت فقط"), tr("لا شيء")]
        opt_keys = ["speech_and_sound", "speech", "sound_only", "none"]
        
        for k, name in events.items():
            hl = QHBoxLayout()
            lbl = QLabel(name)
            combo = QComboBox()
            combo.setAccessibleName(name)
            combo.addItems(options)
            combo.setProperty("_lf_speech_base_accessible", name)
            combo.setAccessibleName(tr(name))
            curr = modes.get(k, "speech_and_sound")
            if curr in opt_keys:
                combo.setCurrentIndex(opt_keys.index(curr))
            hl.addWidget(lbl)
            hl.addWidget(combo)
            l.addLayout(hl)
            self.speech_combos[k] = combo
            
        l.addStretch()
        return w


    def _set_speech_options_enabled(self, enabled: bool):
        """Disable per-category choices while global mute is enabled."""
        available = not bool(enabled)
        for combo in getattr(self, "speech_combos", {}).values():
            combo.setEnabled(available)
            if not available:
                combo.setAccessibleName(tr("غير متاح أثناء كتم النطق بالكامل"))
            else:
                base = combo.property("_lf_speech_base_accessible") or combo.accessibleName()
                combo.setProperty("_lf_speech_base_accessible", base)
                combo.setAccessibleName(tr(base))

    def _create_privacy_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        
        pr = self.settings.get("privacy", {})
        
        self.priv_combos = {}
        events = {
            "pm_policy": tr("من يمكنه مراسلتي"),
            "invite_policy": tr("من يمكنه دعوتي للعب"),
            "join_policy": tr("من يمكنه الانضمام لطاولتي")
        }
        
        for k, name in events.items():
            hl = QHBoxLayout()
            lbl = QLabel(name)
            combo = QComboBox()
            combo.setAccessibleName(name)
            if k == "join_policy":
                options = [tr("الجميع"), tr("الأصدقاء فقط")]
                opt_keys = ["everyone", "friends"]
            else:
                options = [tr("الجميع"), tr("الأصدقاء فقط"), tr("لا أحد")]
                opt_keys = ["everyone", "friends", "nobody"]
            combo.addItems(options)
            curr = pr.get(k, "everyone")
            if curr not in opt_keys:
                curr = "everyone"
            combo.setCurrentIndex(opt_keys.index(curr))
            hl.addWidget(lbl)
            hl.addWidget(combo)
            l.addLayout(hl)
            self.priv_combos[k] = combo
            
        l.addStretch()
        return w

    def _create_games_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        
        lbl = QLabel(tr("اختر لعبة لتعديل إعداداتها:"))
        l.addWidget(lbl)
        
        self.games_list = QListWidget()
        self.games_list.setAccessibleName(tr("قائمة الألعاب"))
        for game_type, definition in GAME_SETTINGS_REGISTRY.items():
            item = QListWidgetItem(definition.title)
            item.setData(Qt.UserRole, game_type)
            self.games_list.addItem(item)
        self.games_list.itemActivated.connect(self._open_game_settings)
        l.addWidget(self.games_list)
        
        if self.games_list.count():
            self.games_list.setCurrentRow(0)
        return w

    def _open_game_settings(self, item):
        game_type = str(item.data(Qt.UserRole)).upper()
        definition = GAME_SETTINGS_REGISTRY.get(game_type)
        if not definition:
            return
        target, rules = load(game_type, definition.default_target_score, definition.default_rules)
        fields = []
        for field in definition.custom_fields:
            d = field.to_dict({"target_score": target, "rules": rules})
            fields.append(d)
        fields += [{"key": "start", "label": "حفظ", "kind": "action"}, {"key": "cancel", "label": "إلغاء", "kind": "action"}]
        menu = SettingsListMenu(self, f"إعدادات {definition.title}", fields)
        result, values = menu.show_menu(speak_text=f"إعدادات {definition.title}")
        if result == "start":
            new_target, new_rules = definition.extract_target_and_rules(values)
            save(game_type, new_target, new_rules)

    def _on_language_changed(self, _lang):
        localize_widget_tree(self)

    def closeEvent(self, event):
        unsubscribe(self._on_language_changed)
        super().closeEvent(event)

    def apply_settings(self):
        # General
        if "general" not in self.settings: self.settings["general"] = {}
        self.settings["general"]["auto_login"] = self.chk_auto_login.isChecked()
        self.settings["general"]["keep_credentials"] = self.chk_keep_creds.isChecked()
        self.settings["general"]["language"] = self.language_combo.currentData() or "system"
        
        # Audio
        if "audio" not in self.settings: self.settings["audio"] = {"volumes": {}}
        if "volumes" not in self.settings["audio"]: self.settings["audio"]["volumes"] = {}
        self.settings["audio"]["mute_all"] = self.chk_mute_all_sounds.isChecked()
        self.settings["audio"]["voice_auto_join"] = self.chk_auto_voice_join.isChecked()
        sound_engine.set_muted(self.settings["audio"]["mute_all"])
        for k, slider in self.sliders.items():
            vol = slider.value() / 100.0
            self.settings["audio"]["volumes"][k] = vol
            sound_engine.set_category_volume(k, vol)
            
        # Speech
        if "speech" not in self.settings: self.settings["speech"] = {"modes": {}}
        if "modes" not in self.settings["speech"]: self.settings["speech"]["modes"] = {}
        self.settings["speech"]["mute_all"] = self.chk_mute_all.isChecked()
        from client.accessibility.reader import reader
        reader.set_muted(self.settings["speech"]["mute_all"])
        
        opt_keys = ["speech_and_sound", "speech", "sound_only", "none"]
        for k, combo in self.speech_combos.items():
            self.settings["speech"]["modes"][k] = opt_keys[combo.currentIndex()]
            
        # Privacy
        if "privacy" not in self.settings: self.settings["privacy"] = {}
        for k, combo in self.priv_combos.items():
            if k == "join_policy":
                priv_keys = ["everyone", "friends"]
            else:
                priv_keys = ["everyone", "friends", "nobody"]
            idx = max(0, min(combo.currentIndex(), len(priv_keys) - 1))
            self.settings["privacy"][k] = priv_keys[idx]
            
        settings_store.save_settings(self.settings)
        from client.localization import set_language, localize_widget_tree, language
        set_language(self.settings["general"].get("language", "system"))
        localize_widget_tree(self)
        if self.parent() is not None:
            localize_widget_tree(self.parent())
        from client.accessibility.reader import reader
        reader.speak(tr("تم تغيير اللغة."), interrupt=True)
        
        # Send privacy to server if authenticated
        if self.parent() and hasattr(self.parent(), "api"):
            def _ignore(r): pass
            payload = self.settings["privacy"]
            if hasattr(self.parent(), "_run_async"):
                self.parent()._run_async(lambda: self.parent().api.update_privacy(payload), _ignore, _ignore)

    def accept_settings(self):
        self.apply_settings()
        self.accept()
