"""Saved Tables List View."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMenu
from PySide6.QtCore import Signal, Qt
from client.views.activity_log_widget import ActivityLogWidget
from client.views.table_view import handle_list_boundary_navigation
from client.localization import tr, subscribe, unsubscribe
from client.accessibility.reader import reader


class _SavedTablesListWidget(QListWidget):
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
        if event.key() == Qt.Key_Escape:
            self.owner.backRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        item = self.currentItem()
        if not item:
            return
        saved_id = item.data(Qt.UserRole)
        if not saved_id:
            return
        menu = QMenu(self)
        menu.setAccessibleName(tr("خيارات الطاولة المحفوظة"))
        del_act = menu.addAction(tr("حذف"))
        del_act.triggered.connect(lambda: self.owner.deleteSelected.emit(int(saved_id)))
        menu.exec(event.globalPos())


class SavedTablesView(QWidget):
    restoreSelected = Signal(int)
    deleteSelected = Signal(int)
    backRequested = Signal()
    activitySelected = Signal(str)
    loadOlderRequested = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)

        self.title_label = QLabel(tr("الطاولات المحفوظة"))
        self.title_label.setAccessibleName(tr("عنوان الطاولات المحفوظة"))
        self.layout.addWidget(self.title_label)

        self.tables_list = _SavedTablesListWidget(self)
        self.tables_list.setAccessibleName(tr("قائمة الطاولات المحفوظة"))
        self.tables_list.itemActivated.connect(self._on_activated)
        body = QHBoxLayout()
        body.addWidget(self.tables_list, 1)
        self.activity_panel = ActivityLogWidget(self, always_visible=True)
        body.addWidget(self.activity_panel, 1)
        self.layout.addLayout(body, 1)
        self.activity_panel.categorySelected.connect(self.activitySelected)
        self.activity_panel.loadOlderRequested.connect(self.loadOlderRequested)
        self._last_tables = []

        subscribe(self._on_language_changed)

    def closeEvent(self, event):
        try:
            unsubscribe(self._on_language_changed)
        except Exception:
            pass
        super().closeEvent(event)

    def _on_language_changed(self, _lang: str):
        self.title_label.setText(tr("الطاولات المحفوظة"))
        self.title_label.setAccessibleName(tr("عنوان الطاولات المحفوظة"))
        self.tables_list.setAccessibleName(tr("قائمة الطاولات المحفوظة"))
        self.update_tables(self._last_tables)

    def _format_datetime(self, iso_str: str) -> str:
        if not iso_str:
            return ""
        try:
            from datetime import datetime
            clean_str = iso_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_str)
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return iso_str[:16].replace("T", " ")

    def _game_label(self, game: str) -> str:
        game_map = {
            "UNO": "أونو",
            "SCOPA": "إسكوبا",
            "NINETY_NINE": "تسعة وتسعون",
            "FARKLE": "فاركل",
            "SNAKES_LADDERS": "السلم والثعبان",
            "DOMINO": "دومينو كلاسيك",
            "AMERICAN_DOMINO": "دومينو أمريكاني",
            "THIEF_HUNT": "مطاردة اللص",
            "TENNIS": "التنس",
        }
        return tr(game_map.get(game, game))

    def update_tables(self, tables: list):
        self._last_tables = list(tables or [])
        self.tables_list.clear()
        if not self._last_tables:
            empty_msg = tr("لا توجد طاولات محفوظة.")
            it = QListWidgetItem(empty_msg)
            it.setData(Qt.UserRole, None)
            self.tables_list.addItem(it)
            return

        for t in self._last_tables:
            sid = t.get("id")
            gname = self._game_label(t.get("game", ""))
            opponents = t.get("opponents_summary") or tr("لا يوجد")
            saved_time = self._format_datetime(t.get("saved_at", ""))
            expires_time = self._format_datetime(t.get("expires_at", ""))

            # Format: Game — Against: X — Saved: Y — Expires: Z
            text = f"{gname} — " + tr("ضد: {0}", opponents) + f" — " + tr("تاريخ الحفظ: {0}", saved_time) + f" — " + tr("تنتهي في: {0}", expires_time)

            it = QListWidgetItem(text)
            it.setData(Qt.UserRole, sid)
            self.tables_list.addItem(it)

        if self.tables_list.count():
            self.tables_list.setCurrentRow(0)

    def _on_activated(self, item: QListWidgetItem):
        sid = item.data(Qt.UserRole)
        if sid:
            self.restoreSelected.emit(int(sid))
