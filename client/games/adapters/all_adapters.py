from PySide6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QSizePolicy
from PySide6.QtCore import Qt
from client.localization import tr
from client.table_framework.adapter import ClientGameAdapter, register_adapter
from client.views.table_view import FarkleDiceList, DominoTileList, DominoSideList, ScopaCardList, SnakesActionList
from client.views.tennis_view import TennisGameWidget

# 1. UNO & 99 (Shared Hand Container)
def setup_cards_ui(table_view, playing):
    if playing:
        if not getattr(table_view, "cards_container", None):
            table_view.cards_container = QWidget(table_view)
            table_view.cards_layout = QVBoxLayout(table_view.cards_container)
            table_view.cards_layout.setContentsMargins(0, 0, 0, 0)
        table_view.mount_game_ui(table_view.cards_container)

def focus_cards(table_view):
    if table_view.is_playing:
        if hasattr(table_view, "focus_first_card"):
            table_view.focus_first_card()
    else:
        table_view.main_table_widget.setFocus()

# 2. Thief Hunt
def setup_thief_ui(table_view, playing):
    if playing:
        if not getattr(table_view, "thief_answer_input", None):
            from client.views.table_view import ThiefAnswerInput
            table_view.thief_answer_input = ThiefAnswerInput(table_view)
            table_view.thief_answer_input.setAccessibleName(tr("اختيار طابق اللص"))
            table_view.thief_answer_input.setAccessibleDescription(tr("اكتب رقم الطابق من 1 إلى 10 ثم اضغط Enter"))
            table_view.thief_answer_input.setFocusPolicy(Qt.StrongFocus)
        table_view.mount_game_ui(table_view.thief_answer_input)


def focus_thief(table_view):
    if table_view.is_playing and getattr(table_view, "thief_answer_input", None) and table_view.thief_answer_input.isVisible():
        table_view.thief_answer_input.setFocus()
    else:
        table_view.main_table_widget.setFocus()

# 3. Farkle
def setup_farkle_ui(table_view, playing):
    if playing:
        if not getattr(table_view, "farkle_container", None):
            table_view.farkle_container = QWidget(table_view)
            table_view.farkle_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
            table_view.farkle_layout = QVBoxLayout(table_view.farkle_container)
            table_view.farkle_layout.setContentsMargins(0, 0, 0, 0)
            table_view.farkle_layout.setSpacing(0)
            table_view.farkle_dice_list = FarkleDiceList(table_view.farkle_container)
            table_view.farkle_dice_list.setAccessibleName("")
            table_view.farkle_dice_list.setAccessibleDescription("")
            table_view.farkle_dice_list.setFocusPolicy(Qt.StrongFocus)
            table_view.farkle_dice_list.itemActivated.connect(table_view._on_farkle_item_activated)
            table_view.farkle_layout.addWidget(table_view.farkle_dice_list)
        table_view.mount_game_ui(table_view.farkle_container)

def focus_farkle(table_view):
    if table_view.is_playing:
        if getattr(table_view, "farkle_dice_list", None):
            if table_view.farkle_dice_list.count() > 0 and table_view.farkle_dice_list.currentRow() < 0:
                table_view.farkle_dice_list.setCurrentRow(0)
            table_view.farkle_dice_list.setFocus()
        else:
            table_view.main_table_widget.setFocus()
    else:
        table_view.main_table_widget.setFocus()

# 4. Domino & American Domino
def setup_domino_ui(table_view, playing):
    if playing:
        if not getattr(table_view, "domino_container", None):
            table_view.domino_container = QWidget(table_view)
            table_view.domino_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
            table_view.domino_layout = QVBoxLayout(table_view.domino_container)
            table_view.domino_layout.setContentsMargins(0, 0, 0, 0)
            table_view.domino_layout.setSpacing(0)
            table_view.domino_tile_list = DominoTileList(table_view.domino_container)
            table_view.domino_tile_list.setAccessibleName("")
            table_view.domino_tile_list.setAccessibleDescription("")
            table_view.domino_tile_list.setFocusPolicy(Qt.StrongFocus)
            table_view.domino_layout.addWidget(table_view.domino_tile_list)
            
            table_view.domino_side_list = DominoSideList(table_view)
            table_view.domino_side_list.setAccessibleName("")
            table_view.domino_side_list.setAccessibleDescription("")
            table_view.domino_side_list.setFocusPolicy(Qt.StrongFocus)
            table_view.domino_side_list.hide()
            table_view.domino_side_list.itemActivated.connect(table_view._on_domino_side_activated)
            # Add domino_side_list directly to table_view layout as overlay
            table_view.layout.addWidget(table_view.domino_side_list)
        table_view.mount_game_ui(table_view.domino_container)

