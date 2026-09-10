"""Keyboard-first server-wide users dialog with search from database."""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QLabel, QComboBox, QPushButton, QLineEdit
from PySide6.QtCore import Qt, Signal, QTimer
from client.localization import tr, subscribe, unsubscribe, language


class OnlineUsersView(QDialog):
    userActivated = Signal(dict)
    searchRequested = Signal(str)
    SORT_LABELS = {"alpha": "الأحرف", "oldest": "الأقدم", "newest": "الأحدث"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("البحث عن لاعبين"))
        self.setAccessibleName(tr("البحث عن لاعبين"))
        self.setModal(True)
        layout = QVBoxLayout(self)

        self.search = QLineEdit(self)
        self.search.setPlaceholderText(tr("اكتب اسم المستخدم للبحث"))
        self.search.setAccessibleName(tr("بحث باسم المستخدم"))
        layout.addWidget(self.search)

        self.sort_label = QLabel(tr("ترتيب حسب"))
        layout.addWidget(self.sort_label)

        self.sort_box = QComboBox(self)
        self.sort_box.setAccessibleName(tr("ترتيب حسب"))
        self._populate_sort_box()
        layout.addWidget(self.sort_box)

        self.users_list = QListWidget(self)
        self.users_list.setAccessibleName(tr("نتائج البحث"))
        layout.addWidget(self.users_list, 1)

        self.actions_button = QPushButton(tr("قائمة الإجراءات"), self)
        self.actions_button.setAccessibleName(tr("قائمة الإجراءات"))
        self.actions_button.setFocusPolicy(Qt.StrongFocus)
        layout.addWidget(self.actions_button)

        self.users = []
        self._initial_users = []
        self.sort_box.currentIndexChanged.connect(self._resort)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(400)
        self._search_timer.timeout.connect(self._do_search)
        self.search.textChanged.connect(self._on_search_changed)
        self.users_list.itemActivated.connect(self._activate_selected)
        self.actions_button.clicked.connect(self._activate_selected)
        self.setMinimumSize(520, 470)
        self.sort_box.setFocusPolicy(Qt.StrongFocus)

        subscribe(self._on_language_changed)

    def closeEvent(self, event):
        try:
            unsubscribe(self._on_language_changed)
        except Exception:
            pass
        super().closeEvent(event)

    def _populate_sort_box(self):
        curr = self.sort_box.currentData() or "alpha"
        self.sort_box.blockSignals(True)
        self.sort_box.clear()
        self.sort_box.addItem(tr("الأحرف"), "alpha")
        self.sort_box.addItem(tr("الأقدم"), "oldest")
        self.sort_box.addItem(tr("الأحدث"), "newest")
        idx = {"alpha": 0, "oldest": 1, "newest": 2}.get(curr, 0)
        self.sort_box.setCurrentIndex(idx)
        self.sort_box.blockSignals(False)

    def _on_language_changed(self, _lang: str):
        self.setWindowTitle(tr("البحث عن لاعبين"))
        self.setAccessibleName(tr("البحث عن لاعبين"))
        self.search.setPlaceholderText(tr("اكتب اسم المستخدم للبحث"))
        self.search.setAccessibleName(tr("بحث باسم المستخدم"))
        self.sort_label.setText(tr("ترتيب حسب"))
        self.sort_box.setAccessibleName(tr("ترتيب حسب"))
        self._populate_sort_box()
        self.users_list.setAccessibleName(tr("نتائج البحث"))
        self.actions_button.setText(tr("قائمة الإجراءات"))
        self.actions_button.setAccessibleName(tr("قائمة الإجراءات"))
        self._resort()

    def _on_search_changed(self):
        query = self.search.text().strip()
        if not query:
            self.set_users(self._initial_users if hasattr(self, '_initial_users') else [])
            return
        self._search_timer.start()

    def _do_search(self):
        query = self.search.text().strip()
        if query:
            self.searchRequested.emit(query)

    def set_users(self, users, is_initial=False):
        if is_initial:
            self._initial_users = list(users or [])
        self.users = list(users or [])
        self._resort()
        if not is_initial:
            from client.accessibility.reader import reader
            count = len(self.users)
            if count == 0:
                reader.speak(tr("لا توجد نتائج مطابقة."), interrupt=True)
            elif count == 1:
                reader.speak(tr("تم العثور على لاعب واحد."), interrupt=True)
            elif count == 2:
                reader.speak(tr("تم العثور على لاعبين اثنين."), interrupt=True)
            else:
                reader.speak(tr(f"تم العثور على {count} لاعبين."), interrupt=True)
        if not hasattr(self, '_focused_once') or not self._focused_once:
            self.search.setFocus()
            self._focused_once = True

    def _resort(self):
        mode = self.sort_box.currentData() or "alpha"
        rows = list(self.users)
        if mode == "alpha":
            rows.sort(key=lambda x: str(x.get("display_name") or x.get("username") or "").casefold())
        elif mode == "oldest":
            rows.sort(key=lambda x: float(x.get("connected_at", 0) or 0))
        else:
            rows.sort(key=lambda x: float(x.get("connected_at", 0) or 0), reverse=True)
        self.users_list.clear()

        for row in rows:
            name = str(row.get("display_name") or row.get("username") or "")
            raw_status = "متصل" if row.get("online") else "غير متصل"
            raw_text = f"{name} ({raw_status})"
            disp_text = tr(raw_text)

            item = QListWidgetItem(disp_text)
            item.setData(Qt.UserRole, row)
            item.setData(Qt.UserRole + 1101, raw_text)
            item.setData(Qt.UserRole + 1102, disp_text)
            self.users_list.addItem(item)
        if self.users_list.count():
            self.users_list.setCurrentRow(0)

    def _activate_selected(self):
        item = self.users_list.currentItem()
        data = item.data(Qt.UserRole) if item else None
        if not data or not data.get("id"):
            from client.accessibility.reader import reader
            reader.speak(tr("القائمة فارغة، لا توجد عناصر لتنفيذ إجراء عليها."), interrupt=True)
            return
        if isinstance(data, dict) and data.get("id"):
            self.userActivated.emit(data)
