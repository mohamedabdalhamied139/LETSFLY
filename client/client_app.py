import client.games.adapters.all_adapters
"""Complete Multi-View Accessible Client Application for TableVerse v2."""
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QListWidget, QListWidgetItem, QMenu, QDialog, QWidget
from PySide6.QtCore import QTimer, Qt, QObject, Signal, QEvent

from client.accessibility.reader import reader
from client.accessibility.key_filter import HardwareKeyFilter
from client.audio.sound_engine import sound_engine
from client.network.api_client import ApiClient
from client.network.ws_client import WebSocketClient
from client.audio.voice_chat import VoiceChatManager
from client.session_store import save_token, load_token, clear_token, save_credentials, load_credentials, clear_credentials

from client.notification_policy import handle_event, handle_template_event, announce_game_event
from client.views.auth_view import AuthView
from client.views.home_view import HomeView
from client.views.rooms_menu_view import RoomsMenuView
from client.views.join_rooms_view import JoinRoomsView
from client.views.saved_tables_view import SavedTablesView
from client.views.friends_view import FriendsView
from client.views.friend_actions import FriendActionsDialog, OnlineUserActionsDialog, SimpleMessageDialog, ProfileDialog, HeadToHeadDialog, MuteDialog, GiftDialog
from client.views.online_users_view import OnlineUsersView
from client.views.social_center_views import PrivateMessagesView, NotificationsView, MyProfileEditDialog, ChallengeDialog
from client.views.game_settings_view import GameSettingsView
from client.views.table_view import TableView
from client.views.table_players_dialog import TablePlayersDialog, TablePlayerActionsDialog, TableVoiceSubmenuDialog, TableSubstituteChoiceDialog, TableVoiceManagerDialog, TableVoiceModeDialog
from core_shared.constants import CARD_TYPES
from core_shared.time_utils import parse_timestamp, format_duration
from core_shared.rules_config import RULE_DEFINITIONS
from client.views.list_menu import ListMenu, SettingsListMenu
from client.localization import tr, localize_widget_tree, install as install_localization, subscribe as subscribe_language_change, language
from client.presentation.error_presenter import ErrorPresenter
from client.presentation.sound_presenter import SoundPresenter
from client.presentation.accessibility_presenter import AccessibilityPresenter
from client.controllers.websocket_event_router import WebSocketEventRouter
from client.controllers.auth_controller import AuthController
from client.controllers.room_controller import RoomController
from client.controllers.social_controller import SocialController

class AsyncSignals(QObject):
    success = Signal(object)
    error = Signal(str)

