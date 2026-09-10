"""Keyboard-first room navigation: Create/Join, then game categories and sub-menus."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem
from PySide6.QtCore import Signal, Qt
from client.views.activity_log_widget import ActivityLogWidget
from client.views.table_view import handle_list_boundary_navigation
from client.localization import tr, subscribe

class _RoomsMenuListWidget(QListWidget):
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
            if self.owner.handle_escape():
                event.accept()
                return
        super().keyPressEvent(event)


class RoomsMenuView(QWidget):
    itemSelected = Signal(str)
    backRequested = Signal()
    activitySelected = Signal(str)
    loadOlderRequested = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.title_label = QLabel(tr("الطاولات"))
        self.layout.addWidget(self.title_label)
        self.menu_list = _RoomsMenuListWidget(self)
        self.menu_list.setAccessibleName(tr("قائمة الطاولات"))
        self.menu_list.itemActivated.connect(self._on_activated)
        body = QHBoxLayout()
        body.addWidget(self.menu_list, 1)
        self.activity_panel = ActivityLogWidget(self, always_visible=True)
        body.addWidget(self.activity_panel, 1)
        self.layout.addLayout(body, 1)
        self.activity_panel.categorySelected.connect(self.activitySelected)
        self.activity_panel.loadOlderRequested.connect(self.loadOlderRequested)
        self._mode = "main"
        subscribe(self._on_language_changed)
        self._populate()

    def _on_language_changed(self, _lang: str):
        self.menu_list.setAccessibleName(tr("قائمة الطاولات"))
        self._populate()

    def _populate(self, focus_tag: str = None):
        from client.table_framework.adapter import get_adapter
        def get_name(gid):
            ad = get_adapter(gid)
            return tr(ad.display_name) if ad else gid

        self.menu_list.clear()
        if self._mode == "cards_games":
            self.title_label.setText(tr("ألعاب الورق"))
            items = [
                (get_name("UNO"), "create_uno"),
                (get_name("SCOPA"), "create_scopa"),
                (get_name("NINETY_NINE"), "create_ninety_nine"),
            ]
        elif self._mode == "dice_games":
            self.title_label.setText(tr("ألعاب النرد"))
            items = [
                (get_name("FARKLE"), "create_farkle"),
                (get_name("SNAKES_LADDERS"), "create_snakes_ladders"),
            ]
        elif self._mode == "domino_games":
            self.title_label.setText(tr("ألعاب الدومينو"))
            items = [
                (get_name("DOMINO"), "create_domino"),
                (get_name("AMERICAN_DOMINO"), "create_american_domino"),
            ]
        elif self._mode == "memory_games":
            self.title_label.setText(tr("ألعاب الذاكرة والتركيز"))
            items = [
                (get_name("THIEF_HUNT"), "create_thief_hunt"),
            ]
        elif self._mode == "sports_games":
            self.title_label.setText(tr("ألعاب رياضية"))
            items = [
                (get_name("TENNIS"), "create_tennis"),
            ]
        elif self._mode == "games":
            self.title_label.setText(tr("تصنيفات الألعاب لإنشاء الطاولة"))
            items = [
                (tr("ألعاب الكروت"), "category_cards"),
                (tr("ألعاب النرد"), "category_dice"),
                (tr("ألعاب الدومينو"), "category_domino"),
                (tr("ألعاب الذاكرة"), "category_memory"),
                (tr("ألعاب الرياضة"), "category_sports"),
            ]
        else:
            self.title_label.setText(tr("الطاولات"))
            items = [(tr("إنشاء"), "create"), (tr("انضمام"), "join")]

        target_row = 0
        for idx, (label, tag) in enumerate(items):
            it = QListWidgetItem(tr(label))
            it.setData(Qt.UserRole, tag)
            self.menu_list.addItem(it)
            if focus_tag and tag == focus_tag:
                target_row = idx

        if self.menu_list.count():
            self.menu_list.setCurrentRow(target_row)

    def set_category(self, mode: str, spoken_title: str):
        self._mode = mode
        self._populate()
        self.menu_list.setFocus()
        from client.accessibility.reader import reader
        reader.speak(tr(spoken_title), interrupt=True)

    def set_game_selection(self, focus_tag: str = None):
        self._mode = "games"
        self._populate(focus_tag=focus_tag)
        self.menu_list.setFocus()

    def set_main(self, focus_tag: str = None):
        self._mode = "main"
        self._populate(focus_tag=focus_tag)
        self.menu_list.setFocus()

    def handle_escape(self) -> bool:
        category_map = {
            "cards_games": "category_cards",
            "dice_games": "category_dice",
            "domino_games": "category_domino",
            "memory_games": "category_memory",
            "sports_games": "category_sports",
        }
        if self._mode in category_map:
            prev_cat = category_map[self._mode]
            self.set_game_selection(focus_tag=prev_cat)
            return True
        elif self._mode == "games":
            self.set_main(focus_tag="create")
            return True
        elif self._mode == "main":
            self.backRequested.emit()
            return True
        return False

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if self.handle_escape():
                return
        super().keyPressEvent(event)

    def _on_activated(self, item):
        tag = item.data(Qt.UserRole)
        if tag == "soon":
            from client.accessibility.reader import reader
            reader.speak(tr("هذا القسم قيد التطوير وقريبًا سيتم إطلاقه."), interrupt=True)
            return
        if tag == "category_cards":
            self.set_category("cards_games", "ألعاب الكروت")
            return
        if tag == "category_dice":
            self.set_category("dice_games", "ألعاب النرد")
            return
        if tag == "category_domino":
            self.set_category("domino_games", "ألعاب الدومينو")
            return
        if tag == "category_memory":
            self.set_category("memory_games", "ألعاب الذاكرة والذكاء")
            return
        if tag == "category_sports":
            self.set_category("sports_games", "ألعاب الرياضة")
            return
        if tag == "back_to_games":
            self.handle_escape()
            return
        if tag == "back_to_main":
            self.set_main(focus_tag="create")
            return
        if tag:
            self.itemSelected.emit(tag)



