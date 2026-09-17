from PySide6.QtWidgets import QDialog,QVBoxLayout,QListWidget,QListWidgetItem,QTextEdit,QLineEdit,QPushButton,QHBoxLayout,QLabel,QComboBox,QCheckBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from client.accessibility.reader import reader
from client.views.table_view import handle_list_boundary_navigation
from client.localization import tr, tr_multiline

class _FriendActionsListWidget(QListWidget):
    """Keyboard-first action list with explicit Enter/Escape semantics."""
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner

    def keyPressEvent(self, event):
        if handle_list_boundary_navigation(self, event):
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            item = self.currentItem()
            if item:
                self.owner._activate(item)
            event.accept()
            return
        if event.key() == Qt.Key_Escape:
            self.owner.selected_tag = None
            self.owner.reject()
            event.accept()
            return
        super().keyPressEvent(event)

class FriendActionsDialog(QDialog):
    def __init__(self, friend, parent=None, can_invite=False):
        super().__init__(parent); self.friend=friend; self.can_invite=bool(can_invite)
        dname = friend.get('display_name','')
        title = tr(f"إجراءات {dname}")
        self.setWindowTitle(title); self.setAccessibleName(title); self.setModal(True)
        l=QVBoxLayout(self); self.list=_FriendActionsListWidget(self); self.list.setAccessibleName(tr("قائمة الإجراءات"))
        actions=[("زيارة الملف الشخصي","profile"),("إرسال رسالة","message"),("انضمام","join"),("أنت ضده","h2h"),("كتم الإشعارات","mute"),("دعوة للطاولة","challenge"),("تحدي في لعبة جديدة","direct_challenge"),("إرسال هدية","gift"),("إلغاء الصداقة","unfriend"),("حظر","block")]
        for label,tag in actions:
            disp_label = tr(label)
            it=QListWidgetItem(disp_label); it.setData(Qt.UserRole,tag)
            it.setData(Qt.UserRole + 1101, label)
            it.setData(Qt.UserRole + 1102, disp_label)
            if tag == "direct_challenge" and (not bool(friend.get("online")) or bool(friend.get("in_table"))):
                it.setFlags(it.flags() & ~Qt.ItemIsEnabled)
                it.setToolTip(tr("اللاعب موجود في طاولة" if bool(friend.get("in_table")) else "لا يمكن تحدي لاعب غير متصل"))
            if tag == "challenge" and (bool(friend.get("in_table")) or not self.can_invite):
                it.setFlags(it.flags() & ~Qt.ItemIsEnabled)
                it.setToolTip(tr("اللاعب موجود حاليًا في طاولة" if bool(friend.get("in_table")) else "يجب أن تكون داخل طاولة لإرسال الدعوة"))
            if tag == "join" and (not bool(friend.get("in_table")) or bool(friend.get("room_private", False))):
                it.setFlags(it.flags() & ~Qt.ItemIsEnabled)
                it.setToolTip(tr("اللاعب ليس في طاولة عامة" if bool(friend.get("room_private", False)) else "اللاعب ليس في طاولة حاليًا"))
            self.list.addItem(it)
        l.addWidget(self.list); self.list.setCurrentRow(0); self.list.itemActivated.connect(self._activate); self.list.setFocus()
        self.selected_tag = None
    def _activate(self,item):
        tag=item.data(Qt.UserRole) if item else None
        if tag:
            self.selected_tag = tag
            self.accept()
    def keyPressEvent(self,event):
        if event.key() == Qt.Key_Escape:
            self.selected_tag = None
            self.reject()
            event.accept()
            return
        super().keyPressEvent(event)

class SimpleMessageDialog(QDialog):
    def __init__(self, title, label, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr(title))
        self.setModal(True)
        l=QVBoxLayout(self)
        l.addWidget(QLabel(tr(label)))
        self.editor=QLineEdit()
        self.editor.setAccessibleName(tr(label))
        self.editor.setMaxLength(500)
        self.editor.setPlaceholderText(tr("اكتب رسالتك هنا"))
        l.addWidget(self.editor)
        b=QPushButton(tr("موافق"))
        c=QPushButton(tr("إلغاء"))
        row=QHBoxLayout(); row.addWidget(b); row.addWidget(c); l.addLayout(row)
        b.clicked.connect(self._submit)
        c.clicked.connect(self.reject)
        self.editor.returnPressed.connect(self._submit)
        self.setTabOrder(self.editor, b)
        self.setTabOrder(b, c)
        self.editor.setFocus()

    def _submit(self):
        if not self.editor.text().strip():
            reader.speak(tr("اكتب رسالتك أولًا."), interrupt=True)
            self.editor.setFocus()
            return
        self.accept()

