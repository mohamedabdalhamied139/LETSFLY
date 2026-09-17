"""Canonical shared activity log used by Home and TableView.

The log is intentionally one keyboard-facing list.  Categories are a logical
selector owned by the same control: Left/Right changes category and Up/Down
changes events.  There is no second focusable/accessible list for categories.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel
from PySide6.QtCore import Signal, Qt
from client.accessibility.reader import reader
from client.localization import tr, subscribe

CATEGORY_LABELS = {
    "TABLE_CHAT": "دردشة الطاولات",
    "PRIVATE_MESSAGES": "الرسائل الخاصة",
    "FRIENDS": "الأصدقاء",
    "GAMEPLAY": "اللعب",
    "ALL": "الجميع",
    "FRIEND_REQUESTS": "طلبات الصداقة",
    "INVITATIONS": "الدعوات",
    "GIFTS": "الهدايا",
}
CATEGORY_ORDER = ("TABLE_CHAT", "PRIVATE_MESSAGES", "FRIENDS", "GAMEPLAY", "ALL", "FRIEND_REQUESTS", "INVITATIONS", "GIFTS")


class _EventList(QListWidget):
    def __init__(self, owner, parent=None):
        super().__init__(parent)
        self.owner = owner

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            item = self.currentItem()
            if item:
                self.itemActivated.emit(item)
            event.accept()
            return
        if key in (Qt.Key_Left, Qt.Key_Right):
            self.owner._move_category(-1 if key == Qt.Key_Left else 1)
            event.accept()
            return
        if key == Qt.Key_Up:
            if self.currentRow() > 0:
                self.setCurrentRow(self.currentRow() - 1)
            item = self.currentItem()
            if item:
                reader.speak(item.text(), interrupt=True)
            event.accept()
            return
        if key == Qt.Key_Down:
            if self.currentRow() < self.count() - 1:
                self.setCurrentRow(self.currentRow() + 1)
            item = self.currentItem()
            if item:
                reader.speak(item.text(), interrupt=True)
            event.accept()
            return
        super().keyPressEvent(event)


class ActivityLogWidget(QWidget):
    """One logical, one-focusable activity log for Home and every TableView."""
    categorySelected = Signal(str)
    loadOlderRequested = Signal(str, int)
    eventActivated = Signal(dict)

    def __init__(self, parent=None, *, title="سجل الأحداث", always_visible=True):
        super().__init__(parent)
        self._events = []
        self._has_more = False
        self._next_before_id = None
        self._selected_category = None
        self.always_visible = bool(always_visible)

        self.layout = QVBoxLayout(self)
        self._source_title = title
        self.title = QLabel(tr(title), self)
        # Empty accessible name prevents repeating the title when list gets focus
        self.title.setAccessibleName("")
        self.layout.addWidget(self.title)
        subscribe(self._on_language_changed)

        self.category_label = QLabel("", self)
        self.category_label.setAccessibleName("")
        self.category_label.setFocusPolicy(Qt.NoFocus)
        self.layout.addWidget(self.category_label)

        self.activity_log = _EventList(self, self)
        self.activity_log.setAccessibleName("")
        self.activity_log.setAccessibleDescription("")
        self.activity_log.itemActivated.connect(self._on_item_activated)
        self.layout.addWidget(self.activity_log, 1)

        self.categories = None
        self.load_older = None
        self._set_visibility(True)

    def _on_item_activated(self, item):
        data = item.data(Qt.UserRole)
        if isinstance(data, dict):
            self.eventActivated.emit(data)

    @staticmethod
    def _category(event):
        return str(event.get("category", "")).upper()

    @staticmethod
    def _logical_game_event_key(event):
        if not isinstance(event, dict) or str(event.get("category", "")).upper() != "GAMEPLAY":
            return None
        game_event_id = event.get("game_event_id")
        if game_event_id is None:
            payload = event.get("payload") or {}
            if isinstance(payload, str):
                try:
                    import json
                    payload = json.loads(payload)
                except Exception:
                    payload = {}
            if isinstance(payload, dict):
                game_event_id = payload.get("game_event_id")
        if game_event_id is None:
            return None
        return (
            "game",
            str(event.get("room_id") or ""),
            str(event.get("event_type") or ""),
            str(game_event_id),
        )

    def _event_exists(self, event):
        if not isinstance(event, dict):
            return False
        event_id = event.get("id")
        text = str(event.get("text", "")).strip()
        logical_key = self._logical_game_event_key(event)
        for existing in self._events:
            if event_id is not None and existing.get("id") is not None and str(existing.get("id")) == str(event_id):
                return True
            if logical_key is not None and self._logical_game_event_key(existing) == logical_key:
                return True
            if text and str(existing.get("text", "")).strip() == text:
                # Deduplicate identical text within same game/room
                room_a = str(event.get("room_id") or "")
                room_b = str(existing.get("room_id") or "")
                cat_a = str(event.get("category", "")).upper()
                cat_b = str(existing.get("category", "")).upper()
                if (not room_a or not room_b or room_a == room_b) and (cat_a == cat_b or cat_a == "GAMEPLAY" or cat_b == "GAMEPLAY"):
                    return True
        return False

    def _category_rows(self, category):
        if category == "ALL":
            return list(self._events)
        return [e for e in self._events if self._category(e) == category]

    def _available_categories(self):
        present = {self._category(e) for e in self._events if self._category(e) in CATEGORY_LABELS and self._category(e) != "ALL"}
        if self._events:
            present.add("ALL")
        return [c for c in CATEGORY_ORDER if c in present]

    def _set_visibility(self, visible):
        self.setVisible(bool(visible))
        self.title.setVisible(bool(visible))
        self.category_label.setVisible(bool(visible))
        self.activity_log.setVisible(bool(visible))

    def set_events(self, events, has_more=False, next_before_id=None, preserve_selection=True):
        old = self._selected_category if preserve_selection else None
        self._events = list(events or [])
        self._has_more = bool(has_more)
        self._next_before_id = next_before_id
        available = self._available_categories()

        self._set_visibility(self.always_visible or bool(available))
        if not available:
            self._selected_category = None
            self.category_label.setText("")
            self.activity_log.clear()
            return

        self._selected_category = old if old in available else available[0]
        self._render_category(self._selected_category, focus=False)

    def add_event(self, event):
        if not isinstance(event, dict) or not event.get("text"):
            return
        if self._event_exists(event):
            return
        self._events.append(dict(event))
        self._events.sort(key=lambda e: int(e.get("id", 0) or 0), reverse=True)
        selected = self._selected_category
        self.set_events(self._events, self._has_more, self._next_before_id, preserve_selection=True)
        if selected:
            self._render_category(selected, focus=False)

    def _focus_event_list(self, delta=0):
        if not self.activity_log.count():
            return
        row = self.activity_log.currentRow()
        if row < 0:
            row = 0
        else:
            row = max(0, min(self.activity_log.count() - 1, row + int(delta)))
        self.activity_log.setCurrentRow(row)
        self.activity_log.setFocus()
        item = self.activity_log.currentItem()
        if item:
            reader.speak(item.text(), interrupt=True)

    def _move_category(self, delta):
        available = self._available_categories()
        if not available:
            return
        current = self._selected_category if self._selected_category in available else available[0]
        index = available.index(current)
        new_index = max(0, min(len(available) - 1, index + int(delta)))
        new_category = available[new_index]
        if new_category == current:
            return
        reader.speak(tr(CATEGORY_LABELS[new_category]), interrupt=True)
        self._render_category(new_category, focus=True)
        self.categorySelected.emit(new_category)

    def _on_language_changed(self, _lang: str):
        self.title.setText(tr(self._source_title))
        if self._selected_category:
            self._render_category(self._selected_category, focus=False)

    def _render_category(self, category, focus=True):
        category = str(category)
        self._selected_category = category
        self.category_label.setText(tr(CATEGORY_LABELS.get(category, "")))
        self.activity_log.clear()
        rows = list(reversed(self._category_rows(category)))
        for event in rows:
            orig_text = str(event.get("text", ""))
            item = QListWidgetItem(tr(orig_text))
            item.setData(Qt.UserRole, dict(event))
            self.activity_log.addItem(item)
        self._set_visibility(True)
        if self.activity_log.count():
            self.activity_log.setCurrentRow(0)
        if focus:
            self.activity_log.setFocus()

    def _activate_category(self, item=None, move_focus=True):
        available = self._available_categories()
        if not available:
            return
        category = self._selected_category if self._selected_category in available else available[0]
        self._render_category(category, focus=move_focus)
        self.categorySelected.emit(category)

    def _load_older(self, _item=None):
        if self._selected_category and self._next_before_id:
            self.loadOlderRequested.emit(self._selected_category, int(self._next_before_id))

    def append_older(self, events, has_more=False, next_before_id=None):
        existing = {str(e.get("id")) for e in self._events if e.get("id") is not None}
        for event in events or []:
            if event.get("id") is None or str(event.get("id")) not in existing:
                self._events.append(dict(event))
        self._events.sort(key=lambda e: int(e.get("id", 0) or 0), reverse=True)
        self._has_more = bool(has_more)
        self._next_before_id = next_before_id
        selected = self._selected_category
        self.set_events(self._events, self._has_more, self._next_before_id, preserve_selection=True)
        if selected:
            self._render_category(selected, focus=False)

    def clear(self):
        self._events.clear()
        self._has_more = False
        self._next_before_id = None
        self._selected_category = None
        self.category_label.setText("")
        self.activity_log.clear()
        self._set_visibility(self.always_visible)

    set_activity_events = set_events
    add_activity_event = add_event
    append_older_events = append_older
