"""Authentication and Session Controller for TableVerse desktop client."""
from __future__ import annotations

import logging
from typing import Any, Optional
from PySide6.QtCore import QTimer
from client.accessibility.reader import reader
from client.audio.sound_engine import sound_engine
from client.localization import tr
from client.session_store import (
    load_token, save_token, clear_token,
    load_credentials, clear_credentials, save_account_profile
)
from client.settings_store import load_settings

logger = logging.getLogger("tableverse.auth_controller")


class AuthController:
    """Encapsulates login, registration, auto-login, and session restoration logic."""

    def __init__(self, app: Any):
        self.app = app

    def login(self, username: str, password: str) -> None:
        """Execute user login flow."""
        self.app.stack.setCurrentWidget(self.app.login_loading_view)
        sound_engine.play_looping("CONNECTING")

        def done(res: dict):
            sound_engine.stop_looping("CONNECTING")
            sound_engine.play_event("CONNECTED")
            self.app.api.token = res.get("access_token")
            self.app.user = res.get("user", {})
            dname = self.app.user.get("display_name", username)
            
            if load_settings().get("general", {}).get("keep_credentials", True):
                save_token(self.app.api.token)
                save_account_profile(username, password, dname, active=True)
            else:
                clear_token()
                clear_credentials()

            self.app.home_view.set_user_greeting(dname)
            current_room_id = self.app.user.get("current_room_id")
            if current_room_id:
                def on_room_found(room):
                    self.app.home_view.activity_panel.clear()
                    self.app._enter_table(room)
                    reader.speak(tr("تمت إعادتك إلى طاولتك السابقة."))
                def on_room_error(_err):
                    self.app._start_session_clean(dname)
                self.app._run_async(lambda: self.app.api.get_room(current_room_id), on_room_found, on_room_error)
            else:
                self.app._start_session_clean(dname)

        def fail(err: str):
            sound_engine.stop_looping("CONNECTING")
            self.app.stack.setCurrentIndex(0)
            if username:
                self.app.auth_view.username_input.setText(username)
            if password:
                self.app.auth_view.password_input.setText(password)
            clean_err = self.app.error_presenter.clean_message(err)
            from client.views.list_menu import show_message_dialog
            show_message_dialog(self.app, clean_err, title="خطأ")
            self.app.auth_view.username_input.setFocus()

        self.app._run_async(lambda: self.app.api.login(username, password), done, fail)

    def register(self, username: str, display_name: str, password: str) -> None:
        """Execute user registration flow."""
        sound_engine.play_looping("CONNECTING")
        self.app.stack.setCurrentWidget(self.app.login_loading_view)

        def done(res: dict):
            sound_engine.stop_looping("CONNECTING")
            sound_engine.play_event("CONNECTED")
            self.app.stack.setCurrentIndex(0)
            from client.views.list_menu import show_message_dialog
            show_message_dialog(self.app, "تم إنشاء الحساب بنجاح. يمكنك الآن تسجيل الدخول.", title="نجاح")
            self.app.auth_view.switch_to_login()

        def fail(err: str):
            sound_engine.stop_looping("CONNECTING")
            self.app.stack.setCurrentIndex(0)
            clean_err = self.app.error_presenter.clean_message(err)
            from client.views.list_menu import show_message_dialog
            show_message_dialog(self.app, clean_err, title="خطأ")
            self.app.auth_view.username_input.setFocus()

        self.app._run_async(lambda: self.app.api.register(username, display_name, password), done, fail)

    def restore_saved_session(self) -> None:
        """Attempt auto-login or prefill credentials on app launch."""
        settings = load_settings()
        reader.set_muted(settings.get("speech", {}).get("mute_all", False))

        keep = settings.get("general", {}).get("keep_credentials", True)
        auto = settings.get("general", {}).get("auto_login", True)

        if not keep:
            clear_token()
            clear_credentials()
            reader.speak(tr("مرحبًا بك في TableVerse. يرجى كتابة اسم المستخدم وكلمة المرور."))
            QTimer.singleShot(100, lambda: self.app.auth_view.username_input.setFocus())
            return

        saved_u, saved_p = load_credentials()
        if saved_u and saved_p:
            self.app.auth_view.username_input.setText(saved_u)
            self.app.auth_view.password_input.setText(saved_p)

        if auto:
            token = load_token()
            if token:
                sound_engine.play_looping("CONNECTING")
                self.app.stack.setCurrentWidget(self.app.login_loading_view)
                self.app.api.token = token

                def done(res: dict):
                    sound_engine.stop_looping("CONNECTING")
                    sound_engine.play_event("CONNECTED")
                    self.app.user = res or {}
                    dname = self.app.user.get("display_name", self.app.user.get("username", ""))
                    self.app.home_view.set_user_greeting(dname)
                    current_room_id = self.app.user.get("current_room_id")
                    if current_room_id:
                        def on_room_found(room):
                            self.app.home_view.activity_panel.clear()
                            self._start_lobby_ws() if hasattr(self, "_start_lobby_ws") else None
                            self.app._enter_table(room)
                            reader.speak(tr("تمت إعادتك إلى طاولتك السابقة."))
                        def on_room_error(_err):
                            self.app._start_session_clean(dname, returning=True)
                        self.app._run_async(lambda: self.app.api.get_room(current_room_id), on_room_found, on_room_error)
                    else:
                        self.app._start_session_clean(dname, returning=True)

                def failed(_):
                    sound_engine.stop_looping("CONNECTING")
                    clear_token()
                    self.app.api.token = None
                    if saved_u and saved_p:
                        self.login(saved_u, saved_p)
                    else:
                        self.app.stack.setCurrentIndex(0)
                        reader.speak(tr("تعذر الدخول التلقائي. يرجى كتابة بيانات الدخول."))
                        QTimer.singleShot(100, lambda: self.app.auth_view.username_input.setFocus())

                self.app._run_async(self.app.api.me, done, failed)
                return

        if saved_u and saved_p:
            self.app.auth_view.username_input.setText(saved_u)
            self.app.auth_view.password_input.setText(saved_p)
            reader.speak(tr("مرحبًا بك. بياناتك محفوظة، اضغط تسجيل الدخول."))
            QTimer.singleShot(100, lambda: self.app.auth_view.login_btn.setFocus())
        else:
            reader.speak(tr("مرحبًا بك في TableVerse. يرجى كتابة اسم المستخدم وكلمة المرور."))
            QTimer.singleShot(100, lambda: self.app.auth_view.username_input.setFocus())
