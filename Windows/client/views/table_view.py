"""Accessible table view for TableVerse UNO.

Features:
- Clean 3-point TAB order:
  - Before start: main gameplay focus -> الدردشة -> السجل
  - After start: gameplay/hand -> الدردشة -> السجل
- Pure card names on focus without redundant prefixes or labels.
- Wild color picker modal (أحمر، أصفر، أخضر، أزرق) with "اختر اللون" speech.
- Clean separation between waiting lobby and gameplay.
"""
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
)
from PySide6.QtCore import Qt, Signal, QTimer
from core_shared.uno_rules import card_display_ar
from client.views.activity_log_widget import ActivityLogWidget
from client.localization import tr, subscribe, get_language


def handle_list_boundary_navigation(list_widget: QListWidget, event) -> bool:
    """Clamps Up/Down arrow navigation at list boundaries, repeating the announcement without wrapping.

    Returns True if the boundary condition was handled and event accepted; False otherwise.
    """
    key = event.key()
    if key == Qt.Key_Up:
        if list_widget.currentRow() <= 0:
            if list_widget.count() > 0:
                list_widget.setCurrentRow(0)
                item = list_widget.currentItem() or list_widget.item(0)
                if item and item.text().strip():
                    from client.accessibility.reader import reader
                    reader.speak(item.text(), interrupt=True)
            event.accept()
            return True
    elif key == Qt.Key_Down:
        if list_widget.currentRow() >= list_widget.count() - 1:
            if list_widget.count() > 0:
                last_idx = list_widget.count() - 1
                list_widget.setCurrentRow(last_idx)
                item = list_widget.currentItem() or list_widget.item(last_idx)
                if item and item.text().strip():
                    from client.accessibility.reader import reader
                    reader.speak(item.text(), interrupt=True)
            event.accept()
            return True
    return False


def safe_is_valid(obj) -> bool:
    """Return True if obj is not None and its underlying C++ object is still valid."""
    if obj is None:
        return False
    try:
        import shiboken6
        return bool(shiboken6.isValid(obj))
    except Exception:
        return True


def safe_set_focus(widget) -> None:
    """Safely focus a widget if its underlying C++ object is still valid."""
    if not safe_is_valid(widget):
        return
    try:
        widget.setFocus()
    except (RuntimeError, AttributeError):
        pass


