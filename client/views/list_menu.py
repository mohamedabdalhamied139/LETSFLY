"""Shared keyboard-first popup list menus for TableVerse.

This module deliberately uses a Qt.Popup + QListWidget instead of QDialog.
All table confirmations and game-setting choices are presented as the same
accessible list style, preserving the shared-table UI model.
"""
from PySide6.QtWidgets import QDialog, QListWidget, QListWidgetItem, QVBoxLayout, QMessageBox, QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from client.accessibility.reader import reader
from client.views.table_view import handle_list_boundary_navigation
from client.localization import tr


class _ListMenuWidget(QListWidget):
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
            self.owner.reject()
            event.accept()
            return
        if event.key() in (Qt.Key_Left, Qt.Key_Right):
            event.accept()
            return
        super().keyPressEvent(event)


class ListMenu(QDialog):
    """Accessible keyboard-first confirmation dialog matching standard TableVerse dialogs."""

    def __init__(self, parent=None, title="", items=None, current=0):
        super().__init__(parent)
        t = tr(title) if title else tr("قائمة")
        self.setWindowTitle(t)
        self.setAccessibleName(t)
        self.setObjectName("letsFlyListMenu")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet("""
            QDialog#letsFlyListMenu {
                background: #1e1e1e;
                border: 2px solid #555555;
                border-radius: 8px;
            }
            QListWidget {
                background: #1e1e1e;
                color: #ffffff;
                border: 0;
                padding: 6px;
                outline: 0;
            }
            QListWidget::item {
                padding: 10px 14px;
                margin: 2px 0px;
            }
            QListWidget::item:selected {
                background: #005fb8;
                color: #ffffff;
                font-weight: bold;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self.list_widget = _ListMenuWidget(self)
        self.list_widget.setFont(QFont("Segoe UI", 14))
        self.list_widget.setFocusPolicy(Qt.StrongFocus)
        self.list_widget.setAccessibleName("")
        self.list_widget.setAccessibleDescription("")
        layout.addWidget(self.list_widget)
        self.result = None
        self._items = []
        self._suppress_row_speech = True
        self.list_widget.itemActivated.connect(self._activate)
        self.list_widget.currentRowChanged.connect(self._on_row_changed)
        if items:
            self.set_items(items)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(max(0, min(current, self.list_widget.count() - 1)))

    def _on_row_changed(self, row):
        if getattr(self, "_suppress_row_speech", False):
            self._suppress_row_speech = False
            return
        if 0 <= row < self.list_widget.count():
            item = self.list_widget.item(row)
            if item:
                pass

    def set_items(self, items):
        self.list_widget.clear()
        self._items = list(items)
        for entry in self._items:
            if isinstance(entry, tuple):
                text, value = entry
            else:
                text, value = str(entry), entry
            item = QListWidgetItem(tr(str(text)))
            item.setData(Qt.UserRole, value)
            item.setData(Qt.UserRole + 1101, str(text))
            self.list_widget.addItem(item)

    def _activate(self, item):
        self.result = item.data(Qt.UserRole)
        self.accept()

    def show_menu(self, anchor=None, speak_text=None):
        self.adjustSize()
        width = max(420, min(760, self.list_widget.sizeHintForColumn(0) + 80))
        height = min(520, max(90, self.list_widget.sizeHintForRow(0) * max(1, self.list_widget.count()) + 28))
        self.resize(width, height)
        p = self.parentWidget()
        if p is not None:
            pos = p.mapToGlobal(p.rect().center())
            self.move(pos.x() - width // 2, pos.y() - height // 2)
        self.result = None
        self._suppress_row_speech = True
        
        cur_item = self.list_widget.currentItem() or (self.list_widget.item(0) if self.list_widget.count() else None)
        # Removed explicit reader.speak(intro) since QDialog + QListWidget natively announce dialog title and focused item
            
        if self.exec():
            return self.result
        return None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.result = None
            self.reject()
            event.accept()
            return
        super().keyPressEvent(event)


def choose(parent, title, items, current=0, speak_text=None):
    """Open one shared list popup and return its selected value."""
    menu = ListMenu(parent, title, items, current)
    return menu.show_menu(speak_text=speak_text or title)


def show_message_dialog(parent, message: str, title: str = "تنبيه") -> None:
    """Standard system alert dialog with Windows sound and an OK button."""
    t_msg = str(tr(message))
    t_title = str(tr(title))

    # Trigger system alert sound (QApplication.beep plays the Windows default sound)
    try:
        QApplication.beep()
    except Exception:
        pass

    reader.speak(f"{t_title}: {t_msg}".strip(), interrupt=True)

    icon = QMessageBox.Information
    title_lower = t_title.lower()
    if any(k in title_lower for k in ("خطأ", "error", "erreur", "فشل", "fail")):
        icon = QMessageBox.Critical
    elif any(k in title_lower for k in ("تنبيه", "تحذير", "warn")):
        icon = QMessageBox.Warning

    box = QMessageBox(icon, t_title, t_msg, parent=parent)
    btn_ok = box.addButton(str(tr("موافق")), QMessageBox.AcceptRole)
    box.setDefaultButton(btn_ok)
    btn_ok.setFocus()
    box.exec()



class _SettingsListWidget(QListWidget):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner

    def keyPressEvent(self, event):
        if hasattr(self.owner, "handle_settings_key"):
            if self.owner.handle_settings_key(event):
                event.accept()
                return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            item = self.currentItem()
            if item:
                self.owner._activate(item)
                event.accept()
                return
        if event.key() == Qt.Key_Escape:
            self.owner.result = None
            self.owner.reject()
            event.accept()
            return
        super().keyPressEvent(event)


from PySide6.QtWidgets import QDialog


class SettingsListMenu(QDialog):
    """Accessible in-place game settings editor.

    - Up/Down arrows change values on number, choice, and bool fields.
    - Direct digit typing (0-9) and Backspace edit number fields in-place.
    - Enter and Tab advance focus to the next setting / 'بدء اللعبة'.
    - Shift+Tab and Up arrow on action items navigate backwards.
    - Enter on 'بدء اللعبة' starts the game immediately.
    """

    def __init__(self, parent=None, title="إعدادات اللعبة", fields=None):
        super().__init__(parent)
        self.setWindowTitle(tr(title))
        self.setAccessibleName(tr(title))
        self.setObjectName("letsFlySettingsList")
        self.setStyleSheet("""
            QDialog#letsFlySettingsList {
                background: #1e1e1e;
                border: 2px solid #555555;
                border-radius: 8px;
            }
            QListWidget {
                background: #1e1e1e;
                color: #ffffff;
                border: 0;
                padding: 6px;
                outline: 0;
            }
            QListWidget::item { padding: 10px 14px; margin: 2px 0px; }
            QListWidget::item:selected { background: #005fb8; color: #ffffff; font-weight: bold; }
        """)
        self.list_widget = _SettingsListWidget(self)
        self.list_widget.setFont(QFont("Segoe UI", 14))
        self.list_widget.setAccessibleName("")
        self.list_widget.setAccessibleDescription("")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.list_widget)
        self.fields = fields or []
        self.values = {}
        self.edit_buffers = {}
        self._typing_number = False
        self.result = None
        self._suppress_row_speech = True
        for field in self.fields:
            self.values[field["key"]] = field.get("value")
            if field.get("kind") == "number":
                self.edit_buffers[field["key"]] = str(field.get("value", ""))
        self._rebuild()
        self.list_widget.itemActivated.connect(self._activate)
        self.list_widget.currentRowChanged.connect(self._on_row_changed)

    def _on_row_changed(self, row):
        self._typing_number = False
        if 0 <= row < self.list_widget.count():
            item = self.list_widget.item(row)
            if item:
                item.setData(Qt.AccessibleTextRole, None)

    def _display(self, field):
        key = field["key"]
        label = tr(field["label"])
        kind = field.get("kind", "action")
        value = self.values.get(key)
        if kind == "bool":
            status = tr("مفعل") if value else tr("معطل")
            return f"{label}: {status}"
        if kind == "choice":
            raw_val = field.get('labels', {}).get(value, value)
            return f"{label}: {tr(raw_val)}"
        if kind == "number":
            return f"{label}: {value}"
        return label

    def _rebuild(self, keep_key=None, announcement=None):
        if self.list_widget.count() == len(self.fields):
            for i, field in enumerate(self.fields):
                item = self.list_widget.item(i)
                new_text = self._display(field)
                if item.text() != new_text:
                    if keep_key is not None and field["key"] == keep_key and announcement is not None:
                        item.setData(Qt.AccessibleTextRole, tr(str(announcement)))
                    else:
                        item.setData(Qt.AccessibleTextRole, None)
                    item.setText(new_text)
            return

        if keep_key is None and self.list_widget.currentItem():
            keep_key = self.list_widget.currentItem().data(Qt.UserRole)
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for field in self.fields:
            item = QListWidgetItem(self._display(field))
            item.setData(Qt.UserRole, field["key"])
            self.list_widget.addItem(item)
        row = 0
        for i in range(self.list_widget.count()):
            if self.list_widget.item(i).data(Qt.UserRole) == keep_key:
                row = i
                break
        if self.list_widget.count():
            self.list_widget.setCurrentRow(row)
        self.list_widget.blockSignals(False)

    def _field(self, key):
        return next((f for f in self.fields if f["key"] == key), None)

    def _activate(self, item):
        key = item.data(Qt.UserRole)
        field = self._field(key)
        if not field:
            return
        kind = field.get("kind", "action")
        if kind == "action":
            self.result = key
            if key == "start":
                self.accept()
            else:
                self.reject()
            return
        if kind == "number":
            self._typing_number = False
            cur_row = self.list_widget.currentRow()
            if cur_row + 1 < self.list_widget.count():
                self.list_widget.setCurrentRow(cur_row + 1)
            return
        if kind == "choice":
            options = list(field.get("options", []))
            if options:
                current = self.values.get(key)
                try:
                    idx = options.index(current)
                except ValueError:
                    idx = 0
                new_idx = (idx + 1) % len(options)
                new_opt = options[new_idx]
                self.values[key] = new_opt
                labels = field.get("labels", {})
                announcement = labels.get(new_opt, str(new_opt))
                self._rebuild(key, announcement=announcement)
                reader.speak(tr(announcement), interrupt=True)
            return
        if kind == "bool":
            new_val = not bool(self.values.get(key))
            conflicts = field.get("conflicts_with") or {}
            if new_val and conflicts:
                for conflict_key, alert_msg in conflicts.items():
                    if self.values.get(conflict_key):
                        self.values[conflict_key] = False
                        self._rebuild(conflict_key, announcement="معطل")
                        reader.speak(tr(f"تنبيه: {alert_msg}"), interrupt=True)
            group = field.get("group")
            if group:
                for f in self.fields:
                    if f.get("group") == group:
                        is_sel = (f["key"] == key)
                        self.values[f["key"]] = is_sel
            else:
                self.values[key] = new_val
            announcement = "مفعل" if self.values.get(key) else "معطل"
            self._rebuild(key, announcement=announcement)
            reader.speak(tr(announcement), interrupt=True)
            return

    def handle_settings_key(self, event):
        item = self.list_widget.currentItem()
        field = self._field(item.data(Qt.UserRole)) if item else None
        if not field:
            return False

        kind = field.get("kind", "action")
        fkey = field["key"]

        # Enter / Return advances through settings. Only the explicit Start
        # action submits the dialog; Enter on a value must never silently change
        # that value or start the game.
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._typing_number = False
            if kind == "action":
                if fkey == "start":
                    self.result = fkey
                    self.accept()
                else:
                    self._activate(item)
                return True
            cur_row = self.list_widget.currentRow()
            if cur_row + 1 < self.list_widget.count():
                self.list_widget.setCurrentRow(cur_row + 1)
            else:
                self.list_widget.setCurrentRow(0)
            return True

        # Up and Down are the primary value controls for this keyboard-first
        # settings menu. Action rows retain normal list navigation.
        if event.key() in (Qt.Key_Up, Qt.Key_Down):
            self._typing_number = False
            direction = 1 if event.key() == Qt.Key_Up else -1
            if kind == "action":
                cur_row = self.list_widget.currentRow()
                next_row = cur_row + (1 if direction < 0 else -1)
                if next_row < 0:
                    next_row = self.list_widget.count() - 1
                elif next_row >= self.list_widget.count():
                    next_row = 0
                self.list_widget.setCurrentRow(next_row)
                return True
            if kind == "number":
                step = int(field.get("step", 1))
                minimum = int(field.get("minimum", 1))
                maximum = field.get("maximum")
                current = int(self.values.get(fkey, minimum))
                val = current + (step * direction)
                val = max(minimum, val)
                if maximum is not None:
                    val = min(int(maximum), val)
                self.values[fkey] = val
                self.edit_buffers[fkey] = str(val)
                announcement = f"{val}"
                self._rebuild(fkey, announcement=announcement)
                reader.speak(tr(announcement), interrupt=True)
                return True
            if kind == "choice":
                options = list(field.get("options", []))
                if options:
                    current = self.values.get(fkey)
                    try:
                        idx = options.index(current)
                    except ValueError:
                        idx = 0
                    new_idx = (idx + direction) % len(options)
                    self.values[fkey] = options[new_idx]
                    labels = field.get("labels", {})
                    announcement = labels.get(options[new_idx], str(options[new_idx]))
                    self._rebuild(fkey, announcement=announcement)
                    reader.speak(tr(str(announcement)), interrupt=True)
                return True
            if kind == "bool":
                self._activate(item)
                return True

        # Left and Right arrow keys remain supported as value aliases.
        if event.key() in (Qt.Key_Left, Qt.Key_Right):
            self._typing_number = False
            if kind == "number":
                step = int(field.get("step", 1))
                minimum = int(field.get("minimum", 1))
                current = int(self.values.get(fkey, minimum))
                if event.key() == Qt.Key_Right:
                    val = current + step
                else:
                    val = max(minimum, current - step)
                self.values[fkey] = val
                self.edit_buffers[fkey] = str(val)
                announcement = f"{val}"
                self._rebuild(fkey, announcement=announcement)
                reader.speak(tr(announcement), interrupt=True)
                return True
            elif kind == "bool":
                self._activate(item)
                return True
            elif kind == "choice":
                options = list(field.get("options", []))
                if options:
                    current = self.values.get(fkey)
                    try:
                        idx = options.index(current)
                    except ValueError:
                        idx = 0
                    direction = 1 if event.key() == Qt.Key_Right else -1
                    new_idx = (idx + direction) % len(options)
                    new_opt = options[new_idx]
                    self.values[fkey] = new_opt
                    labels = field.get("labels", {})
                    announcement = labels.get(new_opt, str(new_opt))
                    self._rebuild(fkey, announcement=announcement)
                    reader.speak(tr(announcement), interrupt=True)
                    return True

        # Digits 0-9 for number fields
        if kind == "number" and (Qt.Key_0 <= event.key() <= Qt.Key_9):
            digit = str(event.key() - Qt.Key_0)
            buf = self.edit_buffers.get(fkey, "")
            if not self._typing_number:
                buf = digit
                self._typing_number = True
            else:
                buf += digit
            self.edit_buffers[fkey] = buf
            try:
                val = int(buf)
                self.values[fkey] = val
                announcement = f"{val}"
                self._rebuild(fkey, announcement=announcement)
                reader.speak(tr(announcement), interrupt=True)
            except ValueError:
                pass
            return True

        if kind == "number" and event.key() == Qt.Key_Backspace:
            buf = self.edit_buffers.get(fkey, "")
            if buf:
                buf = buf[:-1]
                self.edit_buffers[fkey] = buf
                if buf:
                    try:
                        val = int(buf)
                        self.values[fkey] = val
                        announcement = f"{val}"
                        self._rebuild(fkey, announcement=announcement)
                        reader.speak(tr(announcement), interrupt=True)
                    except ValueError:
                        pass
                else:
                    minimum = int(field.get("minimum", 1))
                    self.values[fkey] = minimum
                    announcement = "فارغ"
                    self._rebuild(fkey, announcement=announcement)
                    reader.speak(tr(announcement), interrupt=True)
            return True

        # Space key toggles bool / choice fields
        if event.key() == Qt.Key_Space:
            if kind == "bool":
                new_val = not bool(self.values.get(fkey))
                conflicts = field.get("conflicts_with") or {}
                if new_val and conflicts:
                    for conflict_key, alert_msg in conflicts.items():
                        if self.values.get(conflict_key):
                            self.values[conflict_key] = False
                            self._rebuild(conflict_key, announcement="معطل")
                            reader.speak(tr(f"تنبيه: {alert_msg}"), interrupt=True)

                group = field.get("group")
                if group:
                    for f in self.fields:
                        if f.get("group") == group:
                            is_sel = (f["key"] == fkey)
                            self.values[f["key"]] = is_sel
                else:
                    self.values[fkey] = new_val

                announcement = "مفعل" if self.values.get(fkey) else "معطل"
                self._rebuild(fkey, announcement=announcement)
                reader.speak(tr(announcement), interrupt=True)
                return True
            elif kind == "choice":
                options = list(field.get("options", []))
                if options:
                    current = self.values.get(fkey)
                    try:
                        idx = options.index(current)
                    except ValueError:
                        idx = 0
                    new_idx = (idx + 1) % len(options)
                    new_opt = options[new_idx]
                    self.values[fkey] = new_opt
                    labels = field.get("labels", {})
                    announcement = labels.get(new_opt, str(new_opt))
                    self._rebuild(fkey, announcement=announcement)
                    reader.speak(tr(announcement), interrupt=True)
                    return True

        # Tab and Shift+Tab (Backtab) for moving between rows
        if event.key() == Qt.Key_Backtab or (event.key() == Qt.Key_Tab and (event.modifiers() & Qt.ShiftModifier)):
            self._typing_number = False
            cur_row = self.list_widget.currentRow()
            if cur_row > 0:
                self.list_widget.setCurrentRow(cur_row - 1)
            else:
                self.list_widget.setCurrentRow(self.list_widget.count() - 1)
            return True

        if event.key() == Qt.Key_Tab:
            self._typing_number = False
            cur_row = self.list_widget.currentRow()
            if cur_row + 1 < self.list_widget.count():
                self.list_widget.setCurrentRow(cur_row + 1)
            else:
                self.list_widget.setCurrentRow(0)
            return True

        return False

    def show_menu(self, speak_text=None):
        self.adjustSize()
        width = max(460, min(820, self.list_widget.sizeHintForColumn(0) + 90))
        rows = max(1, self.list_widget.count())
        height = min(600, max(140, self.list_widget.sizeHintForRow(0) * rows + 28))
        self.resize(width, height)
        p = self.parentWidget()
        if p is not None:
            pos = p.mapToGlobal(p.rect().center())
            self.move(pos.x() - width // 2, pos.y() - height // 2)
        self.result = None
        # Removed explicit reader.speak(speak_text) since QDialog natively announces AccessibleName
        if self.exec():
            return self.result, dict(self.values)
        return None, dict(self.values)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.result = None
            self.reject()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        super().closeEvent(event)