def focus_domino(table_view):
    if table_view.is_playing:
        if getattr(table_view, "domino_side_list", None) and table_view.domino_side_list.isVisible():
            table_view.domino_side_list.setFocus()
        elif getattr(table_view, "domino_tile_list", None):
            if table_view.domino_tile_list.count() > 0 and table_view.domino_tile_list.currentRow() < 0:
                table_view.domino_tile_list.setCurrentRow(0)
            table_view.domino_tile_list.setFocus()
        elif getattr(table_view, "domino_container", None):
            table_view.domino_container.setFocus()
    else:
        table_view.main_table_widget.setFocus()

# 5. Snakes
def setup_snakes_ui(table_view, playing):
    if playing:
        if not getattr(table_view, "snakes_container", None):
            table_view.snakes_container = QWidget(table_view)
            table_view.snakes_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
            table_view.snakes_layout = QVBoxLayout(table_view.snakes_container)
            table_view.snakes_layout.setContentsMargins(0, 0, 0, 0)
            table_view.snakes_layout.setSpacing(0)
            table_view.snakes_info_list = SnakesActionList(table_view.snakes_container)
            table_view.snakes_info_list.setAccessibleName("")
            table_view.snakes_info_list.setAccessibleDescription("")
            table_view.snakes_info_list.setFocusPolicy(Qt.StrongFocus)
            table_view.snakes_info_list.itemActivated.connect(table_view._on_snakes_item_activated)
            table_view.snakes_layout.addWidget(table_view.snakes_info_list)
        table_view.mount_game_ui(table_view.snakes_container)

def focus_snakes(table_view):
    if table_view.is_playing:
        if getattr(table_view, "snakes_info_list", None):
            if table_view.snakes_info_list.count() > 0 and table_view.snakes_info_list.currentRow() < 0:
                table_view.snakes_info_list.setCurrentRow(0)
            table_view.snakes_info_list.setFocus()
        else:
            table_view.main_table_widget.setFocus()
    else:
        table_view.main_table_widget.setFocus()

# 6. Scopa
def setup_scopa_ui(table_view, playing):
    if playing:
        if not getattr(table_view, "scopa_container", None):
            table_view.scopa_container = QWidget(table_view)
            table_view.scopa_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
            table_view.scopa_layout = QVBoxLayout(table_view.scopa_container)
            table_view.scopa_layout.setContentsMargins(0, 0, 0, 0)
            table_view.scopa_layout.setSpacing(0)
            table_view.scopa_card_list = ScopaCardList(table_view.scopa_container)
            table_view.scopa_card_list.setAccessibleName("")
            table_view.scopa_card_list.setAccessibleDescription("")
            table_view.scopa_card_list.setFocusPolicy(Qt.StrongFocus)
            table_view.scopa_card_list.itemActivated.connect(table_view._on_scopa_card_activated)
            table_view.scopa_layout.addWidget(table_view.scopa_card_list)
        table_view.mount_game_ui(table_view.scopa_container)

def focus_scopa(table_view):
    if table_view.is_playing:
        lst = getattr(table_view, "scopa_card_list", None)
        if lst and lst.count() > 0:
            if lst.currentRow() < 0:
                lst.setCurrentRow(0)
            from client.views.table_view import safe_set_focus, safe_is_valid
            from PySide6.QtCore import QTimer
            for delay in (0, 30, 80, 150):
                QTimer.singleShot(delay, lambda w=lst: safe_set_focus(w) if safe_is_valid(w) else None)
        else:
            table_view.main_table_widget.setFocus()
    else:
        table_view.main_table_widget.setFocus()

# 7. Tennis
def setup_tennis_ui(table_view, playing):
    if playing:
        if not getattr(table_view, "tennis_game", None):
            app = table_view.window()
            room_id = app.app_state.get("room_id") if hasattr(app, "app_state") else ""
            ws_manager = app.ws_manager if hasattr(app, "ws_manager") else None
            access_manager = app.access_manager if hasattr(app, "access_manager") else None
            app_state = app.app_state if hasattr(app, "app_state") else {}
            assets_dir = app.assets_dir if hasattr(app, "assets_dir") else ""
            table_view.tennis_game = TennisGameWidget(room_id, ws_manager, access_manager, app_state, assets_dir)
            table_view.tennis_game.tennisActionSubmitted.connect(table_view.tennisActionSubmitted.emit)
        table_view.tennis_game.start_tracking()
        table_view.mount_game_ui(table_view.tennis_game)
    else:
        if getattr(table_view, "tennis_game", None):
            table_view.tennis_game.stop_tracking()