class FocusableWidget(QListWidget):
    """Focusable pre-game gameplay container with no table-name text exposed."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAccessibleName("")
        self.setAccessibleDescription("")
        self.setFocusPolicy(Qt.StrongFocus)
        item = QListWidgetItem("")
        item.setToolTip("")
        item.setStatusTip("")
        item.setWhatsThis("")
        accessible_text_role = getattr(Qt.ItemDataRole, "AccessibleTextRole", None)
        accessible_description_role = getattr(Qt.ItemDataRole, "AccessibleDescriptionRole", None)
        if accessible_text_role is not None:
            item.setData(accessible_text_role, "")
        if accessible_description_role is not None:
            item.setData(accessible_description_role, "")
        self.addItem(item)
        self.setCurrentRow(0)

    def focusInEvent(self, event):
        try:
            super().focusInEvent(event)
        except TypeError:
            pass

    def keyPressEvent(self, event):
        if handle_list_boundary_navigation(self, event):
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        win = self.window()
        if win and hasattr(win, "on_apps_key"):
            win.on_apps_key()
            event.accept()
            return
        super().contextMenuEvent(event)


class CardListWidget(QListWidget):
    """Custom QListWidget that delegates Left/Right arrow keys to the parent TableView."""

    def focusInEvent(self, event):
        try:
            super().focusInEvent(event)
        except TypeError:
            pass

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left:
            parent_table = self.parent()
            while parent_table and not hasattr(parent_table, "_move_card_group"):
                parent_table = parent_table.parent()
            if parent_table:
                parent_table._move_card_group(-1)
                event.accept()
                return
        elif event.key() == Qt.Key_Right:
            parent_table = self.parent()
            while parent_table and not hasattr(parent_table, "_move_card_group"):
                parent_table = parent_table.parent()
            if parent_table:
                parent_table._move_card_group(1)
                event.accept()
                return
        if handle_list_boundary_navigation(self, event):
            return
        super().keyPressEvent(event)


class FarkleDiceList(QListWidget):
    """UNO-style gameplay list used for Farkle dice.

    Farkle keeps the exact shared hand/list interaction model: one real
    QListWidget, NVDA announces the focused die, Up/Down moves within it,
    Space toggles selection, Enter activates, and Tab is the only route out to chat.
    """

    def focusInEvent(self, event):
        try:
            super().focusInEvent(event)
        except TypeError:
            pass

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Left, Qt.Key_Right):
            event.accept()
            return
        if event.key() == Qt.Key_Space:
            item = self.currentItem()
            if item:
                data = item.data(Qt.UserRole)
                if isinstance(data, dict) and data.get("type") == "combo":
                    parent_table = self.parent()
                    while parent_table and not hasattr(parent_table, "_on_farkle_item_activated"):
                        parent_table = parent_table.parent()
                    if parent_table:
                        parent_table._on_farkle_item_activated(item)
                event.accept()
                return
        if handle_list_boundary_navigation(self, event):
            return
        super().keyPressEvent(event)


class DominoTileList(QListWidget):
    """Accessible gameplay list used for Domino hand tiles and actions."""

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Left, Qt.Key_Right):
            event.accept()
            return
        if handle_list_boundary_navigation(self, event):
            return
        super().keyPressEvent(event)


class DominoSideList(QListWidget):
    """Accessible list used to choose the resulting domino table ends (e.g. 5/5 or 0/0)."""

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Left, Qt.Key_Right):
            event.accept()
            return
        if event.key() == Qt.Key_Escape:
            parent_table = self.parent()
            while parent_table and not hasattr(parent_table, "hide_domino_side_selection"):
                parent_table = parent_table.parent()
            if parent_table:
                parent_table.hide_domino_side_selection()
            event.accept()
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            item = self.currentItem()
            if item:
                parent_table = self.parent()
                while parent_table and not hasattr(parent_table, "_on_domino_side_activated"):
                    parent_table = parent_table.parent()
                if parent_table:
                    parent_table._on_domino_side_activated(item)
            event.accept()
            return
        if handle_list_boundary_navigation(self, event):
            return
        super().keyPressEvent(event)


class ScopaCardList(QListWidget):
    """Accessible gameplay list used for Scopa hand cards."""

    def focusInEvent(self, event):
        try:
            super().focusInEvent(event)
        except TypeError:
            pass

    def currentItemChanged(self, current, previous):
        super().currentItemChanged(current, previous)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Left, Qt.Key_Right):
            event.accept()
            return
        if handle_list_boundary_navigation(self, event):
            return
        super().keyPressEvent(event)


class SnakesActionList(QListWidget):
    """Accessible gameplay list used for Snakes and Ladders actions."""

    def focusInEvent(self, event):
        try:
            super().focusInEvent(event)
        except TypeError:
            pass

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            item = self.currentItem()
            if item:
                parent_table = self.parent()
                while parent_table and not hasattr(parent_table, "_on_snakes_item_activated"):
                    parent_table = parent_table.parent()
                if parent_table:
                    parent_table._on_snakes_item_activated(item)
                    event.accept()
                    return
        if event.key() in (Qt.Key_Left, Qt.Key_Right):
            if handle_list_boundary_navigation(self, event):
                return
            item = self.currentItem() or (self.item(0) if self.count() > 0 else None)
            if item and item.text().strip():
                from client.accessibility.reader import reader
                reader.speak(item.text(), interrupt=True)
            event.accept()
            return
        if handle_list_boundary_navigation(self, event):
            return
        super().keyPressEvent(event)


class ThiefFloorList(QListWidget):
    """Pure-list floor selector for Thief Hunt gameplay."""
    def keyPressEvent(self, event):
        if handle_list_boundary_navigation(self, event):
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            item = self.currentItem()
            if item:
                parent_table = self.parent()
                while parent_table and not hasattr(parent_table, "_on_thief_floor_activated"):
                    parent_table = parent_table.parent()
                if parent_table:
                    parent_table._on_thief_floor_activated(item)
            event.accept()
            return
        super().keyPressEvent(event)


class TableView(QWidget):
    cardActivated = Signal(str, dict)
    chatSent = Signal(str)
    thiefActionSubmitted = Signal(str, str)
    farkleActionSubmitted = Signal(str, str)
    dominoActionSubmitted = Signal(str, str, str)
    scopaActionSubmitted = Signal(str, str, str)
    tennisActionSubmitted = Signal(str, dict)

    CATEGORIES_ORDER = [
        ("red", "أحمر"), ("yellow", "أصفر"), ("green", "أخضر"), ("blue", "أزرق"),
        ("orange", "برتقالي"), ("pink", "وردي"), ("purple", "بنفسجي"), ("teal", "تركوازي"),
        ("wild", "تبديل اللون"),
    ]

    WILD_COLOR_OPTIONS = ("أحمر", "أصفر", "أخضر", "أزرق")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self._focus_target = "gameplay"
        self._last_hand_signature = None
        self.is_playing = False
        self.game_type = ""
        self._thief_input_mode = None
        self._thief_answer_timer = QTimer(self)
        self._thief_answer_timer.setSingleShot(True)
        self._thief_answer_timer.setInterval(2000)
        # Local answer-window guard. The server remains authoritative, but
        # the input must become usable immediately when narration ends; it
        # must never wait for the HTTP response that starts the server window.
        self._thief_answer_window_timer = QTimer(self)
        self._thief_answer_window_timer.setSingleShot(True)
        self._thief_answer_window_timer.timeout.connect(self._thief_answer_window_expired)
        self._thief_answer_timer.timeout.connect(self._submit_thief_input)
        self._thief_narrating = False
        self._thief_narration_timer = QTimer(self)
        self._thief_narration_timer.setSingleShot(True)
        self._thief_narration_timer.timeout.connect(self.activate_thief_answer_input)
        # Card presentation mode: color groups by default; Shift+H toggles numeric groups.
        self.card_group_mode = "color"
        self._last_farkle_roll_sig = None
        self._last_farkle_rendered_sig = None
        self._farkle_selected_dice = []
        self.farkle_container = None
        self.farkle_dice_list = None
        self._last_domino_rendered_sig = None
        self._last_scopa_rendered_sig = None
        self._scopa_gameplay_focus = False

        # Dynamic category tracking
        self.card_groups: list[CardListWidget] = []
        self.category_keys: list[str] = []
        self.category_labels: list[str] = []
        self.active_card_group: int = 0
        self._last_cards = None
        subscribe(self._on_language_changed)

        # 1. Main Table Screen (Pre-game empty table screen)
        self.main_table_widget = FocusableWidget(self)
        self.main_table_widget.setAccessibleName("")
        self.main_table_widget.setAccessibleDescription("")
        # NOTE: itemActivated is NOT connected here. HardwareKeyFilter intercepts
        # VK_RETURN on this widget and calls _menu_start_game directly; connecting
        # itemActivated as well would cause _menu_start_game to be invoked twice.
        self.layout.addWidget(self.main_table_widget)

        # 2. Dynamic Gameplay Container
        self.gameplay_container = QWidget(self)
        self.gameplay_layout = QVBoxLayout(self.gameplay_container)
        self.gameplay_layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.gameplay_container, 1)

        # 4. Wild Color Selection List (Hidden by default)
        self.wild_color_list = QListWidget(self)
        self.wild_color_list.setAccessibleName(tr("اختيار اللون"))
        self.wild_color_list.setAccessibleDescription("")
        for color_name in self.WILD_COLOR_OPTIONS:
            item = QListWidgetItem(tr(color_name))
            item.setData(Qt.UserRole, color_name)
            self.wild_color_list.addItem(item)
        self.wild_color_list.hide()
        self.wild_color_list.itemActivated.connect(self._wild_color_activated)
        self.layout.addWidget(self.wild_color_list)

        # 4b. 99 Value Choice List (Hidden by default)
        self.ninety_nine_choice_list = QListWidget(self)
        self.ninety_nine_choice_list.setAccessibleName("")
        self.ninety_nine_choice_list.setAccessibleDescription("")
        self.ninety_nine_choice_list.hide()
        self.ninety_nine_choice_list.itemActivated.connect(self._ninety_nine_choice_activated)
        self.layout.addWidget(self.ninety_nine_choice_list)

        # 4. Chat Input
        self.chat_input = QLineEdit()
        self.chat_input.setFocusPolicy(Qt.ClickFocus)
        self.chat_input.setPlaceholderText(tr("الدردشة..."))
        self.chat_input.setAccessibleName(tr("الدردشة"))
        self.chat_input.setAccessibleDescription("")
        self.chat_input.returnPressed.connect(self._on_chat_sent)
        self.layout.addWidget(self.chat_input)

        # 5. Canonical Activity Log — EXACT same widget used by Home.
        self.activity_panel = ActivityLogWidget(self, always_visible=True)
        self.layout.addWidget(self.activity_panel, 1)
        self.activity_log = self.activity_panel.activity_log
        self.activity_categories = self.activity_panel.activity_log
        self.activity_panel.categorySelected.connect(self._on_activity_category_selected)

        self._update_tab_order()

    def get_game_title(self) -> str:
        from client.table_framework.adapter import get_adapter
        adapter = get_adapter(self.game_type)
        return adapter.display_name if adapter else (self.game_type or "")

    def set_game_type(self, game_type: str):
        new_game_type = str(game_type or "").upper()
        previous_game_type = self.game_type
        self.game_type = new_game_type
        self._last_hand_signature = None
        
        # Hide any active adapter-specific popups when game type changes
        if previous_game_type != new_game_type:
            if hasattr(self, 'thief_answer_input'):
                if self.thief_answer_input.hasFocus():
                    self.main_table_widget.show()
                    self.main_table_widget.setFocus()
                self.thief_answer_input.hide()
            if hasattr(self, 'wild_color_list'): self.wild_color_list.hide()
            if hasattr(self, 'domino_side_list'): self.domino_side_list.hide()
            
        self.main_table_widget.setAccessibleName("")
        self.main_table_widget.setAccessibleDescription("")
        self._clear_main_table_item_text()

    def _on_language_changed(self, _lang: str):
        if hasattr(self, "wild_color_list"):
            self.wild_color_list.clear()
            for color_name in self.WILD_COLOR_OPTIONS:
                self.wild_color_list.addItem(QListWidgetItem(tr(color_name)))
        
        self._last_hand_signature = None
        self._last_domino_rendered_sig = None
        self._last_farkle_rendered_sig = None
        self._last_scopa_rendered_sig = None

        if hasattr(self, "_last_cards") and self._last_cards is not None:
            self.update_hand(self._last_cards)
        if hasattr(self, "_domino_state") and self._domino_state:
            self._render_domino_items()
        if hasattr(self, "_farkle_state") and self._farkle_state:
            self._render_farkle_items()
        if hasattr(self, "_scopa_state") and self._scopa_state:
            self._render_scopa_items()
        if hasattr(self, "_snakes_state") and self._snakes_state:
            self._render_snakes_items()

    def set_playing_mode(self, playing: bool):
        prev_playing = getattr(self, "is_playing", None)
        self.is_playing = playing
        if playing:
            self._focus_target = "gameplay"
        self.main_table_widget.setVisible(not playing)
        
        if prev_playing != playing:
            from client.table_framework.adapter import get_adapter
            adapter = get_adapter(self.game_type)
            if adapter and adapter.setup_ui:
                adapter.setup_ui(self, playing)
            
            # Prevent Qt from auto-shifting focus to Chat when main_table_widget is hidden
            if not playing and (self._focus_target == "gameplay" or (not self.chat_input.hasFocus() and not self.activity_log.hasFocus())):
                self.main_table_widget.show()
                safe_set_focus(self.main_table_widget)
            elif playing and (self._focus_target == "gameplay" or (not self.chat_input.hasFocus() and not self.activity_log.hasFocus())):
                # Delay slightly to allow newly mounted widgets to become visible
                for delay in (0, 30, 80, 150):
                    QTimer.singleShot(delay, lambda s=self: s.focus_initial() if safe_is_valid(s) else None)
        else:
            # Fallback to clear if no adapter (should not happen for migrated games)
            if not playing:
                for i in reversed(range(self.gameplay_layout.count())):
                    w = self.gameplay_layout.itemAt(i).widget()
                    if w: w.hide()
                if hasattr(self, 'thief_answer_input'):
                    if self.thief_answer_input.hasFocus():
                        self.main_table_widget.show()
                        safe_set_focus(self.main_table_widget)
                    self.thief_answer_input.setEnabled(False)
                    self.thief_answer_input.hide()
                if hasattr(self, 'wild_color_list'): self.wild_color_list.hide()
                if hasattr(self, 'domino_side_list'): self.domino_side_list.hide()
                if self._focus_target == "gameplay" or (not self.chat_input.hasFocus() and not self.activity_log.hasFocus()):
                    self.main_table_widget.show()
                    safe_set_focus(self.main_table_widget)

    def mount_game_ui(self, widget: QWidget):
        # Hide all OTHER widgets in gameplay_layout without hiding widget itself
        for i in reversed(range(self.gameplay_layout.count())):
            w = self.gameplay_layout.itemAt(i).widget()
            if w and w != widget:
                w.hide()
            
        # Add the new widget if not already in layout
        if self.gameplay_layout.indexOf(widget) == -1:
            self.gameplay_layout.addWidget(widget)
        if not widget.isVisible():
            widget.show()
        self._update_tab_order()

    def configure_thief_state(self, state: dict | None):
        state = state or {}
        phase = state.get("phase", "")
        active = bool(state.get("active"))
        self.set_playing_mode(active)
        if self.game_type != "THIEF_HUNT":
            return
        lst = getattr(self, "thief_answer_input", None)
        if lst is None:
            return
        selectable = (phase == "choose_floor" and bool(state.get("is_thief"))) or (phase == "answering" and not bool(state.get("is_thief")))
        if selectable:
            self._thief_input_mode = phase
            lst.setAccessibleName(tr("اختيار طابق اللص") if phase == "choose_floor" else tr("إجابة الطابق"))
            lst.setAccessibleDescription(tr("اختر رقم الطابق من 1 إلى 10 ثم اضغط Enter"))
            lst.setEnabled(True)
            lst.show()
            if lst.currentRow() < 0:
                lst.setCurrentRow(0)
            if not lst.hasFocus():
                QTimer.singleShot(0, lambda w=lst: safe_set_focus(w))
        elif phase in ("escape", "round_result") and not state.get("is_thief"):
            self._thief_input_mode = phase
            lst.setEnabled(False)
            lst.show()
        else:
            self._thief_input_mode = None
            self._thief_narrating = False
            self._thief_narration_timer.stop()
            self._thief_answer_timer.stop()
            self._thief_answer_window_timer.stop()
            if self.is_playing:
                lst.setEnabled(True)
                lst.show()
            else:
                lst.hide()
        self._update_tab_order()


    def begin_thief_narration(self, duration_ms: int):
        self._thief_narrating = True
        self._thief_narration_timer.stop()
        lst = getattr(self, "thief_answer_input", None)
        if lst is not None:
            lst.setEnabled(False)
            lst.show()
        self._update_tab_order()
        self._thief_narration_timer.start(max(0, int(duration_ms)))


    def activate_thief_answer_input(self, open_server_window: bool = True):
        self._thief_narrating = False
        if self.game_type != "THIEF_HUNT" or not self.is_playing:
            return
        lst = getattr(self, "thief_answer_input", None)
        if lst is None:
            return
        self._thief_input_mode = "answer"
        lst.setAccessibleName(tr("إجابة الطابق"))
        lst.setAccessibleDescription(tr("اختر رقم الطابق من 1 إلى 10 ثم اضغط Enter"))
        lst.setEnabled(True)
        lst.show()
        self._focus_target = "gameplay"
        if lst.currentRow() < 0:
            lst.setCurrentRow(0)
        self._update_tab_order()
        safe_set_focus(lst)
        self._thief_answer_window_timer.stop()
        if open_server_window:
            self.thiefActionSubmitted.emit("begin_answering", "")


    def ensure_thief_answer_input_visible(self):
        if self.game_type != "THIEF_HUNT" or not self.is_playing:
            return
        lst = getattr(self, "thief_answer_input", None)
        if lst is None:
            return
        self._thief_input_mode = "answer"
        self._thief_narrating = False
        self._thief_narration_timer.stop()
        lst.setEnabled(True)
        lst.show()
        lst.setAccessibleName(tr("إجابة الطابق"))
        lst.setAccessibleDescription(tr("اختر رقم الطابق من 1 إلى 10 ثم اضغط Enter"))
        if lst.currentRow() < 0:
            lst.setCurrentRow(0)
        if self._focus_target == "gameplay" or (not self.chat_input.hasFocus() and not self.activity_log.hasFocus()):
            safe_set_focus(lst)
        self._update_tab_order()


    def _thief_answer_window_expired(self):
        """Disable the local floor selector after the answer window closes."""
        if self.game_type != "THIEF_HUNT" or self._thief_input_mode != "answer":
            return
        if getattr(self, "thief_answer_input", None) is not None:
            self.thief_answer_input.setEnabled(False)
        self._thief_input_mode = None
        self._update_tab_order()

    def _on_thief_floor_activated(self, item: QListWidgetItem):
        if self.game_type != "THIEF_HUNT" or not self.is_playing:
            return
        if self._thief_input_mode not in ("choose_floor", "answer"):
            return
        value = str(item.data(Qt.UserRole) or item.text()).strip()
        if not value.isdigit() or not 1 <= int(value) <= 10:
            return
        mode = self._thief_input_mode
        if mode == "choose_floor":
            self.thiefActionSubmitted.emit("choose_floor", value)
        else:
            self.thiefActionSubmitted.emit("answer", value)
            self.thief_answer_input.setEnabled(False)

    def _submit_thief_input(self):
        lst = getattr(self, "thief_answer_input", None)
        if lst is not None and lst.currentItem() is not None:
            self._on_thief_floor_activated(lst.currentItem())


    def _thief_answer_changed(self, text: str):
        # Compatibility hook retained for old callers; gameplay is now list based.
        return


    def show_wild_colors(self):
        self.wild_color_list.clear()
        options = self.WILD_COLOR_OPTIONS
        app = self.window()
        state = getattr(app, "uno_state", None) or {}
        if state.get("dark_side"):
            options = ("برتقالي", "وردي", "بنفسجي", "تركوازي")
        for color_name in options:
            item = QListWidgetItem(tr(color_name))
            item.setData(Qt.UserRole, color_name)
            self.wild_color_list.addItem(item)
        self.wild_color_list.show()
        self.cards_container.hide()
        self.wild_color_list.setCurrentRow(0)
        self.wild_color_list.setFocus()

    def hide_wild_colors(self):
        self.wild_color_list.hide()
        if self.is_playing:
            self.cards_container.show()
            self._show_active_card_group()
        else:
            self.main_table_widget.show()
            self.main_table_widget.setFocus()

    def _wild_color_activated(self, item: QListWidgetItem):
        if self.wild_color_list.isHidden():
            return
        colors_map = {
            "أحمر": "red", "red": "red",
            "أصفر": "yellow", "yellow": "yellow",
            "أخضر": "green", "green": "green",
            "أزرق": "blue", "blue": "blue",
            "برتقالي": "orange", "orange": "orange",
            "وردي": "pink", "pink": "pink",
            "بنفسجي": "purple", "purple": "purple",
            "تركوازي": "teal", "teal": "teal",
        }
        val = str(item.data(Qt.UserRole) or item.text()).strip()
        color = colors_map.get(val.lower(), colors_map.get(val, "red"))
        if color:
            self.wild_color_list.hide()
            if self.is_playing:
                self.cards_container.show()
                self._show_active_card_group()
            self.cardActivated.emit("__WILD_COLOR__", {"chosen_color": color})

    # ---------- 99 Value Selection (Ace / 10) ----------
    def show_ninety_nine_choice(self, options: list):
        self.ninety_nine_choice_list.clear()
        for label, val in options:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, val)
            self.ninety_nine_choice_list.addItem(item)
        self.ninety_nine_choice_list.show()
        if hasattr(self, "cards_container"):
            self.cards_container.hide()
        self.ninety_nine_choice_list.setCurrentRow(0)
        self.ninety_nine_choice_list.setFocus()

    def hide_ninety_nine_choice(self):
        self.ninety_nine_choice_list.hide()
        if self.is_playing:
            if hasattr(self, "cards_container"):
                self.cards_container.show()
            self._show_active_card_group()
        else:
            self.main_table_widget.show()
            self.main_table_widget.setFocus()

    def _ninety_nine_choice_activated(self, item: QListWidgetItem):
        if self.ninety_nine_choice_list.isHidden():
            return
        val = item.data(Qt.UserRole)
        self.hide_ninety_nine_choice()
        app = self.window()
        if hasattr(app, "_send_uno_action"):
            app._send_uno_action("choose", str(val))

    def _update_tab_order(self):
        # Qt dynamic tab ordering across different parents can fail or behave like 
        # separate windows for screen readers. We explicitly route Tab/Shift+Tab 
        # using focusNextPrevChild instead.
        pass


    def focusNextPrevChild(self, next_focus):
        from PySide6.QtWidgets import QApplication
        current = QApplication.focusWidget()
        if not current:
            return super().focusNextPrevChild(next_focus)

        first_widget = self.main_table_widget
        from client.table_framework.adapter import get_adapter
        adapter = get_adapter(self.game_type)
        if adapter and hasattr(adapter, 'get_first_widget') and adapter.get_first_widget:
            fw = adapter.get_first_widget(self)
            if fw:
                first_widget = fw
        elif self.is_playing:
            try:
                active_lst = self.get_active_card_list()
                first_widget = active_lst if active_lst else self.main_table_widget
            except Exception:
                first_widget = self.main_table_widget
        
        if current == self.chat_input:
            if next_focus:
                self._focus_target = "activity_log"
                self.activity_log.setFocus()
            else:
                self._focus_target = "gameplay"
                first_widget.setFocus()
            return True

        elif current == self.activity_log:
            if next_focus:
                self._focus_target = "gameplay"
                first_widget.setFocus()
            else:
                self._focus_target = "chat"
                self.chat_input.setFocus()
            return True
        else:
            # Current is some table element (cards, dominoes, dice, etc)
            if next_focus:
                self._focus_target = "chat"
                self.chat_input.setFocus()
            else:
                self._focus_target = "activity_log"
                self.activity_log.setFocus()
            return True


    def update_farkle_state(self, state: dict | None):
        state = state or {}
        if self.game_type != "FARKLE":
            return
        self._farkle_state = state
        is_active = bool(state.get("active"))
        if getattr(self, "farkle_container", None) is not None:
            self.farkle_container.setVisible(is_active)

        dice = list(state.get("dice") or [])
        sig = (tuple(dice), state.get("event_id"), state.get("current_player_id"))
        if sig != self._last_farkle_roll_sig:
            self._last_farkle_roll_sig = sig
            self._farkle_selected_dice.clear()

        scores = state.get("scores") or {}
        current_name = state.get("current_player_name", "")
        turn_score = int(state.get("turn_score", 0) or 0)
        if getattr(self, "farkle_dice_list", None) is not None:
            self.farkle_dice_list.setAccessibleDescription("")
            self._render_farkle_items()
        self._update_tab_order()


    def _is_modal_active(self) -> bool:
        from PySide6.QtWidgets import QApplication
        if hasattr(self, "wild_color_list") and not self.wild_color_list.isHidden():
            return True
        if hasattr(self, "domino_side_list") and not self.domino_side_list.isHidden():
            return True
        if hasattr(self, "ninety_nine_choice_list") and not self.ninety_nine_choice_list.isHidden():
            return True
        return (
            QApplication.activeModalWidget() is not None
            or QApplication.activePopupWidget() is not None
        )


    def _render_farkle_items(self):
        if getattr(self, "farkle_dice_list", None) is None:
            return
        state = self._farkle_state or {}
        dice = list(state.get("dice") or [])
        my_turn = bool(state.get("is_my_turn"))
        can_roll = (
            my_turn
            and bool(state.get("can_roll"))
            and not bool(state.get("must_score_before_roll"))
        )
        turn_score = int(state.get("turn_score", 0) or 0)
        available_combos = state.get("available_combinations") or []

        new_sig = (
            state.get("event_id"),
            tuple(dice),
            turn_score,
            my_turn,
            can_roll,
            get_language(),
            tuple(c.get("label", "") for c in available_combos),
        )
        if getattr(self, "_last_farkle_rendered_sig", None) == new_sig:
            return
        self._last_farkle_rendered_sig = new_sig

        current_row = max(0, self.farkle_dice_list.currentRow())
        had_dice_focus = (
            self.farkle_dice_list.hasFocus()
            or (hasattr(self.farkle_dice_list, "viewport") and self.farkle_dice_list.viewport().hasFocus())
        )

        self.farkle_dice_list.blockSignals(True)
        self.farkle_dice_list.clear()

        if my_turn:
            # 1. Available winning combinations from the roll
            # Use the centralized localization path for the displayed label.
            # label_en remains metadata only; game state must not bypass the
            # authoritative client translation system.
            for combo in available_combos:
                label_ar = combo.get("label", "")
                label_en = combo.get("label_en", "")
                item_text = tr(label_ar) if label_ar else label_en
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, {
                    "type": "combo",
                    "indices": combo["indices"],
                    "label": label_ar,
                    "label_en": label_en,
                    "points": combo["points"],
                })
                item.setData(Qt.UserRole + 1101, label_ar)
                item.setData(Qt.UserRole + 1102, item_text)
                self.farkle_dice_list.addItem(item)

            # 2. Roll dice option
            num_dice_to_roll = len(dice) if dice else 6
            roll_text = f"ارمِ {num_dice_to_roll} نرد"
            roll_display = tr(roll_text)
            item = QListWidgetItem(roll_display)
            item.setData(Qt.UserRole, {
                "type": "action",
                "action": "roll",
                "label": roll_text,
            })
            item.setData(Qt.UserRole + 1101, roll_text)
            item.setData(Qt.UserRole + 1102, roll_display)
            self.farkle_dice_list.addItem(item)

            # 3. Bank points option
            bank_text = f"تثبيت {turn_score} نقطة لهذا الدور"
            bank_display = tr(bank_text)
            item = QListWidgetItem(bank_display)
            item.setData(Qt.UserRole, {
                "type": "action",
                "action": "bank",
                "label": bank_text,
            })
            item.setData(Qt.UserRole + 1101, bank_text)
            item.setData(Qt.UserRole + 1102, bank_display)
            self.farkle_dice_list.addItem(item)
        else:
            curr_name = state.get("current_player_name", "اللاعب")
            if dice:
                dice_str = " ".join(map(str, sorted(dice)))
                raw_dice = f"نرد {curr_name}: {dice_str}"
                disp_dice = tr(raw_dice)
                item = QListWidgetItem(disp_dice)
                item.setData(Qt.UserRole, {"type": "info"})
                item.setData(Qt.UserRole + 1101, raw_dice)
                item.setData(Qt.UserRole + 1102, disp_dice)
                self.farkle_dice_list.addItem(item)
            raw_wait = f"في انتظار دور {curr_name}..."
            disp_wait = tr(raw_wait)
            item = QListWidgetItem(disp_wait)
            item.setData(Qt.UserRole, {"type": "info"})
            item.setData(Qt.UserRole + 1101, raw_wait)
            item.setData(Qt.UserRole + 1102, disp_wait)
            self.farkle_dice_list.addItem(item)

        self.farkle_dice_list.blockSignals(False)

        if self.farkle_dice_list.count() > 0:
            target_row = min(current_row, self.farkle_dice_list.count() - 1)
            self.farkle_dice_list.setCurrentRow(target_row)
            if self.is_playing and not self._is_modal_active():
                if had_dice_focus or (self._focus_target == "gameplay") or (not self.chat_input.hasFocus() and not self.activity_log.hasFocus()):
                    self.farkle_dice_list.setFocus()


    def _on_farkle_item_activated(self, item: QListWidgetItem):
        if item is None:
            return
        data = item.data(Qt.UserRole)
        if not data or not isinstance(data, dict):
            return
        dtype = data.get("type")
        state = self._farkle_state or {}
        from client.accessibility.reader import reader
        from client.audio.sound_engine import sound_engine

        if dtype == "info":
            text = item.text()
            reader.speak(text, interrupt=True)
            return
        elif dtype == "action":
            action = data.get("action")
            if action == "roll":
                if state.get("must_score_before_roll"):
                    reader.speak(tr("يجب عليك اختيار وتثبيت مجموعة رابحة أولًا قبل الرمي مجددًا."), interrupt=True)
                    sound_engine.play_event("INVALID_ACTION")
                    return
                self.farkleActionSubmitted.emit("roll", "")
            elif action == "bank":
                turn_score = int(state.get("turn_score", 0) or 0)
                min_bank = int(state.get("min_bank", 30) or 30)
                if state.get("must_score_before_roll"):
                    reader.speak(tr("يجب عليك اختيار مجموعة رابحة أولًا قبل تثبيت النقاط."), interrupt=True)
                    sound_engine.play_event("INVALID_ACTION")
                    return
                if turn_score < min_bank:
                    reader.speak(tr(f"لا يمكنك التثبيت الآن. الحد الأدنى للتثبيت هو {min_bank} نقطة."), interrupt=True)
                    sound_engine.play_event("INVALID_ACTION")
                    return
                self.farkleActionSubmitted.emit("bank", "")
        elif dtype == "combo":
            indices = data.get("indices") or []
            if indices:
                indices_str = ",".join(str(x) for x in sorted(indices))
                self.farkleActionSubmitted.emit("score", indices_str)


    def update_domino_state(self, state: dict | None):
        state = state or {}
        if self.game_type not in ("DOMINO", "AMERICAN_DOMINO"):
            return
        self._domino_state = state
        is_active = bool(state.get("active"))
        if not is_active or not self.is_playing:
            self._last_domino_rendered_sig = None
            self.domino_tile_list.clear()
            self.domino_side_list.clear()
            self.domino_side_list.hide()
            self.domino_container.hide()
            self.main_table_widget.show()
            return
        if hasattr(self, "domino_side_list") and self.domino_side_list.isVisible():
            return
        self.domino_container.setVisible(True)
        self._render_domino_items()


    def _render_domino_items(self):
        state = self._domino_state or {}
        if not state.get("active"):
            return

        hand = list(state.get("hand") or [])
        left_end = state.get("left_end")
        right_end = state.get("right_end")
        is_my_turn = bool(state.get("is_my_turn"))
        can_draw = bool(state.get("can_draw"))
        can_pass = bool(state.get("can_pass"))
        boneyard_count = int(state.get("boneyard_count", 0))

        new_sig = (
            tuple((h.get("tile"), h.get("is_valid"), tuple(h.get("valid_sides") or [])) for h in hand),
            left_end, right_end, is_my_turn, can_draw, can_pass, boneyard_count,
            state.get("event_id"), state.get("current_player_id")
        )
        if getattr(self, "_last_domino_rendered_sig", None) == new_sig:
            return
        self._last_domino_rendered_sig = new_sig

        current_row = max(0, self.domino_tile_list.currentRow())
        had_tile_focus = (
            self.domino_tile_list.hasFocus()
            or (hasattr(self.domino_tile_list, "viewport") and self.domino_tile_list.viewport().hasFocus())
        )
        self.domino_tile_list.blockSignals(True)
        self.domino_tile_list.clear()

        if is_my_turn:
            for item_data in hand:
                idx = item_data.get("index")
                label = item_data.get("label", "")
                is_valid = item_data.get("is_valid")
                valid_sides = item_data.get("valid_sides") or []

                item_text = tr(label)
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, {
                    "type": "tile",
                    "tile_index": idx,
                    "tile": item_data.get("tile"),
                    "is_valid": is_valid,
                    "valid_sides": valid_sides,
                    "label": label
                })
                self.domino_tile_list.addItem(item)
        else:
            curr_name = state.get("current_player_name", "اللاعب")
            for item_data in hand:
                label = item_data.get("label", "")
                item = QListWidgetItem(tr(label))
                item.setData(Qt.UserRole, {"type": "info"})
                self.domino_tile_list.addItem(item)
            wait_item = QListWidgetItem(tr(f"في انتظار دور {curr_name}..."))
            wait_item.setData(Qt.UserRole, {"type": "info"})
            self.domino_tile_list.addItem(wait_item)

        self.domino_tile_list.blockSignals(False)

        if self.domino_tile_list.count() > 0:
            target_row = min(current_row, self.domino_tile_list.count() - 1)
            self.domino_tile_list.setCurrentRow(target_row)
            if self.is_playing and not (hasattr(self, "domino_side_list") and self.domino_side_list.isVisible()) and not self._is_modal_active():
                if had_tile_focus or (self._focus_target == "gameplay") or (not self.chat_input.hasFocus() and not self.activity_log.hasFocus()):
                    self.domino_tile_list.setFocus()


    def show_domino_side_selection(self, tile_index: int, tile: list, right_result: str, left_result: str):
        self.domino_side_list.blockSignals(True)
        self.domino_side_list.clear()

        item_r = QListWidgetItem(tr(right_result))
        item_r.setData(Qt.UserRole, {"tile_index": tile_index, "side": "right"})
        self.domino_side_list.addItem(item_r)

        item_l = QListWidgetItem(tr(left_result))
        item_l.setData(Qt.UserRole, {"tile_index": tile_index, "side": "left"})
        self.domino_side_list.addItem(item_l)

        self.domino_side_list.blockSignals(False)
        self.domino_side_list.show()
        self.domino_container.hide()
        self._update_tab_order()
        self.domino_side_list.setCurrentRow(0)
        self.domino_side_list.setFocus()


    def hide_domino_side_selection(self):
        self.domino_side_list.hide()
        if self.is_playing:
            self.domino_container.show()
            self.domino_tile_list.setFocus()
        self._update_tab_order()


    def _prompt_domino_side_selection(self, tile_index: int, tile: list, valid_sides: list):
        state = self._domino_state or {}
        l_end = state.get("left_end")
        r_end = state.get("right_end")
        if l_end is None or r_end is None or len(tile) != 2:
            self.dominoActionSubmitted.emit("play", str(tile_index), "right")
            return

        a, b = tile[0], tile[1]

        # Calculate what the table ends will become if played on right:
        new_r = b if a == r_end else a
        right_result = f"{l_end}/{new_r}"

        # Calculate what the table ends will become if played on left:
        new_l = b if a == l_end else a
        left_result = f"{new_l}/{r_end}"

        self.show_domino_side_selection(tile_index, tile, right_result, left_result)


    def _on_domino_side_activated(self, item: QListWidgetItem):
        data = item.data(Qt.UserRole)
        if not data or not isinstance(data, dict):
            return
        tile_index = data.get("tile_index")
        side = data.get("side", "right")
        self.hide_domino_side_selection()
        self.dominoActionSubmitted.emit("play", str(tile_index), side)


    # ---------- Dynamic Category Navigation ----------
    def get_active_card_list(self) -> CardListWidget | None:
        if self.card_groups and 0 <= self.active_card_group < len(self.card_groups):
            return self.card_groups[self.active_card_group]
        return None

    def _show_active_card_group(self):
        if not self.card_groups:
            return
        for i, lst in enumerate(self.card_groups):
            lst.setVisible(i == self.active_card_group)
        lst = self.card_groups[self.active_card_group]
        if lst.count() > 0:
            if lst.currentRow() < 0:
                lst.setCurrentRow(0)
            lst.setFocus()
        self._update_tab_order()

    def _focus_card_group(self, index: int, target_row: int = 0, announce: bool = True, force_focus: bool = False):
        """Focus a specific card group list.
        Added guard to prevent duplicate announcements when the same widget
        receives focus repeatedly (e.g., during tab cycling). The instance
        attribute ``_last_announced_widget`` tracks the last widget that was
        announced via ``reader.speak``. If the newly focused list is the same
        as the previous one, the speech output is suppressed.

        ``force_focus`` bypasses the chat/log hasFocus guard and is used when
        the user explicitly navigates via Left/Right arrow keys so that focus
        always lands on the new card group, even if Qt stole focus to chat_input
        while hiding the previously focused list.
        """
        if not self.card_groups:
            return
        if hasattr(self, "wild_color_list") and not self.wild_color_list.isHidden():
            return
        if hasattr(self, "ninety_nine_choice_list") and not self.ninety_nine_choice_list.isHidden():
            return
        index = index % len(self.card_groups)
        self.active_card_group = index

        lst = self.card_groups[index]

        # Set row and show the target list BEFORE hiding others.
        # This prevents Qt from auto-moving focus to chat_input when the
        # currently-focused list becomes invisible.
        if lst.count() > 0:
            row = max(0, min(target_row, lst.count() - 1))
            lst.setCurrentRow(row)

        # Show target first, then hide others â€“ avoids focus theft on hide.
        lst.setVisible(True)
        for i, other in enumerate(self.card_groups):
            if i != index:
                other.setVisible(False)

        if lst.count() > 0:
            pending = getattr(self, "_pending_uno_focus", False)
            if pending:
                self._pending_uno_focus = False
            take_focus = force_focus or pending or (self._focus_target == "gameplay") or (not self.chat_input.hasFocus() and not self.activity_log.hasFocus())
            if not self._is_modal_active() and take_focus:
                lst.setFocus()
                for delay in (0, 30, 80, 150):
                    QTimer.singleShot(
                        delay,
                        lambda w=lst: safe_set_focus(w) if safe_is_valid(w) and (self._focus_target == "gameplay" or not (self.chat_input.hasFocus() or self.activity_log.hasFocus())) else None
                    )
            if announce:
                # Avoid repeating the same announcement.
                if getattr(self, "_last_announced_widget", None) != lst:
                    from client.accessibility.reader import reader
                    item = lst.currentItem()
                    item_text = item.text() if item else ""
                    reader.speak(item_text, interrupt=True)
                    self._last_announced_widget = lst
        else:
            take_focus = force_focus or (self._focus_target == "gameplay") or (not self.chat_input.hasFocus() and not self.activity_log.hasFocus())
            if not self._is_modal_active() and take_focus:
                lst.setFocus()
        self._update_tab_order()

    def _move_card_group(self, delta: int):
        if not self.card_groups or len(self.card_groups) <= 1:
            return
        curr_lst = self.card_groups[self.active_card_group]
        current_row = max(0, curr_lst.currentRow())
        next_index = (self.active_card_group + delta) % len(self.card_groups)
        self._focus_card_group(next_index, current_row, announce=True, force_focus=True)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left:
            self._move_card_group(-1)
            event.accept()
            return
        if event.key() == Qt.Key_Right:
            self._move_card_group(1)
            event.accept()
            return
        super().keyPressEvent(event)

    # ---------- Dynamic Hand Update & Focus Preservation ----------
    def update_hand(self, hand_cards: list[dict], drawn_card_id: str | None = None):
        """Render the authoritative private hand into the shared gameplay list."""
        hand_cards = hand_cards or []
        if self.is_playing and self.game_type in ("UNO", "NINETY_NINE"):
            if not getattr(self, "cards_container", None):
                from client.table_framework.adapter import get_adapter
                adapter = get_adapter(self.game_type)
                if adapter and adapter.setup_ui:
                    adapter.setup_ui(self, True)
            if getattr(self, "cards_container", None) is not None:
                self.mount_game_ui(self.cards_container)
                self.cards_container.show()
        self._current_hand_cards = list(hand_cards)
        sig = tuple(
            (c.get("id", ""), c.get("type", ""), c.get("color", ""), c.get("value", None))
            for c in hand_cards
        ) + (drawn_card_id,)

        if self._last_hand_signature == sig:
            return
        self._last_hand_signature = sig

        # 1. Capture current focus state before rebuilding
        prev_key = ""
        prev_cat_index = self.active_card_group
        prev_row = 0
        prev_card_id = ""
        had_gameplay_focus = (
            self._focus_target == "gameplay"
            or any(lst.hasFocus() or (hasattr(lst, "viewport") and lst.viewport().hasFocus()) for lst in self.card_groups)
            or getattr(self, "_pending_uno_focus", False)
            or (self.is_playing and not (self.chat_input.hasFocus() or self.activity_log.hasFocus()))
        )

        if self.card_groups and 0 <= self.active_card_group < len(self.card_groups):
            prev_key = self.category_keys[self.active_card_group]
            prev_lst = self.card_groups[self.active_card_group]
            prev_row = max(0, prev_lst.currentRow())
            prev_item = prev_lst.currentItem()
            if prev_item:
                prev_card_id = str(prev_item.data(Qt.UserRole) or "")

        # 2. Partition hand cards according to the active presentation mode.
        wild_types = {"wild", "wild_draw_two", "wild_draw_four", "wild_draw_six", "wild_draw_ten", "wild_reverse_draw_four", "color_roulette"}
        wild_cards = [
            c for c in hand_cards
            if str(c.get("type", "")).lower() in wild_types
        ]

        if self.card_group_mode == "number":
            # Numeric mode: each number is its own dynamic category.
            # Within a number, cards are grouped by color in the standard
            # color order. Action cards remain separate logical groups.
            color_order = {
                "red": 0, "yellow": 1, "green": 2, "blue": 3,
                "orange": 4, "pink": 5, "purple": 6, "teal": 7,
            }
            number_buckets = {n: [] for n in range(10)}
            skip_cards, reverse_cards, draw_two_cards, skip_everyone_cards = [], [], [], []
            discard_all_cards, buzzer_cards, flip_cards = [], [], []
            standard_cards = []
            for card in hand_cards:
                ctype = str(card.get("type", "")).lower()
                color = str(card.get("color", "")).lower()
                if ctype == "number":
                    try:
                        value = int(card.get("value"))
                    except (TypeError, ValueError):
                        continue
                    if 0 <= value <= 9:
                        number_buckets[value].append(card)
                elif ctype == "skip":
                    skip_cards.append(card)
                elif ctype == "reverse":
                    reverse_cards.append(card)
                elif ctype == "draw_two":
                    draw_two_cards.append(card)
                elif ctype == "skip_everyone":
                    skip_everyone_cards.append(card)
                elif ctype == "discard_all":
                    discard_all_cards.append(card)
                elif ctype == "buzzer":
                    buzzer_cards.append(card)
                elif ctype == "flip":
                    flip_cards.append(card)
                elif card.get("suit") and not ctype:
                    standard_cards.append(card)

            active_specs = []
            for number in range(10):
                cards_in_bucket = number_buckets[number]
                if cards_in_bucket:
                    cards_in_bucket.sort(key=lambda c: color_order.get(str(c.get("color", "")).lower(), 99))
                    active_specs.append((f"number:{number}", str(number), cards_in_bucket))

            if skip_cards:
                skip_cards.sort(key=lambda c: color_order.get(str(c.get("color", "")).lower(), 99))
                active_specs.append(("skip", tr("تخطي"), skip_cards))
            if reverse_cards:
                reverse_cards.sort(key=lambda c: color_order.get(str(c.get("color", "")).lower(), 99))
                active_specs.append(("reverse", tr("عكس الاتجاه"), reverse_cards))
            if draw_two_cards:
                draw_two_cards.sort(key=lambda c: color_order.get(str(c.get("color", "")).lower(), 99))
                active_specs.append(("draw_two", tr("سحب 2"), draw_two_cards))
            if skip_everyone_cards:
                active_specs.append(("skip_everyone", tr("تخطي الجميع"), skip_everyone_cards))
            if discard_all_cards:
                active_specs.append(("discard_all", tr("إسقاط الكل"), discard_all_cards))
            if buzzer_cards:
                active_specs.append(("buzzer", tr("جرس"), buzzer_cards))
            if flip_cards:
                active_specs.append(("flip", tr("قلب"), flip_cards))
            if wild_cards:
                active_specs.append(("wild", tr("تبديل اللون"), wild_cards))
            if standard_cards:
                active_specs.append(("standard", tr("البطاقات"), standard_cards))
        else:
            color_buckets = {key: [] for key, _label in self.CATEGORIES_ORDER if key != "wild"}
            for card in hand_cards:
                ctype = str(card.get("type", "")).lower()
                color = str(card.get("color", "")).lower()
                if ctype in wild_types:
                    continue
                if color in color_buckets:
                    color_buckets[color].append(card)
                elif card.get("suit") and not ctype:
                    color_buckets.setdefault("standard", []).append(card)
            buckets = {**color_buckets, "wild": wild_cards}
            active_specs = []
            for key, label in self.CATEGORIES_ORDER:
                cards_in_bucket = buckets.get(key, [])
                if cards_in_bucket:
                    active_specs.append((key, tr(label), cards_in_bucket))
            if "standard" in buckets and buckets["standard"]:
                active_specs.append(("standard", tr("البطاقات"), buckets["standard"]))

        # 3. Clean up previous widgets
        for lst in self.card_groups:
            lst.hide()
            self.cards_layout.removeWidget(lst)
            lst.deleteLater()
        self.card_groups.clear()
        self.category_keys.clear()
        self.category_labels.clear()

        if not active_specs:
            self.active_card_group = 0
            self._update_tab_order()
            return

        # 4. Construct new dynamic QListWidgets
        for key, label, cards in active_specs:
            self.category_keys.append(key)
            self.category_labels.append(label)

            lst = CardListWidget(self.cards_container)
            lst.setAccessibleName("")
            lst.setAccessibleDescription("")
            lst.itemActivated.connect(self._on_card_activated)

            for card in cards:
                display_text = tr(card_display_ar(card))
                cid = str(card.get("id") or "")
                it = QListWidgetItem(display_text)
                it.setData(Qt.UserRole, cid)
                it.setData(Qt.UserRole + 1, card)
                lst.addItem(it)

            lst.hide()
            self.cards_layout.addWidget(lst, 1)
            self.card_groups.append(lst)

        # 5. Determine target category and row with stable priority
        target_cat_idx = 0
        target_row = 0
        found_target = False

        # Priority A: Newly drawn card
        if drawn_card_id:
            for cat_idx, (key, label, cards) in enumerate(active_specs):
                for card_idx, card in enumerate(cards):
                    if str(card.get("id") or "") == str(drawn_card_id):
                        target_cat_idx = cat_idx
                        target_row = card_idx
                        found_target = True
                        break
                if found_target:
                    break

        # Priority B: Previously focused card ID is still present
        if not found_target and prev_card_id:
            for cat_idx, (key, label, cards) in enumerate(active_specs):
                for card_idx, card in enumerate(cards):
                    if str(card.get("id") or "") == prev_card_id:
                        target_cat_idx = cat_idx
                        target_row = card_idx
                        found_target = True
                        break
                if found_target:
                    break

        # Priority C: Same category key still exists
        if not found_target and prev_key in self.category_keys:
            target_cat_idx = self.category_keys.index(prev_key)
            target_row = max(0, min(prev_row, len(active_specs[target_cat_idx][2]) - 1))
            found_target = True

        # Priority D: Category disappeared; pick nearest available category
        if not found_target:
            target_cat_idx = max(0, min(prev_cat_index, len(active_specs) - 1))
            target_row = max(0, min(prev_row, len(active_specs[target_cat_idx][2]) - 1))

        # 6. Apply focus if in playing mode
        if (hasattr(self, "wild_color_list") and not self.wild_color_list.isHidden()) or (hasattr(self, "ninety_nine_choice_list") and not self.ninety_nine_choice_list.isHidden()):
            self.cards_container.hide()
            return
        self._focus_card_group(target_cat_idx, target_row, announce=False, force_focus=had_gameplay_focus)

    def toggle_number_order(self):
        """Toggle between the normal color grouping and numeric grouping."""
        self.card_group_mode = "number" if self.card_group_mode != "number" else "color"
        self._last_hand_signature = None
        mode_name = "ترتيب الأرقام" if self.card_group_mode == "number" else "ترتيب الألوان"
        try:
            from client.accessibility.reader import reader
            reader.speak(tr(mode_name), interrupt=True)
        except Exception:
            pass
        # Rebuild immediately from the latest hand instead of waiting for polling.
        if self.is_playing:
            app = self.window()
            state = getattr(app, "uno_state", None) or {}
            hand = state.get("hand") if (isinstance(state, dict) and state.get("hand") is not None) else getattr(self, "_current_hand_cards", [])
            drawn_id = state.get("drawn_card_id") if isinstance(state, dict) else None
            self.update_hand(hand, drawn_id)

    def showEvent(self, event):
        super().showEvent(event)
        self.focus_initial()

    def focus_initial(self):
        """Initial focus when entering or displaying the shared table view."""
        if not safe_is_valid(self):
            return
        try:
            if self._is_modal_active():
                return
            self._update_tab_order()
            
            from client.table_framework.adapter import get_adapter
            adapter = get_adapter(self.game_type)
            
            if adapter and adapter.focus_initial:
                adapter.focus_initial(self)
                return

            if adapter and hasattr(adapter, 'get_first_widget') and adapter.get_first_widget:
                fw = adapter.get_first_widget(self)
                if fw and safe_is_valid(fw) and fw.isVisible():
                    if hasattr(fw, "currentRow") and fw.count() > 0 and fw.currentRow() < 0:
                        fw.setCurrentRow(0)
                    safe_set_focus(fw)
                    return

            if self.is_playing:
                self.focus_first_card()
            else:
                safe_set_focus(self.main_table_widget)
        except (RuntimeError, AttributeError):
            pass

    def focus_first_card(self):
        """Focus the active card in the current dynamic category list."""
        if not safe_is_valid(self):
            return
        try:
            if hasattr(self, "wild_color_list") and safe_is_valid(self.wild_color_list) and self.wild_color_list.isVisible():
                for delay in (0, 30, 80, 150):
                    QTimer.singleShot(delay, lambda w=self.wild_color_list: safe_set_focus(w) if safe_is_valid(w) else None)
                return
            if hasattr(self, "ninety_nine_choice_list") and safe_is_valid(self.ninety_nine_choice_list) and self.ninety_nine_choice_list.isVisible():
                for delay in (0, 30, 80, 150):
                    QTimer.singleShot(delay, lambda w=self.ninety_nine_choice_list: safe_set_focus(w) if safe_is_valid(w) else None)
                return
            lst = self.get_active_card_list()
            if lst and safe_is_valid(lst) and lst.count() > 0:
                if lst.currentRow() < 0:
                    lst.setCurrentRow(0)
                for delay in (0, 30, 80, 150):
                    QTimer.singleShot(delay, lambda w=lst: safe_set_focus(w) if safe_is_valid(w) else None)
        except (RuntimeError, AttributeError):
            pass

    def _render_snakes_items(self):
        lst = getattr(self, "snakes_info_list", None)
        if lst is None:
            return
        had_focus = (
            lst.hasFocus()
            or (hasattr(lst, "viewport") and lst.viewport().hasFocus())
        )
        current_row = max(0, lst.currentRow())

        lst.blockSignals(True)
        lst.clear()

        raw_text = "ارمي النرد"
        disp_text = tr(raw_text)
        action_item = QListWidgetItem(disp_text)
        action_item.setData(Qt.UserRole, {"action": "roll"})
        action_item.setData(Qt.UserRole + 1101, raw_text)
        action_item.setData(Qt.UserRole + 1102, disp_text)
        lst.addItem(action_item)
        lst.blockSignals(False)

        if lst.count() > 0:
            target_row = min(current_row, lst.count() - 1)
            lst.setCurrentRow(target_row)
            if self.is_playing and not self._is_modal_active():
                if had_focus or (self._focus_target == "gameplay") or (not self.chat_input.hasFocus() and not self.activity_log.hasFocus()):
                    lst.setFocus()

    def update_snakes_state(self, state: dict):
        if not state.get("active"):
            return

        self._snakes_state = state
        self.main_table_widget.hide()
        self.snakes_container.show()

        self._render_snakes_items()

        self.snakes_info_list.setAccessibleDescription("")
        self._update_tab_order()

    def _on_snakes_item_activated(self, item: QListWidgetItem):
        app = self.window()
        if app and hasattr(app, "on_snakes_roll_shortcut"):
            app.on_snakes_roll_shortcut()

    def _on_card_activated(self, item: QListWidgetItem):
        cid = str(item.data(Qt.UserRole) or "")
        card = item.data(Qt.UserRole + 1) or {}
        if cid:
            self.cardActivated.emit(cid, card)

    def _on_chat_sent(self):
        text = self.chat_input.text().strip()
        if text:
            self.chat_input.clear()
            self.chatSent.emit(text)

    def add_log(self, text: str, category: str = "GAMEPLAY", event_id=None, game_event_id=None, event_type=None, room_id=None):
        """Feed one event into the canonical shared activity-log widget."""
        self.activity_panel.add_event({
            "id": event_id,
            "game_event_id": game_event_id,
            "event_type": event_type,
            "room_id": room_id,
            "category": str(category or "GAMEPLAY").upper(),
            "text": str(text),
            "is_read": False,
        })
        self.activity_log.scrollToBottom()

    def _on_activity_category_selected(self, _category: str):
        # The shared widget owns rendering and focus. This hook intentionally
        # contains no second category implementation.
        return

    def clear_hand_for_round_transition(self):
        # Move focus to main_table_widget first to prevent screen reader focus vanishing
        self._focus_target = "gameplay"
        self.main_table_widget.show()
        safe_set_focus(self.main_table_widget)

        from client.table_framework.adapter import get_adapter
        adapter = get_adapter(self.game_type)
        if adapter and adapter.clear_hand:
            adapter.clear_hand(self)
        
        # Always clear generic/legacy UI components defensively
        self.update_hand([])
        if hasattr(self, 'wild_color_list'):
            self.wild_color_list.hide()
        if hasattr(self, 'ninety_nine_choice_list'):
            self.ninety_nine_choice_list.hide()
        if hasattr(self, 'thief_answer_input'):
            self.thief_answer_input.setEnabled(False)
            self.thief_answer_input.hide()
            
        for i in reversed(range(self.gameplay_layout.count())):
            w = self.gameplay_layout.itemAt(i).widget()
            if w: w.hide()

        safe_set_focus(self.main_table_widget)
        QTimer.singleShot(0, lambda: safe_set_focus(self.main_table_widget))

    def contextMenuEvent(self, event):
        win = self.window()
        if win and hasattr(win, "on_apps_key"):
            win.on_apps_key()
            event.accept()
            return
        super().contextMenuEvent(event)

    # ---------- Scopa Hand & Gameplay Handling ----------
    def update_scopa_state(self, state: dict | None):
        state = state or {}
        if self.game_type != "SCOPA":
            return
        self._scopa_state = state
        is_active = bool(state.get("active"))
        if not is_active or not self.is_playing:
            self._last_scopa_rendered_sig = None
            self.scopa_card_list.clear()
            self.scopa_container.hide()
            self.main_table_widget.show()
            return
        self.scopa_container.setVisible(True)
        self._render_scopa_items()

    def _render_scopa_items(self):
        state = self._scopa_state or {}
        if not state.get("active"):
            return

        hand = list(state.get("my_hand") or [])
        curr_turn_id = state.get("current_turn_id")
        curr_name = state.get("current_turn_name", "اللاعب")

        new_sig = (
            tuple((c.get("value"), c.get("suit")) for c in hand),
            curr_turn_id,
            state.get("event_id"),
        )
        if getattr(self, "_last_scopa_rendered_sig", None) == new_sig:
            return
        self._last_scopa_rendered_sig = new_sig

        current_row = max(0, self.scopa_card_list.currentRow())
        had_scopa_focus = (
            self.scopa_card_list.hasFocus()
            or (hasattr(self.scopa_card_list, "viewport") and self.scopa_card_list.viewport().hasFocus())
        )
        previous_turn_id = getattr(self, "_last_scopa_turn_id", None)
        turn_changed = previous_turn_id is not None and str(previous_turn_id) != str(curr_turn_id)
        app = self.window()
        my_id = (app.user or {}).get("id") if app and hasattr(app, "user") and app.user else None
        is_my_turn = (str(curr_turn_id) == str(my_id))
        self._last_scopa_turn_id = curr_turn_id

        # Determine if gameplay had or should have focus before modifying items.
        had_gameplay_focus = (
            had_scopa_focus
            or getattr(self, "_scopa_gameplay_focus", False)
            or self._focus_target == "gameplay"
            or (self.is_playing and not (
                (hasattr(self, "chat_input") and self.chat_input.hasFocus())
                or (hasattr(self, "activity_log") and (self.activity_log.hasFocus() or (hasattr(self.activity_log, "viewport") and self.activity_log.viewport().hasFocus())))
            ))
        )

        self.scopa_card_list.blockSignals(True)

        # Update items in-place or adjust count without calling clear(),
        # so Qt does not forcibly kick focus out to the chat widget.
        desired_items_data = []
        for idx, card in enumerate(hand):
            from core_shared.uno_rules import card_display_ar
            c_text = card_display_ar(card)
            desired_items_data.append({
                "text": c_text,
                "data": {
                    "type": "card",
                    "card_index": idx,
                    "card": card,
                    "label": c_text
                },
                "is_waiting": False
            })

        if not hand and is_active:
            desired_items_data.append({
                "text": "",
                "data": {"type": "waiting"},
                "is_waiting": True
            })

        # Synchronize scopa_card_list items with desired_items_data
        target_count = len(desired_items_data)
        # Remove excess items from the end
        while self.scopa_card_list.count() > target_count:
            self.scopa_card_list.takeItem(self.scopa_card_list.count() - 1)

        # Update existing or add new items
        for idx, item_spec in enumerate(desired_items_data):
            if idx < self.scopa_card_list.count():
                item = self.scopa_card_list.item(idx)
            else:
                item = QListWidgetItem()
                self.scopa_card_list.addItem(item)

            item.setText(item_spec["text"])
            item.setData(Qt.UserRole, item_spec["data"])
            item.setToolTip("")
            item.setStatusTip("")
            item.setWhatsThis("")
            accessible_text_role = getattr(Qt.ItemDataRole, "AccessibleTextRole", None)
            accessible_description_role = getattr(Qt.ItemDataRole, "AccessibleDescriptionRole", None)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if accessible_text_role is not None:
                item.setData(accessible_text_role, item_spec["text"] if not item_spec["is_waiting"] else "")
            if accessible_description_role is not None:
                item.setData(accessible_description_role, item_spec["text"] if not item_spec["is_waiting"] else "")

        self.scopa_card_list.blockSignals(False)

        if self.scopa_card_list.count() > 0:
            target_row = min(current_row, self.scopa_card_list.count() - 1)
            self.scopa_card_list.setCurrentRow(target_row)
            if self.is_playing and not self._is_modal_active() and hand:
                user_in_chat_or_log = bool(
                    (hasattr(self, "chat_input") and self.chat_input.hasFocus())
                    or (hasattr(self, "activity_log") and (self.activity_log.hasFocus() or (hasattr(self.activity_log, "viewport") and self.activity_log.viewport().hasFocus())))
                )
                if had_gameplay_focus or not user_in_chat_or_log:
                    self._scopa_gameplay_focus = True
                    self._focus_target = "gameplay"
                    # If this update was due to a deal batch or turn change, give sounds and speech time to play before focusing
                    focus_delays = (250, 400) if (state.get("event_type") == "DEAL_BATCH" or turn_changed) else (0, 30)
                    for delay in focus_delays:
                        QTimer.singleShot(delay, lambda w=self.scopa_card_list: safe_set_focus(w))

    def _on_scopa_card_activated(self, item: QListWidgetItem):
        data = item.data(Qt.UserRole)
        if not data or not isinstance(data, dict):
            return
        if data.get("type") != "card":
            return
        card_index = data.get("card_index")
        if card_index is not None:
            self._scopa_gameplay_focus = True
            self._focus_target = "gameplay"
            safe_set_focus(self.scopa_card_list)
            self.scopaActionSubmitted.emit("play", str(card_index), "")

    def _clear_main_table_item_text(self):
        """Keep the pre-game table focus item completely text-free for NVDA/Qt accessibility."""
        if not isinstance(self.main_table_widget, QListWidget):
            return
        while self.main_table_widget.count() > 1:
            self.main_table_widget.takeItem(self.main_table_widget.count() - 1)
        if self.main_table_widget.count() == 0:
            item = QListWidgetItem("")
            self.main_table_widget.addItem(item)
        else:
            item = self.main_table_widget.item(0)
        if item is None:
            return
        item.setText("")
        item.setToolTip("")
        item.setStatusTip("")
        item.setWhatsThis("")
        accessible_text_role = getattr(Qt.ItemDataRole, "AccessibleTextRole", None)
        accessible_description_role = getattr(Qt.ItemDataRole, "AccessibleDescriptionRole", None)
        if accessible_text_role is not None:
            item.setData(accessible_text_role, "")
        if accessible_description_role is not None:
            item.setData(accessible_description_role, "")
        self.main_table_widget.setAccessibleName("")
        self.main_table_widget.setAccessibleDescription("")

    def set_status(self, text: str):
        # The shared pre-game focus item intentionally has no table/status text.
        # Keep this compatibility method so existing game/lifecycle callers do not
        # need a second status mechanism.
        self._clear_main_table_item_text()

    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)

    def cleanup(self):
        """Clean up active timers and disconnect safely."""
        try:
            if hasattr(self, '_thief_answer_timer') and safe_is_valid(self._thief_answer_timer) and self._thief_answer_timer.isActive():
                self._thief_answer_timer.stop()
            if hasattr(self, '_thief_answer_window_timer') and safe_is_valid(self._thief_answer_window_timer) and self._thief_answer_window_timer.isActive():
                self._thief_answer_window_timer.stop()
            if hasattr(self, '_thief_narration_timer') and safe_is_valid(self._thief_narration_timer) and self._thief_narration_timer.isActive():
                self._thief_narration_timer.stop()
        except Exception:
            pass

