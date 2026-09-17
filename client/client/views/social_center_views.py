from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QLabel, QLineEdit, QTextEdit, QPushButton, QHBoxLayout, QComboBox
from PySide6.QtCore import Qt
from client.accessibility.reader import reader
from client.localization import tr, subscribe, unsubscribe, language

GAME_LABELS = {
    "UNO":"أونو", "SCOPA":"إسكوبا", "NINETY_NINE":"تسعة وتسعون", "FARKLE":"فاركل",
    "SNAKES_LADDERS":"السلم والثعبان", "DOMINO":"الدومينو", "AMERICAN_DOMINO":"الدومينو الأمريكي",
    "THIEF_HUNT":"صيد اللص", "TENNIS":"التنس"
}

class PrivateMessagesView(QDialog):
    def __init__(self, rows=None, parent=None):
        super().__init__(parent); self.setWindowTitle(tr("الرسائل الخاصة")); self.setAccessibleName(tr("الرسائل الخاصة")); self.setModal(True)
        l=QVBoxLayout(self); self.list=QListWidget(self); self.list.setAccessibleName(tr("الرسائل الخاصة")); l.addWidget(self.list)
        for r in rows or []:
            who=r.get("sender") if r.get("sender_id")!=getattr(parent,"user",{}).get("id") else r.get("recipient")
            self.list.addItem(QListWidgetItem(f"{who}: {r.get('message','')}"))
        if not self.list.count(): self.list.addItem(tr("لا توجد رسائل خاصة."))
        self.list.setCurrentRow(0); self.list.setFocus(); self.setMinimumSize(620,420)

class NotificationsView(QDialog):
    def __init__(self, rows=None, parent=None):
        super().__init__(parent); self.setWindowTitle(tr("الإشعارات")); self.setAccessibleName(tr("الإشعارات")); self.setModal(True); self.rows=list(rows or [])
        l=QVBoxLayout(self); self.list=QListWidget(self); self.list.setAccessibleName(tr("الإشعارات")); l.addWidget(self.list)
        for r in self.rows:
            raw_text = str(r.get("text", ""))
            disp_text = tr(raw_text)
            item=QListWidgetItem(disp_text); item.setData(Qt.UserRole,r)
            item.setData(Qt.UserRole + 1101, raw_text)
            item.setData(Qt.UserRole + 1102, disp_text)
            self.list.addItem(item)
        if not self.list.count(): self.list.addItem(tr("لا توجد إشعارات جديدة."))
        self.action=QPushButton(tr("إجراءات الدعوة"),self); self.action.setAccessibleName(tr("إجراء")); l.addWidget(self.action); self.action.clicked.connect(self._action)
        self.list.currentItemChanged.connect(lambda *_: self._sync_action()); self._sync_action(); self.list.setCurrentRow(0); self.list.setFocus(); self.setMinimumSize(620,420)
    def _sync_action(self):
        row=self.list.currentItem().data(Qt.UserRole) if self.list.currentItem() else None
        self.action.setEnabled(bool(isinstance(row,dict) and row.get("event_type")=="CHALLENGE_INVITATION"))
    def _action(self):
        row=self.list.currentItem().data(Qt.UserRole) if self.list.currentItem() else None
        if isinstance(row,dict) and row.get("event_type")=="CHALLENGE_INVITATION": self.done(100)
