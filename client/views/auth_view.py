"""Accessible, clearly separated Login and Registration screens."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QDialog, QListWidget, QListWidgetItem
from PySide6.QtCore import Signal, Qt
from client.accessibility.reader import reader
from client.localization import tr, subscribe, unsubscribe, language


class AccessibleButton(QPushButton):
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.click()
            event.accept()
            return
        super().keyPressEvent(event)


class AccountSwitcherDialog(QDialog):
    """Accessible dialog to switch between stored accounts or remove saved accounts."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("تبديل الحساب"))
        self.setAccessibleName(tr("تبديل الحساب"))
        self.setModal(True)
        self.selected_account = None

        layout = QVBoxLayout(self)
        self.prompt_label = QLabel(tr("اختر حسابًا لتسجيل الدخول به:"))
        layout.addWidget(self.prompt_label)

        self.list_widget = QListWidget(self)
        self.list_widget.setAccessibleName(tr("قائمة الحسابات المحفوظة"))
        layout.addWidget(self.list_widget, 1)

        btn_row = QHBoxLayout()
        self.login_btn = QPushButton(tr("تسجيل الدخول بهذا الحساب"))
        self.remove_btn = QPushButton(tr("حذف الحساب من القائمة"))
        self.cancel_btn = QPushButton(tr("إلغاء"))
        btn_row.addWidget(self.login_btn)
        btn_row.addWidget(self.remove_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

        self.login_btn.clicked.connect(self._on_login_clicked)
        self.remove_btn.clicked.connect(self._on_remove_clicked)
        self.cancel_btn.clicked.connect(self.reject)
        self.list_widget.itemActivated.connect(self._on_item_activated)

        self._refresh_list()
        self.resize(500, 350)
        self.list_widget.setFocus()

    def _refresh_list(self):
        from client.session_store import load_all_account_profiles
        profiles = load_all_account_profiles()
        self.list_widget.clear()
        for p in profiles:
            u = p.get("username", "")
            d = p.get("display_name", u)
            is_act = p.get("is_active", False)
            raw_tag = "[الحالي] " if is_act else ""
            raw_text = f"{raw_tag}{d} ({u})"
            disp_text = tr(raw_text)
            it = QListWidgetItem(disp_text)
            it.setData(Qt.UserRole, p)
            it.setData(Qt.UserRole + 1101, raw_text)
            it.setData(Qt.UserRole + 1102, disp_text)
            self.list_widget.addItem(it)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _on_item_activated(self, item):
        self._on_login_clicked()

    def _on_login_clicked(self):
        cur = self.list_widget.currentItem()
        if not cur:
            reader.speak(tr("اختر حسابًا أولًا."), interrupt=True)
            return
        data = cur.data(Qt.UserRole)
        if isinstance(data, dict):
            from client.session_store import set_active_account_profile
            set_active_account_profile(data.get("username", ""))
            self.selected_account = data
            self.accept()

    def _on_remove_clicked(self):
        cur = self.list_widget.currentItem()
        if not cur:
            reader.speak(tr("اختر حسابًا لحذفه."), interrupt=True)
            return
        data = cur.data(Qt.UserRole)
        if isinstance(data, dict):
            u = data.get("username", "")
            from client.session_store import remove_account_profile
            remove_account_profile(u)
            reader.speak(tr(f"تم حذف الحساب {u} من الجهاز."), interrupt=True)
            self._refresh_list()
            if self.list_widget.count() == 0:
                self.reject()


class AuthView(QWidget):
    loginRequested = Signal(str, str)
    registerRequested = Signal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.title_label = QLabel(tr("تسجيل الدخول"))
        self.title_label.setAccessibleName(tr("عنوان الشاشة"))
        self.layout.addWidget(self.title_label)

        self.mode_label = QLabel(tr("وضع تسجيل الدخول"))
        self.layout.addWidget(self.mode_label)

        self.display_name_input = QLineEdit()
        self.display_name_input.setAccessibleName(tr("الاسم"))
        self.display_name_input.setPlaceholderText(tr("اكتب الاسم"))

        self.username_input = QLineEdit()
        self.username_input.setAccessibleName(tr("اسم المستخدم"))
        self.username_input.setPlaceholderText(tr("اكتب اسم المستخدم"))

        self.password_input = QLineEdit()
        self.password_input.setAccessibleName(tr("كلمة المرور"))
        self.password_input.setPlaceholderText(tr("اكتب كلمة المرور"))
        self.password_input.setEchoMode(QLineEdit.Password)

        self.layout.addWidget(self.display_name_input)
        self.layout.addWidget(self.username_input)
        self.layout.addWidget(self.password_input)

        self.login_btn = AccessibleButton(tr("تسجيل الدخول"))
        self.login_btn.clicked.connect(self._on_login_click)
        self.layout.addWidget(self.login_btn)

        self.switch_account_btn = AccessibleButton(tr("تبديل الحساب (الحسابات المحفوظة)"))
        self.switch_account_btn.clicked.connect(self._on_switch_account_click)
        self.layout.addWidget(self.switch_account_btn)

        self.register_btn = AccessibleButton(tr("إنشاء حساب"))
        self.register_btn.clicked.connect(self._on_register_click)
        self.layout.addWidget(self.register_btn)

        self.mode_btn = AccessibleButton(tr("الانتقال إلى إنشاء حساب"))
        self.mode_btn.clicked.connect(self.toggle_mode)
        self.layout.addWidget(self.mode_btn)

        self.password_input.returnPressed.connect(self._submit_current)
        self.username_input.returnPressed.connect(self._submit_current)
        self.display_name_input.returnPressed.connect(self._submit_current)
        self.setTabOrder(self.display_name_input, self.username_input)
        self.setTabOrder(self.username_input, self.password_input)
        self.setTabOrder(self.password_input, self.login_btn)
        self.setTabOrder(self.login_btn, self.switch_account_btn)
        self.setTabOrder(self.switch_account_btn, self.register_btn)
        self.setTabOrder(self.register_btn, self.mode_btn)
        self._register_mode = False
        self._refresh_mode()

        try:
            from client.session_store import load_credentials
            saved_u, saved_p = load_credentials()
            if saved_u:
                self.username_input.setText(saved_u)
            if saved_p:
                self.password_input.setText(saved_p)
        except Exception:
            pass

        subscribe(self._on_language_changed)

    def closeEvent(self, event):
        try:
            unsubscribe(self._on_language_changed)
        except Exception:
            pass
        super().closeEvent(event)

    def _on_language_changed(self, _lang: str):
        self.title_label.setAccessibleName(tr("عنوان الشاشة"))
        self.display_name_input.setAccessibleName(tr("الاسم"))
        self.display_name_input.setPlaceholderText(tr("اكتب الاسم"))
        self.username_input.setAccessibleName(tr("اسم المستخدم"))
        self.username_input.setPlaceholderText(tr("اكتب اسم المستخدم"))
        self.password_input.setAccessibleName(tr("كلمة المرور"))
        self.password_input.setPlaceholderText(tr("اكتب كلمة المرور"))
        self._refresh_mode()

    def toggle_mode(self):
        self._register_mode = not self._register_mode
        self._refresh_mode()
        first = self.display_name_input if self._register_mode else self.username_input
        first.setFocus()
        reader.speak(tr("شاشة إنشاء الحساب." if self._register_mode else "شاشة تسجيل الدخول."))

    def _refresh_mode(self):
        self.display_name_input.setVisible(self._register_mode)
        self.title_label.setText(tr("إنشاء حساب" if self._register_mode else "تسجيل الدخول"))
        self.mode_label.setText(tr("وضع إنشاء الحساب" if self._register_mode else "وضع تسجيل الدخول"))
        self.login_btn.setVisible(not self._register_mode)
        self.login_btn.setText(tr("تسجيل الدخول"))
        self.switch_account_btn.setVisible(not self._register_mode)
        self.switch_account_btn.setText(tr("تبديل الحساب (الحسابات المحفوظة)"))
        self.register_btn.setVisible(self._register_mode)
        self.register_btn.setText(tr("إنشاء حساب"))
        self.mode_btn.setText(tr("الانتقال إلى تسجيل الدخول" if self._register_mode else "الانتقال إلى إنشاء حساب"))

    def _on_switch_account_click(self):
        from client.session_store import load_all_account_profiles
        profiles = load_all_account_profiles()
        if not profiles:
            reader.speak(tr("لا توجد حسابات محفوظة على هذا الجهاز."), interrupt=True)
            return
        dlg = AccountSwitcherDialog(self)
        if dlg.exec() and dlg.selected_account:
            u = dlg.selected_account.get("username", "")
            p = dlg.selected_account.get("password", "")
            self.username_input.setText(u)
            self.password_input.setText(p)
            self.loginRequested.emit(u, p)

    def _submit_current(self):
        self._on_register_click() if self._register_mode else self._on_login_click()

    def _on_login_click(self):
        u = self.username_input.text().strip()
        p = self.password_input.text()
        if not u or not p:
            reader.speak(tr("اكتب اسم المستخدم ثم كلمة المرور."))
            return
        self.loginRequested.emit(u, p)

    def _on_register_click(self):
        d = self.display_name_input.text().strip()
        u = self.username_input.text().strip()
        p = self.password_input.text()
        if not d or not u or not p:
            reader.speak(tr("اكتب الاسم واسم المستخدم وكلمة المرور."))
            return
        self.registerRequested.emit(u, d, p)
