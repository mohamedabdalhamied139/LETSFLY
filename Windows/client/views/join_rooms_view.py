"""Available Rooms List View."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem
from PySide6.QtCore import Signal, Qt
from client.views.activity_log_widget import ActivityLogWidget
from client.views.table_view import handle_list_boundary_navigation
from client.localization import tr, subscribe, unsubscribe, language


class _JoinRoomsListWidget(QListWidget):
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
                event.accept()
                return
        if event.key() == Qt.Key_F4 and event.modifiers() == Qt.NoModifier:
            item = self.currentItem()
            if item:
                rid = item.data(Qt.UserRole)
                if rid:
                    self.owner.spectatorSelected.emit(str(rid))
                    event.accept()
                    return
        if event.key() == Qt.Key_Escape:
            self.owner.backRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class JoinRoomsView(QWidget):
    roomSelected = Signal(str)
    spectatorSelected = Signal(str)
    backRequested = Signal()
    activitySelected = Signal(str)
    loadOlderRequested = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)

        self.title_label = QLabel(tr("الطاولات المتاحة حاليًا"))
        self.title_label.setAccessibleName(tr("عنوان الطاولات المتاحة"))
        self.layout.addWidget(self.title_label)

        self.rooms_list = _JoinRoomsListWidget(self)
        self.rooms_list.setAccessibleName(tr("قائمة الطاولات المتاحة"))
        self.rooms_list.itemActivated.connect(self._on_activated)
        body = QHBoxLayout()
        body.addWidget(self.rooms_list, 1)
        self.activity_panel = ActivityLogWidget(self, always_visible=True)
        body.addWidget(self.activity_panel, 1)
        self.layout.addLayout(body, 1)
        self.activity_panel.categorySelected.connect(self.activitySelected)
        self.activity_panel.loadOlderRequested.connect(self.loadOlderRequested)
        self._last_rooms = []

        subscribe(self._on_language_changed)

    def closeEvent(self, event):
        try:
            unsubscribe(self._on_language_changed)
        except Exception:
            pass
        super().closeEvent(event)

    def _on_language_changed(self, _lang: str):
        self.title_label.setText(tr("الطاولات المتاحة حاليًا"))
        self.title_label.setAccessibleName(tr("عنوان الطاولات المتاحة"))
        self.rooms_list.setAccessibleName(tr("قائمة الطاولات المتاحة"))
        self.update_rooms(self._last_rooms)

    def update_rooms(self, rooms: list):
        self._last_rooms = list(rooms or [])
        self.rooms_list.clear()
        if not self._last_rooms:
            empty_msg = tr("لا توجد طاولات متاحة حاليًا.")
            it = QListWidgetItem(empty_msg)
            it.setData(Qt.UserRole, None)
            it.setData(Qt.UserRole + 1101, "لا توجد طاولات متاحة حاليًا.")
            it.setData(Qt.UserRole + 1102, empty_msg)
            self.rooms_list.addItem(it)
            return

        for r in self._last_rooms:
            rid = r.get("id")
            host = r.get("host_name") or "مجهول"
            count = len(r.get("players", []))
            raw_status = "جارية" if r.get("status") == "playing" else "في الانتظار"
            game_raw = r.get("game_label", r.get("game", "لعبة"))
            raw_text = f"{game_raw} — {host} — {count}/10 لاعبين — {raw_status}"
            disp_text = tr(raw_text)

            it = QListWidgetItem(disp_text)
            it.setToolTip("")
            it.setData(Qt.UserRole, rid)
            it.setData(Qt.UserRole + 1101, raw_text)
            it.setData(Qt.UserRole + 1102, disp_text)
            self.rooms_list.addItem(it)

        if self.rooms_list.count():
            self.rooms_list.setCurrentRow(0)

    def remove_room_by_id(self, room_id: str):
        if not room_id or not self._last_rooms:
            return
        str_rid = str(room_id)
        new_rooms = [r for r in self._last_rooms if str(r.get("id")) != str_rid]
        if len(new_rooms) != len(self._last_rooms):
            self.update_rooms(new_rooms)

    def _on_activated(self, item: QListWidgetItem):
        rid = item.data(Qt.UserRole)
        if rid:
            self.roomSelected.emit(str(rid))
