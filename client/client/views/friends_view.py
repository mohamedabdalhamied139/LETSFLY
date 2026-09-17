"""Keyboard-first friends dialog with a single canonical actions entry point."""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTabWidget, QListWidget, QListWidgetItem, QPushButton
from PySide6.QtCore import Qt
from client.localization import tr, subscribe, unsubscribe, language
from client.views.social_center_views import GAME_LABELS


class FriendsView(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("الأصدقاء"))
        self.setAccessibleName(tr("الأصدقاء"))
        self.setModal(True)

        l = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        self.tabs.setAccessibleName(tr("أقسام الأصدقاء"))

        self.friends = QListWidget(self)
        self.friends.setAccessibleName(tr("الأصدقاء"))
        self.incoming = QListWidget(self)
        self.incoming.setAccessibleName(tr("طلبات الصداقة"))
        self.outgoing = QListWidget(self)
        self.outgoing.setAccessibleName(tr("الطلبات المرسلة"))

        self.tabs.addTab(self.friends, tr("الأصدقاء"))
        self.tabs.addTab(self.incoming, tr("الطلبات"))
        self.tabs.addTab(self.outgoing, tr("الطلبات المرسلة"))
        l.addWidget(self.tabs)

        self.actions_button = QPushButton(tr("قائمة الإجراءات"), self)
        self.actions_button.setAccessibleName(tr("قائمة الإجراءات"))
        self.actions_button.setFocusPolicy(Qt.StrongFocus)
        l.addWidget(self.actions_button)

        self._lists = (self.friends, self.incoming, self.outgoing)
        for w in self._lists:
            w.setFocusPolicy(Qt.StrongFocus)

        self._active_tab = 0
        self.tabs.currentChanged.connect(self._focus_current)
        self.friends.itemActivated.connect(lambda item: self._do_action())
        self.incoming.itemActivated.connect(lambda item: self._do_action())
        self.outgoing.itemActivated.connect(lambda item: self._do_action())
        self.actions_button.clicked.connect(self._do_action)
        self.setMinimumSize(520, 470)

        self.selected_data = None
        self.selected_tab = None
        self._on_action = None

        self._last_friends = []
        self._last_incoming = []
        self._last_outgoing = []

        subscribe(self._on_language_changed)

    def closeEvent(self, event):
        try:
            unsubscribe(self._on_language_changed)
        except Exception:
            pass
        super().closeEvent(event)

    def _on_language_changed(self, _lang: str):
        self.setWindowTitle(tr("الأصدقاء"))
        self.setAccessibleName(tr("الأصدقاء"))
        self.tabs.setAccessibleName(tr("أقسام الأصدقاء"))
        self.friends.setAccessibleName(tr("الأصدقاء"))
        self.incoming.setAccessibleName(tr("طلبات الصداقة"))
        self.outgoing.setAccessibleName(tr("الطلبات المرسلة"))

        self.tabs.setTabText(0, tr("الأصدقاء"))
        self.tabs.setTabText(1, tr("الطلبات"))
        self.tabs.setTabText(2, tr("الطلبات المرسلة"))

        self._focus_current(self.tabs.currentIndex())
        self.set_data(self._last_friends, self._last_incoming, self._last_outgoing)

    def set_action_callback(self, callback):
        """Set callback: callback(data, tab_name) where tab_name is 'friend', 'incoming', 'outgoing'"""
        self._on_action = callback

    def _focus_current(self, index):
        if 0 <= index < len(self._lists):
            self._active_tab = index
            self._lists[index].setFocus()
        labels = ["قائمة الإجراءات", "إجراءات الطلب", "إجراءات الطلب المرسل"]
        raw = labels[index] if index < len(labels) else labels[0]
        self.actions_button.setText(tr(raw))
        self.actions_button.setAccessibleName(tr(raw))

    @staticmethod
    def _fill(widget, rows, empty_text, selected_key=None):
        widget.clear()
        if not rows:
            disp_empty = tr(empty_text)
            it = QListWidgetItem(disp_empty)
            it.setData(Qt.UserRole + 1101, empty_text)
            it.setData(Qt.UserRole + 1102, disp_empty)
            widget.addItem(it)
            return

        selected_row = 0

        for pos, row in enumerate(rows):
            name = str(row.get("display_name") or row.get("username") or "")
            if "online" in row:
                if row.get("online"):
                    game = row.get("game")
                    if game:
                        gname_ar = GAME_LABELS.get(game, game)
                        raw_text = f"{name} — متصل — يلعب {gname_ar}"
                    else:
                        raw_text = f"{name} — متصل"
                else:
                    raw_text = f"{name} — غير متصل"
            else:
                raw_text = name
            disp_text = tr(raw_text)

            item = QListWidgetItem(disp_text)
            item.setData(Qt.UserRole, row)
            item.setData(Qt.UserRole + 1101, raw_text)
            item.setData(Qt.UserRole + 1102, disp_text)
            widget.addItem(item)
            if selected_key is not None and (row.get("id"), row.get("request_id")) == selected_key:
                selected_row = pos
        widget.setCurrentRow(selected_row)

    def _get_current_data(self):
        index = self.tabs.currentIndex()
        lst = self._lists[index] if 0 <= index < len(self._lists) else self.friends
        item = lst.currentItem()
        if not item:
            return None, index
        data = item.data(Qt.UserRole)
        if not isinstance(data, dict):
            return None, index
        return data, index

    def _do_action(self):
        data, index = self._get_current_data()
        if not data or not data.get("id"):
            from client.accessibility.reader import reader
            reader.speak(tr("القائمة فارغة، لا توجد عناصر لتنفيذ إجراء عليها."), interrupt=True)
            return
        tab_names = ["friend", "incoming", "outgoing"]
        tab_name = tab_names[index] if index < len(tab_names) else "friend"
        if self._on_action:
            self._on_action(data, tab_name)

    def set_data(self, friends=None, incoming=None, outgoing=None):
        self._last_friends = list(friends or [])
        self._last_incoming = list(incoming or [])
        self._last_outgoing = list(outgoing or [])

        current_index = self.tabs.currentIndex()
        current_list = self._lists[current_index] if 0 <= current_index < len(self._lists) else self.friends
        current_item = current_list.currentItem()
        current_data = current_item.data(Qt.UserRole) if current_item else None
        selected_key = None
        if isinstance(current_data, dict):
            selected_key = (current_data.get("id"), current_data.get("request_id"))

        self._fill(self.friends, self._last_friends, "لا يوجد أصدقاء.", selected_key if current_index == 0 else None)
        self._fill(self.incoming, self._last_incoming, "لا توجد طلبات صداقة.", selected_key if current_index == 1 else None)
        self._fill(self.outgoing, self._last_outgoing, "لا توجد طلبات مرسلة.", selected_key if current_index == 2 else None)

        self.tabs.blockSignals(True)
        self.tabs.setCurrentIndex(max(0, min(current_index, len(self._lists) - 1)))
        self.tabs.blockSignals(False)
        self._active_tab = self.tabs.currentIndex()

    def show_data(self, friends=None, incoming=None, outgoing=None):
        self.set_data(friends, incoming, outgoing)
        index = self._active_tab
        self.tabs.setCurrentIndex(index)
        self._lists[index].setFocus()
        self.exec()
