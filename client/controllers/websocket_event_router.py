"""WebSocket Event Router for TableVerse desktop client.

Decouples WebSocket event routing and domain event dispatching from TableVerseApp.
"""
from __future__ import annotations

import logging
import time
from typing import Any
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from client.accessibility.reader import reader
from client.audio.sound_engine import sound_engine
from client.localization import tr
from client.notification_policy import handle_event, handle_template_event

logger = logging.getLogger("tableverse.ws_event_router")


class WebSocketEventRouter:
    """Dispatches incoming WebSocket events from server/room to domain handlers."""

    def __init__(self, app: Any):
        self.app = app

    def route(self, event: dict) -> None:
        """Main routing entry point."""
        if not isinstance(event, dict):
            logger.debug("Ignoring non-dict WebSocket event: %r", event)
            return

        et = event.get("type")
        if not et:
            return

        # 1. Connection & Ping Events
        if et in ("ws_ping", "ws_connecting", "ws_connected", "ws_disconnected"):
            self.handle_connection_event(et, event)
            return

        # 2. Game Action Confirmation
        if et == "game_action_result":
            self.handle_game_action_result(event)
            return

        # 3. Room Management & Voice Events
        if et in (
            "table_saved_closed", "kicked_from_room", "banned_from_room",
            "voice_kicked", "voice_banned", "voice_banned_notice",
            "voice_disabled_notice", "voice_mode_changed", "voice_joined",
            "voice_packet", "table_restored"
        ):
            self.handle_room_lifecycle_event(et, event)
            return

        # 4. Activity Log Stream
        if et == "activity_event":
            self.handle_activity_event(event)
            return

        if not self.app.current_room:
            return

        event_room_id = event.get("room_id")
        if event_room_id is not None and str(event_room_id) != str(self.app.current_room.get("id")):
            return

        # 5. Snapshot Recovery
        if et == "room_snapshot":
            self.handle_room_snapshot(event)
            return

        # 6. Player / Participant / Voice membership
        if et in (
            "player_joined", "player_left", "captain_changed", "co_captain_changed",
            "bot_added", "bot_removed", "player_connection_lost", "player_reconnected",
            "player_kicked", "player_banned", "pending_spectator_changed", "room_privacy_changed",
            "spectator_changed", "voice_user_joined", "voice_user_kicked", "voice_user_banned",
            "voice_mute_changed", "player_substituted"
        ):
            self.handle_participant_event(et, event)
            return

        # 7. Chat Messages
        if et == "chat_message" or "text" in event:
            self.handle_chat_event(event)
            return

        # 8. Game Results & State Progression
        self.handle_gameplay_event(et, event)

    def handle_connection_event(self, et: str, event: dict) -> None:
        """Handle transport connection state changes and pings."""
        if et == "ws_ping":
            reader.speak(tr(f"{event.get('rtt_ms', 0)} مللي ثانية"), interrupt=True)
            return

        if et == "ws_connecting":
            sound_engine.play_looping("CONNECTING")
            now = time.monotonic()
            if now - getattr(self.app, "_last_connecting_announced_at", 0.0) >= 10.0:
                self.app._last_connecting_announced_at = now
                reader.speak(tr("connecting"), interrupt=False)
            return

        if et == "ws_connected":
            was_reconnecting = getattr(self.app, "_is_reconnecting", False)
            self.app._is_reconnecting = False
            self.app._reconnect_timeout_timer.stop()
            sound_engine.stop_looping("CONNECTING")
            if was_reconnecting:
                sound_engine.play_event("CONNECTED")
                reader.speak(tr("connection restored successfully"), interrupt=True)

            if self.app.current_room:
                self.app.poll_timer.start()
                room_id = self.app.current_room.get("id")
                if was_reconnecting and room_id:
                    self.app.stack.setCurrentIndex(4)
                    if hasattr(self.app, "table_view") and self.app.table_view:
                        self.app.table_view.focus_initial()
                    generation = self.app._room_generation
                    def done(fresh_room):
                        if generation != self.app._room_generation or not self.app.current_room or str(self.app.current_room.get("id")) != str(room_id):
                            return
                        self.app.current_room = fresh_room
                        self.app._poll_table_state()
                    def fail(err):
                        text = str(err)
                        if "HTTP 404" in text or "not found" in text.lower() or "غير موجود" in text:
                            self.app._leave_table_after_failed_reconnect()
                        else:
                            self.app._poll_table_state()
                    self.app._run_async(lambda: self.app.api.get_room(room_id), done, fail)
                else:
                    QTimer.singleShot(0, self.app._poll_table_state)
            return

        if et == "ws_disconnected":
            if not getattr(self.app, "_is_reconnecting", False):
                self.app._is_reconnecting = True
                self.app._reconnect_focus = QApplication.focusWidget()
                self.app._last_connecting_announced_at = time.monotonic()
                sound_engine.play_event("CONNECTION_LOST")
                reader.speak(tr("connection lost"), interrupt=True)
                sound_engine.play_looping("CONNECTING")
                self.app._reconnect_timeout_timer.start(120000)
            else:
                sound_engine.play_looping("CONNECTING")

            if self.app.current_room:
                self.app.poll_timer.start()
            if self.app.current_room and self.app.voice.in_voice_chat:
                self.app._voice_restore_after_reconnect = False
                self.app.voice.suspend_for_reconnect()
                self.app.voice.stateChanged.emit("الاتصال الصوتي غير متاح.")
            return

    def handle_game_action_result(self, event: dict) -> None:
        """Dispatch asynchronous game action completion callbacks."""
        request_id = str(event.get("request_id") or "")
        pending = self.app._ws_action_pending.pop(request_id, None)
        if pending is None:
            return
        on_success, on_error, generation, room_id = pending
        if generation != self.app._room_generation or str((self.app.current_room or {}).get("id")) != room_id:
            return
        if event.get("ok"):
            if on_success:
                on_success(event.get("state"))
        elif on_error:
            on_error(str(event.get("error") or "تعذر تنفيذ الحركة."))

    def handle_room_lifecycle_event(self, et: str, event: dict) -> None:
        """Handle table persistence, kick/ban, and voice mode lifecycle events."""
        if et == "table_saved_closed":
            msg = event.get("message") or "تم حفظ الطاولة وإنهاء الجلسة."
            reader.speak(tr(msg), interrupt=True)
            if QApplication.activePopupWidget() is not None:
                try:
                    QApplication.activePopupWidget().close()
                except Exception:
                    pass
                self.app._active_context_menu = None
            self.app._menu_leave_room()
            return

        if et in ("kicked_from_room", "banned_from_room"):
            msg = event.get("message") or ("تم طردك من الطاولة." if et == "kicked_from_room" else "تم حظرك من الطاولة.")
            reader.speak(tr(msg), interrupt=True)
            if QApplication.activePopupWidget() is not None:
                try:
                    QApplication.activePopupWidget().close()
                except Exception:
                    pass
                self.app._active_context_menu = None
            self.app._menu_leave_room()
            return

        if et == "voice_kicked":
            reader.speak(tr(event.get("message") or "تم إخراجك من المحادثة الصوتية بواسطة القائد."), interrupt=True)
            if self.app.voice.in_voice_chat:
                self.app.voice.leave_voice_session()
            return

        if et == "voice_banned":
            reader.speak(tr(event.get("message") or "تم حظرك من المحادثة الصوتية في هذه الطاولة."), interrupt=True)
            if self.app.voice.in_voice_chat:
                self.app.voice.leave_voice_session()
            return

        if et == "voice_banned_notice":
            reader.speak(tr(event.get("message") or "أنت محظور من المحادثة الصوتية في هذه الطاولة."), interrupt=True)
            return

        if et == "voice_disabled_notice":
            reader.speak(tr(event.get("message") or "المحادثة الصوتية معطلة في هذه الطاولة من قبل القائد."), interrupt=True)
            return

        if et == "voice_mode_changed":
            new_mode = str(event.get("mode") or "all").lower()
            if self.app.current_room:
                self.app.current_room["voice_mode"] = new_mode
                if "voice_participants" in event:
                    self.app.current_room["voice_participants"] = event["voice_participants"]
            my_id = int((self.app.user or {}).get("id") or 0)
            host_id = int((self.app.current_room or {}).get("host_id") or 0)
            is_host = (my_id == host_id)
            if new_mode == "listen_only":
                msg = "قام القائد بضبط وضع المحادثة الصوتية: استماع فقط (تعطيل تحدث اللاعبين)."
                self.app.table_view.add_log(tr(msg), category="ALL")
                reader.speak(tr(msg), interrupt=False)
                if not is_host and self.app.voice and not self.app.voice.muted:
                    self.app.voice.stop_microphone(silent=True)
                    self.app.voice.muted = True
            elif new_mode == "owner_only":
                msg = "قام القائد بتعطيل المحادثة الصوتية تماماً في الطاولة."
                self.app.table_view.add_log(tr(msg), category="ALL")
                reader.speak(tr(msg), interrupt=False)
                if not is_host and self.app.voice.in_voice_chat:
                    self.app.voice.leave_voice_session()
            else:
                msg = "قام القائد بإتاحة المحادثة الصوتية للجميع."
                self.app.table_view.add_log(tr(msg), category="ALL")
                reader.speak(tr(msg), interrupt=False)
            return

        if et == "voice_joined":
            self.app.voice.handle_server_event(event)
            return

        if et == "voice_packet":
            data = event.get("data")
            if isinstance(data, (bytes, bytearray)):
                self.app.voice.receive_packet(bytes(data))
            return

        if et == "table_restored":
            msg = event.get("message") or tr("تم استرجاع طاولة محفوظة.")
            rid = event.get("room_id")
            reader.speak(tr(msg), interrupt=True)
            if rid:
                self.app._handle_join_room(rid)
            return

    def handle_activity_event(self, event: dict) -> None:
        """Feed global or gameplay activity events into visible panels."""
        if str(event.get("category", "")).upper() == "GAMEPLAY" and event.get("game_event_id") is not None:
            room_id = str(event.get("room_id") or "")
            key = ("game", room_id, str(event.get("event_type") or ""), str(event.get("game_event_id")))
            seen = getattr(self.app, "_seen_game_activity_events", None)
            if seen is None:
                seen = set()
                self.app._seen_game_activity_events = seen
            seen.add(key)
            if len(seen) > 512:
                self.app._seen_game_activity_events = set(list(seen)[-256:])

        for view in (self.app.home_view, self.app.rooms_menu_view, self.app.join_rooms_view, self.app.table_view, self.app.saved_tables_view):
            panel = getattr(view, "activity_panel", None)
            if panel is not None:
                panel.add_event(event)

    def handle_room_snapshot(self, event: dict) -> None:
        """Handle full room state snapshot recovery."""
        room = event.get("room") or {}
        if room.get("id") == self.app.current_room.get("id"):
            self.app._recover_room_snapshot(
                room,
                event.get("uno_state"),
                event.get("thief_state"),
                event.get("farkle_state"),
                event.get("domino_state"),
                event.get("american_domino_state"),
                event.get("snakes_state"),
                event.get("scopa_state"),
                event.get("tennis_state"),
                event.get("ninety_nine_state"),
            )

    def handle_participant_event(self, et: str, event: dict) -> None:
        """Handle player join/leave, role change, voice participant updates."""
        if et == "player_connection_lost":
            name = event.get('name', 'لاعب')
            if str(event.get("user_id")) != str((self.app.user or {}).get("id")):
                sound_engine.play_event("CONNECTION_LOST")
                reader.speak(tr("{name} فقد الاتصال", name=name), interrupt=False)
            return
        elif et == "player_reconnected":
            name = event.get('name', 'لاعب')
            self.app.table_view.add_log(tr("{name} أعاد الاتصال مجددا", name=name), category="ALL")
            if str(event.get("user_id")) != str((self.app.user or {}).get("id")):
                sound_engine.play_event("CONNECTED")
                reader.speak(tr("{name} أعاد الاتصال مجددا", name=name), interrupt=False)
            return
        elif et in ("player_joined", "bot_added"):
            name = event.get('name', 'لاعب')
            self.app.table_view.add_log(tr("{name} انضم للطاولة", name=name), category="ALL")
            if str(event.get("user_id")) != str((self.app.user or {}).get("id")):
                handle_template_event("game_events", "{name} انضم للطاولة", "TABLE_JOIN", interrupt=False, name=name)
            if self.app.current_room:
                if "players" in event:
                    self.app.current_room["players"] = event["players"]
                if "player_names" in event:
                    self.app.current_room["player_names"] = event["player_names"]
                if "players_dict" in event:
                    self.app.current_room["players_dict"] = event["players_dict"]
                uid = event.get("user_id")
                if uid is not None:
                    try:
                        uid = int(uid)
                        if uid not in self.app.current_room.setdefault("players", []):
                            self.app.current_room["players"].append(uid)
                        pdict = self.app.current_room.setdefault("players_dict", {})
                        pdict[str(uid)] = name
                    except Exception:
                        pass
        elif et in ("player_left", "bot_removed"):
            name = event.get('name', 'لاعب')
            self.app.table_view.add_log(tr("{name} غادر الطاولة", name=name), category="ALL")
            if str(event.get("user_id")) != str((self.app.user or {}).get("id")):
                handle_template_event("game_events", "{name} غادر الطاولة", "TABLE_LEAVE", interrupt=False, name=name)
            if self.app.current_room:
                if "players" in event:
                    self.app.current_room["players"] = event["players"]
                if "player_names" in event:
                    self.app.current_room["player_names"] = event["player_names"]
                if "players_dict" in event:
                    self.app.current_room["players_dict"] = event["players_dict"]
        elif et == "player_kicked":
            name = event.get('name', 'لاعب')
            self.app.table_view.add_log(tr("تم طرد {name} من الطاولة بواسطة القائد.", name=name), category="ALL")
            if str(event.get("user_id")) != str((self.app.user or {}).get("id")):
                reader.speak(tr("تم طرد {name} من الطاولة بواسطة القائد.", name=name), interrupt=False)
            if self.app.current_room:
                if "players" in event:
                    self.app.current_room["players"] = event["players"]
                if "player_names" in event:
                    self.app.current_room["player_names"] = event["player_names"]
                if "players_dict" in event:
                    self.app.current_room["players_dict"] = event["players_dict"]
        elif et == "player_banned":
            name = event.get('name', 'لاعب')
            self.app.table_view.add_log(tr("تم حظر {name} من الطاولة بواسطة القائد.", name=name), category="ALL")
            if str(event.get("user_id")) != str((self.app.user or {}).get("id")):
                reader.speak(tr("تم حظر {name} من الطاولة بواسطة القائد.", name=name), interrupt=False)
            if self.app.current_room:
                if "players" in event:
                    self.app.current_room["players"] = event["players"]
                if "player_names" in event:
                    self.app.current_room["player_names"] = event["player_names"]
                if "players_dict" in event:
                    self.app.current_room["players_dict"] = event["players_dict"]
        elif et == "pending_spectator_changed":
            uid = int(event.get("user_id") or 0)
            is_pend = bool(event.get("is_pending_spectator"))
            my_id = int((self.app.user or {}).get("id") or 0)
            if uid == my_id and self.app.current_room:
                self.app.current_room["is_pending_spectator"] = is_pend
        elif et == "room_privacy_changed":
            is_priv = bool(event.get("is_private"))
            if self.app.current_room:
                if self.app.current_room.get("rules") is None:
                    self.app.current_room["rules"] = {}
                self.app.current_room["rules"]["private"] = is_priv
        elif et == "spectator_changed":
            name = event.get('name', 'لاعب')
            is_spec = bool(event.get('is_spectator'))
            status_text = "متفرج" if is_spec else "لاعب"
            self.app.table_view.add_log(tr("{name} الآن في وضع {status}.", name=name, status=tr(status_text)), category="ALL")
            if str(event.get("user_id")) != str((self.app.user or {}).get("id")):
                reader.speak(tr("{name} الآن في وضع {status}.", name=name, status=tr(status_text)), interrupt=False)
            if self.app.current_room:
                if "spectators" in event:
                    self.app.current_room["spectators"] = event["spectators"]
                if "players" in event:
                    self.app.current_room["players"] = event["players"]
                if "player_names" in event:
                    self.app.current_room["player_names"] = event["player_names"]
                if "players_dict" in event:
                    self.app.current_room["players_dict"] = event["players_dict"]
                my_id = int((self.app.user or {}).get("id") or 0)
                if str(event.get("user_id")) == str(my_id):
                    self.app.current_room["is_spectator"] = is_spec
                self.app.current_room["is_host"] = (int(self.app.current_room.get("host_id") or 0) == my_id)
        elif et == "voice_mute_changed":
            name = event.get('name', 'لاعب')
            is_muted = bool(event.get('is_muted'))
            txt = "تم كتم ميكروفون {name}." if is_muted else "تم إلغاء كتم ميكروفون {name}."
            self.app.table_view.add_log(tr(txt, name=name), category="ALL")
            reader.speak(tr(txt, name=name), interrupt=False)
            if self.app.current_room:
                vm = set(self.app.current_room.get("voice_muted") or [])
                uid = int(event.get("user_id") or 0)
                if is_muted:
                    vm.add(uid)
                else:
                    vm.discard(uid)
                self.app.current_room["voice_muted"] = list(vm)
        elif et == "voice_user_joined":
            name = event.get('name', 'لاعب')
            uid = int(event.get("user_id") or 0)
            self.app.table_view.add_log(tr("انضم {name} إلى المحادثة الصوتية.", name=name), category="ALL")
            if str(uid) != str((self.app.user or {}).get("id")):
                reader.speak(tr("انضم {name} إلى المحادثة الصوتية.", name=name), interrupt=False)
            if self.app.current_room:
                vp = set(int(u) for u in (self.app.current_room.get("voice_participants") or []))
                if uid > 0:
                    vp.add(uid)
                self.app.current_room["voice_participants"] = list(vp)
        elif et == "voice_user_kicked":
            name = event.get('name', 'لاعب')
            uid = int(event.get("user_id") or 0)
            self.app.table_view.add_log(tr("تمت إزالة {name} من المحادثة الصوتية.", name=name), category="ALL")
            reader.speak(tr("تمت إزالة {name} من المحادثة الصوتية.", name=name), interrupt=False)
            if self.app.current_room:
                vp = set(int(u) for u in (self.app.current_room.get("voice_participants") or []))
                vp.discard(uid)
                self.app.current_room["voice_participants"] = list(vp)
        elif et == "voice_user_banned":
            name = event.get('name', 'لاعب')
            uid = int(event.get("user_id") or 0)
            self.app.table_view.add_log(tr("تم حظر {name} من المحادثة الصوتية.", name=name), category="ALL")
            reader.speak(tr("تم حظر {name} من المحادثة الصوتية.", name=name), interrupt=False)
            if self.app.current_room:
                vp = set(int(u) for u in (self.app.current_room.get("voice_participants") or []))
                vp.discard(uid)
                self.app.current_room["voice_participants"] = list(vp)
        elif et == "captain_changed":
            name = event.get('name', 'لاعب')
            self.app.table_view.add_log(tr("{name} أصبح كابتن الطاولة", name=name), category="ALL")
            handle_template_event("game_events", "{name} أصبح كابتن الطاولة", "", interrupt=False, name=name)
            if self.app.current_room:
                self.app.current_room["host_id"] = event.get("user_id")
                self.app.current_room["host_name"] = name
                my_id = int((self.app.user or {}).get("id") or 0)
                self.app.current_room["is_host"] = (event.get("user_id") == my_id)
                if "co_host_id" in event:
                    self.app.current_room["co_host_id"] = event.get("co_host_id")
                    self.app.current_room["is_co_host"] = (event.get("co_host_id") == my_id)
        elif et == "co_captain_changed":
            name = event.get('name', '')
            is_co = bool(event.get('is_co_host'))
            if is_co and name:
                self.app.table_view.add_log(tr("{name} أصبح نائب كابتن الطاولة", name=name), category="ALL")
                handle_template_event("game_events", "{name} أصبح نائب كابتن الطاولة", "", interrupt=False, name=name)
            else:
                self.app.table_view.add_log(tr("تم إلغاء نائب كابتن الطاولة"), category="ALL")
            if self.app.current_room:
                self.app.current_room["co_host_id"] = event.get("co_host_id")
                my_id = int((self.app.user or {}).get("id") or 0)
                self.app.current_room["is_co_host"] = (event.get("co_host_id") == my_id if event.get("co_host_id") is not None else False)
        elif et == "player_substituted":
            name = event.get('name', 'لاعب')
            is_bot = bool(event.get('is_bot', True))
            if is_bot:
                rep_name = event.get('bot_name', 'Bot')
            else:
                rep_name = event.get('replacement_name', 'لاعب')
            self.app.table_view.add_log(tr("تم استبدال {name} بـ {rep}", name=name, rep=rep_name), category="ALL")
            if str(event.get("user_id")) != str((self.app.user or {}).get("id")):
                reader.speak(tr("تم استبدال {name} بـ {rep}", name=name, rep=rep_name), interrupt=False)
            if self.app.current_room:
                if "players" in event:
                    self.app.current_room["players"] = event["players"]
                if "spectators" in event:
                    self.app.current_room["spectators"] = event["spectators"]
                if "player_names" in event:
                    self.app.current_room["player_names"] = event["player_names"]
                if "players_dict" in event:
                    self.app.current_room["players_dict"] = event["players_dict"]

    def handle_chat_event(self, event: dict) -> None:
        """Handle in-table chat text messages."""
        sender = event.get("sender", "مجهول")
        text = event.get("text", "")
        if text:
            self.app.table_view.add_log(f"{sender}: {text}", category="TABLE_CHAT")
            focused = getattr(self.app.table_view, "is_chat_focused", lambda: False)()
            if not focused:
                handle_template_event("table_chat", "رسالة طاولة من {sender}: {text}", "CHAT_MESSAGE", interrupt=True, sender=sender, text=text)
            else:
                handle_template_event("table_chat", "{sender} يقول {text}", "CHAT_MESSAGE", interrupt=False, sender=sender, text=text)

    def handle_gameplay_event(self, et: str, event: dict) -> None:
        """Handle in-game status, round completion, match results, and state updates."""
        if et == "game_stopped":
            sound_engine.play_event("GAME_STOPPED")
            handle_event("game_events", "تم إيقاف المباراة. العودة إلى وضع الانتظار.", "", interrupt=True)
            self.app.table_view.set_playing_mode(False)
            self.app.table_view.clear_hand_for_round_transition()
            self.app.table_view.main_table_widget.setFocus()
            return

        if et == "score_updated":
            name = event.get("name", "لاعب")
            total = event.get("total", 0)
            self.app.table_view.add_log(f"{name} {total}")
            return

        if et in ("tennis_action_result", "tennis_sound", "tennis_point_result"):
            if hasattr(self.app.table_view, "tennis_game"):
                self.app.table_view.tennis_game.handle_event(event)
            return

        if et == "tennis_state_changed":
            state = event.get("state")
            if state:
                self.app._apply_tennis_state(state)
            else:
                self.app._poll_table_state()
            return

        if et == "tennis_match_finished":
            self.app._announce_terminal_result(event)
            self.app._reset_game_runtime_state()
            if self.app.current_room:
                self.app.current_room["status"] = "waiting"
            self.app.table_view.set_game_type("TENNIS")
            self.app.table_view.set_playing_mode(False)
            self.app.table_view.clear_hand_for_round_transition()
            from client.views.table_view import is_user_in_chat_or_log
            if not is_user_in_chat_or_log(self.app.table_view):
                self.app.table_view.main_table_widget.setFocus()
            return

        if et in ("domino_match_finished", "american_domino_match_finished"):
            self.app._announce_terminal_result(event)
            self.app._reset_game_runtime_state()
            if self.app.current_room:
                self.app.current_room["status"] = "waiting"
            gtype = (self.app.current_room or {}).get("game", "DOMINO")
            self.app.table_view.set_game_type(gtype)
            self.app.table_view.set_playing_mode(False)
            self.app.table_view.clear_hand_for_round_transition()
            self.app.table_view.update_domino_state({"active": False})
            from client.views.table_view import is_user_in_chat_or_log
            if not is_user_in_chat_or_log(self.app.table_view):
                self.app.table_view.main_table_widget.setFocus()
            return

        if et == "farkle_match_finished":
            self.app._announce_terminal_result(event)
            self.app._reset_game_runtime_state()
            if self.app.current_room:
                self.app.current_room["status"] = "waiting"
            self.app.farkle_state = event.get("state") or {}
            self.app.table_view.set_game_type("FARKLE")
            self.app.table_view.set_playing_mode(False)
            if hasattr(self.app.table_view, "farkle_dice_list") and self.app.table_view.farkle_dice_list:
                self.app.table_view.farkle_dice_list.clear()
            from client.views.table_view import is_user_in_chat_or_log
            if not is_user_in_chat_or_log(self.app.table_view):
                self.app.table_view.main_table_widget.setFocus()
            return

        if et == "scopa_match_finished":
            if self.app._announce_scopa_final_play(event):
                QTimer.singleShot(2500, lambda e=dict(event): self.app._finish_scopa_match(e))
            else:
                self.app._finish_scopa_match(event)
            return

        if et == "snakes_match_finished":
            if getattr(self.app, "_snakes_stepping", False):
                self.app._pending_snakes_terminal_event = dict(event)
            else:
                self.app._finish_snakes_match(event)
            return

        if et == "thief_match_finished":
            self.app._announce_terminal_result(event)
            self.app._reset_game_runtime_state()
            if self.app.current_room:
                self.app.current_room["status"] = "waiting"
            self.app.table_view.set_playing_mode(False)
            self.app.table_view.set_game_type("THIEF_HUNT")
            self.app.table_view.clear_hand_for_round_transition()
            from client.views.table_view import is_user_in_chat_or_log
            if not is_user_in_chat_or_log(self.app.table_view):
                self.app.table_view.main_table_widget.setFocus()
            return

        if et == "scopa_round_finished":
            announced = self.app._announce_scopa_final_play(event)
            round_summary = event.get("round_summary")
            if round_summary:
                event_id = str(event.get("event_id") or "")
                key = (str((self.app.current_room or {}).get("id") or ""), event_id, "ROUND_FINISHED", round_summary)
                seen_plays = getattr(self.app, "_seen_scopa_final_plays", None)
                if seen_plays is None:
                    seen_plays = set()
                    try:
                        self.app._seen_scopa_final_plays = seen_plays
                    except AttributeError:
                        pass
                if key not in seen_plays:
                    seen_plays.add(key)
                    delay = 900 if event.get("final_play_action") else 0
                    QTimer.singleShot(delay, lambda: sound_engine.play_event("ROUND_END"))
                    QTimer.singleShot(delay, lambda text=round_summary: reader.speak(tr(text), interrupt=False))
            if self.app.current_room:
                if isinstance(event.get("scores"), dict):
                    self.app.current_room["scores"] = event.get("scores")
                if event.get("target_score") is not None:
                    self.app.current_room["target_score"] = event.get("target_score")
            return

        if et in ("round_finished", "ninety_nine_round_finished", "domino_round_finished", "american_domino_round_finished"):
            self.app.uno_state = None
            self.app.domino_state = None
            self.app.scopa_state = None
            self.app._was_my_turn = False
            self.app.table_view.set_playing_mode(False)
            self.app.table_view.clear_hand_for_round_transition()
            if self.app.current_room:
                if isinstance(event.get("scores"), dict):
                    self.app.current_room["scores"] = event.get("scores")
                if event.get("target_score") is not None:
                    self.app.current_room["target_score"] = event.get("target_score")
            return

        if et == "match_finished":
            self.app._announce_terminal_result(event)
            self.app._reset_game_runtime_state()
            if self.app.current_room:
                self.app.current_room["status"] = "waiting"
            self.app.table_view.set_playing_mode(False)
            self.app.table_view.clear_hand_for_round_transition()
            from client.views.table_view import is_user_in_chat_or_log
            if not is_user_in_chat_or_log(self.app.table_view):
                self.app.table_view.main_table_widget.setFocus()
            return

        if et == "game_finished":
            if event.get("game") == "SCOPA":
                return
            self.app._reset_game_runtime_state()
            if self.app.current_room:
                self.app.current_room["status"] = "waiting"
            self.app.table_view.set_playing_mode(False)
            if event.get("game") in ("UNO", "NINETY_NINE"):
                self.app.table_view.clear_hand_for_round_transition()
            elif event.get("game") in ("DOMINO", "AMERICAN_DOMINO"):
                self.app.table_view.clear_hand_for_round_transition()
                self.app.table_view.update_domino_state({"active": False})
            from client.views.table_view import is_user_in_chat_or_log
            if not is_user_in_chat_or_log(self.app.table_view):
                self.app.table_view.main_table_widget.setFocus()
            return

        if et in (
            "uno_state_changed", "game_state_changed", "ninety_nine_state_changed",
            "thief_state_changed", "farkle_state_changed", "domino_state_changed",
            "american_domino_state_changed", "snakes_state_changed", "scopa_state_changed"
        ):
            state = event.get("state")
            game = self.app.current_room.get("game", "")
            if state:
                from client.table_framework.adapter import get_adapter
                adapter = get_adapter(game)
                if adapter and adapter.apply_state:
                    adapter.apply_state(self.app, state)
                elif game == "SCOPA": self.app._apply_scopa_state(state)
                elif game == "TENNIS": self.app._apply_tennis_state(state)
                elif game == "THIEF_HUNT": self.app._apply_thief_state(state)
                elif game == "FARKLE": self.app._apply_farkle_state(state)
                elif game in ("DOMINO", "AMERICAN_DOMINO"): self.app._apply_domino_state(state)
                elif game == "SNAKES_LADDERS": self.app._apply_snakes_state(state)
                elif game == "NINETY_NINE": self.app._apply_ninety_nine_state(state)
                else: self.app._apply_uno_state(state)
            else:
                self.app._poll_table_state()
            return
