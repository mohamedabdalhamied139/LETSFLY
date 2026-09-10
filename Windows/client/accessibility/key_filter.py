"""Windows keyboard filter for accessible game shortcuts."""
import sys
import ctypes
import logging
from PySide6.QtCore import QAbstractNativeEventFilter, QTimer
from PySide6.QtWidgets import QApplication, QLineEdit, QTextEdit, QPlainTextEdit

logger = logging.getLogger("tableverse.keys")

# Windows message constants
WM_ACTIVATE = 0x0006
WM_KILLFOCUS = 0x0008
WM_ACTIVATEAPP = 0x001C
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105


class HardwareKeyFilter(QAbstractNativeEventFilter):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self._down = set()

    def _speak(self, text):
        try:
            from .reader import reader
            from client.localization import tr
            reader.speak(tr(text), interrupt=False)
        except Exception:
            pass

    def _call(self, method, *args):
        fn = getattr(self.window, method, None)
        if not callable(fn):
            return False
        # Run UI action after the native event is returned to Qt.
        QTimer.singleShot(0, lambda: fn(*args))
        return True

    def _typing(self):
        w = QApplication.focusWidget()
        return isinstance(w, (QLineEdit, QTextEdit, QPlainTextEdit))

    def nativeEventFilter(self, event_type, message):
        if sys.platform != "win32":
            return False, 0
        if event_type not in ("windows_generic_MSG", "windows_dispatcher_MSG"):
            return False, 0

        try:
            from ctypes import wintypes
            msg = wintypes.MSG.from_address(int(message.__int__()))
            # Reset tracked keys on window activation changes or Alt/Tab/Win presses
            if msg.message in (WM_ACTIVATE, WM_KILLFOCUS, WM_ACTIVATEAPP):
                self._down.clear()
                return False, 0

            vk = int(msg.wParam)

            # Never intercept Alt, Tab, or Windows keys; clear stuck keys on Alt/Tab
            if vk in (0x12, 0x09, 0x5B, 0x5C):
                self._down.clear()
                return False, 0

            if msg.message in (WM_KEYUP, WM_SYSKEYUP):
                self._down.discard(vk)
                return (True, 0) if vk == 0x5D else (False, 0)

            if msg.message not in (WM_KEYDOWN, WM_SYSKEYDOWN):
                return False, 0

            if not self.window.isActiveWindow():
                self._down.clear()
                return False, 0

            # If a modal dialog (such as ListMenu, SettingsListMenu, or QDialog) is active,
            # let Qt handle all keys normally without intercepting shortcuts.
            if QApplication.activeModalWidget() is not None:
                return False, 0

            # Ignore auto-repeat only for character shortcut keys ('A'..'Z')
            if 0x41 <= vk <= 0x5A:
                if vk in self._down:
                    return True, 0
                self._down.add(vk)
            else:
                self._down.discard(vk)

            # Apps key or Shift+F10 is always a context-menu command, never text.
            user32 = ctypes.windll.user32
            shift = bool(user32.GetKeyState(0x10) & 0x8000)
            if vk == 0x5D or (vk == 0x79 and shift):
                self._call("on_apps_key")
                self._speak("قائمة السياق")
                return True, 0

            # F1 / Ctrl+F1 are shared help commands and must work even when
            # the focus is inside a text input (including a game's answer box).
            if vk == 0x70:
                if not self.window.is_in_room():
                    return False, 0
                user32 = ctypes.windll.user32
                ctrl = bool(user32.GetKeyState(0x11) & 0x8000)
                method = "on_ctrl_f1_help" if ctrl else "on_f1_help"
                if self._call(method):
                    return True, 0

            # Shift+R / Shift+ق: Room active rules announcement (help command, available even while typing)
            if vk == 0x52 and shift:
                if self.window.is_in_room():
                    self._call("on_announce_rules")
                    return True, 0

            # Ctrl+H: Room privacy toggle (available anywhere in table, even while typing)
            if vk == 0x48:
                user32 = ctypes.windll.user32
                ctrl = bool(user32.GetKeyState(0x11) & 0x8000)
                alt = bool(user32.GetKeyState(0x12) & 0x8000)
                if ctrl and not shift and not alt:
                    if self.window.is_in_room():
                        self._call("on_toggle_room_privacy")
                        return True, 0

            # F5 is a real network reconnect command and remains available even
            # while an editable control has focus.
            if vk == 0x74:  # F5
                if self._call("on_manual_reconnect"):
                    return True, 0

            # Alt+Shift+V is a global table command. M is deliberately handled
            # only after the editable-control guard so typing an "m" in chat or
            # another text field never changes microphone state.
            alt = bool(user32.GetKeyState(0x12) & 0x8000)
            if self.window.is_in_room() and vk == 0x56 and shift and alt:
                self._call("on_toggle_voice_chat")
                return True, 0

            if self._typing():
                return False, 0

            if QApplication.activeModalWidget() is not None or QApplication.activePopupWidget() is not None:
                return False, 0

            if self.window.is_in_room() and vk == 0x4D and not shift and not alt:
                voice = getattr(self.window, "voice", None)
                if voice is not None and getattr(voice, "in_voice_chat", False):
                    self._call("on_toggle_voice_mute")
                    return True, 0

            # Alt+F4: Show confirmation dialog instead of quitting abruptly
            if alt and vk == 0x73:
                self._call("on_f4_exit")
                return True, 0

            function_actions = {
                0x71: ("on_f2_wallet", "الرصيد"),
                0x72: ("on_f3_ping", "اختبار الاتصال"),
            }
            if vk == 0x73 and not alt:
                # F4 alone: Dedicated spectator shortcut across all screens in the game
                self._call("on_toggle_spectator_shortcut")
                return True, 0

            if vk in function_actions:
                method, spoken = function_actions[vk]
                if self._call(method):
                    if spoken:
                        self._speak(spoken)
                    return True, 0

            # Final gameplay shortcuts (active when in room and not typing).
            if self.window.is_in_room():
                user32 = ctypes.windll.user32
                shift = bool(user32.GetKeyState(0x10) & 0x8000)
                current_room = getattr(self.window, "current_room", None) or {}
                game = str(current_room.get("game") or "UNO").upper()

                # --- 1. Common Table / Lifecycle Shortcuts (All Games) ---

                # Q = leave room with confirmation.
                if vk == 0x51:  # 'Q'
                    self._call("on_leave_room_shortcut")
                    return True, 0

                # Shift+X = stop the current game (host confirmation).
                if vk == 0x58 and shift:  # Shift+X
                    self._call("_menu_stop_game")
                    return True, 0

                # P = announce players in the room; Shift+P = open table players dialog.
                if vk == 0x50:  # 'P'
                    if shift:
                        self._call("on_open_table_players")
                    else:
                        self._call("on_announce_players")
                    return True, 0

                # S = announce scores & target.
                if vk == 0x53 and not shift:  # 'S'
                    self._call("on_announce_scores")
                    return True, 0

                # T = announce current turn; Shift+T = table and round time.
                if vk == 0x54:
                    if shift:
                        self._call("on_announce_table_time")
                    else:
                        self._call("on_announce_turn")
                    return True, 0

                # B / Shift+B = Bot management
                if vk == 0x42:  # 'B'
                    if shift:
                        self._call("on_remove_bot")
                    elif game == "UNO":
                        if getattr(self.window, "uno_state", None) and self.window.uno_state.get("buzzer_pending"):
                            self._call("on_buzzer_or_bot")
                        else:
                            self._call("on_add_bot")
                    else:
                        self._call("on_add_bot")
                    return True, 0

                # --- 2. UNO Game-Specific Shortcuts ---
                if game == "UNO":
                    if vk == 0x48 and shift:  # Shift+H = toggle color/number order
                        self._call("on_toggle_number_order")
                        return True, 0
                    if vk == 0x58 and not shift:  # 'X' = challenge Wild Draw Four
                        self._call("on_challenge_bluff")
                        return True, 0

                    if vk == 0x44 and not shift:  # 'D' is disabled in UNO (Space is used)
                        return True, 0

                    uno_actions = {
                        0x20: "on_draw_card",            # 'Space' = draw card
                        0x52: "on_announce_top",         # 'R' = top card & chosen color
                        0x55: "on_uno_shortcut",         # 'U' = call UNO
                        0x43: "on_announce_no_uno",      # 'C' = announce UNO offender
                        0x56: "on_announce_card_counts", # 'V' = player card counts
                    }
                    if not shift and vk in uno_actions:
                        self._call(uno_actions[vk])
                        return True, 0

                elif game == "NINETY_NINE":
                    nn_actions = {
                        0x52: "on_announce_top",         # 'R' = current pile value
                        0x43: "on_c_shortcut",           # 'C' = tokens count
                        0x56: "on_announce_card_counts", # 'V' = player tokens list
                    }
                    if not shift and vk in nn_actions:
                        self._call(nn_actions[vk])
                        return True, 0

                # --- 3. Farkle Game-Specific Shortcuts ---
                elif game == "FARKLE":
                    farkle_actions = {
                        0x43: "on_c_shortcut",     # 'C' = turn collected points (pure number)
                        0x44: "on_draw_shortcut",  # 'D' = announce/repeat last roll
                        0x52: "on_draw_shortcut",  # 'R' = announce/repeat last roll
                    }
                    if not shift and vk in farkle_actions:
                        self._call(farkle_actions[vk])
                        return True, 0

                # --- 4. Domino Game-Specific Shortcuts ---
                elif game in ("DOMINO", "AMERICAN_DOMINO"):
                    domino_actions = {
                        0x52: "on_domino_announce_ends",        # 'R' = announce table ends (e.g. 0/1)
                        0x44: "on_draw_shortcut",                # 'D' = draw tile from boneyard
                        0x20: "on_draw_shortcut",                # 'Space' = draw tile from boneyard
                        0x43: "on_c_shortcut",                   # 'C' = boneyard remaining count
                        0x56: "on_announce_domino_board_tiles",  # 'V' = display played tiles list dialog
                    }
                    if not shift and vk in domino_actions:
                        self._call(domino_actions[vk])
                        return True, 0

                # --- 5. Thief Hunt Game-Specific Shortcuts ---
                elif game == "THIEF_HUNT":
                    pass

                # --- 6. Snakes & Ladders Game-Specific Shortcuts ---
                elif game == "SNAKES_LADDERS":
                    snakes_actions = {
                        0x44: "on_draw_shortcut",          # 'D' = repeat last roll
                        0x52: "on_snakes_radar_shortcut",  # 'R' = table status (radar & nearest ladder/snake)
                        0x56: "on_snakes_positions",       # 'V' = player board positions
                    }
                    if not shift and vk in snakes_actions:
                        self._call(snakes_actions[vk])
                        return True, 0

                # --- 7. Scopa Game-Specific Shortcuts ---
                elif game == "SCOPA":
                    scopa_actions = {
                        0x52: "on_announce_top",         # 'R' = announce table cards
                        0x43: "on_c_shortcut",           # 'C' = captured cards & deck count
                        0x48: "on_announce_card_counts", # 'H' = hand count
                        0x56: "on_announce_card_counts", # 'V' = hand count
                    }
                    if not shift and vk in scopa_actions:
                        self._call(scopa_actions[vk])
                        return True, 0



            # Enter is context-sensitive. Farkle/Domino/Snakes/Scopa owns Enter only while its
            # gameplay area has focus; otherwise native Qt controls retain
            # normal Enter behavior (buttons, edits, dialogs, etc.).
            if vk == 0x0D:  # Enter / Numpad Enter (VK_RETURN)
                focus = QApplication.focusWidget()
                table_view = getattr(self.window, "table_view", None)
                current_room = getattr(self.window, "current_room", None) or {}
                cur_game = str(current_room.get("game", "")).upper()
                if cur_game == "FARKLE":
                    farkle_list = getattr(table_view, "farkle_dice_list", None) if table_view else None
                    if focus is not None and focus is farkle_list:
                        item = farkle_list.currentItem()
                        if item is not None and table_view:
                            table_view._on_farkle_item_activated(item)
                            return True, 0
                elif cur_game == "SNAKES_LADDERS":
                    snakes_list = getattr(table_view, "snakes_info_list", None) if table_view else None
                    if focus is not None and (focus is snakes_list or (hasattr(snakes_list, "viewport") and focus is snakes_list.viewport())):
                        item = snakes_list.currentItem()
                        if item is not None and table_view:
                            table_view._on_snakes_item_activated(item)
                        else:
                            self._call("on_snakes_roll_shortcut")
                        return True, 0
                elif cur_game in ("DOMINO", "AMERICAN_DOMINO"):
                    domino_side_list = getattr(table_view, "domino_side_list", None) if table_view else None
                    if focus is not None and focus is domino_side_list:
                        item = domino_side_list.currentItem()
                        if item is not None and table_view:
                            table_view._on_domino_side_activated(item)
                            return True, 0
                    domino_list = getattr(table_view, "domino_tile_list", None) if table_view else None
                    if focus is not None and focus is domino_list:
                        self._call("on_play_selected_domino_tile")
                        return True, 0
                elif cur_game == "SCOPA":
                    scopa_list = getattr(table_view, "scopa_card_list", None) if table_view else None
                    if focus is not None and (focus is scopa_list or (hasattr(scopa_list, "viewport") and focus is scopa_list.viewport())):
                        item = scopa_list.currentItem()
                        if item is not None and table_view:
                            table_view._on_scopa_card_activated(item)
                            return True, 0


                wild_color_list = getattr(table_view, "wild_color_list", None) if table_view else None
                if focus is not None and (focus is wild_color_list or (hasattr(wild_color_list, "viewport") and focus is wild_color_list.viewport())):
                    item = wild_color_list.currentItem()
                    if item is not None and table_view:
                        table_view._wild_color_activated(item)
                        return True, 0

                ninety_nine_list = getattr(table_view, "ninety_nine_choice_list", None) if table_view else None
                if focus is not None and (focus is ninety_nine_list or (hasattr(ninety_nine_list, "viewport") and focus is ninety_nine_list.viewport())):
                    item = ninety_nine_list.currentItem()
                    if item is not None and table_view:
                        table_view._ninety_nine_choice_activated(item)
                        return True, 0

                card_groups = getattr(table_view, "card_groups", []) if table_view else []
                if focus is not None and any(focus is cg or (hasattr(cg, "viewport") and focus is cg.viewport()) for cg in card_groups):
                    self._call("on_play_selected_card")
                    return True, 0
                # Enter on the main table area while the room is waiting starts
                # the game flow (including the default-settings confirmation).
                main_table = getattr(table_view, "main_table_widget", None) if table_view else None
                if focus is not None and (focus is main_table or (hasattr(main_table, "viewport") and focus is main_table.viewport())) and self.window.is_in_room():
                    room = getattr(self.window, "current_room", None) or {}
                    if room.get("status") == "waiting":
                        self._call("_menu_start_game")
                        return True, 0
                return False, 0

            # Escape: safe navigation/cancel, never a blind immediate room leave.
            if vk == 0x1B:
                table_view = getattr(self.window, "table_view", None)
                if table_view and hasattr(table_view, "domino_side_list") and table_view.domino_side_list.isVisible():
                    table_view.hide_domino_side_selection()
                    return True, 0
                if self.window.is_choosing_wild():
                    self._call("on_cancel_wild")
                elif self.window.is_choosing_ninety_nine_value():
                    self._call("on_cancel_ninety_nine_choice")
                else:
                    self._call("on_escape_navigation")
                return True, 0

        except Exception:
            return False, 0

        return False, 0
