"""Lobby game-settings editor; uses the canonical SettingsListMenu."""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem
from PySide6.QtCore import Qt
from client.table_framework.settings_registry import GAME_SETTINGS_REGISTRY
from client.game_preferences import load, save
from client.views.list_menu import SettingsListMenu
from client.localization import tr

class GameSettingsView(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("إعدادات اللعبة"))
        self.setAccessibleName(tr("إعدادات اللعبة"))
        layout = QVBoxLayout(self)
        self.games = QListWidget(self)
        self.games.setAccessibleName(tr("الألعاب"))
        layout.addWidget(self.games)
        for game_type, definition in GAME_SETTINGS_REGISTRY.items():
            item = QListWidgetItem(definition.title)
            item.setData(Qt.UserRole, game_type)
            self.games.addItem(item)
        self.games.itemActivated.connect(self._open)
        self.setMinimumSize(520, 420)
        if self.games.count(): self.games.setCurrentRow(0)

    def _open(self, item):
        game_type = str(item.data(Qt.UserRole)).upper()
        definition = GAME_SETTINGS_REGISTRY.get(game_type)
        if not definition:
            return
        target, rules = load(game_type, definition.default_target_score, definition.default_rules)
        fields = []
        for field in definition.custom_fields:
            d = field.to_dict({"target_score": target, "rules": rules})
            fields.append(d)
        fields += [{"key": "start", "label": "حفظ", "kind": "action"}, {"key": "cancel", "label": "إلغاء", "kind": "action"}]
        menu = SettingsListMenu(self, f"إعدادات {definition.title}", fields)
        result, values = menu.show_menu(speak_text=f"إعدادات {definition.title}")
        if result == "start":
            new_target, new_rules = definition.extract_target_and_rules(values)
            save(game_type, new_target, new_rules)