class MyProfileEditDialog(QDialog):
    """Accessible profile dialog designed as an interactive list."""
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("ملفي الشخصي"))
        self.setAccessibleName(tr("ملفي الشخصي"))
        self.setModal(True)
        self.delete_requested = False

        self._display_name = str(data.get("display_name", "")).strip()
        self._username = str(data.get("username", "")).strip()
        self._gender = str(data.get("gender", "")).strip()
        self._bio = str(data.get("bio", "")).strip()

        layout = QVBoxLayout(self)
        self.list_widget = QListWidget(self)
        self.list_widget.setAccessibleName(tr("قائمة عناصر الملف الشخصي"))
        layout.addWidget(self.list_widget, 1)

        btn_row = QHBoxLayout()
        self.save_btn = QPushButton(tr("حفظ"))
        self.cancel_btn = QPushButton(tr("إلغاء"))
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        self.list_widget.itemActivated.connect(self._on_item_activated)

        self._refresh_items()
        self.list_widget.setCurrentRow(0)
        self.list_widget.setFocus()
        self.resize(550, 380)

        subscribe(self._on_language_changed)

    def closeEvent(self, event):
        try:
            unsubscribe(self._on_language_changed)
        except Exception:
            pass
        super().closeEvent(event)

    def _on_language_changed(self, _lang: str):
        self.setWindowTitle(tr("ملفي الشخصي"))
        self.setAccessibleName(tr("ملفي الشخصي"))
        self.list_widget.setAccessibleName(tr("قائمة عناصر الملف الشخصي"))
        self.save_btn.setText(tr("حفظ"))
        self.cancel_btn.setText(tr("إلغاء"))
        self._refresh_items()

    def _refresh_items(self, keep_tag=None):
        cur_row = self.list_widget.currentRow()
        self.list_widget.clear()

        g_display = self._gender if self._gender else "غير محدد"
        b_display = self._bio if self._bio else "لا يوجد"

        items = [
            (f"الاسم: {self._display_name}", "name"),
            (f"اسم المستخدم: {self._username} (غير قابل للتعديل)", "username"),
            (f"الجنس: {g_display}", "gender"),
            (f"الحالة / البايو: {b_display}", "bio"),
            ("حذف الحساب", "delete_account"),
        ]

        for text, tag in items:
            disp_text = tr(text)
            it = QListWidgetItem(disp_text)
            it.setData(Qt.UserRole, tag)
            it.setData(Qt.UserRole + 1101, text)
            it.setData(Qt.UserRole + 1102, disp_text)
            self.list_widget.addItem(it)

        if keep_tag:
            for i in range(self.list_widget.count()):
                if self.list_widget.item(i).data(Qt.UserRole) == keep_tag:
                    self.list_widget.setCurrentRow(i)
                    return
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(max(0, min(cur_row, self.list_widget.count() - 1)))

    def _on_item_activated(self, item):
        tag = item.data(Qt.UserRole)
        from client.views.list_menu import ListMenu
        if tag == "name":
            d = QDialog(self)
            d.setWindowTitle(tr("تعديل الاسم"))
            d.setModal(True)
            dl = QVBoxLayout(d)
            dl.addWidget(QLabel(tr("اكتب الاسم الجديد:")))
            le = QLineEdit(self._display_name, d)
            le.setAccessibleName(tr("الاسم"))
            dl.addWidget(le)
            btns = QHBoxLayout()
            ok_b = QPushButton(tr("موافق"))
            can_b = QPushButton(tr("إلغاء"))
            btns.addWidget(ok_b); btns.addWidget(can_b)
            dl.addLayout(btns)
            ok_b.clicked.connect(d.accept)
            can_b.clicked.connect(d.reject)
            le.setFocus()
            if d.exec():
                new_n = le.text().strip()
                if new_n:
                    self._display_name = new_n
                    self._refresh_items("name")
                    reader.speak(tr(f"تم تحديث الاسم إلى {new_n}"), interrupt=True)
            self.list_widget.setFocus()

        elif tag == "gender":
            menu = ListMenu(self, tr("اختر الجنس"), [(tr("ذكر"), "ذكر"), (tr("أنثى"), "أنثى")])
            choice = menu.show_menu(speak_text=tr("اختر الجنس"))
            if choice in ("ذكر", "أنثى"):
                self._gender = choice
                self._refresh_items("gender")
                reader.speak(tr(f"تم تحديد الجنس: {choice}"), interrupt=True)
            self.list_widget.setFocus()

        elif tag == "bio":
            d = QDialog(self)
            d.setWindowTitle(tr("تعديل الحالة / البايو"))
            d.setModal(True)
            dl = QVBoxLayout(d)
            dl.addWidget(QLabel(tr("اكتب الحالة أو البايو:")))
            te = QTextEdit(d)
            te.setTabChangesFocus(True)
            te.setPlainText(self._bio)
            te.setAccessibleName(tr("البايو"))
            dl.addWidget(te, 1)
            btns = QHBoxLayout()
            ok_b = QPushButton(tr("موافق"))
            can_b = QPushButton(tr("إلغاء"))
            btns.addWidget(ok_b); btns.addWidget(can_b)
            dl.addLayout(btns)
            ok_b.clicked.connect(d.accept)
            can_b.clicked.connect(d.reject)
            te.setFocus()
            if d.exec():
                self._bio = te.toPlainText().strip()
                self._refresh_items("bio")
                reader.speak(tr("تم تحديث البايو"), interrupt=True)
            self.list_widget.setFocus()

        elif tag == "delete_account":
            menu = ListMenu(
                self, tr("تأكيد حذف الحساب نهائيًا"),
                [(tr("نعم، احذف حسابي نهائيًا"), "yes"), (tr("لا، تراجع"), "no")]
            )
            choice = menu.show_menu(speak_text=tr("هل أنت متأكد من حذف حسابك نهائيًا؟ هذا الإجراء دائم ولا يمكن التراجع عنه."))
            if choice == "yes":
                self.delete_requested = True
                self.accept()
            else:
                self.list_widget.setFocus()

    def values(self):
        return {
            "display_name": self._display_name,
            "gender": self._gender,
            "bio": self._bio
        }

    def is_delete_requested(self):
        return self.delete_requested

class ChallengeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle(tr("دعوة للتحدي")); self.setAccessibleName(tr("دعوة للتحدي")); self.setModal(True)
        l=QVBoxLayout(self); l.addWidget(QLabel(tr("اختر اللعبة"))); self.game=QComboBox(self); self.game.setAccessibleName(tr("اللعبة"));
        for key,label in GAME_LABELS.items(): self.game.addItem(tr(label),key)
        l.addWidget(self.game); l.addWidget(QLabel(tr("سيتم إنشاء طاولة جديدة بتكلفة 2 عملة، وتكلفة الدعوة 1 عملة. الإجمالي 3 عملات.")))
        row=QHBoxLayout(); ok=QPushButton(tr("إرسال الدعوة")); cancel=QPushButton(tr("إلغاء")); row.addWidget(ok); row.addWidget(cancel); l.addLayout(row); ok.clicked.connect(self.accept); cancel.clicked.connect(self.reject); self.game.setFocus()
    def selected_game(self): return str(self.game.currentData())