class ProfileDialog(QDialog):
    def __init__(self, data, parent=None, allow_edit=False):
        super().__init__(parent)
        self.setWindowTitle(tr("الملف الشخصي"))
        self.setAccessibleName(tr("الملف الشخصي"))
        self.setModal(True)
        self.edit_requested = False
        layout = QVBoxLayout(self)

        # A single read-only multi-line editor gives NVDA natural line-by-line
        # navigation while preventing accidental modification of profile data.
        self.profile_text = QTextEdit(self)
        self.profile_text.setAccessibleName(tr("محتوى الملف الشخصي"))
        self.profile_text.setReadOnly(True)
        self.profile_text.setFocusPolicy(Qt.StrongFocus)

        name = data.get('display_name', '')
        gender = data.get('gender', 'غير محدد')
        bio = data.get('bio') or 'لا يوجد بايو'
        last = data.get('last_seen_at')
        status = "متصل الآن" if data.get('online') else "آخر ظهور: " + _format_last_seen(last)

        lines = [
            f"الاسم: {name}",
            f"الجنس: {gender}",
            f"البايو: {bio}",
            f"الحالة: {status}",
            "إحصائيات اللاعب",
        ]
        stats = data.get('stats', []) or []
        if stats:
            for item in stats:
                lines.append(
                    f"{item.get('game_name')}: لعب {item.get('played')}, كسب {item.get('wins')}, خسر {item.get('losses')}, التصنيف {item.get('rating', 1000)}, الرتبة {item.get('tier', 'Bronze')}, المركز {item.get('rank', '-') }"
                )
        else:
            lines.append("لا توجد مباريات مع لاعبين بشريين.")

        self.profile_text.setPlainText(tr_multiline("\n".join(lines)))
        layout.addWidget(self.profile_text)

        if allow_edit:
            self.edit_btn = QPushButton(tr("تعديل الملف الشخصي"), self)
            self.edit_btn.setAccessibleName(tr("تعديل الملف الشخصي"))
            self.edit_btn.setFocusPolicy(Qt.StrongFocus)
            self.edit_btn.clicked.connect(self._request_edit)
            layout.addWidget(self.edit_btn)
            self.setTabOrder(self.profile_text, self.edit_btn)

        self.profile_text.moveCursor(QTextCursor.Start)
        # Put keyboard focus on the actionable edit control when this is the
        # user's own profile. This avoids requiring NVDA users to discover a
        # button after a read-only text editor with no other action.
        if allow_edit:
            self.edit_btn.setFocus()
            self.edit_btn.setDefault(True)
            self.edit_btn.setAutoDefault(True)
        else:
            self.profile_text.setFocus()
        self.setMinimumSize(520, 420)

    def keyPressEvent(self, event):
        # Enter/Space on the profile content activates the same canonical edit
        # action, so keyboard users are never trapped in the read-only view.
        if getattr(self, "edit_requested", False) is False and hasattr(self, "edit_btn"):
            if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space) and self.profile_text.hasFocus():
                self._request_edit()
                event.accept()
                return
        super().keyPressEvent(event)

    def _request_edit(self):
        self.edit_requested = True
        self.done(101)

def _format_last_seen(value):
    if not value:
        return tr("غير متاح")
    try:
        from datetime import datetime
        from client.localization import language
        dt = datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone()
        if language() == "en":
            return dt.strftime('%Y-%m-%d at %H:%M')
        return dt.strftime('%Y-%m-%d الساعة %H:%M')
    except Exception:
        return str(value)

class HeadToHeadDialog(QDialog):
    def __init__(self,data,parent=None):
        super().__init__(parent); self.setWindowTitle(tr("أنت ضده")); self.setAccessibleName(tr("إحصائيات المواجهات")); l=QVBoxLayout(self)
        total = data.get('total_played', 0)
        you_wins = data.get('you_wins', 0)
        other_wins = data.get('other_wins', 0)
        summary = f"إجمالي المباريات: {total}. فزت: {you_wins}، خسرت: {other_wins}."
        l.addWidget(QLabel(tr(f"إجمالي المباريات: {total}"))); l.addWidget(QLabel(tr(f"فزت: {you_wins}   خسرت: {other_wins}"))); self.list=QListWidget(); self.list.setAccessibleName(tr("إحصائيات المواجهات حسب اللعبة")); l.addWidget(self.list)
        for s in data.get('summary',[]):
            game_title = tr(s.get('game_name', ''))
            item_text = tr(f"{s['game_name']}: لعب {s['played']}، فزت {s['you_wins']}، خسرت {s['other_wins']}")
            self.list.addItem(item_text)
        if not self.list.count(): self.list.addItem(tr("لم تلعبا أي مباراة مسجلة ضد بعضكما."))
        self.list.setCurrentRow(0)
        reader.speak(tr(summary), interrupt=True)