class TableVerseApp(QMainWindow):
    wsEvent = Signal(dict)
    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("TableVerse"))
        self.resize(800, 600)

        self.api = ApiClient()
        self.ws = WebSocketClient()
        self.error_presenter = ErrorPresenter(reader, sound_engine, tr)
        self.sound_presenter = SoundPresenter(sound_engine)
        self.accessibility_presenter = AccessibilityPresenter(reader, tr)
        self.ws_event_router = WebSocketEventRouter(self)
        self.auth_controller = AuthController(self)
        self.room_controller = RoomController(self)
        self.social_controller = SocialController(self)
        self.user = None
        self.current_room = None
        self.uno_state = None
        self.thief_state = None
        self.farkle_state = None
        self.domino_state = None
        self.snakes_state = None
        self.scopa_state = None
        self.tennis_state = None
        self._last_domino_event_id = 0
        self._last_snakes_event_id = 0
        self._pending_wild_card_id = None
        self._last_spoken_action = ""
        self._last_event_id = 0
        self._was_my_turn = False
        self._active_signals = []
        self._poll_in_flight = False
        self._action_in_flight = False
        self._room_ws_url = None
        self._active_context_menu = None
        self._last_bluff_prompt_key = None
        self._last_farkle_event_id = 0
        self._seen_scopa_final_plays = set()
        self._last_exchange_prompt_key = None
        self._match_result_sound_played = False
        self._pre_deactivate_focus = None  # widget focused before window lost OS focus
        self._room_generation = 0
        self._table_join_fallback_monotonic = None
        self._round_fallback_monotonic = None
        self._round_fallback_number = None
        self._voice_restore_after_reconnect = False
        self._reconnect_focus = None
        self._profile_operation_id = 0
        self._ws_action_pending = {}
        self._force_close = False
        self.default_as_spectator = False

        # Central Stack
        self.stack = QStackedWidget(self)
        self.stack.currentChanged.connect(self._on_stack_changed)
        self.setCentralWidget(self.stack)

        self.auth_view = AuthView(self)            # Index 0
        self.home_view = HomeView(self)            # Index 1
        self.rooms_menu_view = RoomsMenuView(self) # Index 2
        self.join_rooms_view = JoinRoomsView(self) # Index 3
        self.table_view = TableView(self)          # Index 4
        self.saved_tables_view = SavedTablesView(self) # Index 5
        self.login_loading_view = QWidget(self)
        self.login_loading_view.setAccessibleName("")
        self.login_loading_view.setAccessibleDescription("")
        install_localization(QApplication.instance())
        subscribe_language_change(self._on_language_changed)
        localize_widget_tree(self)
        sound_engine._ensure_initialized()

        self.stack.addWidget(self.auth_view)
        self.stack.addWidget(self.home_view)
        self.stack.addWidget(self.rooms_menu_view)
        self.stack.addWidget(self.join_rooms_view)
        self.stack.addWidget(self.table_view)
        self.stack.addWidget(self.saved_tables_view)
        self.stack.addWidget(self.login_loading_view)

        for view in (self.home_view, self.rooms_menu_view, self.join_rooms_view, self.table_view, self.saved_tables_view):
            panel = getattr(view, "activity_panel", None)
            if panel is not None:
                panel.eventActivated.connect(self._on_activity_event_activated)

        # Connect Navigation Signals
        self.auth_view.loginRequested.connect(self._handle_login)
        self.auth_view.registerRequested.connect(self._handle_register)
        self.home_view.itemSelected.connect(self._handle_home_selection)
        self.home_view.activitySelected.connect(self._handle_home_activity_selection)
        self.home_view.loadOlderRequested.connect(self._handle_home_activity_load_older)
        self.rooms_menu_view.itemSelected.connect(self._handle_rooms_menu_selection)
        self.rooms_menu_view.backRequested.connect(self._show_home)
        self.rooms_menu_view.activitySelected.connect(lambda category: self._handle_activity_selection_for_view(self.rooms_menu_view, category))
        self.rooms_menu_view.loadOlderRequested.connect(lambda category, before_id: self._handle_activity_load_older_for_view(self.rooms_menu_view, category, before_id))
        self.join_rooms_view.roomSelected.connect(self._handle_join_room)
        self.join_rooms_view.spectatorSelected.connect(lambda rid: self._handle_join_room(rid, as_spectator=True))
        self.join_rooms_view.backRequested.connect(lambda: (self.stack.setCurrentIndex(2), self.rooms_menu_view.set_main(), self.rooms_menu_view.menu_list.setFocus(), reader.speak(tr("قائمة الطاولات"))))
        self.join_rooms_view.activitySelected.connect(lambda category: self._handle_activity_selection_for_view(self.join_rooms_view, category))
        self.join_rooms_view.loadOlderRequested.connect(lambda category, before_id: self._handle_activity_load_older_for_view(self.join_rooms_view, category, before_id))
        self.saved_tables_view.restoreSelected.connect(self._handle_restore_saved_table)
        self.saved_tables_view.deleteSelected.connect(self._handle_delete_saved_table)
        self.saved_tables_view.backRequested.connect(lambda: (self.stack.setCurrentIndex(2), self.rooms_menu_view.set_main(), self.rooms_menu_view.menu_list.setFocus(), reader.speak(tr("قائمة الطاولات"))))
        self.saved_tables_view.activitySelected.connect(lambda category: self._handle_activity_selection_for_view(self.saved_tables_view, category))
        self.saved_tables_view.loadOlderRequested.connect(lambda category, before_id: self._handle_activity_load_older_for_view(self.saved_tables_view, category, before_id))
        self.table_view.cardActivated.connect(self._handle_play_card)
        self.table_view.chatSent.connect(self._handle_send_chat)
        self.table_view.thiefActionSubmitted.connect(self._handle_thief_action)
        self.table_view.farkleActionSubmitted.connect(self._handle_farkle_action)
        self.table_view.dominoActionSubmitted.connect(self._handle_domino_action)
        self.table_view.scopaActionSubmitted.connect(self._handle_scopa_action)
        self.table_view.tennisActionSubmitted.connect(self._handle_tennis_action)
        self.voice = VoiceChatManager(self.ws, self)
        self.voice.stateChanged.connect(self._on_voice_state_message)
        self.wsEvent.connect(self.ws_event_router.route)

        # Polling Timer for Table State
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(1000)
        self.poll_timer.timeout.connect(self._poll_table_state)
        self.online_timer = QTimer(self)
        self.online_timer.setInterval(15000)
        self.online_timer.timeout.connect(self._refresh_online_count)

        # 2-minute Grace Period Timer for Reconnection
        self._reconnect_timeout_timer = QTimer(self)
        self._reconnect_timeout_timer.setSingleShot(True)
        self._reconnect_timeout_timer.setInterval(120000)  # 120 seconds = 2 minutes
        self._reconnect_timeout_timer.timeout.connect(self._on_reconnect_deadline_expired)
        self._is_reconnecting = False
        self._last_connecting_announced_at = 0.0

        # Install Physical Hardware Virtual-Key Filter
        self.key_filter = HardwareKeyFilter(self)
        # Qt fallback for in-game shortcuts. Native filter remains primary.
        self._game_shortcuts = []
        self._install_game_shortcut_fallbacks()
        QApplication.instance().installNativeEventFilter(self.key_filter)

        self._restore_saved_session()

    def _install_game_shortcut_fallbacks(self):
        from PySide6.QtGui import QShortcut, QKeySequence
        entries = [
            ("D", "on_draw_shortcut"),
            ("Space", "on_draw_card"),
            ("T", "on_announce_turn"),
            ("Shift+T", "on_announce_table_time"),
            ("Alt+Shift+V", "on_toggle_voice_chat"),
            ("M", "on_toggle_voice_mute"),
            ("F5", "on_table_settings"),
            ("R", "on_announce_top"),
            ("Shift+R", "on_announce_rules"),
            ("Shift+ق", "on_announce_rules"),
            ("S", "on_announce_scores"),
            ("U", "on_uno_shortcut"),
            ("C", "on_c_shortcut"),
            ("V", "on_announce_card_counts"),
            ("B", "on_buzzer_or_bot"),
            ("Shift+B", "on_remove_bot"),
            ("P", "on_announce_players"),
            ("Shift+P", "on_open_table_players"),
            ("Shift+ح", "on_open_table_players"),
            ("F4", "on_toggle_spectator_shortcut"),
            ("Q", "on_leave_room_shortcut"),
            ("X", "on_challenge_bluff"),
            ("Shift+H", "on_toggle_number_order"),
            ("F1", "on_f1_help"),
            ("Ctrl+F1", "on_ctrl_f1_help"),
            ("F2", "on_f2_wallet"),
            ("F3", "on_f3_ping"),
            ("Ctrl+F", "on_ctrl_friends"),
            ("Ctrl+W", "on_ctrl_online_users"),
            ("Ctrl+H", "on_toggle_room_privacy"),
            ("Ctrl+S", "on_save_table_shortcut"),
            ("Ctrl+M", "on_open_voice_manager"),
        ]
        for key, method in entries:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ApplicationShortcut)
            shortcut.activated.connect(lambda m=method: self._dispatch_game_shortcut(m))
            self._game_shortcuts.append(shortcut)

    def _dispatch_game_shortcut(self, method):
        if method == "on_ctrl_friends":
            self.on_ctrl_friends(); return
        if method == "on_ctrl_online_users":
            self.on_ctrl_online_users(); return
        if method in ("on_table_settings",):
            self.on_table_settings()
            return
        if method in ("on_manual_reconnect",):
            self.on_manual_reconnect()
            return
        if method == "on_toggle_spectator_shortcut":
            self.on_toggle_spectator_shortcut()
            return
        if method in ("on_toggle_voice_chat", "on_toggle_voice_mute", "on_toggle_room_privacy", "on_save_table_shortcut", "on_open_voice_manager"):
            if self.is_in_room():
                getattr(self, method)()
            return
        if method in ("on_f1_help", "on_ctrl_f1_help"):
            getattr(self, method)()
            return
        if not self.is_in_room():
            return
        focus = QApplication.focusWidget()
        from PySide6.QtWidgets import QLineEdit, QTextEdit, QPlainTextEdit
        # Help commands are global table commands and must remain available
        # even while an editable game control has focus.
        is_help = method in ("on_f1_help", "on_ctrl_f1_help", "on_announce_rules")
        # Thief Hunt score reporting uses S as an explicit game command. It
        # must remain available while the answer QLineEdit has focus; otherwise
        # the global editable-control guard swallows S and the player cannot
        # ask for the current score during the answer window.
        is_thief_score = (
            method == "on_announce_scores"
            and (self.current_room or {}).get("game") == "THIEF_HUNT"
        )
        if (
            not is_help
            and not is_thief_score
            and isinstance(focus, (QLineEdit, QTextEdit, QPlainTextEdit))
            and not focus.isReadOnly()
        ):
            return

        game = str((self.current_room or {}).get("game", "")).upper()
        if game == "NINETY_NINE":
            allowed_99 = {
                "on_announce_scores",  # S (tokens)
                "on_announce_top",     # R (pile value)
                "on_announce_turn",    # T (current turn)
                "on_f1_help", "on_ctrl_f1_help", "on_announce_rules",
                "on_leave_room_shortcut", "on_f2_wallet", "on_f3_ping",
                "on_announce_players", "on_open_table_players", "on_toggle_spectator_shortcut"
            }
            if method not in allowed_99:
                return

        if method == "on_announce_top":
            if game == "SNAKES_LADDERS":
                method = "on_snakes_radar_shortcut"
            elif game in ("DOMINO", "AMERICAN_DOMINO"):
                method = "on_domino_announce_ends"
            elif game == "FARKLE":
                method = "on_draw_shortcut"
            elif game in ("SCOPA", "NINETY_NINE", "UNO"):
                method = "on_announce_top"
            else:
                return
        elif method == "on_announce_card_counts":
            if game == "SNAKES_LADDERS":
                method = "on_snakes_positions"
            elif game in ("DOMINO", "AMERICAN_DOMINO"):
                method = "on_announce_domino_board_tiles"
            elif game in ("SCOPA", "UNO"):
                method = "on_announce_card_counts"
            else:
                return
        else:
            uno_only = {"on_uno_shortcut", "on_announce_no_uno", "on_challenge_bluff", "on_toggle_number_order"}
            if method in uno_only and game != "UNO":
                return
            if method == "on_draw_card" and game != "UNO":
                return
            if method == "on_draw_shortcut" and game == "UNO":
                return
            if method in ("on_domino_announce_ends", "on_announce_domino_board_tiles") and game not in ("DOMINO", "AMERICAN_DOMINO"):
                return

        fn = getattr(self, method, None)
        if callable(fn):
            fn()

    # ---------- State Query Helpers ----------
    def is_in_room(self) -> bool:
        return self.stack.currentIndex() == 4 and self.current_room is not None

    def is_choosing_wild(self) -> bool:
        return bool(self._pending_wild_card_id) or bool(getattr(self, "table_view", None) and not self.table_view.wild_color_list.isHidden())

    def is_choosing_ninety_nine_value(self) -> bool:
        return bool(getattr(self, "table_view", None) and hasattr(self.table_view, "ninety_nine_choice_list") and not self.table_view.ninety_nine_choice_list.isHidden())

    def on_cancel_ninety_nine_choice(self):
        if hasattr(self, "table_view") and hasattr(self.table_view, "hide_ninety_nine_choice"):
            self.table_view.hide_ninety_nine_choice()
        self._send_uno_action("cancel_choice")
        if hasattr(self, "table_view") and hasattr(self.table_view, "focus_cards"):
            self.table_view.focus_cards()

    def is_choosing_domino_side(self) -> bool:
        return bool(getattr(self.table_view, "domino_side_list", None) and self.table_view.domino_side_list.isVisible())

    def on_cancel_domino_side(self):
        self.table_view.hide_domino_side_selection()
        from client.accessibility.reader import reader
        reader.speak(tr("تم الإلغاء."), interrupt=True)

    def on_play_selected_domino_tile(self):
        item = self.table_view.domino_tile_list.currentItem()
        if item is None:
            return
        data = item.data(Qt.UserRole)
        if not data or not isinstance(data, dict):
            return
        dtype = data.get("type")
        if dtype == "action":
            act = data.get("action")
            if act == "pass":
                self._handle_domino_action("pass")
            return
        elif dtype == "tile":
            if not data.get("is_valid"):
                sound_engine.play_event("INVALID_ACTION")
                from client.accessibility.reader import reader
                reader.speak(tr("كارت غير صالح"), interrupt=True)
                return

            valid_sides = data.get("valid_sides") or []
            tile_idx = data.get("tile_index")
            tile = data.get("tile") or []

            state = self.domino_state or {}
            l_end = state.get("left_end")
            r_end = state.get("right_end")
            board = state.get("board") or []

            can_make_symmetric_choice = False
            if len(valid_sides) == 2 and l_end is not None and r_end is not None and len(tile) == 2:
                a, b = tile[0], tile[1]
                if l_end != r_end and set(tile) == {l_end, r_end}:
                    can_make_symmetric_choice = True
                elif self.current_room and self.current_room.get("game") == "AMERICAN_DOMINO" and len(board) >= 1:
                    is_double = (a == b)
                    sim_left_end = a if b == l_end else b
                    sim_left_val = (a + b) if is_double else sim_left_end
                    sim_right_val = (board[-1][0] + board[-1][1]) if board[-1][0] == board[-1][1] else board[-1][1]
                    sum_left = sim_left_val + sim_right_val

                    sim_right_end = b if a == r_end else a
                    sim_right_val_2 = (a + b) if is_double else sim_right_end
                    sim_left_val_2 = (board[0][0] + board[0][1]) if board[0][0] == board[0][1] else board[0][0]
                    sum_right = sim_left_val_2 + sim_right_val_2

                    if sum_left != sum_right:
                        can_make_symmetric_choice = True

            if can_make_symmetric_choice:
                self.table_view._prompt_domino_side_selection(tile_idx, tile, valid_sides)
                return
            elif len(valid_sides) == 1:
                side = valid_sides[0]
                self._handle_domino_action("play", str(tile_idx), side)
            else:
                self._handle_domino_action("play", str(tile_idx), "right")

    # ---------- Native keyboard callback aliases ----------
    def on_play_selected_card(self):
        active_group = self.table_view.get_active_card_list()
        if active_group is None:
            return
        item = active_group.currentItem()
        if item is None:
            return
        cid = str(item.data(Qt.UserRole) or "")
        card = item.data(Qt.UserRole + 1) or {}
        if not cid:
            return
        self._play_card_from_keyboard(cid, card)

    def _prevalidate_wild_card_play(self, card_id: str, card: dict) -> tuple[bool, str]:
        """Pre-validation UX check before opening the Color Selection dialog."""
        state = self.uno_state or {}
        rules = state.get("rules") or {}
        hand = state.get("hand") or []
        current_color = str(state.get("current_color", "")).lower()
        pending_draw_count = int(state.get("pending_draw_count") or 0)
        drawn_card_id = state.get("drawn_card_id")
        ctype = str(card.get("type", "")).lower()

        # 1. Drawn card restriction: If a card was drawn and must be played, only the drawn card is allowed
        if drawn_card_id and str(card_id) != str(drawn_card_id):
            return False, "بعد السحب يمكنك لعب الكارت المسحوب فقط."

        # 2. Pending draw stacking / response restriction
        if pending_draw_count > 0:
            top_card = state.get("top_card") or {}
            pending_draw_type = str(top_card.get("type", "")).lower()
            can_stack = False
            if ctype == pending_draw_type:
                can_stack = True
            elif rules.get("advanced_responses") and ctype in ("skip", "reverse", "wild"):
                can_stack = True
            elif rules.get("no_mercy"):
                wild_draws = {"wild_draw_two": 2, "wild_draw_six": 6, "wild_draw_ten": 10}
                if pending_draw_type in wild_draws and ctype in wild_draws:
                    can_stack = wild_draws[ctype] >= wild_draws.get(pending_draw_type, 0)
            if not can_stack:
                return False, "يجب الرد بكارت سحب مناسب أو تنفيذ السحب."

        return True, ""

    def _play_card_from_keyboard(self, card_id, card):
        # Use the same turn guard as mouse activation. Interception rules are
        # the only normal out-of-turn exception.
        if not self._can_play_card_out_of_turn(card):
            my_id = (self.user or {}).get("id")
            current_id = (self.uno_state or {}).get("current_player_id")
            if current_id is not None and str(current_id) != str(my_id):
                sound_engine.play_event("INVALID_ACTION")
                reader.speak(tr("ليس دورك"), interrupt=True)
                return
        # Use the same authoritative play path as mouse/Enter activation.
        ctype = str(card.get("type", "")).lower()
        color = str(card.get("color", "")).lower()
        if ctype in ("wild", "wild_draw_two", "wild_draw_four", "wild_draw_six", "wild_draw_ten", "wild_reverse_draw_four", "color_roulette") or color == "wild":
            valid, reason = self._prevalidate_wild_card_play(card_id, card)
            if not valid:
                sound_engine.play_event("INVALID_ACTION")
                reader.speak(tr(reason), interrupt=True)
                return
            self._pending_wild_card_id = card_id
            self.table_view.show_wild_colors()
            sound_engine.play_event("WILD_COLOR_PROMPT")
            reader.speak(tr("اختر اللون"), interrupt=True)
            return
        self._send_uno_action("play", card_id=card_id)

    def on_cancel_wild(self):
        self._pending_wild_card_id = None
        self.table_view.hide_wild_colors()
        reader.speak(tr("تم إلغاء اختيار اللون."), interrupt=True)

    def on_escape_navigation(self):
        # Escape from a context menu must close the popup and return focus to
        # the table itself. The native key filter intercepts Escape before QMenu
        # can close itself, so do this explicitly.
        active_popup = QApplication.activePopupWidget()
        if active_popup is not None:
            try:
                active_popup.close()
            except Exception:
                pass
            self._active_context_menu = None
            if self.is_in_room():
                self.table_view.focus_initial()
                reader.speak(tr("الطاولة"), interrupt=True)
            return
        if self.is_choosing_wild():
            self.on_cancel_wild()
            return
        if self.is_choosing_ninety_nine_value():
            self.on_cancel_ninety_nine_choice()
            return
        if self.is_choosing_domino_side():
            self.on_cancel_domino_side()
            return
        idx = self.stack.currentIndex()
        if idx == 4:
            self.table_view.focus_initial()
        elif idx == 5:
            self.stack.setCurrentIndex(2)
            self.rooms_menu_view.set_main(focus_tag="saved_tables")
            self.rooms_menu_view.menu_list.setFocus()
            reader.speak(tr("قائمة الطاولات"))
        elif idx == 3:
            self.stack.setCurrentIndex(2)
            self.rooms_menu_view.set_main(focus_tag="join")
            self.rooms_menu_view.menu_list.setFocus()
            reader.speak(tr("قائمة الطاولات"))
        elif idx == 2:
            self.rooms_menu_view.handle_escape()
        elif idx == 1:
            pass  # Escape on Home screen does not go back to login screen
        elif idx == 0:
            pass

    def _on_stack_changed(self, index):
        # Invalidate profile callbacks whenever the user navigates away from
        # the home context; stale async work must never reopen a profile dialog.
        if index != 1:
            self._profile_operation_id += 1

    # ---------- Thread-Safe Async Runner ----------
    def _run_async(self, func, on_success, on_error=None):
        signals = AsyncSignals()
        signals.success.connect(on_success)
        signals.error.connect(on_error or self._show_error)
        self._active_signals.append(signals)

        def cleanup():
            try:
                self._active_signals.remove(signals)
            except Exception:
                pass

        signals.success.connect(cleanup)
        signals.error.connect(cleanup)

        def worker():
            try:
                res = func()
                signals.success.emit(res)
            except Exception as exc:
                signals.error.emit(str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _show_error(self, message: str):
        self.error_presenter.show_error(message)

    # ---------- Auth Handlers ----------
    def _handle_login(self, u, p):
        self.auth_controller.login(u, p)

    def _handle_register(self, u, d, p):
        self.auth_controller.register(u, d, p)

    def _on_activity_event_activated(self, event_data):
        et = event_data.get("event_type")
        payload = event_data.get("payload")
        if isinstance(payload, str):
            import json
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}
        payload = payload or {}
        
        if et == "PRIVATE_MESSAGE":
            actor_id = event_data.get("actor_id")
            my_id = self.user.get("id")
            if str(actor_id) == str(my_id):
                target_id = payload.get("recipient_id")
                target_name = payload.get("recipient")
                if not target_id: return
            else:
                target_id = actor_id
                target_name = payload.get("sender") or "لاعب"
                
            dlg = SimpleMessageDialog(tr("إرسال رسالة إلى {name}", name=target_name), tr("اكتب رسالتك:"), self)
            if dlg.exec():
                self._run_async(lambda: self.api.send_private_message(target_id, dlg.editor.text().strip()), lambda _r: None, lambda e: reader.speak(tr(f"تعذر إرسال الرسالة: {e}"), interrupt=True))
                
        elif et == "CHALLENGE_INVITATION":
            inv_id = payload.get("invitation_id")
            room_id = payload.get("room_id")
            if inv_id and room_id:
                self._run_async(lambda: self.api.accept_challenge(int(inv_id)), lambda x: (reader.speak(tr("تم قبول الدعوة."), interrupt=True), self._handle_join_room(room_id)), lambda e: reader.speak(tr(f"تعذر قبول الدعوة: {e}"), interrupt=True))


    def _restore_saved_session(self):
        self.auth_controller.restore_saved_session()

    def _start_session_clean(self, dname, returning=False):
        """Start a fresh activity session: stale events never survive a relaunch."""
        def after_clear(_result=None):
            self.home_view.activity_panel.clear()
            self._start_lobby_ws()
            self._show_home(speak=False)
            reader.speak(tr("مرحبًا بعودتك {name}.", name=dname) if returning else tr("مرحبًا {name}.", name=dname))
        def clear_failed(_error=None):
            # Local state must still be clean even if the server is unreachable.
            self.home_view.activity_panel.clear()
            self._start_lobby_ws()
            self._show_home(speak=False)
            reader.speak(tr("مرحبًا بعودتك {name}.", name=dname) if returning else tr("مرحبًا {name}.", name=dname))
        self._run_async(lambda: self.api.clear_activity(timeout=3), after_clear, clear_failed)

    def _load_home_activity(self, speak=False):
        if not self.api.token:
            return
        def done(res):
            res = res or {}
            self.home_view.set_activity_events(
                res.get("events", []),
                has_more=res.get("has_more", False),
                next_before_id=res.get("next_before_id"),
                preserve_selection=True,
            )
            if speak and self.home_view.activity_log.count():
                reader.speak(tr("تم تحديث سجل الأحداث."))
        self._run_async(lambda: self.api.activity(limit=100), done, lambda _: None)

    def _load_activity_into(self, view, speak=False):
        if not self.api.token or not hasattr(view, "activity_panel"):
            return
        def done(res):
            res = res or {}
            view.activity_panel.set_events(
                res.get("events", []),
                has_more=res.get("has_more", False),
                next_before_id=res.get("next_before_id"),
                preserve_selection=True,
            )
            if speak and view.activity_panel.activity_log.count():
                reader.speak(tr("تم تحديث سجل الأحداث."))
        self._run_async(lambda: self.api.activity(limit=100), done, lambda _e: None)

    def _handle_activity_selection_for_view(self, view, category):
        category = str(category).upper()
        def done(res):
            res = res or {}
            view.activity_panel.set_events(
                res.get("events", []),
                has_more=res.get("has_more", False),
                next_before_id=res.get("next_before_id"),
                preserve_selection=True,
            )
            if category != "ALL":
                self._run_async(lambda: self.api.mark_activity_read(category=category), lambda _r: self._load_activity_into(view), lambda _e: None)
        self._run_async(lambda: self.api.activity(limit=100, category=None if category == "ALL" else category), done, lambda _e: None)

    def _handle_activity_load_older_for_view(self, view, category, before_id):
        category = str(category).upper()
        self._run_async(
            lambda: self.api.activity(limit=100, before_id=before_id, category=None if category == "ALL" else category),
            lambda res: view.activity_panel.append_older(res.get("events", []), res.get("has_more", False), res.get("next_before_id")),
            lambda _e: None,
        )

    def _handle_home_activity_selection(self, category):
        category = str(category).upper()
        def done(res):
            res = res or {}
            self.home_view.set_activity_events(
                res.get("events", []),
                has_more=res.get("has_more", False),
                next_before_id=res.get("next_before_id"),
                preserve_selection=True,
            )
            # Mark only the selected real category read. ALL is a derived view.
            if category != "ALL":
                self._run_async(lambda: self.api.mark_activity_read(category=category), lambda _r: self._load_home_activity(speak=False), lambda _e: None)
        self._run_async(lambda: self.api.activity(limit=100, category=None if category == "ALL" else category), done, lambda _: None)

    def _handle_home_activity_load_older(self, category, before_id):
        category = str(category).upper()
        def done(res):
            res = res or {}
            self.home_view.append_older_events(
                res.get("events", []),
                has_more=res.get("has_more", False),
                next_before_id=res.get("next_before_id"),
            )
        self._run_async(
            lambda: self.api.activity(limit=100, before_id=before_id, category=None if category == "ALL" else category),
            done, lambda _: None
        )

    # ---------- Navigation Routing ----------
    def _show_home(self, speak=True):
        self.stack.setCurrentIndex(1)
        self.poll_timer.stop()
        self.online_timer.start()
        self._refresh_online_count()
        self.home_view.menu_list.setFocus()
        self._load_home_activity(speak=False)
        if speak:
            reader.speak(tr("القائمة الرئيسية"))

    def _handle_home_selection(self, tag: str):
        if tag == "rooms":
            self.stack.setCurrentIndex(2)
            self.rooms_menu_view.menu_list.setFocus()
            self._load_activity_into(self.rooms_menu_view)
            reader.speak(tr("قائمة الطاولات"))
        elif tag == "friends":
            self.on_ctrl_friends()
        elif tag == "online":
            self.on_ctrl_online_users()
        elif tag == "private_messages":
            self.on_private_messages()
        elif tag == "my_profile":
            self._open_my_profile()
        elif tag == "settings":
            self._open_app_settings()
        elif tag == "notifications":
            self.on_notifications()
        elif tag == "contact":
            self._open_contact_dialog()
        elif tag == "logout":
            menu = ListMenu(
                self, "تأكيد تسجيل الخروج",
                [("نعم", "yes"), ("لا", "no")]
            )
            choice = menu.show_menu(speak_text="هل أنت متأكد من تسجيل الخروج؟")
            if choice != "yes":
                return
            if self.api.token:
                try:
                    self._run_async(self.api.logout, lambda _: None, lambda _: None)
                except Exception:
                    pass
            self.user = None
            self.api.token = None
            clear_token()
            self.ws.stop()
            self.api.close()
            self.online_timer.stop()
            self.stack.setCurrentIndex(0)
            self.auth_view.username_input.setFocus()
            reader.speak(tr("تم تسجيل الخروج."))

    def on_private_messages(self):
        self.social_controller.open_private_messages()

    def on_f4_exit(self):
        menu = ListMenu(
            self, "تأكيد الخروج",
            [("نعم", "yes"), ("لا", "no")]
        )
        choice = menu.show_menu(speak_text="هل أنت متأكد من الخروج من البرنامج؟")
        if choice == "yes":
            self._force_close = True
            self.close()

    def _open_my_profile(self):
        """Open the user's profile, then optionally edit and return to the refreshed profile."""
        if not self.api.token or not self.user or self.user.get("id") is None:
            reader.speak(tr("تعذر فتح الملف الشخصي."), interrupt=True)
            return
        self._profile_operation_id += 1
        operation_id = self._profile_operation_id

        def load_profile_then_show():
            if operation_id != self._profile_operation_id:
                return

            def loaded(data):
                if operation_id != self._profile_operation_id:
                    return
                profile = dict((data or {}).get("user", data) if isinstance(data, dict) else {})
                self.user.update({k: profile.get(k, self.user.get(k, "")) for k in ("display_name", "gender", "bio")})
                self.home_view.set_user_greeting(profile.get("display_name", self.user.get("display_name", "")))
                dlg = ProfileDialog(profile, self, allow_edit=True)
                result = dlg.exec()
                if result == 101 and dlg.edit_requested:
                    self._open_my_profile_editor(profile, operation_id)

            self._run_async(
                lambda: self.api.user_profile(int(self.user.get("id"))),
                loaded,
                lambda e: reader.speak(tr(f"تعذر تحميل الملف الشخصي: {e}"), interrupt=True)
                if operation_id == self._profile_operation_id else None,
            )

        load_profile_then_show()

    def _open_my_profile_editor(self, profile, operation_id):
        if operation_id != self._profile_operation_id or self.stack.currentIndex() != 1:
            return
        dlg = MyProfileEditDialog(profile or {}, self)
        if not dlg.exec():
            # Returning from Cancel keeps the profile context intact.
            self._open_my_profile()
            return
        if dlg.is_delete_requested():
            self._confirm_and_delete_account()
            return

        vals = dlg.values()

        def saved(res):
            if operation_id != self._profile_operation_id or self.stack.currentIndex() != 1:
                return
            updated = dict(res or {})
            self.user.update({k: updated.get(k, vals.get(k, "")) for k in ("display_name", "gender", "bio")})
            self.home_view.set_user_greeting(updated.get("display_name", vals.get("display_name", "")))
            reader.speak(tr("تم حفظ الملف الشخصي."), interrupt=True)
            # Fetch the authoritative profile again and display it; never route
            # through the game/home navigation as part of a profile save.
            self._run_async(
                lambda: self.api.user_profile(int(self.user.get("id"))),
                lambda fresh: self._show_my_profile_after_save(fresh, operation_id),
                lambda e: reader.speak(tr(f"تعذر تحديث عرض الملف الشخصي: {e}"), interrupt=True)
                if operation_id == self._profile_operation_id else None,
            )

        self._run_async(
            lambda: self.api.update_my_profile(**vals),
            saved,
            lambda e: reader.speak(tr(f"تعذر حفظ الملف الشخصي: {e}"), interrupt=True)
            if operation_id == self._profile_operation_id else None,
        )

    def _show_my_profile_after_save(self, profile, operation_id):
        if operation_id != self._profile_operation_id or self.stack.currentIndex() != 1:
            return
        profile = dict(profile or {})
        self.user.update({k: profile.get(k, self.user.get(k, "")) for k in ("display_name", "gender", "bio")})
        self.home_view.set_user_greeting(profile.get("display_name", self.user.get("display_name", "")))
        ProfileDialog(profile, self, allow_edit=True).exec()

    def _confirm_and_delete_account(self):
        reader.speak(tr("جاري حذف الحساب..."), interrupt=True)
        def done(_res):
            reader.speak(tr("تم حذف الحساب بنجاح."), interrupt=True)
            self.user = None
            self.api.token = None
            clear_token()
            self.ws.stop()
            self.api.close()
            self.online_timer.stop()
            self.stack.setCurrentIndex(0)
            self.auth_view.username_input.setFocus()
        def fail(err):
            reader.speak(tr(f"تعذر حذف الحساب: {err}"), interrupt=True)
        self._run_async(self.api.delete_my_account, done, fail)

    def _show_pm_view(self, rows, return_focus=None):
        dlg=PrivateMessagesView(rows,self); dlg.exec()
        if return_focus is not None and return_focus.isVisible(): return_focus.setFocus()

    def on_notifications(self):
        self.social_controller.open_notifications()

    def _open_contact_dialog(self):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton, QHBoxLayout
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("تحدث معنا"))
        dialog.setAccessibleName(tr("تحدث معنا"))
        dialog.setModal(True)
        layout = QVBoxLayout(dialog)
        label = QLabel(tr("اكتب رسالتك لنا:"))
        label.setAccessibleName(tr("اكتب رسالتك لنا"))
        layout.addWidget(label)
        editor = QTextEdit(dialog)
        editor.setTabChangesFocus(True)
        editor.setAccessibleName(tr("رسالتك"))
        editor.setPlaceholderText(tr("اكتب رسالتك هنا"))
        layout.addWidget(editor, 1)
        buttons = QHBoxLayout()
        send = QPushButton(tr("إرسال"))
        cancel = QPushButton(tr("إلغاء"))
        buttons.addWidget(send); buttons.addWidget(cancel)
        layout.addLayout(buttons)
        send.setDefault(True)
        cancel.clicked.connect(dialog.reject)
        def submit():
            text = editor.toPlainText().strip()
            if not text:
                reader.speak(tr("اكتب رسالتك أولًا."), interrupt=True)
                editor.setFocus()
                return
            send.setEnabled(False)
            reader.speak(tr("جاري إرسال رسالتك..."), interrupt=True)
            def done(_res):
                dialog.accept()
                self.home_view.menu_list.setFocus()
                reader.speak(tr("تم إرسال رسالتك بنجاح."), interrupt=True)
            def fail(err):
                send.setEnabled(True)
                editor.setFocus()
                reader.speak(tr(f"تعذر إرسال الرسالة: {err}"), interrupt=True)
            self._run_async(lambda: self.api.send_feedback(text), done, fail)
        send.clicked.connect(submit)
        dialog.resize(600, 400)
        editor.setFocus()
        dialog.exec()
        self.home_view.menu_list.setFocus()

    def _open_app_settings(self):
        from client.views.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self)
        dialog.exec()
        self.home_view.menu_list.setFocus()

    def _open_home_game_settings(self):
        dialog = GameSettingsView(self)
        dialog.exec()
        self.home_view.menu_list.setFocus()

    def _refresh_online_count(self):
        if not self.api.token:
            return
        def done(res):
            self.home_view.set_online_count((res or {}).get("count", 0))
        self._run_async(self.api.online_users, done, lambda _e: None)

    def on_ctrl_friends(self):
        self.social_controller.open_friends()

    def _handle_friend_request(self, row, kind, friends_dialog):
        self.social_controller.handle_friend_request(row, kind, friends_dialog)

    def _open_friend_actions(self, friend, friends_dialog):
        self.social_controller.open_friend_actions(friend, friends_dialog)

    def _open_online_user_actions(self, user, online_dialog):
        self.social_controller.open_online_user_actions(user, online_dialog)

    def on_ctrl_online_users(self):
        self.social_controller.open_online_users()

    def _handle_rooms_menu_selection(self, tag: str):
        if tag == "create":
            self.rooms_menu_view.set_game_selection()
            self._load_activity_into(self.rooms_menu_view)
            reader.speak(tr("نوع اللعبة."))
        elif tag == "create_uno":
            self._create_new_room("UNO")
        elif tag == "create_thief_hunt":
            self._create_new_room("THIEF_HUNT")
        elif tag == "create_farkle":
            self._create_new_room("FARKLE")
        elif tag == "create_domino":
            self._create_new_room("DOMINO")
        elif tag == "create_american_domino":
            self._create_new_room("AMERICAN_DOMINO")
        elif tag == "create_snakes_ladders":
            self._create_new_room("SNAKES_LADDERS")
        elif tag == "create_scopa":
            self._create_new_room("SCOPA")
        elif tag == "create_ninety_nine":
            self._create_new_room("NINETY_NINE")
        elif tag == "create_tennis":
            self._create_new_room("TENNIS")
        elif tag == "join":
            self.stack.setCurrentIndex(3)
            self._load_activity_into(self.join_rooms_view)
            self._refresh_available_rooms()
        elif tag == "saved_tables":
            self.stack.setCurrentIndex(5)
            self._load_activity_into(self.saved_tables_view)
            self._refresh_saved_tables()

    def _refresh_available_rooms(self):
        self.room_controller.refresh_available_rooms()

    def _create_new_room(self, game="UNO"):
        self.room_controller.create_new_room(game)

    def _handle_join_room(self, room_id: str, as_spectator: bool = False):
        self.room_controller.join_room(room_id, as_spectator=as_spectator)

    def _reset_game_runtime_state(self):
        self.uno_state = None
        self.thief_state = None
        self.domino_state = None
        self.farkle_state = None
        self.snakes_state = None
        self.scopa_state = None
        self.tennis_state = None
        self._last_scopa_event_id = 0
        self._last_event_id = 0
        self._last_spoken_action = ""
        self._last_bluff_prompt_key = None
        self._last_exchange_prompt_key = None
        self._last_farkle_event_id = 0
        self._last_domino_event_id = 0
        self._last_domino_round = 0
        self._last_snakes_event_id = 0
        self._last_snakes_step_event_id = 0
        self._last_thief_event_key = None
        self._match_result_sound_played = False
        self._was_my_turn = False
        self._pending_wild_card_id = None
        if hasattr(self, "table_view") and self.table_view is not None:
            self.table_view._last_domino_rendered_sig = None
            self.table_view._last_farkle_rendered_sig = None
            self.table_view._last_hand_signature = None
            self.table_view.set_status("الطاولة")

    def _enter_table(self, room: dict):
        self._room_generation += 1
        self.current_room = room
        self._table_join_fallback_monotonic = time.monotonic()
        self._round_fallback_monotonic = None
        self._round_fallback_number = None
        self.voice.join_room(str(room.get("id") or ""))
        self._maybe_auto_join_voice(room)
        game_type = str(room.get("game") or "").upper()
        self.table_view.set_game_type(game_type)
        sound_engine.preload_game_sounds(game_type)
        self._reset_game_runtime_state()
        self.table_view.set_playing_mode(bool(room.get("status") == "playing"))
        self.table_view.activity_panel.clear()
        self.table_view.clear_hand_for_round_transition()
        self._start_room_ws(room.get("id"))
        
        from client.table_framework.adapter import get_adapter
        adapter = get_adapter(game_type)
        gname = adapter.display_name if adapter else game_type
        self.setWindowTitle("")
        
        self.stack.setCurrentIndex(4)
        self.poll_timer.start()
        self.table_view.focus_initial()
        QTimer.singleShot(50, self.table_view.focus_initial)

    def _poll_thief_state(self):
        rid = self.current_room.get("id") if self.current_room else None
        if not rid:
            return
        self._poll_in_flight = True
        def done(state):
            self._poll_in_flight = False
            self._apply_thief_state(state)
        def fail(_):
            self._poll_in_flight = False
        self._run_async(lambda: self.api.thief_state(rid), done, fail)

    def _apply_thief_state(self, state):
        previous = self.thief_state or {}
        self.thief_state = state or {}
        self.table_view.set_game_type("THIEF_HUNT")
        previous_phase = previous.get("phase")
        current_phase = self.thief_state.get("phase")
        previous_round = int(previous.get("round_number", 0) or 0)
        current_round = int(self.thief_state.get("round_number", 0) or 0)
        phase_changed = previous_phase != current_phase
        round_changed = current_round != previous_round and current_round > 0
        if phase_changed or not previous:
            self.table_view.configure_thief_state(self.thief_state)
        if round_changed:
            # The server's round_number is authoritative. Announce it once
            # before the escape narration for every normal, tie-break, and
            # elimination round. The supplied "game start" cue is used only
            # for the first round; later rounds use the shared round-start cue.
            if current_round == 1:
                sound_engine.play_event("THIEF_GAME_START")
            if self.thief_state.get("event_type") != "ESCAPE_START":
                reader.speak(tr(f"الجولة {current_round}"), interrupt=False)
        eid = int(self.thief_state.get("event_id", 0) or 0)
        et = self.thief_state.get("event_type", "")
        key = f"{eid}:{et}"
        if key != getattr(self, "_last_thief_event_key", None):
            self._last_thief_event_key = key
            text = self.thief_state.get("last_action", "")
            if text:
                self.table_view.add_log(text)
            if et == "ESCAPE_START":
                sound_engine.play_event("THIEF_ESCAPE")
                floor = self.thief_state.get("start_floor")
                dirs = self.thief_state.get("directions", [])
                narration_parts = []
                if current_round:
                    narration_parts.append(f"الجولة {current_round}")
                if floor:
                    narration_parts.append(f"اللص في الطابق {floor}")
                if dirs:
                    narration_parts.append("، ".join(dirs))
                narration = "، ".join(narration_parts)
                if narration:
                    # Send the narration as one NVDA utterance. This avoids a
                    # second queued speech command whose duration was previously
                    # omitted from the local transition estimate.
                    reader.speak(tr(narration), interrupt=False)
                # NVDA Controller has no speech-completion callback. Keep the
                # answer field hidden and the table focused while the queued
                # narration is spoken, then open the field immediately after
                # an estimated speech duration. This is not a thinking delay.
                # NVDA Controller's speakText is asynchronous and exposes no
                # speech-completion callback. Use a short narration estimate
                # only to separate the spoken phase from the answer phase.
                # Crucially, once this estimate ends the input is shown locally
                # immediately; it does not wait for the server HTTP response.
                # Deterministic estimate based on floor narration + count of directions (approx 1.2s per direction + 1.8s for start floor)
                dir_count = len(dirs) if dirs else 0
                estimated_ms = max(4000, 1800 + (dir_count * 1200))
                self.table_view.begin_thief_narration(estimated_ms)
                return
            elif et == "ANSWER_START":
                # The supplied answer-start recording is played as the prompt.
                # The server's eight-second deadline remains authoritative and
                # is not extended by the recording duration.
                sound_engine.play_event("THIEF_ANSWER_START")
                self.table_view.activate_thief_answer_input(open_server_window=False)
            elif et in ("ROUND_WIN", "THIEF_WIN", "ROUND_TIE", "TIE_BREAK_START", "MATCH_WIN"):
                if et == "ROUND_WIN":
                    sound_engine.play_event("THIEF_CAUGHT")
                    # This is a semantic round-winner cue. The sound asset
                    # must describe the state, not contain a player's name.
                    sound_engine.play_event("THIEF_ROUND_WINNER")
                    sound_engine.play_event("THIEF_ROUND_END")
                elif et == "THIEF_WIN":
                    sound_engine.play_event("THIEF_ROUND_END")
                elif et == "ROUND_TIE":
                    sound_engine.play_event("THIEF_ROUND_END")
                elif et == "MATCH_WIN":
                    if not self._match_result_sound_played:
                        winner_id = self.thief_state.get("match_winner_id")
                        my_id = (self.user or {}).get("id")
                        cue = "MATCH_WIN" if str(winner_id) == str(my_id) else "MATCH_LOSS"
                        # A virtual thief has no user id, so every human client
                        # receives the loss cue in that case.
                        sound_engine.play_event(cue)
                        self._match_result_sound_played = True
                reader.speak(tr(text), interrupt=True)
        # Thief Hunt answer input is controlled by the authoritative game
        # phase, not by polling cadence or a possibly stale room snapshot.
        # Keep it visible for the entire answering phase. This guard is
        # intentionally idempotent so it is safe to run on every poll.
        if (
            self.thief_state.get("active")
            and self.thief_state.get("phase") == "answering"
            and not self.thief_state.get("is_thief")
        ):
            self.table_view.ensure_thief_answer_input_visible()

        if self.thief_state.get("phase") == "match_finished":
            self.table_view.set_playing_mode(False)
            self.table_view.main_table_widget.show()
            self.table_view.main_table_widget.setFocus()

    def _send_game_action_ws(self, action: str, card_id: str = "", chosen_color: str = "", target_player_id: str = "", data: dict = None, on_success=None, on_error=None) -> bool:
        """Send gameplay through the existing room WebSocket when available.

        The REST game-action endpoint remains the compatibility fallback.
        Each WebSocket action has a unique request id so a response cannot be
        confused with another move.
        """
        room = self.current_room or {}
        room_id = room.get("id")
        if not room_id or not self.ws.is_connected():
            return False
        request_id = uuid.uuid4().hex
        self._ws_action_pending[request_id] = (on_success, on_error, self._room_generation, str(room_id))
        from PySide6.QtCore import QTimer
        QTimer.singleShot(10_000, lambda rid=request_id: self._expire_ws_action(rid))
        payload = {
            "action": str(action),
            "card_id": str(card_id or ""),
            "chosen_color": str(chosen_color or ""),
            "target_player_id": str(target_player_id or ""),
            "data": dict(data or {}),
        }
        if not self.ws.send_json({"type": "game_action", "request_id": request_id, "payload": payload}):
            self._ws_action_pending.pop(request_id, None)
            return False
        return True

    def _expire_ws_action(self, request_id: str):
        pending = self._ws_action_pending.pop(request_id, None)
        if pending:
            _success, on_error, _generation, _room_id = pending
            if on_error:
                on_error("انتهت مهلة تنفيذ الحركة. حاول مرة أخرى.")

    def _handle_thief_action(self, action, value):
        if not self.current_room or self.current_room.get("game") != "THIEF_HUNT":
            return
        rid = self.current_room.get("id")
        def done(state):
            self._apply_thief_state(state)
        def fail(msg):
            reader.speak(tr(msg), interrupt=True)
        if self._send_game_action_ws(action, card_id=value, on_success=done, on_error=fail):
            return
        self._run_async(lambda: self.api.thief_action(rid, action, value), done, fail)

    def _handle_farkle_action(self, action, value=""):
        if not self.current_room or self.current_room.get("game") != "FARKLE":
            return
        rid = self.current_room.get("id")
        def done(state):
            self._apply_farkle_state(state)
        def fail(message):
            reader.speak(tr(str(message)), interrupt=True)
        if self._send_game_action_ws(action, data={"value": value}, on_success=done, on_error=fail):
            return
        self._run_async(lambda: self.api.farkle_action(rid, action, value), done, fail)

    def _apply_farkle_state(self, state: dict):
        self.farkle_state = state or {}
        from client.table_framework.state_engine import ClientStateEngine
        def update_view(active, round_finished):
            if not active:
                self.table_view.update_farkle_state({"active": False})
            else:
                self.table_view.update_farkle_state(self.farkle_state)
        ClientStateEngine.process_common_state(self, "FARKLE", state, update_view)

    def _handle_domino_action(self, action: str, card_id: str = "", chosen_color: str = ""):
        if not self.current_room:
            return
        g = str(self.current_room.get("game", "")).upper()
        if g not in ("DOMINO", "AMERICAN_DOMINO"):
            return
        rid = self.current_room.get("id")
        def done(state):
            self._apply_domino_state(state)
        def fail(message):
            reader.speak(tr(str(message)), interrupt=True)
        if self._send_game_action_ws(action, card_id=card_id, chosen_color=chosen_color, data={"side": chosen_color}, on_success=done, on_error=fail):
            return
        if g == "AMERICAN_DOMINO":
            self._run_async(lambda: self.api.american_domino_action(rid, action, card_id, chosen_color), done, fail)
        else:
            self._run_async(lambda: self.api.domino_action(rid, action, card_id, chosen_color), done, fail)

    def _apply_domino_state(self, state: dict):
        self.domino_state = state or {}
        from client.table_framework.state_engine import ClientStateEngine
        
        def update_view(active, round_finished):
            if not active:
                self.table_view.update_domino_state({"active": False})
            elif not self.is_choosing_domino_side():
                self.table_view.update_domino_state(self.domino_state)
                
        game_type = self.current_room.get("game", "DOMINO")
        ClientStateEngine.process_common_state(self, game_type, state, update_view)

    def _poll_table_state(self):
        if not self.current_room or getattr(self, '_poll_in_flight', False):
            return
        rid = self.current_room.get("id")
        generation = self._room_generation
        self._poll_in_flight = True
        game_type = self.current_room.get("game")
        
        def done(state):
            self._poll_in_flight = False
            if generation != self._room_generation:
                return
            current = self.current_room or {}
            if current.get("id") != rid or str(current.get("game") or "").upper() != str(game_type or "").upper():
                return
            if not isinstance(state, dict):
                return
            
            # Stale response guard: if incoming polled state has an older event_id than what we already processed via WS, ignore it
            incoming_eid = int(state.get("event_id", 0) or 0)
            gt_upper = str(game_type or "").upper()
            last_eid_attr = f"_last_{gt_upper.lower()}_event_id"
            if gt_upper == "UNO":
                last_eid_attr = "_last_event_id"
            elif gt_upper == "NINETY_NINE":
                last_eid_attr = "_last_ninety_nine_event_id"
            current_eid = int(getattr(self, last_eid_attr, 0) or 0)
            if incoming_eid > 0 and current_eid > 1 and incoming_eid < current_eid:
                return

            from client.table_framework.adapter import get_adapter
            adapter = get_adapter(game_type)
            if adapter and adapter.apply_state:
                adapter.apply_state(self, state)
            elif game_type == "THIEF_HUNT": self._apply_thief_state(state)
            elif game_type == "FARKLE": self._apply_farkle_state(state)
            elif game_type in ("DOMINO", "AMERICAN_DOMINO"): self._apply_domino_state(state)
            elif game_type == "SNAKES_LADDERS": self._apply_snakes_state(state)
            elif game_type == "SCOPA": self._apply_scopa_state(state)
            elif game_type == "TENNIS": self._apply_tennis_state(state)
            elif game_type == "NINETY_NINE":
                self._apply_ninety_nine_state(state)
            else: self._apply_uno_state(state)

        def fail(_):
            self._poll_in_flight = False

        self._run_async(lambda: self.api.game_state(rid), done, fail)

    def _apply_snakes_state(self, state: dict):
        self.snakes_state = state or {}
        from client.table_framework.state_engine import ClientStateEngine
        def update_view(active, round_finished):
            if not active:
                self.table_view.update_snakes_state({"active": False})
            else:
                self.table_view.update_snakes_state(self.snakes_state)
        ClientStateEngine.process_common_state(self, "SNAKES_LADDERS", state, update_view)
        et = str(self.snakes_state.get("event_type") or "")
        roll = int(self.snakes_state.get("last_roll") or 0)
        event_id = int(self.snakes_state.get("event_id", 0) or 0)
        if et in ("DICE_ROLLED", "BONUS_ROLL", "MATCH_FINISHED") and roll > 0 and event_id != getattr(self, "_last_snakes_step_event_id", 0):
            self._last_snakes_step_event_id = event_id
            self._snakes_stepping = True
            roll_action = str(self.snakes_state.get("roll_action") or "")
            if roll_action:
                reader.speak(tr(roll_action), interrupt=True)
            self._snakes_pending_announcement = str(self.snakes_state.get("arrival_action") or self.snakes_state.get("last_action") or "")
            raw_cues = self.snakes_state.get("sound_cues") or ()
            self._snakes_pending_arrival_cues = [
                c for c in raw_cues
                if sound_engine.has_cue(c) and c in ("SNAKE_BITE", "LADDER_CLIMB", "FREEZE_TRAP", "MYSTERY_BOX", "PLAYER_BUMP", "MATCH_WIN")
            ]
            self._play_snakes_steps(roll, 1)
        elif et in ("CANNOT_MOVE", "MATCH_WON", "PLAYER_FROZEN"):
            self._snakes_stepping = False
            self._snakes_pending_arrival_cues = []
            if et in ("CANNOT_MOVE", "PLAYER_FROZEN"):
                reader.speak(tr(str(self.snakes_state.get("last_action") or "")), interrupt=True)

    def _play_snakes_steps(self, roll: int, current_step: int = 1):
        if not self.is_in_room() or (self.current_room or {}).get("game") != "SNAKES_LADDERS":
            self._snakes_stepping = False
            self._snakes_pending_arrival_cues = []
            return
        if current_step > roll:
            arrival_cues = getattr(self, "_snakes_pending_arrival_cues", [])
            self._snakes_pending_arrival_cues = []
            for cue in arrival_cues:
                sound_engine.play_event(cue)
            announcement = getattr(self, "_snakes_pending_announcement", "")
            self._snakes_pending_announcement = ""
            if announcement:
                QTimer.singleShot(80, lambda text=announcement: reader.speak(tr(text), interrupt=True))

            # If match is finished, execute any pending match finished transition
            state = getattr(self, "snakes_state", {}) or {}
            et = str(state.get("event_type") or "")
            if et in ("MATCH_FINISHED", "MATCH_WON") or state.get("winner_id") is not None:
                self._snakes_stepping = False
                pending_term = getattr(self, "_pending_snakes_terminal_event", None)
                if pending_term:
                    self._pending_snakes_terminal_event = None
                    self._finish_snakes_match(pending_term)
                return

            # Trigger the next player's turn sound and announcement now that arrival and movement are complete
            def _announce_snakes_turn():
                self._snakes_stepping = False
                if not self.is_in_room() or (self.current_room or {}).get("game") != "SNAKES_LADDERS":
                    return
                state = getattr(self, "snakes_state", {}) or {}
                curr_id = state.get("current_turn_id")
                if curr_id is None:
                    curr_id = state.get("current_player_id")
                if curr_id is None:
                    return
                curr_id_str = str(curr_id)
                last_turn_attr = "_last_announced_turn_id_snakes_ladders"
                last_announced_turn = getattr(self, last_turn_attr, None)
                my_id = (self.user or {}).get("id")
                is_my_turn = (curr_id_str == str(my_id)) if my_id is not None else False
                current_name = (state.get("current_player_name") or state.get("current_turn_name") or "غير معروف")

                if curr_id_str != str(last_announced_turn):
                    setattr(self, last_turn_attr, curr_id_str)
                    setattr(self, "_last_turn_snakes_ladders", curr_id_str)
                    setattr(self, "_was_my_turn_snakes_ladders", is_my_turn)
                    if is_my_turn:
                        sound_engine.play_event("TURN_START")
                        announce_game_event("دورك", interrupt=False)
                    else:
                        announce_game_event(f"دور {current_name}", interrupt=False)

            delay_turn = 500 if announcement else 100
            QTimer.singleShot(delay_turn, _announce_snakes_turn)
            return
        sound_engine.play_event("STEP_MOVE")
        QTimer.singleShot(320, lambda: self._play_snakes_steps(roll, current_step + 1))

    def _handle_tennis_action(self, action: str, data: dict = None):
        if not self.current_room:
            return
        rid = self.current_room.get("id")
        generation = self._room_generation
        def done(res):
            if generation != self._room_generation or (self.current_room or {}).get("id") != rid:
                return
            # WebSocket broadcasts tennis_action_result separately; this response
            # only acknowledges successful processing of the request.
            pass
        def fail(err):
            self._show_error(err)
        if self._send_game_action_ws(action, data=data or {}, on_success=done, on_error=fail):
            return
        self._run_async(lambda: self.api.tennis_action(rid, action, data or {}), done, fail)

    def _apply_tennis_state(self, state: dict):
        self.tennis_state = state or {}
        self.table_view.set_game_type("TENNIS")
        room_status = str((self.current_room or {}).get("status", "")).lower()
        active = bool(self.tennis_state and self.tennis_state.get("state") not in ("FINISHED", "WAITING", "")) and (room_status == "playing")
        self.table_view.set_playing_mode(active)
        if hasattr(self.table_view, "tennis_game"):
            self.table_view.tennis_game.handle_event({
                "type": "tennis_state_changed",
                "state": self.tennis_state
            })
        if active:
            sc = self.tennis_state.get("score", {})
            server_idx = sc.get("server_idx", 0)
            players = self.tennis_state.get("players", [])
            server_name = players[server_idx].get("name", "اللاعب") if server_idx < len(players) else "اللاعب"
            self.table_view.set_status(f"الإرسال مع {server_name}")
            if not self.table_view.chat_input.hasFocus() and not self.table_view.activity_log.hasFocus():
                QTimer.singleShot(0, self.table_view.tennis_game.setFocus)
                QTimer.singleShot(40, self.table_view.tennis_game.setFocus)
        else:
            self.table_view.set_status(self.table_view.get_game_title())
            self.table_view.main_table_widget.show()
            self.table_view.main_table_widget.setFocus()

    def _apply_scopa_state(self, state: dict):
        state = dict(state or {})
        my_id = (self.user or {}).get("id")
        if my_id is not None and state:
            hands_count = state.get("hands_count") or {}
            expected_count = int(hands_count.get(str(my_id), 0) or 0)
            incoming_hand = state.get("my_hand")
            if expected_count > 0 and not incoming_hand:
                previous_hand = list((self.scopa_state or {}).get("my_hand") or [])
                if len(previous_hand) == expected_count:
                    state["my_hand"] = previous_hand
                else:
                    self._poll_table_state()
        self.scopa_state = state
        from client.table_framework.state_engine import ClientStateEngine
        def update_view(active, round_finished):
            self.table_view.update_scopa_state(self.scopa_state)
        ClientStateEngine.process_common_state(self, "SCOPA", state, update_view)

    def _handle_scopa_action(self, action: str, card_index_str: str = "", choice_idx_str: str = ""):
        if not self.current_room:
            return
        rid = self.current_room.get("id")
        def done(state):
            self._apply_scopa_state(state)
        def fail(err):
            self._show_error(err)
        data = {"choice_idx": choice_idx_str}
        if self._send_game_action_ws(action, card_id=card_index_str, data=data, on_success=done, on_error=fail):
            return
        self._run_async(lambda: self.api.scopa_action(rid, action, card_index_str, choice_idx_str), done, fail)



    def _apply_ninety_nine_state(self, state: dict):
        self.uno_state = state or {}
        self._maybe_prompt_special_rule_actions()
        from client.table_framework.state_engine import ClientStateEngine
        def update_view(active, round_finished):
            if active and not round_finished:
                self.table_view.update_hand(self.uno_state.get("hand", []), self.uno_state.get("drawn_card_id"))
            elif round_finished:
                self.table_view.clear_hand_for_round_transition()
        ClientStateEngine.process_common_state(self, "NINETY_NINE", state, update_view)

    def _apply_uno_state(self, state: dict):
        self.uno_state = state or {}
        self._maybe_prompt_special_rule_actions()
        from client.table_framework.state_engine import ClientStateEngine
        def update_view(active, round_finished):
            if active and not round_finished:
                if not self.is_choosing_wild():
                    hand = self.uno_state.get("hand", [])
                    self.table_view.update_hand(hand, self.uno_state.get("drawn_card_id"))
            elif round_finished:
                self.table_view.clear_hand_for_round_transition()
        game_type = self.current_room.get("game", "UNO")
        ClientStateEngine.process_common_state(self, game_type, state, update_view)

    def _maybe_prompt_special_rule_actions(self):
        """Handle rule variants that require a user choice rather than a shortcut."""
        state = self.uno_state or {}
        my_id = (self.user or {}).get("id")
        game = str((self.current_room or {}).get("game", "")).upper()

        if game == "NINETY_NINE" and state.get("active"):
            pending = state.get("pending_choice")
            if pending and (str(pending.get("player_id")) == str(my_id) or str(pending.get("user_id")) == str(my_id)):
                c_type = pending.get("type")
                card_val = pending.get("card_value") or (10 if c_type == "10" else 1 if c_type == "A" else None)
                options = []
                if card_val == 10 or c_type == "10":
                    options = [("+10", "10"), ("-10", "-10")]
                elif card_val == 1 or c_type == "A":
                    options = [("+1", "1"), ("+11", "11")]
                    
                if options and hasattr(self, "table_view") and hasattr(self.table_view, "show_ninety_nine_choice"):
                    if not self.is_choosing_ninety_nine_value():
                        self.table_view.show_ninety_nine_choice(options)
            else:
                if hasattr(self, "table_view") and hasattr(self.table_view, "hide_ninety_nine_choice") and self.is_choosing_ninety_nine_value():
                    self.table_view.hide_ninety_nine_choice()
        
        pending_bluff = state.get("pending_bluff")
        if pending_bluff and str(pending_bluff.get("target_id")) == str(my_id):
            key = (pending_bluff.get("bluffer_id"), pending_bluff.get("target_id"), state.get("event_id"))
            if key != self._last_bluff_prompt_key:
                self._last_bluff_prompt_key = key
                # No modal dialog here: the decision is intentionally keyboard-driven.
                # X challenges the Wild Draw Four; D accepts the penalty and draws four.
                reader.speak(tr("تحدي الخداع X، أو سحب 4 D"), interrupt=True)
                return
        else:
            self._last_bluff_prompt_key = None
        pending_exchange = state.get("pending_exchange_user")
        if pending_exchange is not None and str(pending_exchange) == str(my_id):
            key = (pending_exchange, state.get("event_id"))
            if key != self._last_exchange_prompt_key:
                self._last_exchange_prompt_key = key
                players = [p for p in state.get("players", []) if str(p.get("user_id")) != str(my_id) and not p.get("eliminated")]
                if players:
                    names = [(p.get("name") or tr("لاعب"), str(p.get("user_id"))) for p in players]
                    target_id = ListMenu(self, tr("تبديل اليد"), names).show_menu(
                        speak_text=tr("تبديل اليد"))
                    if target_id:
                        self._send_uno_action("exchange_hand", str(target_id))

    # ---------- In-Game Actions ----------
    def _can_play_card_out_of_turn(self, card: dict) -> bool:
        """Return whether the current rules explicitly permit this card outside turn."""
        state = self.uno_state or {}
        my_id = (self.user or {}).get("id")
        current_id = state.get("current_player_id")
        if current_id is None or str(current_id) == str(my_id):
            return True
        rules = state.get("rules") or {}
        if not (rules.get("interceptions") or rules.get("super_interceptions")):
            return False
        if str(card.get("type", "")).lower() in (
            "wild", "wild_draw_four", "wild_draw_two", "wild_draw_six",
            "wild_draw_ten", "wild_reverse_draw_four", "color_roulette"
        ) or str(card.get("color", "")).lower() == "wild":
            return False
        top = state.get("top_card") or {}
        ctype = str(card.get("type", "")).lower()
        ttype = str(top.get("type", "")).lower()
        exact = (ctype == ttype and str(card.get("color", "")).lower() == str(top.get("color", "")).lower()
                 and (ctype != "number" or card.get("value") == top.get("value")))
        super_match = ctype == ttype and (ctype != "number" or card.get("value") == top.get("value"))
        return bool((rules.get("interceptions") and exact) or (rules.get("super_interceptions") and super_match))

    def _handle_play_card(self, card_id: str, card: dict):
        if card_id == "__WILD_COLOR__":
            self.on_choose_color(card.get("chosen_color", ""))
            return
        if not self.is_in_room():
            return
        # A normal card may only be played on the current player's turn.
        # The server remains authoritative, but we prevent the UI from opening
        # Wild/color dialogs for an ordinary out-of-turn click. Interception
        # rules are the explicit exception and are allowed to reach the server.
        if not self._can_play_card_out_of_turn(card):
            my_id = (self.user or {}).get("id")
            current_id = (self.uno_state or {}).get("current_player_id")
            if current_id is not None and str(current_id) != str(my_id):
                sound_engine.play_event("INVALID_ACTION")
                reader.speak(tr("ليس دورك"), interrupt=True)
                return
        ctype = str(card.get("type", "")).lower()
        color = str(card.get("color", "")).lower()
        if ctype in ("wild", "wild_draw_two", "wild_draw_four", "wild_draw_six", "wild_draw_ten", "wild_reverse_draw_four", "color_roulette") or color == "wild":
            valid, reason = self._prevalidate_wild_card_play(card_id, card)
            if not valid:
                sound_engine.play_event("INVALID_ACTION")
                reader.speak(tr(reason), interrupt=True)
                return
            self._pending_wild_card_id = card_id
            self.table_view.show_wild_colors()
            sound_engine.play_event("WILD_COLOR_PROMPT")
            reader.speak(tr("اختر اللون"), interrupt=True)
        else:
            self._send_uno_action("play", card_id)

    def on_choose_color(self, color: str):
        if self._pending_wild_card_id:
            cid = self._pending_wild_card_id
            self._pending_wild_card_id = None
            self._send_uno_action("play", cid, color)

    def on_challenge_bluff(self):
        if not self.is_in_room():
            return
        game = str((self.current_room or {}).get("game", "")).upper()
        if game != "UNO":
            return
        state = self.uno_state or {}
        rules = state.get("rules") or {}
        if not bool(rules.get("bluff")):
            return

        pending_bluff = state.get("pending_bluff")
        my_id = (self.user or {}).get("id")
        if not pending_bluff:
            return
        if str(pending_bluff.get("target_id")) != str(my_id):
            return
        self._send_uno_action("challenge_bluff")

    def on_enter_shortcut(self):
        if not self.is_in_room():
            return
        if self.current_room.get("game") != "FARKLE":
            return
        if self.table_view and getattr(self.table_view, "farkle_dice_list", None):
            item = self.table_view.farkle_dice_list.currentItem()
            if item is not None:
                self.table_view._on_farkle_item_activated(item)
                return
        state = self.farkle_state or {}
        if not state.get("active"):
            return
        if not state.get("is_my_turn"):
            reader.speak(tr("ليس دورك الآن."), interrupt=True)
            return
        if state.get("can_roll") and not state.get("must_score_before_roll"):
            self._handle_farkle_action("roll", "")

    def on_draw_shortcut(self):
        if not self.is_in_room():
            return
        game = str(self.current_room.get("game", "")).upper()
        if game == "FARKLE":
            state = self.farkle_state or {}
            roll = state.get("last_roll") or state.get("dice") or []
            if roll:
                sep = ", " if language() != "ar" else "، "
                reader.speak(sep.join(map(str, roll)), interrupt=True)
            else:
                reader.speak(tr("لا توجد رمية سابقة."), interrupt=True)
            return
        elif game in ("DOMINO", "AMERICAN_DOMINO"):
            state = self.domino_state or {}
            if not state.get("active"):
                return
            if not state.get("is_my_turn"):
                reader.speak(tr("ليس دورك الآن."), interrupt=True)
                return
            if state.get("can_draw"):
                self._handle_domino_action("draw")
            elif state.get("can_pass"):
                self._handle_domino_action("pass")
            else:
                reader.speak(tr("لديك حركة صالحة للعب."), interrupt=True)
            return
        elif game == "SNAKES_LADDERS":
            state = self.snakes_state or {}
            roll = state.get("last_roll", 0)
            if roll > 0:
                reader.speak(tr(f"آخر نرد: {roll}"), interrupt=True)
            else:
                reader.speak(tr("لا توجد رمية سابقة."), interrupt=True)
            return

    def on_draw_card(self):
        if not self.is_in_room():
            return
        game = str(self.current_room.get("game", "")).upper()
        if game == "UNO":
            self._send_uno_action("draw")
        elif game in ("DOMINO", "AMERICAN_DOMINO"):
            self.on_draw_shortcut()

    def on_uno_shortcut(self):
        if not self.is_in_room():
            return
        game = str((self.current_room or {}).get("game", "")).upper()
        if game != "UNO":
            return
        self._send_uno_action("call_uno")

    def on_buzzer_or_bot(self):
        # B remains Add Bot in the waiting lobby. During a buzzer round it
        # becomes the buzzer response, matching the supplied rule.
        if self.is_in_room() and self.uno_state and self.uno_state.get("buzzer_pending"):
            self._send_uno_action("buzzer")
            return
        self.on_add_bot()

    def on_add_bot(self):
        self.room_controller.add_bot()

    def on_remove_bot(self):
        self.room_controller.remove_bot()

    def on_announce_players(self):
        if not self.current_room:
            return
        raw_names = self.current_room.get("player_names")
        names = []
        if isinstance(raw_names, dict):
            names = [str(v) for v in raw_names.values() if v]
        elif isinstance(raw_names, list):
            names = [str(v) for v in raw_names if v]

        if not names:
            for st in (self.uno_state, self.domino_state, self.scopa_state, self.snakes_state, self.thief_state):
                if st and isinstance(st.get("players"), list):
                    names = [p.get("name", "لاعب") for p in st.get("players", []) if isinstance(p, dict)]
                    if names:
                        break
                elif st and isinstance(st.get("player_names"), dict):
                    names = [str(v) for v in st["player_names"].values() if v]
                    if names:
                        break
            if not names and self.farkle_state and isinstance(self.farkle_state.get("player_names"), dict):
                names = [str(v) for v in self.farkle_state["player_names"].values() if v]

        if not names:
            reader.speak(tr("لا يوجد لاعبون على الطاولة."), interrupt=True)
            return

        count = len(names)
        join_word = " and " if language() == "en" else " و "
        names_str = join_word.join(names)
        if count == 1:
            text = tr("لاعب واحد على الطاولة: {0}", names[0])
        elif count == 2:
            text = tr("لاعبان على الطاولة: {0} و {1}", names[0], names[1])
        elif 3 <= count <= 10:
            text = tr("{0} لاعبين على الطاولة: {1}", count, names_str)
        else:
            text = tr("{0} لاعباً على الطاولة: {1}", count, names_str)

        reader.speak(text, interrupt=True)

    def on_open_table_players(self):
        """Open the Table Players list dialog with captain at the top, vice-captain, and contextual actions."""
        if not self.current_room:
            return
        my_id = int((self.user or {}).get("id") or 0)
        dlg = TablePlayersDialog(self.current_room, my_id, self)
        res = dlg.exec()
        if res != QDialog.Accepted:
            return
        if getattr(dlg, "quick_action", None):
            tag, target_user = dlg.quick_action
            self._execute_table_player_action(tag, target_user)
            return
        if dlg.selected_user:
            if isinstance(dlg.selected_user, dict) and dlg.selected_user.get("type") == "open_voice_manager":
                self.on_open_voice_manager()
                return
            self._open_table_player_actions(dlg.selected_user)

    def on_open_voice_manager(self):
        """Open Voice Manager dialog (مدير الصوت) with controls and player voice status."""
        if not self.is_in_room() or not self.current_room:
            return
        my_id = int((self.user or {}).get("id") or 0)
        dlg = TableVoiceManagerDialog(self.current_room, my_id, self)
        if dlg.exec() != QDialog.Accepted or not dlg.selected_action:
            return

        action_data = dlg.selected_action
        action_type = action_data.get("type")
        if action_type == "voice_mode_menu":
            cur_mode = str(self.current_room.get("voice_mode") or "all").lower()
            mode_dlg = TableVoiceModeDialog(cur_mode, self)
            if mode_dlg.exec() == QDialog.Accepted and mode_dlg.selected_mode:
                new_mode = mode_dlg.selected_mode
                rid = str(self.current_room.get("id") or "")
                def done(r):
                    mode_val = r.get("mode") or new_mode
                    if self.current_room:
                        self.current_room["voice_mode"] = mode_val
                    if mode_val == "listen_only":
                        msg = "تم ضبط وضع المحادثة الصوتية: استماع فقط (تعطيل تحدث اللاعبين)."
                    elif mode_val == "owner_only":
                        msg = "تم تعطيل المحادثة الصوتية تماماً في الطاولة."
                    else:
                        msg = "تمت إتاحة المحادثة الصوتية للجميع."
                    self.table_view.add_log(tr(msg), category="ALL")
                    reader.speak(tr(msg), interrupt=True)
                def fail(e):
                    reader.speak(tr("تعذر تغيير وضع المحادثة الصوتية: {error}", error=tr(str(e))), interrupt=True)
                self._run_async(lambda: self.api.set_voice_mode(rid, new_mode), done, fail)
            return
        elif action_type == "session_action":
            act = action_data.get("action")
            if act == "leave_voice":
                self.voice.leave_voice_session()
            elif act == "join_voice":
                self.voice.toggle_voice_session()
            elif act == "toggle_mute":
                self.voice.toggle_mute()
        elif action_type == "player":
            target_user = action_data.get("user") or {}
            is_host = str(self.current_room.get("host_id")) == str((self.user or {}).get("id"))
            if not is_host:
                reader.speak(tr("التحكم بالصوت متاح لقائد الطاولة فقط."), interrupt=True)
                return
            target_id = int(target_user.get("id") or 0)
            if target_id == my_id:
                reader.speak(tr("لا يمكنك التحكم في نفسك من هنا."), interrupt=True)
                return
            self._open_table_voice_submenu(target_user)

    def _open_table_player_actions(self, target_user: dict):
        if not self.current_room or not isinstance(target_user, dict):
            return
        my_id = int((self.user or {}).get("id") or 0)
        is_host = str(self.current_room.get("host_id")) == str((self.user or {}).get("id"))
        is_co_host = str(self.current_room.get("co_host_id")) == str((self.user or {}).get("id"))
        target_id = int(target_user.get("id") or 0)
        voice_muted_list = self.current_room.get("voice_muted") or []
        is_target_muted = target_id in voice_muted_list

        act_dlg = TablePlayerActionsDialog(target_user, is_host, my_id, is_target_muted, is_co_host=is_co_host, parent=self)
        if act_dlg.exec() != QDialog.Accepted or not act_dlg.selected_tag:
            return
        self._execute_table_player_action(act_dlg.selected_tag, target_user)

    def _execute_table_player_action(self, tag: str, target_user: dict):
        if not self.current_room or not isinstance(target_user, dict):
            return
        rid = str(self.current_room.get("id") or "")
        target_id = int(target_user.get("id") or 0)
        target_name = str(target_user.get("display_name") or "لاعب")

        if tag == "kick":
            self._run_async(
                lambda: self.api.kick_player(rid, target_id),
                lambda _r: reader.speak(tr("تم طرد {name} من الطاولة.", name=target_name), interrupt=True),
                lambda e: reader.speak(tr("تعذر طرد اللاعب: {error}", error=tr(str(e))), interrupt=True)
            )
        elif tag == "ban":
            self._run_async(
                lambda: self.api.ban_player(rid, target_id),
                lambda _r: reader.speak(tr("تم حظر {name} من الطاولة.", name=target_name), interrupt=True),
                lambda e: reader.speak(tr("تعذر حظر اللاعب: {error}", error=tr(str(e))), interrupt=True)
            )
        elif tag == "transfer_host":
            self._run_async(
                lambda: self.api.transfer_host(rid, target_id),
                lambda _r: reader.speak(tr("تم نقل قيادة الطاولة إلى {name}.", name=target_name), interrupt=True),
                lambda e: reader.speak(tr("تعذر نقل القيادة: {error}", error=tr(str(e))), interrupt=True)
            )
        elif tag == "set_co_host":
            self._run_async(
                lambda: self.api.set_co_host(rid, target_id),
                lambda r: reader.speak(
                    tr("تم تعيين {name} نائباً للقائد." if r.get("is_co_host") else "تم إلغاء تعيين {name} كنائب للقائد.", name=target_name),
                    interrupt=True
                ),
                lambda e: reader.speak(tr("تعذر تغيير نائب القائد: {error}", error=tr(str(e))), interrupt=True)
            )
        elif tag == "substitute":
            sub_dlg = TableSubstituteChoiceDialog(target_user, self.current_room, my_id, self)
            if sub_dlg.exec() != QDialog.Accepted or not sub_dlg.selected_choice:
                return
            choice = sub_dlg.selected_choice
            is_bot = bool(choice.get("is_bot"))
            rep_id = choice.get("id")
            rep_name = str(choice.get("display_name") or "لاعب")

            if is_bot:
                self._run_async(
                    lambda: self.api.substitute_player(rid, target_id, is_bot=True),
                    lambda _r: reader.speak(tr("تم استبدال {name} ببوت.", name=target_name), interrupt=True),
                    lambda e: reader.speak(tr("تعذر استبدال اللاعب: {error}", error=tr(str(e))), interrupt=True)
                )
            else:
                self._run_async(
                    lambda: self.api.substitute_player(rid, target_id, replacement_user_id=rep_id, is_bot=False),
                    lambda _r: reader.speak(tr("تم استبدال {name} بـ {rep}.", name=target_name, rep=rep_name), interrupt=True),
                    lambda e: reader.speak(tr("تعذر استبدال اللاعب: {error}", error=tr(str(e))), interrupt=True)
                )
        elif tag == "make_spectator":
            self._run_async(
                lambda: self.api.toggle_spectator(rid, target_id),
                lambda _r: reader.speak(tr("تم تحويل {name} إلى وضع المتفرج.", name=target_name), interrupt=True),
                lambda e: reader.speak(tr("تعذر تغيير وضع اللاعب: {error}", error=tr(str(e))), interrupt=True)
            )
        elif tag == "voice_submenu":
            self._open_table_voice_submenu(target_user)
        elif tag == "profile":
            self._run_async(
                lambda: self.api.user_profile(target_id),
                lambda r: ProfileDialog(r, self).exec(),
                lambda e: reader.speak(tr(f"تعذر فتح الملف الشخصي: {e}"), interrupt=True)
            )
        elif tag == "add_friend":
            self._run_async(
                lambda: self.api.send_friend_request(target_id),
                lambda _r: reader.speak(tr("تم إرسال طلب الصداقة."), interrupt=True),
                lambda e: reader.speak(tr(f"تعذر إرسال طلب الصداقة: {e}"), interrupt=True)
            )
        elif tag == "message":
            msg_dlg = SimpleMessageDialog(tr("إرسال رسالة إلى {name}", name=target_name), tr("اكتب رسالتك:"), self)
            if msg_dlg.exec():
                self._run_async(
                    lambda: self.api.send_private_message(target_id, msg_dlg.editor.text().strip()),
                    lambda _r: None,
                    lambda e: reader.speak(tr(f"تعذر إرسال الرسالة: {e}"), interrupt=True)
                )

    def _open_table_voice_submenu(self, target_user: dict):
        if not self.current_room or not isinstance(target_user, dict):
            return
        rid = str(self.current_room.get("id") or "")
        is_host = bool(self.current_room.get("is_host"))
        target_id = int(target_user.get("id") or 0)
        target_name = str(target_user.get("display_name") or "لاعب")
        voice_muted_list = self.current_room.get("voice_muted") or []
        is_target_muted = target_id in voice_muted_list

        dlg = TableVoiceSubmenuDialog(target_user, is_host, is_target_muted, self)
        if dlg.exec() != QDialog.Accepted or not dlg.selected_tag:
            return

        tag = dlg.selected_tag
        if tag == "voice_mute":
            self._run_async(
                lambda: self.api.voice_mute_player(rid, target_id),
                lambda r: reader.speak(
                    tr("تم كتم ميكروفون {name}." if r.get("is_muted") else "تم إلغاء كتم ميكروفون {name}.", name=target_name),
                    interrupt=True
                ),
                lambda e: reader.speak(tr("تعذر تغيير حالة كتم الميكروفون: {error}", error=tr(str(e))), interrupt=True)
            )
        elif tag == "voice_kick":
            self._run_async(
                lambda: self.api.voice_kick_player(rid, target_id),
                lambda _r: reader.speak(tr("تمت إزالة {name} من المحادثة الصوتية.", name=target_name), interrupt=True),
                lambda e: reader.speak(tr("تعذر إزالة اللاعب من الصوت: {error}", error=tr(str(e))), interrupt=True)
            )
        elif tag == "voice_ban":
            self._run_async(
                lambda: self.api.voice_ban_player(rid, target_id),
                lambda _r: reader.speak(tr("تم حظر {name} من المحادثة الصوتية.", name=target_name), interrupt=True),
                lambda e: reader.speak(tr("تعذر حظر اللاعب من الصوت: {error}", error=tr(str(e))), interrupt=True)
            )
        elif tag == "voice_volume":
            from PySide6.QtWidgets import QInputDialog
            current_pct = int(round(self.voice.get_user_volume(target_id) * 100))
            val, ok = QInputDialog.getInt(
                self,
                tr("تعديل مستوى الصوت"),
                tr("أدخل مستوى صوت {name} بالنسبة المئوية (من 0 إلى 200):", name=target_name),
                current_pct,
                0,
                200,
                5
            )
            if ok:
                new_scale = val / 100.0
                self.voice.save_user_volume(target_id, new_scale)
                reader.speak(tr("تم ضبط مستوى صوت {name} على {0}%.", val, name=target_name), interrupt=True)

    def on_toggle_room_privacy(self):
        self.room_controller.toggle_room_privacy()

    def on_toggle_spectator_shortcut(self):
        self.room_controller.toggle_spectator_shortcut()

    def _send_uno_action(self, act: str, card_id: str = "", color: str = ""):
        if not self.current_room or self._action_in_flight:
            return
        rid = self.current_room.get("id")
        self._action_in_flight = True
        def done(state):
            self._action_in_flight = False
            self._apply_uno_state(state)
        def fail(msg):
            self._action_in_flight = False
            self._show_error(msg)
        if self._send_game_action_ws(act, card_id=card_id, chosen_color=color, on_success=done, on_error=fail):
            return
        self._run_async(lambda: self.api.uno_action(rid, act, card_id, color), done, fail)

    # ---------- Real-time WebSocket ----------
    def _emit_ws_event(self, data):
        self.wsEvent.emit(data)

    def _update_current_room_from_ws(self, room):
        if room:
            self.current_room = room

    def _start_lobby_ws(self):
        self.ws.stop()
        events_url = self.api.get_ws_url("/ws/events")
        self.ws.start(self._emit_ws_event, events_url, (self.api.token or ""))

    def _start_room_ws(self, room_id):
        self.ws.stop()
        self._room_ws_url = self.api.get_ws_url(f"/ws/room/{room_id}")
        self.ws.start(self._emit_ws_event, self._room_ws_url, (self.api.token or ""))

    def _recover_room_snapshot(self, room, uno_state=None, thief_state=None, farkle_state=None, domino_state=None, american_domino_state=None, snakes_state=None, scopa_state=None, tennis_state=None, ninety_nine_state=None):
        if not room or not self.current_room or room.get("id") != self.current_room.get("id"):
            return
        self.current_room = room
        game_type = str(room.get("game") or "").upper()
        self.setWindowTitle("")
        self.voice.join_room(str(room.get("id") or ""))
        self._maybe_auto_join_voice(room)
        if self._voice_restore_after_reconnect:
            self._voice_restore_after_reconnect = False
            v_mode = str(room.get("voice_mode") or "all").lower()
            my_id = int((self.user or {}).get("id") or 0)
            host_id = int(room.get("host_id") or 0)
            is_host = (my_id == host_id)
            if v_mode != "owner_only" or is_host:
                if self.voice.activate_voice_session(start_microphone=True):
                    self.voice.stateChanged.emit("الاتصال الصوتي عاد.")
        self.table_view.set_game_type(game_type)
        # For Thief Hunt, the game snapshot is authoritative for whether the
        # gameplay area is active. A stale room-status snapshot must never hide
        # the answer field for a currently-answering round.
        if game_type != "THIEF_HUNT":
            self.table_view.set_playing_mode(room.get("status") == "playing")
        if uno_state is not None:
            self._apply_uno_state(uno_state)
        if thief_state is not None:
            self._apply_thief_state(thief_state)
        if farkle_state is not None:
            self._apply_farkle_state(farkle_state)
        if domino_state is not None:
            self._apply_domino_state(domino_state)
        if american_domino_state is not None:
            self._apply_domino_state(american_domino_state)
        if snakes_state is not None:
            self._apply_snakes_state(snakes_state)
        if scopa_state is not None:
            self._apply_scopa_state(scopa_state)
        if tennis_state is not None:
            self._apply_tennis_state(tennis_state)
        if ninety_nine_state is not None:
            self._apply_ninety_nine_state(ninety_nine_state)

        focus = self._reconnect_focus
        self._reconnect_focus = None
        if focus is not None and focus.isVisible():
            QTimer.singleShot(50, focus.setFocus)
        else:
            QTimer.singleShot(50, self.table_view.focus_initial)

    def _handle_ws_event(self, event: dict):
        self.ws_event_router.route(event)

    def _announce_terminal_result(self, event: dict):
        my_id = (self.user or {}).get("id")
        winning_ids = event.get("winning_ids")
        if isinstance(winning_ids, (list, tuple, set)) and my_id is not None:
            won = any(str(w) == str(my_id) for w in winning_ids)
        elif event.get("winning_team") is not None and my_id is not None and isinstance(event.get("teams"), dict):
            won = (event.get("teams").get(str(my_id)) == event.get("winning_team"))
        else:
            winner_id = event.get("winner_id") or event.get("match_winner_id")
            won = winner_id is not None and my_id is not None and str(winner_id) == str(my_id)
        if not getattr(self, "_match_result_sound_played", False):
            sound_engine.play_event("MATCH_WIN" if won else "MATCH_LOSS")
            self._match_result_sound_played = True
        reader.speak(tr("فزت بالمباراة." if won else "انتهت المباراة."), interrupt=False)

    def _finish_snakes_match(self, event: dict):
        self._announce_terminal_result(event)
        self.snakes_state = None
        self.table_view.set_game_type("SNAKES_LADDERS")
        self.table_view.set_playing_mode(False)
        self.table_view.clear_hand_for_round_transition()
        self.table_view.main_table_widget.setFocus()

    def _finish_scopa_match(self, event: dict):
        self._announce_terminal_result(event)
        self.scopa_state = None
        self.table_view.set_game_type("SCOPA")
        self.table_view.set_playing_mode(False)
        self.table_view.clear_hand_for_round_transition()
        self.table_view.main_table_widget.setFocus()

    def _announce_scopa_final_play(self, event: dict):
        """Speak and play the final Scopa card once, regardless of frame order."""
        action = str(event.get("final_play_action") or "").strip()
        event_type = str(event.get("final_play_event_type") or "").strip()
        if not action or not event_type:
            return False
        event_id = str(event.get("final_play_event_id") or event.get("event_id") or "")
        key = (str((self.current_room or {}).get("id") or ""), event_id, event_type, action)
        if key in self._seen_scopa_final_plays:
            return False
        self._seen_scopa_final_plays.add(key)
        if len(self._seen_scopa_final_plays) > 64:
            self._seen_scopa_final_plays.clear()
            self._seen_scopa_final_plays.add(key)
        for cue in sound_engine.event_cues("SCOPA", event_type, event):
            sound_engine.play_event(cue)
        reader.speak(tr(action), interrupt=False)
        return True

    def _on_language_changed(self, _value=None):
        """Apply language changes immediately to all existing UI without restart."""
        try:
            from client.localization import language
            active_lang = language()
            localize_widget_tree(self)
            QApplication.instance().setLayoutDirection(Qt.RightToLeft if active_lang == "ar" else Qt.LeftToRight)
            # Sync active game states to table_view so game widgets re-render in new language
            if hasattr(self, "table_view") and self.table_view:
                if hasattr(self, "snakes_state") and self.snakes_state:
                    self.table_view._snakes_state = self.snakes_state
                if hasattr(self, "farkle_state") and self.farkle_state:
                    self.table_view._farkle_state = self.farkle_state
                if hasattr(self, "domino_state") and self.domino_state:
                    self.table_view._domino_state = self.domino_state
                if hasattr(self, "scopa_state") and self.scopa_state:
                    self.table_view._scopa_state = self.scopa_state
                self.table_view._on_language_changed(active_lang)
            # Refresh dynamic home/table menus from their existing state.
            for view in (self.auth_view, self.home_view, self.rooms_menu_view, self.join_rooms_view, self.table_view, self.saved_tables_view):
                localize_widget_tree(view)
        except Exception:
            pass

    def _on_voice_state_message(self, text: str):
        reader.speak(tr(text), interrupt=True)

    def _maybe_auto_join_voice(self, room=None):
        """Join table voice automatically when the user enabled the setting.
        Membership is automatic; microphone remains muted until M is pressed.
        """
        try:
            from client.settings_store import load_settings
            audio = load_settings().get("audio", {})
            if not bool(audio.get("voice_auto_join", False)):
                return
            if not self.is_in_room() or not self.voice.room_id:
                return
            if not self.voice.in_voice_chat:
                self.voice.toggle_voice_session()
        except Exception:
            pass

    def on_toggle_voice_chat(self):
        if not self.is_in_room():
            return
        my_id = int((self.user or {}).get("id") or 0)
        host_id = int((self.current_room or {}).get("host_id") or 0)
        is_host = (my_id == host_id)
        mode = str((self.current_room or {}).get("voice_mode") or "all").lower()
        if mode == "owner_only" and not is_host:
            reader.speak(tr("المحادثة الصوتية معطلة في هذه الطاولة من قبل القائد."), interrupt=True)
            return
        self.voice.toggle_voice_session()

    def on_toggle_voice_mute(self):
        if not self.is_in_room():
            return
        my_id = int((self.user or {}).get("id") or 0)
        host_id = int((self.current_room or {}).get("host_id") or 0)
        is_host = (my_id == host_id)
        mode = str((self.current_room or {}).get("voice_mode") or "all").lower()
        if (mode in ("listen_only", "owner_only")) and not is_host:
            reader.speak(tr("التحدث معطل في هذه الطاولة بواسطة القائد."), interrupt=True)
            return
        self.voice.toggle_mute()

    def on_query_voice_status(self):
        """Query voice connection state, mic status, and active speakers."""
        if not self.is_in_room():
            return
        if not self.voice.in_voice_chat:
            reader.speak(tr("لست في المحادثة الصوتية حاليًا."), interrupt=True)
            return
        mic_status = tr("الميكروفون مكتوم") if self.voice.muted else tr("الميكروفون مفتوح")
        active_ids = self.voice.get_active_speaker_ids()
        if active_ids:
            room = self.current_room or {}
            names_dict = room.get("player_names") or room.get("players_dict") or {}
            speaker_names = [names_dict.get(uid, names_dict.get(str(uid), tr("لاعب"))) for uid in active_ids]
            speakers_str = "، ".join(speaker_names)
            msg = tr("متصل بالصوت، {0}. يتحدث الآن: {1}.", mic_status, speakers_str)
        else:
            msg = tr("متصل بالصوت، {0}. لا أحد يتحدث حاليًا.", mic_status)
        reader.speak(msg, interrupt=True)

    def on_announce_table_time(self):
        if not self.is_in_room():
            return
        room = self.current_room or {}
        now = datetime.now(timezone.utc)
        table_start = parse_timestamp(room.get("viewer_joined_at") or room.get("table_started_at") or room.get("table_created_at"))
        if table_start is not None:
            table_seconds = max(0.0, (now - table_start).total_seconds())
        else:
            table_seconds = max(0.0, time.monotonic() - (self._table_join_fallback_monotonic or time.monotonic()))

        round_start = parse_timestamp(room.get("round_started_at"))
        if round_start is not None:
            round_seconds = max(0.0, (now - round_start).total_seconds())
        elif self._round_fallback_monotonic is not None:
            round_seconds = max(0.0, time.monotonic() - self._round_fallback_monotonic)
        else:
            round_seconds = 0.0
        cur_lang = language()
        reader.speak(
            tr(f"وقت الطاولة {format_duration(table_seconds, cur_lang)}، ووقت الجولة {format_duration(round_seconds, cur_lang)}."),
            interrupt=True,
        )

    def on_table_settings(self):
        from client.views.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self)
        dialog.exec()
        if self.is_in_room() and hasattr(self, "table_view") and self.table_view:
            self.table_view.focus_initial()

    def on_manual_reconnect(self):
        if not self.api.token:
            reader.speak(tr("لا يوجد اتصال بحسابك."), interrupt=True)
            return
        room = dict(self.current_room or {})
        room_id = room.get("id")
        self._reconnect_focus = QApplication.focusWidget()
        self._voice_restore_after_reconnect = bool(self.voice.in_voice_chat)
        self.voice.suspend_for_reconnect()
        self.ws.stop()
        if room_id:
            self._start_room_ws(room_id)
            generation = self._room_generation
            def done(fresh_room):
                if generation != self._room_generation or not self.current_room or str(self.current_room.get("id")) != str(room_id):
                    return
                self.current_room = fresh_room
                self._poll_table_state()
                reader.speak(tr("تمت إعادة الاتصال بالطاولة."), interrupt=True)
            def fail(err):
                text = str(err)
                if "HTTP 404" in text or "not found" in text.lower() or "غير موجود" in text:
                    self._leave_table_after_failed_reconnect()
                else:
                    reader.speak(tr(f"تعذرت إعادة الاتصال: {text}"), interrupt=True)
            self._run_async(lambda: self.api.get_room(room_id), done, fail)
        else:
            self._start_lobby_ws()
            reader.speak(tr("تمت إعادة الاتصال."), interrupt=True)

    def _leave_table_after_failed_reconnect(self):
        self.voice.leave_room()
        self.ws.stop()
        self.current_room = None
        self.poll_timer.stop()
        self.setWindowTitle(tr("TableVerse"))
        self.stack.setCurrentIndex(2)
        self.rooms_menu_view.menu_list.setFocus()
        reader.speak(tr("الطاولة لم تعد متاحة. تم الرجوع لقائمة الطاولات."), interrupt=True)

    def _on_reconnect_deadline_expired(self):
        self._is_reconnecting = False
        sound_engine.stop_looping("CONNECTING")
        if self.current_room:
            self._leave_table_after_failed_reconnect()
        else:
            reader.speak(tr("تم قطع الاتصال."), interrupt=True)

    def on_snakes_roll_shortcut(self):
        if not self.current_room or not self.snakes_state or not self.snakes_state.get("active"):
            return
        if getattr(self, "_snakes_stepping", False) or not self.snakes_state.get("is_my_turn"):
            reader.speak(tr("ليس دورك الآن."), interrupt=True)
            sound_engine.play_event("INVALID_ACTION")
            return
        self._snakes_stepping = True
        rid = self.current_room.get("id")
        def done(state):
            self._apply_snakes_state(state)
        def fail(msg):
            self._snakes_stepping = False
            reader.speak(tr(str(msg)), interrupt=True)
        if self._send_game_action_ws("roll", on_success=done, on_error=fail):
            return
        self._run_async(
            lambda: self.api.snakes_action(rid, "roll"),
            done,
            fail
        )

    def on_snakes_radar_shortcut(self):
        if not self.current_room or not self.snakes_state or not self.snakes_state.get("active"):
            return
        radar = self.snakes_state.get("radar") or {}
        pos = radar.get("position", 0)
        ladder = radar.get("nearest_ladder")
        snake = radar.get("nearest_snake")
        
        parts = [tr("المربع {position}", position=pos)]
        if ladder:
            parts.append(tr("سلم في {base} إلى {top}", base=ladder[0], top=ladder[1]))
        if snake:
            parts.append(tr("ثعبان في {head} إلى {tail}", head=snake[0], tail=snake[1]))
        reader.speak(("، " if language() == "ar" else ", ").join(parts), interrupt=True)

    def on_snakes_positions(self):
        if not self.current_room or not self.snakes_state or not self.snakes_state.get("active"):
            reader.speak(tr("المباراة لم تبدأ بعد."), interrupt=True)
            return
        players = self.snakes_state.get("players") or []
        if not players:
            return
        parts = []
        for idx, p in enumerate(players, start=1):
            pname = p.get("name", "لاعب")
            pos = p.get("position", 0)
            status_parts = []
            if p.get("is_frozen"):
                status_parts.append(tr("مجمد"))
            if p.get("has_shield"):
                status_parts.append(tr("مع درع"))
            status_str = f" ({'، '.join(status_parts)})" if status_parts else ""
            parts.append(tr("المركز {rank}: {name} في المربع {position}{status}", rank=idx, name=pname, position=pos, status=status_str))
        reader.speak(("، " if language() == "ar" else ", ").join(parts), interrupt=True)

    def on_announce_turn(self):
        game = str((self.current_room or {}).get("game", "")).upper()
        if game == "FARKLE":
            state = self.farkle_state or {}
            if not state.get("active"):
                reader.speak(tr("المباراة لم تبدأ بعد."), interrupt=True)
                return
            curr = state.get("current_player_name", "")
            reader.speak(tr("دور {name}", name=curr) if curr else tr("غير محدد"), interrupt=True)
            return
        elif game in ("DOMINO", "AMERICAN_DOMINO"):
            state = self.domino_state or {}
            if not state.get("active"):
                reader.speak(tr("المباراة لم تبدأ بعد."), interrupt=True)
                return
            curr = state.get("current_player_name", "")
            reader.speak(tr("دور {name}", name=curr) if curr else tr("غير محدد"), interrupt=True)
            return
        elif game == "SNAKES_LADDERS":
            state = self.snakes_state or {}
            if not state.get("active"):
                reader.speak(tr("المباراة لم تبدأ بعد."), interrupt=True)
                return
            curr = state.get("current_player_name", "")
            reader.speak(tr("دور {name}", name=curr) if curr else tr("غير محدد"), interrupt=True)
            return
        elif game == "SCOPA":
            state = self.scopa_state or {}
            if not state.get("active"):
                reader.speak(tr("المباراة لم تبدأ بعد."), interrupt=True)
                return
            curr = state.get("current_turn_name", "")
            reader.speak(tr("دور {name}", name=curr) if curr else tr("غير محدد"), interrupt=True)
            return
        elif game == "NINETY_NINE":
            state = getattr(self, "uno_state", {}) or {}
            if not state.get("active"):
                reader.speak(tr("المباراة لم تبدأ بعد."), interrupt=True)
                return
            idx = state.get("current_turn_index", 0)
            players = state.get("players", [])
            curr_name = ""
            if 0 <= idx < len(players):
                curr_name = players[idx].get("name", "")
            if not curr_name:
                curr_name = state.get("current_player_name", "")
            reader.speak(tr("دور {name}", name=curr_name) if curr_name else tr("غير محدد"), interrupt=True)
            return
        elif game == "TENNIS":
            state = getattr(self, "tennis_state", {}) or {}
            sc = state.get("score", {})
            server_idx = sc.get("server_idx", 0)
            players = state.get("players", [])
            if players:
                server_name = players[server_idx].get("name", "اللاعب") if server_idx < len(players) else "اللاعب"
                reader.speak(tr("الإرسال مع {name}", name=server_name), interrupt=True)
            else:
                reader.speak(tr("المباراة لم تبدأ بعد."), interrupt=True)
            return

        if not self.uno_state or not self.uno_state.get("active"):
            reader.speak(tr("المباراة لم تبدأ بعد."), interrupt=True)
            return
        curr = self.uno_state.get("current_player_name", "")
        reader.speak(tr("دور {name}", name=curr) if curr else tr("غير محدد"), interrupt=True)

    def on_domino_announce_ends(self):
        game = str((self.current_room or {}).get("game", "")).upper()
        if game not in ("DOMINO", "AMERICAN_DOMINO"):
            return
        state = self.domino_state or {}
        if not state.get("active"):
            reader.speak(tr("المباراة لم تبدأ بعد."), interrupt=True)
            return
        l_end = state.get("left_end")
        r_end = state.get("right_end")
        if l_end is not None and r_end is not None:
            if game == "AMERICAN_DOMINO":
                open_sum = state.get("open_ends_sum", l_end + r_end)
                reader.speak(tr(f"{l_end}/{r_end}، المجموع {open_sum}"), interrupt=True)
            else:
                reader.speak(tr(f"{l_end}/{r_end}"), interrupt=True)
        else:
            reader.speak(tr("فارغة"), interrupt=True)

    def on_announce_domino_board_tiles(self):
        game = str((self.current_room or {}).get("game", "")).upper()
        if game not in ("DOMINO", "AMERICAN_DOMINO"):
            return
        state = self.domino_state or {}
        if not state.get("active"):
            reader.speak(tr("المباراة لم تبدأ بعد."), interrupt=True)
            return
        board = list(state.get("board") or [])
        if not board:
            reader.speak(tr("لم تنزل أي قطع على الطاولة بعد."), interrupt=True)
            return
        from server.app.games.domino import tile_display_name
        items = [(tile_display_name(tuple(t)), i) for i, t in enumerate(board)]
        ListMenu(
            self, "قائمة القطع على الطاولة", items,
        ).show_menu(speak_text=f"قطع الطاولة، عددها {len(board)}")

    def on_announce_rules(self):
        room = self.current_room or {}
        rules = room.get("rules") or {}
        game = str(room.get("game", "")).upper()
        if not rules and game != "SCOPA":
            reader.speak(tr("اللعب بالوضع الافتراضي."), interrupt=True)
            return

        active_rules = []
        if game == "UNO":
            from core_shared.rules_config import RULE_DEFINITIONS
            rule_dict = {k: name for k, name, _ in RULE_DEFINITIONS}
            for k, enabled in rules.items():
                if enabled and isinstance(enabled, bool):
                    active_rules.append(rule_dict.get(k, k))
        elif game == "SCOPA":
            mode_map = {
                "classic": "سكوبا الكلاسيكية",
                "escoba_15": "إسكوبا 15",
                "asso_piglia_tutto": "آسو بيجليا توتو",
                "scopone": "سكوبون",
                "inverted": "سكوبا المعكوسة"
            }
            mode = rules.get("scopa_mode") or room.get("scopa_mode") or "classic"
            active_rules.append(mode_map.get(mode, mode))
            if rules.get("asso_piglia_tutto") and "آسو بيجليا توتو" not in active_rules: active_rules.append("آسو بيجليا توتو")
            if rules.get("scopone") and "سكوبون" not in active_rules: active_rules.append("سكوبون")
            if rules.get("inverted") and "سكوبا المعكوسة" not in active_rules: active_rules.append("سكوبا المعكوسة")
            target = room.get("target_score") or rules.get("target_score") or 11
            active_rules.append(tr("الهدف {0} نقطة", target))
        elif game == "SNAKES_LADDERS":
            if rules.get("knockout"): active_rules.append("نظام استبعاد اللاعبين")
            if rules.get("mystery_tiles"): active_rules.append("المربعات الغامضة")
        elif game == "THIEF_HUNT":
            active_rules.append(tr("عدد الجولات: {0}", rules.get('rounds', 5)))
            if rules.get("allow_human_thief"): active_rules.append("السماح للاعبين بدور اللص")
            if rules.get("elimination_mode"): active_rules.append("نظام الإقصاء")
        elif game in ("DOMINO", "AMERICAN_DOMINO"):
            mode = rules.get("mode", "draw")
            active_rules.append("لعب بدون سحب" if mode == "block" else ("خمسات" if mode == "all_fives" else "لعب مع سحب"))
            if rules.get("count_remaining_pips"): active_rules.append("حساب نقاط الخصوم")
        elif game == "FARKLE":
            active_rules.append(tr("الحد الأدنى للإيداع: {0}", rules.get('min_bank', 30)))
            active_rules.append(tr("الحد الأدنى لفتح الرصيد: {0}", rules.get('first_bank_min', 50)))
        elif game == "TENNIS":
            diff_names = {"EASY": "سهل", "NORMAL": "متوسط", "HARD": "صعب", "EXPERT": "محترف"}
            diff = rules.get("bot_difficulty", "NORMAL")
            active_rules.append(tr("صعوبة البوت: {0}", diff_names.get(diff, diff)))
            target = room.get("target_score") or 1
            active_rules.append(tr("عدد المجموعات للفوز: {0}", target))
        elif game in ("NINETY_NINE", "NINETYNINE"):
            tokens = rules.get("starting_tokens") or room.get("target_score") or 11
            active_rules.append(tr("النقاط: {0}", tokens))
            timer_val = rules.get("turn_timer") or room.get("turn_timer") or "none"
            from client.table_framework.settings_registry import TIMER_LABELS
            timer_label = TIMER_LABELS.get(str(timer_val), str(timer_val))
            active_rules.append(tr("وقت الدور: {0}", timer_label))

        else:
            for k, v in rules.items():
                if isinstance(v, bool):
                    if v: active_rules.append(str(k))
                else:
                    active_rules.append(f"{k}: {v}")

        if not active_rules:
            reader.speak(tr("اللعب بالوضع الافتراضي."), interrupt=True)
        else:
            sep = ", " if language() == "en" else "، "
            localized_rules = [tr(r) for r in active_rules]
            reader.speak(tr("الإعدادات الحالية: {rules}", rules=sep.join(localized_rules)), interrupt=True)

    def on_announce_top(self):
        game = str((self.current_room or {}).get("game", "")).upper()
        if game == "NINETY_NINE":
            state = getattr(self, "uno_state", {}) or {}
            if not state.get("active"):
                reader.speak(tr("المباراة لم تبدأ بعد."), interrupt=True)
                return
            pile = state.get("pile_value", 0)
            reader.speak(tr(f"المجموع {pile}"), interrupt=True)
            return

        if game == "SCOPA":
            state = self.scopa_state or {}
            if not state.get("active"):
                reader.speak(tr("المباراة لم تبدأ بعد."), interrupt=True)
                return
            table_cards = state.get("table_cards") or []
            if not table_cards:
                reader.speak(tr("الطاولة فارغة."), interrupt=True)
            else:
                from core_shared.uno_rules import card_display_ar
                names = [tr(card_display_ar(c)) for c in table_cards]
                cards_str = ("، " if language() == "ar" else ", ").join(names)
                reader.speak(cards_str, interrupt=True)
            return
        if game != "UNO":
            return
        if not self.uno_state or not self.uno_state.get("active"):
            reader.speak(tr("المباراة لم تبدأ بعد."), interrupt=True)
            return
        top = self.uno_state.get("top_card") or {}
        from core_shared.uno_rules import card_display_ar
        top_name = card_display_ar(top)
        # For Wild cards, R must announce the effective color chosen by the
        # player, not just the generic card name.
        if top.get("type") in ("wild", "wild_draw_four", "buzzer") or top.get("card_type") in ("wild", "wild_draw_four", "buzzer"):
            chosen_color = self.uno_state.get("current_color") or top.get("chosen_color") or ""
            if chosen_color:
                from core_shared.constants import COLOR_NAMES_AR
                color_ar = COLOR_NAMES_AR.get(chosen_color, chosen_color)
                top_name = f"{top_name} {color_ar}"
        reader.speak(tr(top_name), interrupt=True)

    def on_c_shortcut(self):
        game = str((self.current_room or {}).get("game", "")).upper()
        if game == "FARKLE":
            state = self.farkle_state or {}
            turn_score = int(state.get("turn_score", 0) or 0)
            reader.speak(str(turn_score), interrupt=True)
            return
        elif game in ("DOMINO", "AMERICAN_DOMINO"):
            state = self.domino_state or {}
            hand = state.get("hand", [])
            players = state.get("players", [])
            bcount = int(state.get("boneyard_count", 0) or 0)
            my_count = len(hand)
            my_id = (self.user or {}).get("id")
            parts = [tr(f"أنت {my_count}")]
            for p in players:
                if p.get("user_id") == my_id:
                    continue
                name = p.get("name", "اللاعب")
                count = p.get("tile_count", 0)
                parts.append(tr(f"{name} {count}"))
            parts.append(tr("المتبقي في البنك {count}", count=bcount))
            sep = "، " if language() == "ar" else ", "
            reader.speak(sep.join(parts), interrupt=True)
            return
        elif game == "SCOPA":
            state = self.scopa_state or {}
            deck_c = int(state.get("deck_count", 0))
            my_cap = int(state.get("my_captured_count", 0))
            reader.speak(tr("أكلت {captured} كارت، والمتبقي في البنك {remaining} كارت.", captured=my_cap, remaining=deck_c), interrupt=True)
            return
        elif game == "UNO":
            self.on_announce_no_uno()

    def on_announce_no_uno(self):
        game = str((self.current_room or {}).get("game", "")).upper()
        if game != "UNO":
            return
        state = self.uno_state or {}
        pending_players = state.get("pending_uno_players", [])
        if pending_players:
            offender = pending_players[0]
            offender_id = offender.get("user_id")
            name = offender.get("name", "لاعب")
            reader.speak(name, interrupt=True)
            if offender_id is not None:
                self._send_uno_action("catch_uno", str(offender_id))
        else:
            reader.speak(tr("لا يوجد مخالف"), interrupt=True)

    def on_announce_card_counts(self):
        game = str((self.current_room or {}).get("game", "")).upper()
        if game == "SCOPA":
            state = self.scopa_state or {}
            if not state.get("active"):
                reader.speak(tr("المباراة لم تبدأ بعد."), interrupt=True)
                return
            hand = state.get("my_hand", [])
            reader.speak(tr(f"معك {len(hand)} كروت في يدك."), interrupt=True)
            return
        if game != "UNO":
            return
        state = self.uno_state or {}
        hand = state.get("hand", [])
        players = state.get("players", [])
        parts = [tr(f"أنت {len(hand)}")]
        my_id = (self.user or {}).get("id")
        for p in players:
            if p.get("user_id") == my_id:
                continue
            name = p.get("name", "لاعب")
            count = p.get("card_count", 0)
            parts.append(tr(f"{name} {count}"))
        sep = "، " if language() == "ar" else ", "
        reader.speak(sep.join(parts), interrupt=True)

    def on_announce_thief_results(self):
        state = self.thief_state or {}
        players = state.get("players", [])
        if not players:
            return
        parts = [tr(f"{p.get('name', 'لاعب')} {p.get('wins', 0)} جولات") for p in players]
        total = int(state.get("total_rounds", 0) or 0)
        sep = "، " if language() == "ar" else ", "
        text = sep.join(parts)
        if total:
            text += sep + tr(f"عدد الجولات {total}")
        reader.speak(text, interrupt=True)

    def _format_score_announcement(self, player_scores: list, target_score: int | None = None) -> str:
        sep = "، " if language() == "ar" else ", "
        if player_scores:
            parts = [tr(f"{name} {score}") for name, score in player_scores]
            if target_score is not None:
                parts.append(tr(f"عدد النقاط النهائي {target_score}"))
            return sep.join(parts)
        return tr(f"عدد النقاط النهائي {target_score}") if target_score is not None else tr("لا توجد نقاط بعد.")

    def on_announce_scores(self):
        if not self.current_room:
            return

        game = str(self.current_room.get("game", "")).upper()

        if game == "TENNIS":
            state = getattr(self, "tennis_state", {}) or {}
            sc = state.get("score", {})
            pts = sc.get("points", {})
            games = sc.get("games", {})
            sets = sc.get("sets", {})
            server_idx = sc.get("server_idx", 0)
            
            players = state.get("players", [])
            p0_name = players[0].get("name", "لاعب 1") if len(players) > 0 else "لاعب 1"
            p1_name = players[1].get("name", "لاعب 2") if len(players) > 1 else "لاعب 2"
            
            server_name = p0_name if server_idx == 0 else p1_name
            
            p0_pts = pts.get("0", pts.get(0, "0"))
            p1_pts = pts.get("1", pts.get(1, "0"))
            p0_games = games.get("0", games.get(0, 0))
            p1_games = games.get("1", games.get(1, 0))
            p0_sets = sets.get("0", sets.get(0, 0))
            p1_sets = sets.get("1", sets.get(1, 0))
            
            clauses = [
                tr("النقاط: {p0} لـ {n0} مقابل {p1} لـ {n1}.", p0=p0_pts, n0=p0_name, p1=p1_pts, n1=p1_name),
                tr("الأشواط: {g0} لـ {n0} و {g1} لـ {n1}.", g0=p0_games, n0=p0_name, g1=p1_games, n1=p1_name),
                tr("المجموعات: {s0} لـ {n0} و {s1} لـ {n1}.", s0=p0_sets, n0=p0_name, s1=p1_sets, n1=p1_name),
                tr("الإرسال مع: {name}.", name=server_name),
            ]
            reader.speak(" ".join(clauses), interrupt=True)
            return

        if game == "SNAKES_LADDERS":
            state = self.snakes_state or {}
            players = state.get("players") or []
            if not players:
                reader.speak(tr("المباراة لم تبدأ بعد."), interrupt=True)
                return
            parts = [(p.get("name", "لاعب"), p.get("position", 0)) for p in players]
            reader.speak(self._format_score_announcement(parts, 100), interrupt=True)
            return

        if game == "FARKLE":
            state = self.farkle_state or {}
            scores = state.get("scores") or self.current_room.get("scores") or {}
            names = state.get("player_names") or self.current_room.get("player_names") or {}
            parts = [
                (names.get(str(uid)) or names.get(int(uid) if str(uid).lstrip("-").isdigit() else uid) or "لاعب", int(score or 0))
                for uid, score in scores.items()
            ]
            target = state.get("target_score") or self.current_room.get("target_score")
            reader.speak(self._format_score_announcement(parts, target), interrupt=True)
            return

        if game in ("DOMINO", "AMERICAN_DOMINO"):
            state = self.domino_state or {}
            scores = state.get("scores") or self.current_room.get("scores") or {}
            players = state.get("players") or []
            target = state.get("target_score") or self.current_room.get("target_score") or (150 if game == "AMERICAN_DOMINO" else 100)
            if players:
                parts = [(p.get("name", "لاعب"), int(p.get("score", 0))) for p in players]
            else:
                names = self.current_room.get("player_names") or {}
                parts = [
                    (names.get(str(uid)) or names.get(int(uid) if str(uid).lstrip("-").isdigit() else uid) or "لاعب", int(score or 0))
                    for uid, score in scores.items()
                ]
            reader.speak(self._format_score_announcement(parts, target), interrupt=True)
            return

        if game == "NINETY_NINE":
            state = getattr(self, "uno_state", {}) or {}
            tokens = state.get("tokens") or {}
            players = state.get("players") or []
            if not tokens:
                reader.speak(tr("المباراة لم تبدأ بعد."), interrupt=True)
                return
            if players:
                parts = [
                    (p.get("name", "لاعب"), tokens.get(str(p.get("id")), tokens.get(int(p.get("id")) if str(p.get("id")).lstrip("-").isdigit() else p.get("id"), 0)))
                    for p in players
                ]
            else:
                names = self.current_room.get("player_names") or {}
                parts = [
                    (names.get(str(uid)) or names.get(int(uid) if str(uid).lstrip("-").isdigit() else uid) or "لاعب", t_count)
                    for uid, t_count in tokens.items()
                ]
            target = self.current_room.get("target_score")
            reader.speak(self._format_score_announcement(parts, target), interrupt=True)
            return

        if game == "THIEF_HUNT":
            self.on_announce_thief_results()
            return

        if game == "SCOPA":
            state = self.scopa_state or {}
            target = state.get("target_score") or (self.current_room or {}).get("target_score") or 11
            is_team = bool(state.get("is_team_game"))
            scores = state.get("scores") or (self.current_room or {}).get("scores") or {}
            players = state.get("players") or []
            if is_team:
                teams_map = state.get("teams") or {}
                team_members = {}
                if players:
                    for p in players:
                        if isinstance(p, dict):
                            uid = p.get("id") or p.get("user_id")
                            tid = teams_map.get(str(uid), teams_map.get(uid))
                            if tid is not None:
                                team_members.setdefault(str(tid), []).append(p.get("name", "لاعب"))
                else:
                    raw_names = (self.current_room or {}).get("player_names") or []
                    room_players = (self.current_room or {}).get("players") or []
                    for idx, uid in enumerate(room_players):
                        pname = raw_names[idx] if (isinstance(raw_names, list) and idx < len(raw_names)) else str(uid)
                        tid = teams_map.get(str(uid), teams_map.get(uid))
                        if tid is not None:
                            team_members.setdefault(str(tid), []).append(pname)
                parts = []
                for tid, sc in sorted(scores.items(), key=lambda x: str(x[0])):
                    members = team_members.get(str(tid), [])
                    label = " & ".join(members) if members else tr("فريق {0}", int(tid)+1)
                    parts.append((label, sc))
            elif players:
                parts = [(p.get("name", "لاعب"), int(p.get("score", 0))) for p in players if isinstance(p, dict)]
            else:
                raw_names = (self.current_room or {}).get("player_names")
                names_map = {}
                if isinstance(raw_names, dict):
                    names_map = raw_names
                elif isinstance(raw_names, list):
                    room_players = (self.current_room or {}).get("players") or []
                    for idx, p_name in enumerate(raw_names):
                        if idx < len(room_players):
                            names_map[str(room_players[idx])] = str(p_name)
                parts = [(names_map.get(str(uid), "لاعب"), sc) for uid, sc in scores.items()]

            reader.speak(self._format_score_announcement(parts, target), interrupt=True)
            return

        scores = self.current_room.get("scores", {})
        players = (self.uno_state or {}).get("players", [])
        parts = [(p.get("name", "لاعب"), scores.get(str(p.get("user_id")), 0)) for p in players]
        target = self.current_room.get("target_score")
        reader.speak(self._format_score_announcement(parts, target), interrupt=True)

    def on_f1_help(self):
        if not self.is_in_room():
            self._show_rules_help("shortcuts", game="GENERAL")
            return
        self._show_rules_help("shortcuts")

    def on_ctrl_f1_help(self):
        if not self.is_in_room():
            from client.localization import tr
            from client.views.list_menu import choose
            games = [
                (tr("أونو"), "UNO"),
                (tr("إسكوبا"), "SCOPA"),
                (tr("تسعة وتسعون"), "NINETY_NINE"),
                (tr("فاركل"), "FARKLE"),
                (tr("السلم والثعبان"), "SNAKES_LADDERS"),
                (tr("الدومينو الكلاسيك"), "DOMINO"),
                (tr("الدومينو الأمريكاني"), "AMERICAN_DOMINO"),
                (tr("مطاردة اللص"), "THIEF_HUNT"),
                (tr("تنس"), "TENNIS"),
            ]
            chosen = choose(self, tr("قائمة الألعاب"), games)
            if chosen:
                self._show_rules_help("rules", game=chosen)
            return
        self._show_rules_help("rules")

    def _show_rules_help(self, mode="rules", game=None):
        """Show accessible in-game Notepad-style text help viewer."""
        from pathlib import Path
        from client.views.text_help_viewer import TextHelpViewerDialog

        from client.localization import language, tr

        if not game:
            game = str((self.current_room or {}).get("game", "")).upper()
        if game == "THIEF_HUNT":
            help_name = "thief_hunt_shortcuts_accessible.txt" if mode == "shortcuts" else "thief_hunt_rules_accessible.txt"
            title = "اختصارات مطاردة اللص" if mode == "shortcuts" else "شرح لعبة مطاردة اللص"
        elif game == "UNO":
            help_name = "uno_shortcuts_accessible.txt" if mode == "shortcuts" else "uno_rules_accessible.txt"
            title = "اختصارات أونو" if mode == "shortcuts" else "شرح لعبة أونو"
        elif game == "FARKLE":
            help_name = "farkle_shortcuts_accessible.txt" if mode == "shortcuts" else "farkle_rules_accessible.txt"
            title = "اختصارات فاركل" if mode == "shortcuts" else "شرح لعبة فاركل"
        elif game == "DOMINO":
            help_name = "domino_shortcuts_accessible.txt" if mode == "shortcuts" else "domino_rules_accessible.txt"
            title = "اختصارات الدومينو الكلاسيك" if mode == "shortcuts" else "شرح لعبة الدومينو الكلاسيك"
        elif game == "AMERICAN_DOMINO":
            help_name = "american_domino_shortcuts_accessible.txt" if mode == "shortcuts" else "american_domino_rules_accessible.txt"
            title = "اختصارات الدومينو الأمريكاني" if mode == "shortcuts" else "شرح لعبة الدومينو الأمريكاني"
        elif game == "SNAKES_LADDERS":
            help_name = "snakes_and_ladders_shortcuts_accessible.txt" if mode == "shortcuts" else "snakes_and_ladders_rules_accessible.txt"
            title = "اختصارات السلم والثعبان" if mode == "shortcuts" else "شرح لعبة السلم والثعبان"
        elif game == "SCOPA":
            help_name = "scopa_shortcuts_accessible.txt" if mode == "shortcuts" else "scopa_rules_accessible.txt"
            title = "اختصارات السكوبا" if mode == "shortcuts" else "شرح لعبة السكوبا"
        elif game == "TENNIS":
            help_name = "tennis_shortcuts_accessible.txt" if mode == "shortcuts" else "tennis_rules_accessible.txt"
            title = "اختصارات التنس" if mode == "shortcuts" else "شرح التنس"
        elif game in ("NINETY_NINE", "NINETYNINE"):
            help_name = "ninety_nine_shortcuts_accessible.txt" if mode == "shortcuts" else "ninety_nine_rules_accessible.txt"
            title = "اختصارات تسعة وتسعون" if mode == "shortcuts" else "شرح لعبة تسعة وتسعون"
        else:
            help_name = "game_shortcuts_accessible.txt" if mode == "shortcuts" else "game_rules_accessible.txt"
            title = "الاختصارات العامة للعبة" if mode == "shortcuts" else "شرح اللعبة"

        cur_lang = language()
        help_name_localized = help_name.replace(".txt", f"_{cur_lang}.txt") if cur_lang != "ar" else help_name
        help_name_en = help_name.replace(".txt", "_en.txt")

        def resolve_help_path(filename: str):
            candidates = [Path(__file__).resolve().parent / "help" / filename]
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                base = Path(meipass)
                candidates.extend([base / "client" / "help" / filename, base / "help" / filename])
            return next((candidate for candidate in candidates if candidate.is_file()), None)

        def read_help(path):
            try:
                return path.read_text(encoding="utf-8-sig") if path else ""
            except Exception:
                return ""

        ar_path = resolve_help_path(help_name)
        en_path = resolve_help_path(help_name_en)
        cur_path = resolve_help_path(help_name_localized)

        sources = {
            "ar": read_help(ar_path),
            "en": read_help(en_path),
        }
        if cur_lang not in sources and cur_path:
            sources[cur_lang] = read_help(cur_path)

        active_source = sources.get(cur_lang, "") or sources.get("en", "") or sources.get("ar", "")
        if not active_source:
            reader.speak(tr("تعذر تحميل الشرح."), interrupt=True)
            return

        dialog = TextHelpViewerDialog(self, title, active_source, text_sources=sources)
        dialog.exec()

    def on_f2_wallet(self):
        def done(res):
            bal = res.get("coins", 0)
            reader.speak(tr(f"رصيدك {bal}"), interrupt=True)
        self._run_async(self.api.wallet, done)

    def on_f3_ping(self):
        # F3 is strictly a measurement of the already-connected authenticated
        # WebSocket. Never fall back to /api/health because that would silently
        # change the meaning of the result and create an extra HTTP round trip.
        if not self.api.token:
            reader.speak(tr("لا يوجد اتصال بحسابك."), interrupt=True)
            return
        result = self.ws.ping()
        if result == "offline":
            reader.speak(tr("لا يوجد اتصال بالطاولة أو بالخادم."), interrupt=True)
        elif result == "busy":
            reader.speak(tr("جاري اختبار الاتصال بالفعل."), interrupt=True)

    def on_toggle_number_order(self):
        if not self.is_in_room():
            return
        game = str((self.current_room or {}).get("game", "")).upper()
        if game != "UNO":
            return
        if self.table_view.is_playing:
            self.table_view.toggle_number_order()

    def on_leave_room_shortcut(self):
        self.room_controller.on_leave_room_shortcut()

    def on_apps_key(self):
        if self.is_in_room():
            self._show_room_context_menu()
        elif self.stack.currentIndex() == 1:
            self._show_home_context_menu()
        elif self.stack.currentIndex() == 2:
            self._show_rooms_context_menu()

    def _show_home_context_menu(self):
        menu = QMenu(self)
        menu.setAccessibleName(tr("قائمة خيارات القائمة الرئيسية"))
        wallet = menu.addAction(tr("الرصيد"))
        menu.addSeparator()
        logout = menu.addAction(tr("تسجيل الخروج"))
        wallet.triggered.connect(self.on_f2_wallet)
        logout.triggered.connect(lambda: self._handle_home_selection("logout"))
        
        enabled = [a for a in menu.actions() if a.isEnabled() and not a.isSeparator()]
        if enabled:
            menu.setActiveAction(enabled[0])
            
        menu.exec(self.mapToGlobal(self.rect().center()))

    def _show_rooms_context_menu(self):
        menu = QMenu(self)
        menu.setAccessibleName(tr("خيارات الطاولات"))
        create = menu.addAction(tr("إنشاء"))
        join = menu.addAction(tr("انضمام"))
        menu.addSeparator()
        back = menu.addAction(tr("العودة للقائمة الرئيسية"))
        create.triggered.connect(lambda: self._handle_rooms_menu_selection("create"))
        join.triggered.connect(lambda: self._handle_rooms_menu_selection("join"))
        back.triggered.connect(self._show_home)
        
        enabled = [a for a in menu.actions() if a.isEnabled() and not a.isSeparator()]
        if enabled:
            menu.setActiveAction(enabled[0])
            
        menu.exec(self.mapToGlobal(self.rect().center()))

    def _show_room_context_menu(self):
        menu = QMenu(self)
        menu.setAccessibleName(tr("قائمة خيارات الطاولة"))
        is_host = str(self.current_room.get("host_id")) == str((self.user or {}).get("id"))
        is_co_host = str(self.current_room.get("co_host_id")) == str((self.user or {}).get("id"))
        status = self.current_room.get("status")
        if status == "playing":
            start_act = menu.addAction(tr("إيقاف اللعبة"))
            start_act.setEnabled(is_host or is_co_host)
            start_act.triggered.connect(self._menu_stop_game)
        else:
            start_act = menu.addAction(tr("بدء اللعبة"))
            start_act.setEnabled((is_host or is_co_host) and status == "waiting")
            start_act.triggered.connect(self._menu_start_game)
        players_act = menu.addAction(tr("قائمة اللاعبين"))
        spectator_act = menu.addAction(tr("وضع المتفرج"))
        
        # Save table option
        save_act = menu.addAction(tr("حفظ الطاولة") + " (Ctrl+S)")
        can_save = (status == "playing" and len(self.current_room.get("players", [])) > 1)
        save_act.setEnabled(can_save)
        save_act.triggered.connect(self.on_save_table_shortcut)

        # Privacy toggle in a balanced, logical middle position
        is_priv = bool((self.current_room.get("rules") or {}).get("private", False))
        priv_title = tr("اجعل الطاولة عامة") if is_priv else tr("اجعل الطاولة خاصة")
        privacy_act = menu.addAction(priv_title)
        privacy_act.setEnabled(is_host)
        privacy_act.triggered.connect(self.on_toggle_room_privacy)

        menu.addSeparator()
        bot_act = menu.addAction(tr("إضافة بوت"))
        bot_act.setEnabled(is_host and status == "waiting")
        remove_bot_act = menu.addAction(tr("إزالة بوت"))
        remove_bot_act.setEnabled(is_host and status == "waiting")
        menu.addSeparator()
        leave_act = menu.addAction(tr("مغادرة الطاولة"))

        players_act.triggered.connect(self.on_open_table_players)
        spectator_act.triggered.connect(self.on_toggle_spectator_shortcut)
        bot_act.triggered.connect(self.on_add_bot)
        remove_bot_act.triggered.connect(self.on_remove_bot)
        leave_act.triggered.connect(self.on_leave_room_shortcut)
        self._active_context_menu = menu
        menu.aboutToHide.connect(lambda: setattr(self, "_active_context_menu", None))
        
        # Explicitly set active action to the first ENABLED action so NVDA announces it
        enabled = [a for a in menu.actions() if a.isEnabled() and not a.isSeparator()]
        if enabled:
            menu.setActiveAction(enabled[0])
            
        menu.exec(self.mapToGlobal(self.rect().center()))
        self._active_context_menu = None

    def _game_title(self, game=None):
        titles = {
            "UNO": "أونو",
            "FARKLE": "فاركل",
            "DOMINO": "دومينو كلاسيك",
            "AMERICAN_DOMINO": "دومينو أمريكاني",
            "THIEF_HUNT": "مطاردة اللص",
            "SNAKES_LADDERS": "السلم والثعبان",
            "SCOPA": "إسكوبا",
            "TENNIS": "التنس",
        }
        return titles.get(game or (self.current_room or {}).get("game"), "اللعبة")

    def _menu_stop_game(self):
        if not self.current_room:
            return
        status = str(self.current_room.get("status", "")).lower()
        is_playing = (status == "playing") or getattr(self.table_view, "is_playing", False)
        if not is_playing:
            reader.speak(tr("اللعبة متوقفة بالفعل."), interrupt=True)
            return

        is_host = bool(self.current_room.get("is_host"))
        if not is_host:
            reader.speak(tr("إيقاف اللعبة متاح لمضيف الطاولة فقط."), interrupt=True)
            return

        if QApplication.activePopupWidget() is not None:
            try:
                QApplication.activePopupWidget().close()
            except Exception:
                pass
            self._active_context_menu = None

        choice = ListMenu(
            self, "إيقاف اللعبة",
            [("نعم، إيقاف اللعبة", "stop"), ("لا، متابعة اللعبة", "continue")],
        ).show_menu(speak_text="إيقاف اللعبة")
        if choice != "stop":
            if self.table_view.is_playing and self.table_view.get_active_card_list() is not None:
                self.table_view.get_active_card_list().setFocus()
            else:
                self.table_view.main_table_widget.setFocus()
            return
        rid = self.current_room.get("id")
        reader.speak(tr("جاري إيقاف اللعبة..."), interrupt=True)

        def done(room):
            self.current_room = room
            self._reset_game_runtime_state()
            self.table_view.set_game_type(room.get("game", ""))
            self.table_view.set_playing_mode(False)
            self.table_view.clear_hand_for_round_transition()
            self.table_view.update_domino_state({"active": False})
            self.table_view.activity_panel.clear()
            self.table_view.main_table_widget.setFocus()
            self._poll_table_state()
            reader.speak(tr("تم إيقاف اللعبة. عادت الطاولة إلى الانتظار."), interrupt=True)

        def fail(msg):
            reader.speak(tr(f"تعذر إيقاف اللعبة: {msg}"), interrupt=True)

        self._run_async(lambda: self.api.stop_game(rid), done, fail)

    def _choose_start_mode(self, game_name, default_summary=""):
        result = ListMenu(
            self, "هل تريد اللعب بالاعدادات الافتراضية؟",
            [
                ("نعم", "default"),
                ("لا", "custom"),
            ],
        ).show_menu(speak_text="هل تريد اللعب بالاعدادات الافتراضية؟")
        return result

    def _open_settings_list(self, title, fields):
        menu = SettingsListMenu(self, title, fields)
        result, values = menu.show_menu(speak_text=title)
        if result != "start":
            return None
        return values

    def _menu_start_game(self):
        if getattr(self, "_start_dialog_open", False):
            return
        if not self.current_room or self.current_room.get("status") != "waiting":
            return
        is_host = str(self.current_room.get("host_id")) == str((self.user or {}).get("id"))
        is_co_host = str(self.current_room.get("co_host_id")) == str((self.user or {}).get("id"))
        if not (is_host or is_co_host):
            reader.speak(tr("بدء اللعبة متاح للقائد أو نائب القائد فقط."), interrupt=True)
            return
        if len((self.current_room or {}).get("players", [])) < 2:
            reader.speak(tr("يجب وجود لاعبين اثنين على الأقل لبدء اللعبة."), interrupt=True)
            return

        game_type = str(self.current_room.get("game", "")).upper()
        from client.table_framework.settings_registry import GAME_SETTINGS_REGISTRY
        game_def = GAME_SETTINGS_REGISTRY.get(game_type)
        
        if not game_def:
            # Fallback if a game isn't registered yet (e.g. legacy/unfinished games)
            return

        from client.game_preferences import load as load_game_preferences
        saved_target, saved_rules = load_game_preferences(game_type, game_def.default_target_score, game_def.default_rules)
        self._start_dialog_open = True
        try:
            mode = self._choose_start_mode(game_def.title)
            if mode in (None, "cancel"):
                return

            state_api = getattr(self.api, game_def.state_getter)
            state_handler = getattr(self, game_def.state_applier)

            if mode == "default":
                target, rules = saved_target, dict(saved_rules)
            else:
                # Custom Mode: Build fields automatically from registry specification
                fields = [f.to_dict({"target_score": saved_target, "rules": saved_rules}) for f in game_def.custom_fields]
                fields += [{"key": "start", "label": "بدء اللعبة", "kind": "action"},
                           {"key": "cancel", "label": "إلغاء", "kind": "action"}]

                dialog_title = tr("تخصيص {title}", title=tr(game_def.title))
                values = self._open_settings_list(dialog_title, fields)
                if values is None:
                    return

                target, rules = game_def.extract_target_and_rules(values)

            # Scopa team selection: If teams are enabled and 4 or 6 players, host chooses teams
            if game_type == "SCOPA" and bool(rules.get("teams_enabled")):
                players_list = list(self.current_room.get("players") or [])
                raw_names = self.current_room.get("player_names") or []
                if len(players_list) in (4, 6):
                    formatted_players = []
                    for idx, uid in enumerate(players_list):
                        pname = raw_names[idx] if (isinstance(raw_names, list) and idx < len(raw_names)) else (raw_names.get(str(uid), f"لاعب {uid}") if isinstance(raw_names, dict) else f"لاعب {uid}")
                        formatted_players.append((int(uid), str(pname)))
                    from client.views.table_players_dialog import TableTeamSelectionDialog
                    team_dlg = TableTeamSelectionDialog(formatted_players, int((self.user or {}).get("id") or 0), parent=self)
                    if team_dlg.exec() != QDialog.Accepted:
                        return
                    rules["custom_teams"] = team_dlg.get_custom_teams()

            if game_type == "UNO":
                self._start_game_with_settings(target, rules)
            else:
                self._start_game_and_load_state(target, rules, state_api, state_handler)
        finally:
            self._start_dialog_open = False

    def _start_game_and_load_state(self, target, rules, state_api, state_handler):
        rid = self.current_room.get("id") if self.current_room else None
        if not rid:
            return
        reader.speak(tr("جاري بدء اللعبة..."), interrupt=True)
        def done(room):
            prev_room_id = self.current_room.get("id") if self.current_room else None
            self.current_room = room
            if prev_room_id != room.get("id"):
                self._enter_table(room)
            else:
                self.table_view.set_playing_mode(bool(room.get("status") == "playing"))
            def on_state(state):
                state_handler(state)
                QTimer.singleShot(50, self.table_view.focus_initial)
            self._run_async(
                lambda: state_api(room.get("id")),
                on_state,
                lambda msg: reader.speak(tr(f"تعذر تحميل حالة اللعبة: {msg}"), interrupt=True),
            )
        def fail(msg):
            reader.speak(tr(f"لم تبدأ اللعبة: {msg}"), interrupt=True)
        self._run_async(lambda: self.api.start_game(rid, target, rules), done, fail)

    def _start_game_with_settings(self, target: int, rules: dict):
        rid = self.current_room.get("id") if self.current_room else None
        if not rid:
            return
        reader.speak(tr("جاري بدء اللعبة..."), interrupt=True)

        def done(room):
            if not isinstance(room, dict):
                reader.speak(tr("تعذر بدء اللعبة."), interrupt=True)
                return
            prev_room_id = self.current_room.get("id") if self.current_room else None
            self.current_room = room
            if prev_room_id != room.get("id"):
                self._enter_table(room)
            else:
                self.table_view.set_playing_mode(bool(room.get("status") == "playing"))
            rid2 = room.get("id", rid)

            def state_done(state):
                self._apply_uno_state(state)
                if not bool((state or {}).get("active")):
                    reader.speak(tr("تعذر تحميل حالة اللعبة."), interrupt=True)
                    return
                QTimer.singleShot(50, self.table_view.focus_initial)

            def state_fail(message):
                reader.speak(tr(f"بدأت اللعبة، لكن تعذر تحميل الكروت: {message}"), interrupt=True)

            self._run_async(lambda: self.api.uno_state(rid2), state_done, state_fail)

        def fail(message):
            reader.speak(tr(f"لم تبدأ اللعبة: {message}"), interrupt=True)

        self._run_async(lambda: self.api.start_game(rid, target, rules), done, fail)

    def _menu_add_bot(self):
        if not self.current_room:
            return
        rid = self.current_room.get("id")
        def done(room):
            self.current_room = room
            names = room.get("player_names", [])
            name = names[-1] if names else "لاعب"
            reader.speak(tr(f"{name} انضم"), interrupt=False)
        self._run_async(lambda: self.api.add_bot(rid), done)

    def _menu_leave_room(self):
        self.room_controller.leave_room_menu()

    def _handle_send_chat(self, text):
        if not self.current_room:
            return
        sender = (self.user or {}).get("display_name", "أنت")
        if not self.ws.send_json({"text": text}):
            self._show_error(tr("الدردشة غير متصلة حاليًا."))

    def changeEvent(self, event):
        if event.type() == QEvent.ActivationChange:
            if hasattr(self, "key_filter") and hasattr(self.key_filter, "_down"):
                self.key_filter._down.clear()
            if not self.isActiveWindow():
                # Window is losing focus — snapshot the current focused widget NOW
                self._pre_deactivate_focus = QApplication.focusWidget()
            else:
                # Window is regaining focus — decide where to send focus.
                saved = getattr(self, "_pre_deactivate_focus", None)
                self._pre_deactivate_focus = None

                # 1. Preserve focus on active modal dialogs / popups
                active_modal = QApplication.activeModalWidget()
                active_popup = QApplication.activePopupWidget()
                if active_modal is not None:
                    if saved is not None and hasattr(saved, "isVisible") and saved.isVisible() and saved.isEnabled():
                        QTimer.singleShot(0, saved.setFocus)
                    else:
                        QTimer.singleShot(0, active_modal.setFocus)
                    super().changeEvent(event)
                    return
                if active_popup is not None:
                    if saved is not None and hasattr(saved, "isVisible") and saved.isVisible() and saved.isEnabled():
                        QTimer.singleShot(0, saved.setFocus)
                    else:
                        QTimer.singleShot(0, active_popup.setFocus)
                    super().changeEvent(event)
                    return

                if self.is_in_room():
                    # If user was explicitly in Chat or Activity Log before switching away, restore it
                    if saved is not None and hasattr(saved, "isVisible") and saved.isVisible() and saved in (
                        self.table_view.chat_input,
                        self.table_view.activity_log,
                        getattr(self.table_view.activity_panel, "activity_log", None),
                    ):
                        QTimer.singleShot(0, saved.setFocus)
                        super().changeEvent(event)
                        return

                    # If saved was a valid gameplay control, restore focus to it
                    if saved is not None and hasattr(saved, "isVisible") and saved.isVisible() and saved.isEnabled():
                        QTimer.singleShot(0, saved.setFocus)
                        super().changeEvent(event)
                        return

                    # Fallback to standard initial focus for current game
                    QTimer.singleShot(0, self.table_view.focus_initial)
                    super().changeEvent(event)
                    return

                # If not in room, restore saved widget or active view list
                if saved is not None and hasattr(saved, "isVisible") and saved.isVisible() and saved.isEnabled():
                    QTimer.singleShot(0, saved.setFocus)
                else:
                    curr_idx = self.stack.currentIndex()
                    if curr_idx == 1 and hasattr(self.home_view, "menu_list"):
                        QTimer.singleShot(0, self.home_view.menu_list.setFocus)
                    elif curr_idx == 2 and hasattr(self.rooms_menu_view, "menu_list"):
                        QTimer.singleShot(0, self.rooms_menu_view.menu_list.setFocus)
                    elif curr_idx == 3 and hasattr(self.join_rooms_view, "rooms_list"):
                        QTimer.singleShot(0, self.join_rooms_view.rooms_list.setFocus)
                    elif curr_idx == 5 and hasattr(self.saved_tables_view, "tables_list"):
                        QTimer.singleShot(0, self.saved_tables_view.tables_list.setFocus)
        super().changeEvent(event)

    def contextMenuEvent(self, event):
        self.on_apps_key()
        event.accept()

    def closeEvent(self, event):
        if not getattr(self, "_force_close", False):
            event.ignore()
            self.on_f4_exit()
            return

        # Activity history is session-scoped by product design: clear it on a
        # normal application close so the next launch starts clean. Best-effort
        # with a short timeout so shutdown can never hang on the network.
        try:
            self.home_view.activity_panel.clear()
            self.rooms_menu_view.activity_panel.clear()
            self.join_rooms_view.activity_panel.clear()
            self.table_view.activity_panel.clear()
        except Exception:
            pass
        token = self.api.token
        if token:
            try:
                self.api.clear_activity(timeout=3)
            except Exception:
                pass
        try:
            self.voice.shutdown()
            self.ws.stop()
            self.api.close()
            self.online_timer.stop()
            self.poll_timer.stop()
        finally:
            super().closeEvent(event)
            QApplication.instance().quit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.on_escape_navigation()
            return
        super().keyPressEvent(event)


    def on_save_table_shortcut(self):
        self.room_controller.save_table_shortcut()

    def _refresh_saved_tables(self):
        self.room_controller.refresh_saved_tables()

    def _handle_delete_saved_table(self, saved_id: int):
        self.room_controller.delete_saved_table(saved_id)

    def _handle_restore_saved_table(self, saved_id: int):
        self.room_controller.restore_saved_table(saved_id)