def clear_hand_tennis(table_view):
    if getattr(table_view, "tennis_game", None):
        table_view.tennis_game.stop_tracking()

def focus_tennis(table_view):
    if table_view.is_playing:
        if getattr(table_view, "tennis_game", None):
            table_view.tennis_game.setFocus()
        else:
            table_view.main_table_widget.setFocus()

# Helpers for apply_state
def apply_uno_state(app, state):
    if hasattr(app, "_apply_uno_state"):
        app._apply_uno_state(state)

def apply_ninety_nine_state(app, state):
    if hasattr(app, "_apply_ninety_nine_state"):
        app._apply_ninety_nine_state(state)

def apply_thief_state(app, state):
    if hasattr(app, "_apply_thief_state"):
        app._apply_thief_state(state)

def apply_farkle_state(app, state):
    if hasattr(app, "_apply_farkle_state"):
        app._apply_farkle_state(state)

def apply_domino_state(app, state):
    if hasattr(app, "_apply_domino_state"):
        app._apply_domino_state(state)

def apply_snakes_state(app, state):
    if hasattr(app, "_apply_snakes_state"):
        app._apply_snakes_state(state)

def apply_scopa_state(app, state):
    if hasattr(app, "_apply_scopa_state"):
        app._apply_scopa_state(state)

def apply_tennis_state(app, state):
    if hasattr(app, "_apply_tennis_state"):
        app._apply_tennis_state(state)

# Helpers for get_first_widget
def get_fw_cards(table_view): return table_view.get_active_card_list() if table_view.is_playing else table_view.main_table_widget
def get_fw_thief(table_view): return table_view.thief_answer_input if table_view.is_playing and getattr(table_view, "thief_answer_input", None) else table_view.main_table_widget
def get_fw_farkle(table_view): return table_view.farkle_dice_list if table_view.is_playing and getattr(table_view, "farkle_dice_list", None) else table_view.main_table_widget
def get_fw_domino(table_view):
    if not table_view.is_playing: return table_view.main_table_widget
    if getattr(table_view, "domino_side_list", None) and table_view.domino_side_list.isVisible(): return table_view.domino_side_list
    return table_view.domino_tile_list if getattr(table_view, "domino_tile_list", None) else table_view.main_table_widget
def get_fw_snakes(table_view): return table_view.snakes_info_list if table_view.is_playing and getattr(table_view, "snakes_info_list", None) else table_view.main_table_widget
def get_fw_scopa(table_view): return table_view.scopa_card_list if table_view.is_playing and getattr(table_view, "scopa_card_list", None) else table_view.main_table_widget
def get_fw_tennis(table_view): return table_view.tennis_game if table_view.is_playing and getattr(table_view, "tennis_game", None) else table_view.main_table_widget

# Register Adapters
register_adapter(ClientGameAdapter("UNO", "أونو", None, apply_uno_state, setup_cards_ui, None, focus_cards, None, None, get_fw_cards))
register_adapter(ClientGameAdapter("NINETY_NINE", "تسعة وتسعون", None, apply_ninety_nine_state, setup_cards_ui, None, focus_cards, None, None, get_fw_cards))
register_adapter(ClientGameAdapter("THIEF_HUNT", "صيد اللص", None, apply_thief_state, setup_thief_ui, None, focus_thief, None, None, get_fw_thief))
register_adapter(ClientGameAdapter("FARKLE", "فاركل", None, apply_farkle_state, setup_farkle_ui, None, focus_farkle, None, None, get_fw_farkle))
register_adapter(ClientGameAdapter("DOMINO", "دومينو", None, apply_domino_state, setup_domino_ui, None, focus_domino, None, None, get_fw_domino))
register_adapter(ClientGameAdapter("AMERICAN_DOMINO", "دومينو أمريكي", None, apply_domino_state, setup_domino_ui, None, focus_domino, None, None, get_fw_domino))
register_adapter(ClientGameAdapter("SNAKES_LADDERS", "السلم والثعبان", None, apply_snakes_state, setup_snakes_ui, None, focus_snakes, None, None, get_fw_snakes))
register_adapter(ClientGameAdapter("SCOPA", "إسكوبا", None, apply_scopa_state, setup_scopa_ui, None, focus_scopa, None, None, get_fw_scopa))
register_adapter(ClientGameAdapter("TENNIS", "تنس", None, apply_tennis_state, setup_tennis_ui, None, focus_tennis, clear_hand_tennis, None, get_fw_tennis))