class MuteDialog(QDialog):
    def __init__(self,flags,parent=None):
        super().__init__(parent); self.setWindowTitle(tr("كتم الإشعارات")); self.setAccessibleName(tr("كتم الإشعارات")); l=QVBoxLayout(self); self.boxes={}
        for key,label in (("all",tr("كتم كل الإشعارات")),("private_messages",tr("كتم الرسائل الخاصة")),("invitations",tr("كتم الدعوات")),("presence",tr("كتم الحالة"))):
            b=QCheckBox(label); b.setChecked(bool(flags.get(key))); self.boxes[key]=b; l.addWidget(b)
        ok=QPushButton(tr("حفظ")); cancel=QPushButton(tr("إلغاء")); row=QHBoxLayout(); row.addWidget(ok); row.addWidget(cancel); l.addLayout(row); ok.clicked.connect(self.accept); cancel.clicked.connect(self.reject); self.boxes['all'].setFocus()
    def values(self): return {k:b.isChecked() for k,b in self.boxes.items()}

class GiftDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent); self.setWindowTitle(tr("إرسال هدية")); self.setAccessibleName(tr("إرسال هدية")); l=QVBoxLayout(self); l.addWidget(QLabel(tr("اختر قيمة الهدية (من 5 إلى 30 عملة):"))); self.amount=QComboBox(); self.amount.setAccessibleName(tr("قيمة الهدية"));
        for n in range(5,31): self.amount.addItem(str(n),n)
        l.addWidget(self.amount); l.addWidget(QLabel(tr("الحد اليومي للحساب: 30 عملة. الحد الشهري للحساب: 150 عملة."))); ok=QPushButton(tr("إرسال")); c=QPushButton(tr("إلغاء")); row=QHBoxLayout(); row.addWidget(ok); row.addWidget(c); l.addLayout(row); ok.clicked.connect(self.accept); c.clicked.connect(self.reject); self.amount.setFocus()
    def value(self): return int(self.amount.currentData())


class OnlineUserActionsDialog(QDialog):
    """The same canonical social actions used for friends, minus friend-only transfers."""
    def __init__(self, user, parent=None, can_invite=False):
        super().__init__(parent)
        self.friend = user; self.can_invite = bool(can_invite)
        dname = user.get('display_name','')
        title = tr(f"إجراءات {dname}")
        self.setWindowTitle(title)
        self.setAccessibleName(title)
        self.setModal(True)
        l=QVBoxLayout(self)
        self.list=_FriendActionsListWidget(self); self.list.setAccessibleName(tr("قائمة الإجراءات"))
        friend_action = ("إلغاء طلب الصداقة", "cancel_friend_request") if user.get("has_pending_request") else ("إضافة صديق", "add_friend")
        actions=[("زيارة الملف الشخصي","profile"),friend_action,("إرسال رسالة","message"),("انضمام","join"),("أنت ضده","h2h"),("دعوة للتحدي","challenge"),("حظر","block")]
        for label,tag in actions:
            disp_label = tr(label)
            it=QListWidgetItem(disp_label); it.setData(Qt.UserRole,tag)
            it.setData(Qt.UserRole + 1101, label)
            it.setData(Qt.UserRole + 1102, disp_label)
            if tag == "add_friend" and user.get("is_friend"):
                it.setFlags(it.flags() & ~Qt.ItemIsEnabled)
                it.setToolTip(tr("اللاعب صديق بالفعل"))
            if tag == "challenge" and (bool(user.get("in_table")) or not self.can_invite):
                it.setFlags(it.flags() & ~Qt.ItemIsEnabled)
                it.setToolTip(tr("اللاعب موجود حاليًا في طاولة" if bool(user.get("in_table")) else "يجب أن تكون داخل طاولة لإرسال الدعوة"))
            if tag == "join" and (not bool(user.get("in_table")) or bool(user.get("room_private", False))):
                it.setFlags(it.flags() & ~Qt.ItemIsEnabled)
                it.setToolTip(tr("اللاعب ليس في طاولة عامة" if bool(user.get("room_private", False)) else "اللاعب ليس في طاولة حاليًا"))
            self.list.addItem(it)
        l.addWidget(self.list); self.list.setCurrentRow(0); self.list.itemActivated.connect(self._activate); self.list.setFocus()
        self.selected_tag = None
    def _activate(self,item):
        tag=item.data(Qt.UserRole) if item else None
        if tag:
            self.selected_tag = tag
            self.accept()
    def keyPressEvent(self,event):
        if event.key() == Qt.Key_Escape:
            self.selected_tag = None
            self.reject()
            event.accept()
            return
        super().keyPressEvent(event)
