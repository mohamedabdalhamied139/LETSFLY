"""Room and Table Management Controller for TableVerse desktop client."""
from __future__ import annotations

import logging
import time
from typing import Any, Optional
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from client.accessibility.reader import reader
from client.audio.sound_engine import sound_engine
from client.localization import tr
from client.views.list_menu import ListMenu

logger = logging.getLogger("tableverse.room_controller")


class RoomController:
    """Encapsulates table joins, leaves, creation, privacy, spectator mode, and saved tables."""

    def __init__(self, app: Any):
        self.app = app

    def refresh_available_rooms(self) -> None:
        """Fetch list of open tables."""
        def done(rooms):
            self.app.join_rooms_view.update_rooms(rooms)
            self.app.join_rooms_view.rooms_list.setFocus()
            reader.speak(tr("قائمة الطاولات المتاحة."))
        self.app._run_async(self.app.api.list_rooms, done)

    def create_new_room(self, game: str = "UNO") -> None:
        """Create a new room for the selected game type."""
        self.app._room_generation += 1
        self.app.poll_timer.stop()
        self.app._poll_in_flight = False
        self.app._action_in_flight = False
        self.app.ws.stop()
        generation = self.app._room_generation

        def done(room):
            if generation != self.app._room_generation:
                return
            self.app.current_room = room
            if isinstance(room, dict) and "coins" in room and self.app.user is not None:
                self.app.user["coins"] = room["coins"]
            self.app._enter_table(room)
            sound_engine.play_event("TABLE_JOIN")
            my_name = (self.app.user or {}).get("display_name", "محمد")
            if getattr(self.app, "default_as_spectator", False):
                reader.speak(tr("{name} انضم للطاولة كمتفرج", name=my_name), interrupt=False)
                rid = str(room.get("id") or "")

                def spec_done(r):
                    if isinstance(r.get("room"), dict):
                        self.app.current_room = r["room"]
                    elif self.app.current_room:
                        self.app.current_room["is_spectator"] = True
                    if self.app.current_room:
                        my_id = int((self.app.user or {}).get("id") or 0)
                        self.app.current_room["is_host"] = (int(self.app.current_room.get("host_id") or 0) == my_id)

                self.app._run_async(lambda: self.app.api.toggle_spectator(rid), spec_done)
            else:
                reader.speak(tr("{name} انضم للطاولة", name=my_name), interrupt=False)

        self.app._run_async(lambda: self.app.api.create_room(game), done)

    def join_room(self, room_id: str, as_spectator: bool = False) -> None:
        """Join an existing room as a player or spectator."""
        if not as_spectator and getattr(self.app, "default_as_spectator", False):
            as_spectator = True
        self.app._room_generation += 1
        self.app.poll_timer.stop()
        self.app._poll_in_flight = False
        self.app._action_in_flight = False
        self.app.ws.stop()
        generation = self.app._room_generation

        def done(room):
            if generation != self.app._room_generation:
                return
            self.app.current_room = room
            self.app._enter_table(room)
            sound_engine.play_event("TABLE_JOIN")
            my_name = (self.app.user or {}).get("display_name", "محمد")
            if as_spectator:
                reader.speak(tr("{name} انضم للطاولة كمتفرج", name=my_name), interrupt=False)
            else:
                reader.speak(tr("{name} انضم للطاولة", name=my_name), interrupt=False)

        self.app._run_async(lambda: self.app.api.join_room(room_id, as_spectator=as_spectator), done)

    def leave_room_menu(self) -> None:
        """Leave current table and return to rooms menu."""
        if not self.app.current_room:
            return
        rid = self.app.current_room.get("id")

        def done(_):
            sound_engine.play_event("TABLE_LEAVE")
            self.app.current_room = None
            self.app.voice.leave_room()
            self.app._reset_game_runtime_state()
            if hasattr(self.app, "table_view") and self.app.table_view:
                self.app.table_view.cleanup()
                self.app.table_view.set_playing_mode(False)
            self.app.poll_timer.stop()
            self.app._poll_in_flight = False
            self.app._action_in_flight = False
            self.app._pending_wild_card_id = None
            self.app._start_lobby_ws()
            self.app.stack.setCurrentIndex(2)
            self.app.setWindowTitle("")
            self.app.rooms_menu_view.menu_list.setFocus()
            reader.speak(tr("تمت مغادرة الطاولة والرجوع لقائمة الطاولات."))

        self.app._run_async(lambda: self.app.api.leave_room(rid), done)

    def on_leave_room_shortcut(self) -> None:
        """Handle Q key shortcut to leave table with confirmation prompt."""
        if not self.app.is_in_room():
            return
        if QApplication.activePopupWidget() is not None:
            try:
                QApplication.activePopupWidget().close()
            except Exception:
                pass
            self.app._active_context_menu = None

        choice = ListMenu(
            self.app, "هل تريد الخروج من الطاولة",
            [("نعم", "leave"), ("لا", "stay")],
        ).show_menu()
        if choice == "leave":
            self.leave_room_menu()
        else:
            if self.app.table_view.is_playing and self.app.table_view.get_active_card_list() is not None:
                self.app.table_view.get_active_card_list().setFocus()
            else:
                self.app.table_view.main_table_widget.setFocus()

    def toggle_room_privacy(self) -> None:
        """Ctrl+H shortcut to toggle room privacy (public/private)."""
        if not self.app.is_in_room() or not self.app.current_room:
            return
        is_host = str(self.app.current_room.get("host_id")) == str((self.app.user or {}).get("id"))
        if not is_host:
            reader.speak(tr("تغيير خصوصية الطاولة متاح لقائد الطاولة فقط."), interrupt=True)
            return
        rid = str(self.app.current_room.get("id") or "")

        def done(r):
            is_priv = bool(r.get("is_private"))
            if self.app.current_room:
                if self.app.current_room.get("rules") is None:
                    self.app.current_room["rules"] = {}
                self.app.current_room["rules"]["private"] = is_priv
            msg = "تم تغيير الطاولة إلى خاصة." if is_priv else "تم تغيير الطاولة إلى عامة."
            self.app.table_view.add_log(tr(msg), category="ALL")
            reader.speak(tr(msg), interrupt=True)

        def fail(e):
            reader.speak(tr("تعذر تغيير خصوصية الطاولة: {error}", error=tr(str(e))), interrupt=True)

        self.app._run_async(lambda: self.app.api.toggle_room_privacy(rid), done, fail)

    def toggle_spectator_shortcut(self) -> None:
        """F4 shortcut to toggle spectator mode in room, or toggle default spectator mode across the game."""
        if self.app.is_in_room() and self.app.current_room:
            rid = str(self.app.current_room.get("id") or "")

            def done(r):
                if r.get("is_pending_spectator") is not None:
                    is_pend = bool(r.get("is_pending_spectator"))
                    if self.app.current_room:
                        self.app.current_room["is_pending_spectator"] = is_pend
                    msg = "ستتحول إلى وضع المتفرج بعد نهاية اللعبة الحالية." if is_pend else "تم إلغاء وضع المتفرج، ستستمر كلاعب في اللعبة القادمة."
                    reader.speak(tr(msg), interrupt=True)
                    return
                is_spec = bool(r.get("is_spectator"))
                if isinstance(r.get("room"), dict):
                    self.app.current_room = r["room"]
                elif self.app.current_room:
                    self.app.current_room["is_spectator"] = is_spec
                if self.app.current_room:
                    my_id = int((self.app.user or {}).get("id") or 0)
                    self.app.current_room["is_host"] = (int(self.app.current_room.get("host_id") or 0) == my_id)
                msg = "أنت الآن في وضع المتفرج." if is_spec else "أنت الآن في وضع اللعب."
                reader.speak(tr(msg), interrupt=True)

            def fail(e):
                reader.speak(tr("تعذر تغيير وضع المتفرج: {error}", error=tr(str(e))), interrupt=True)

            self.app._run_async(lambda: self.app.api.toggle_spectator(rid), done, fail)
            return

        self.app.default_as_spectator = not getattr(self.app, "default_as_spectator", False)
        msg = "أنت الآن في وضع المتفرج." if self.app.default_as_spectator else "أنت الآن في وضع اللعب."
        reader.speak(tr(msg), interrupt=True)

    def add_bot(self) -> None:
        """Add a bot player to the table."""
        if not self.app.current_room:
            return
        is_host = str(self.app.current_room.get("host_id")) == str((self.app.user or {}).get("id"))
        if not is_host:
            reader.speak(tr("إضافة بوت متاح لمضيف الطاولة فقط."), interrupt=True)
            return
        rid = self.app.current_room.get("id")

        def done(room):
            self.app.current_room = room
            if isinstance(room, dict) and "coins" in room and self.app.user is not None:
                self.app.user["coins"] = room["coins"]

        self.app._run_async(lambda: self.app.api.add_bot(rid), done)

    def remove_bot(self) -> None:
        """Remove a bot player from the table."""
        if not self.app.current_room:
            return
        is_host = str(self.app.current_room.get("host_id")) == str((self.app.user or {}).get("id"))
        if not is_host:
            reader.speak(tr("إزالة بوت متاح لمضيف الطاولة فقط."), interrupt=True)
            return
        bot_ids = [uid for uid in self.app.current_room.get("players", []) if uid < 0]
        if not bot_ids:
            reader.speak(tr("لا يوجد بوت"), interrupt=True)
            return
        rid = self.app.current_room.get("id")

        def done(res):
            if isinstance(res, dict) and "room" in res:
                self.app.current_room = res["room"]

        self.app._run_async(lambda: self.app.api.remove_bot(rid), done)

    def save_table_shortcut(self) -> None:
        """Ctrl+S shortcut to save active table state."""
        if not self.app.is_in_room():
            return
        status = (self.app.current_room or {}).get("status")
        players = (self.app.current_room or {}).get("players", [])
        if status != "playing":
            reader.speak(tr("لا يمكن حفظ الطاولة إلا أثناء اللعب الفعلي."), interrupt=True)
            return
        if len(players) <= 1:
            reader.speak(tr("يجب أن تحتوي الطاولة على أكثر من لاعب لحفظها."), interrupt=True)
            return
        rid = str((self.app.current_room or {}).get("id") or "")
        if not rid:
            return
        reader.speak(tr("جاري حفظ الطاولة..."), interrupt=True)

        def done(res):
            sound_engine.play_event("CONNECTED")
            msg = res.get("message") or tr("تم حفظ الطاولة بنجاح مقابل عملتين.")
            reader.speak(tr(msg), interrupt=True)
            if self.app.current_room:
                self.leave_room_menu()

        def fail(err):
            sound_engine.play_event("INVALID_ACTION")
            reader.speak(str(err), interrupt=True)

        self.app._run_async(lambda: self.app.api.save_room(rid), done, fail)

    def refresh_saved_tables(self) -> None:
        """Fetch list of saved tables."""
        def done(tables):
            self.app.saved_tables_view.update_tables(tables)
            self.app.saved_tables_view.tables_list.setFocus()
            reader.speak(tr("قائمة الطاولات المحفوظة."))

        def fail(err):
            reader.speak(str(err), interrupt=True)

        self.app._run_async(self.app.api.list_saved_tables, done, fail)

    def delete_saved_table(self, saved_id: int) -> None:
        """Delete a saved table."""
        def done(res):
            sound_engine.play_event("ACTION_CLICK")
            reader.speak(tr("تم حذف الطاولة المحفوظة."), interrupt=True)
            self.refresh_saved_tables()

        def fail(err):
            reader.speak(str(err), interrupt=True)

        self.app._run_async(lambda: self.app.api.delete_saved_table(saved_id), done, fail)

    def restore_saved_table(self, saved_id: int) -> None:
        """Resume a saved table."""
        reader.speak(tr("استعادة الطاولة..."), interrupt=True)

        def done(res):
            room = res.get("room") if isinstance(res, dict) else None
            if room:
                self.app._enter_table(room)
                sound_engine.play_event("TABLE_JOIN")
                reader.speak(tr("تم استرجاع الطاولة بنجاح."), interrupt=True)
            else:
                rid = res.get("room_id") if isinstance(res, dict) else None
                if rid:
                    self.join_room(rid)

        def fail(err):
            sound_engine.play_event("INVALID_ACTION")
            reader.speak(str(err), interrupt=True)

        self.app._run_async(lambda: self.app.api.restore_saved_table(saved_id), done, fail)
