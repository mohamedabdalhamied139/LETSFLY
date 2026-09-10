"""Accessible Home screen using the exact same activity-log widget as tables."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem
from PySide6.QtCore import Signal, Qt
from client.views.activity_log_widget import ActivityLogWidget
from client.views.table_view import handle_list_boundary_navigation
# Canonical categories: TABLE_CHAT, PRIVATE_MESSAGES, FRIENDS, GAMEPLAY, ALL,
# FRIEND_REQUESTS, INVITATIONS. They are rendered by the same widget as tables.


class _HomeListWidget(QListWidget):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
    def keyPressEvent(self, event):
        if handle_list_boundary_navigation(self, event):
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            item = self.currentItem()
            if item:
                self.owner._on_activated(item)
                event.accept(); return
        super().keyPressEvent(event)


from client.localization import tr, subscribe

class HomeView(QWidget):
    itemSelected = Signal(str)
    activitySelected = Signal(str)
    loadOlderRequested = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._user_display_name = None
        self._online_count = 0
        self.layout = QVBoxLayout(self)
        self.welcome_label = QLabel(tr("القائمة الرئيسية"))
        self.welcome_label.setAccessibleName(tr("عنوان القائمة الرئيسية"))
        self.layout.addWidget(self.welcome_label)

        body = QHBoxLayout()
        # The canonical ActivityLogWidget remains exactly the same component
        # used by TableView; Home only changes its placement.
        self.activity_panel = ActivityLogWidget(self, always_visible=True)
        body.addWidget(self.activity_panel, 1)

        self.menu_list = _HomeListWidget(self)
        self.menu_list.setAccessibleName(tr("القائمة الرئيسية"))
        self.menu_list.itemActivated.connect(self._on_activated)
        self.menu_list.itemDoubleClicked.connect(self._on_activated)
        body.addWidget(self.menu_list, 0)
        self.layout.addLayout(body, 1)

        self.activity_title = self.activity_panel.title
        self.activity_categories = self.activity_panel.activity_log
        self.activity_log = self.activity_panel.activity_log
        self.load_older = self.activity_panel.load_older
        self.activity_panel.categorySelected.connect(self.activitySelected)
        self.activity_panel.loadOlderRequested.connect(self.loadOlderRequested)
        subscribe(self._on_language_changed)
        self._populate()

    def _on_language_changed(self, _lang: str):
        if self._user_display_name:
            self.set_user_greeting(self._user_display_name)
        else:
            self.welcome_label.setText(tr("القائمة الرئيسية"))
            self.welcome_label.setAccessibleName(tr("عنوان القائمة الرئيسية"))
        self.menu_list.setAccessibleName(tr("القائمة الرئيسية"))
        self._populate()

    def set_user_greeting(self, display_name):
        self._user_display_name = display_name
        self.welcome_label.setText(tr(f"مرحبًا بعودتك {display_name}."))

    def _populate(self):
        self.menu_list.clear()
        menu_items = (
            ("الطاولات", "rooms"),
            ("الأصدقاء", "friends"),
            (f"المتصلون ({self._online_count})", "online"),
            ("ملفي الشخصي", "my_profile"),
            ("الإعدادات", "settings"),
            ("الإشعارات", "notifications"),
            ("تحدث معنا", "contact"),
            ("تسجيل الخروج", "logout")
        )
        for label, tag in menu_items:
            it = QListWidgetItem(tr(label))
            it.setData(Qt.UserRole, tag)
            it.setData(Qt.UserRole + 1101, label)
            self.menu_list.addItem(it)
        if self.menu_list.count():
            self.menu_list.setCurrentRow(0)

    def set_online_count(self, count):
        count = max(0, int(count or 0))
        self._online_count = count
        for i in range(self.menu_list.count()):
            item = self.menu_list.item(i)
            if item.data(Qt.UserRole) == "online":
                raw = f"المتصلون ({count})"
                item.setText(tr(raw))
                item.setData(Qt.UserRole + 1101, raw)
                break

    def set_activity_events(self, events, has_more=False, next_before_id=None, preserve_selection=True):
        self.activity_panel.set_events(events, has_more, next_before_id, preserve_selection)

    def add_activity_event(self, event):
        self.activity_panel.add_event(event)

    def append_older_events(self, events, has_more=False, next_before_id=None):
        self.activity_panel.append_older(events, has_more, next_before_id)

    def _on_activated(self, item):
        tag = item.data(Qt.UserRole)
        if tag: self.itemSelected.emit(tag)

    def _handle_home_activity_selection(self, category):
        self.activity_panel._render_category(category, focus=True)
