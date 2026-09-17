"""Social and Profile Management Controller for TableVerse desktop client."""
from __future__ import annotations

import logging
from typing import Any, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

from client.accessibility.reader import reader
from client.localization import tr
from client.views.list_menu import ListMenu
from client.views.friends_view import FriendsView
from client.views.friend_actions import (
    FriendActionsDialog, OnlineUserActionsDialog, SimpleMessageDialog,
    ProfileDialog, HeadToHeadDialog, MuteDialog, GiftDialog
)
from client.views.online_users_view import OnlineUsersView
from client.views.social_center_views import PrivateMessagesView, NotificationsView, MyProfileEditDialog, ChallengeDialog

logger = logging.getLogger("tableverse.social_controller")


class SocialController:
    """Encapsulates friends, online users, private messaging, notifications, and profile operations."""

    def __init__(self, app: Any):
        self.app = app

    def open_friends(self) -> None:
        """Open friends view dialog (Ctrl+F)."""
        if not self.app.api.token:
            return
        return_focus = QApplication.focusWidget()

        def done(res):
            res = res or {}
            dialog = FriendsView(self.app)

            def on_action(data, tab_name):
                if tab_name == "friend":
                    self.open_friend_actions(data, dialog)
                elif tab_name == "incoming":
                    self.handle_friend_request(data, "incoming", dialog)
                elif tab_name == "outgoing":
                    self.handle_friend_request(data, "outgoing", dialog)

            self.app._pending_outgoing_requests.clear()
            self.app._pending_outgoing_requests.update(int(s.get("id")) for s in (res.get("sent") or []) if s.get("id"))
            dialog.set_action_callback(on_action)
            dialog.show_data(res.get("friends", []), res.get("requests", []), res.get("sent", []))
            if return_focus is not None and return_focus.isVisible():
                return_focus.setFocus()

        self.app._run_async(self.app.api.friends, done, lambda e: reader.speak(tr(f"تعذر تحميل الأصدقاء: {e}"), interrupt=True))

    def handle_friend_request(self, row: dict, kind: str, friends_dialog: Any) -> None:
        """Accept, reject, or cancel a friend request."""
        rid = int(row.get("request_id"))
        if kind == "incoming":
            menu = ListMenu(self.app, "إجراءات طلب الصداقة", [("قبول", "accept"), ("رفض", "reject")])
            choice = menu.show_menu(speak_text="إجراءات طلب الصداقة")
            if choice:
                fn = self.app.api.accept_friend_request if choice == "accept" else self.app.api.reject_friend_request

                def request_success(_r):
                    reader.speak(tr("تم تنفيذ الطلب."), interrupt=True)
                    if friends_dialog is not None and friends_dialog.isVisible():
                        self.app._run_async(
                            self.app.api.friends,
                            lambda data: friends_dialog.set_data(
                                (data or {}).get("friends", []),
                                (data or {}).get("requests", []),
                                (data or {}).get("sent", []),
                            ),
                            lambda _e: None,
                        )

                self.app._run_async(lambda: fn(rid), request_success, lambda e: reader.speak(tr(f"تعذر تنفيذ الطلب: {e}"), interrupt=True))
        else:
            uid = int(row.get("id") or 0)
            def cancel_outgoing_ok(_r):
                if uid:
                    self.app._pending_outgoing_requests.discard(uid)
                reader.speak(tr("تم إلغاء طلب الصداقة."), interrupt=True)
                if friends_dialog is not None and friends_dialog.isVisible():
                    self.app._run_async(
                        self.app.api.friends,
                        lambda data: (
                            self.app._pending_outgoing_requests.clear(),
                            self.app._pending_outgoing_requests.update(int(s.get("id")) for s in (data or {}).get("sent", []) if s.get("id")),
                            friends_dialog.set_data(
                                (data or {}).get("friends", []),
                                (data or {}).get("requests", []),
                                (data or {}).get("sent", []),
                            )
                        ),
                        lambda _e: None,
                    )
            self.app._run_async(
                lambda: self.app.api.cancel_friend_request(rid),
                cancel_outgoing_ok,
                lambda e: reader.speak(tr(f"تعذر إلغاء الطلب: {e}"), interrupt=True)
            )

    def open_friend_actions(self, friend: dict, friends_dialog: Any) -> None:
        """Open context actions for an existing friend."""
        if not isinstance(friend, dict) or not friend.get("id"):
            return
        actions = FriendActionsDialog(friend, friends_dialog, can_invite=bool(self.app.current_room))
        if actions.exec() != QDialog.Accepted or not actions.selected_tag:
            return
        tag = actions.selected_tag
        uid = int(friend["id"])
        name = str(friend.get("display_name") or friend.get("username") or "")

        if tag == "profile":
            self.app._run_async(lambda: self.app.api.user_profile(uid), lambda r: ProfileDialog(r, friends_dialog).exec(), lambda e: reader.speak(tr(f"تعذر فتح الملف الشخصي: {e}"), interrupt=True))
        elif tag == "message":
            dlg = SimpleMessageDialog(tr("إرسال رسالة إلى {name}", name=name), tr("اكتب رسالتك:"), friends_dialog)
            if dlg.exec():
                self.app._run_async(lambda: self.app.api.send_private_message(uid, dlg.editor.text().strip()), lambda _r: None, lambda e: reader.speak(tr(f"تعذر إرسال الرسالة: {e}"), interrupt=True))
        elif tag == "join":
            room_id = friend.get("room_id")
            if room_id:
                self.app._handle_join_room(room_id)
        elif tag == "h2h":
            self.app._run_async(lambda: self.app.api.head_to_head(uid), lambda r: HeadToHeadDialog(r, friends_dialog).exec(), lambda e: reader.speak(tr(f"تعذر تحميل الإحصائيات: {e}"), interrupt=True))
        elif tag == "mute":
            def got(flags):
                dlg = MuteDialog(flags, friends_dialog)
                if dlg.exec():
                    self.app._run_async(lambda: self.app.api.set_mutes(uid, dlg.values()), lambda _r: reader.speak(tr("تم حفظ إعدادات الكتم."), interrupt=True), lambda e: reader.speak(tr(f"تعذر حفظ الكتم: {e}"), interrupt=True))
            self.app._run_async(lambda: self.app.api.get_mutes(uid), got, lambda e: reader.speak(tr(f"تعذر تحميل إعدادات الكتم: {e}"), interrupt=True))
        elif tag == "challenge":
            room_id = (self.app.current_room or {}).get("id")
            if not room_id:
                reader.speak(tr("يجب أن تكون داخل طاولة لإرسال الدعوة."), interrupt=True)
                return
            self.app._run_async(lambda: self.app.api.invite_user_to_room(uid, room_id), lambda _r: reader.speak(tr("تم إرسال دعوة الانضمام للطاولة مقابل عملة واحدة."), interrupt=True), lambda e: reader.speak(tr(f"تعذر إرسال الدعوة: {e}"), interrupt=True))
        elif tag == "direct_challenge":
            dlg = ChallengeDialog(friends_dialog)
            if dlg.exec() == QDialog.Accepted:
                game = dlg.selected_game()
                self.app._run_async(
                    lambda: self.app.api.challenge_user(uid, game),
                    lambda r: (reader.speak(tr("تم إرسال دعوة التحدي مقابل 3 عملات."), interrupt=True), self.app._handle_join_room(r.get("room_id")) if isinstance(r, dict) and r.get("room_id") else None),
                    lambda e: reader.speak(tr(f"تعذر إرسال التحدي: {e}"), interrupt=True)
                )
        elif tag == "gift":
            dlg = GiftDialog(friends_dialog)
            if dlg.exec():
                self.app._run_async(lambda: self.app.api.gift_user(uid, dlg.value()), lambda r: reader.speak(tr(f"تم إرسال هدية قدرها {r.get('amount')} عملة."), interrupt=True), lambda e: reader.speak(tr(f"تعذر إرسال الهدية: {e}"), interrupt=True))
        elif tag == "unfriend":
            menu = ListMenu(self.app, "تأكيد إلغاء الصداقة", [("نعم", "yes"), ("لا", "no")])
            choice = menu.show_menu(speak_text=f"هل أنت متأكد من إلغاء الصداقة مع {name}؟")
            if choice == "yes":
                self.app._run_async(lambda: self.app.api.unfriend(uid), lambda _r: reader.speak(tr("تم إلغاء الصداقة."), interrupt=True), lambda e: reader.speak(tr(f"تعذر إلغاء الصداقة: {e}"), interrupt=True))
        elif tag == "block":
            self.app._run_async(lambda: self.app.api.block_user(uid), lambda _r: reader.speak(tr("تم حظر اللاعب."), interrupt=True), lambda e: reader.speak(tr(f"تعذر الحظر: {e}"), interrupt=True))

    def open_online_users(self) -> None:
        """Open online users view dialog (Ctrl+W)."""
        if not self.app.api.token:
            return
        return_focus = QApplication.focusWidget()
        dialog = OnlineUsersView(self.app)
        self._active_online_dialog = dialog
        dialog.userActivated.connect(lambda user, d=dialog: self.open_online_user_actions(user, d))

        def on_search(query):
            def search_done(res):
                res = res or {}
                dialog.set_users(res.get("users", []))
            self.app._run_async(lambda: self.app.api.search_users(query), search_done, lambda _e: None)

        dialog.searchRequested.connect(on_search)

        def done(res):
            res = res or {}
            dialog.set_users(res.get("users", []), is_initial=True)
            dialog.exec()
            self._active_online_dialog = None
            if return_focus is not None and return_focus.isVisible():
                return_focus.setFocus()

        self.app._run_async(self.app.api.online_users, done, lambda e: reader.speak(tr(f"تعذر تحميل المتصلين: {e}"), interrupt=True))

    def refresh_online_users_if_active(self) -> None:
        """Silently refresh online users list if the OnlineUsersView dialog is currently open."""
        dialog = getattr(self, "_active_online_dialog", None)
        if not dialog or not dialog.isVisible() or not self.app.api.token:
            return
        # Only refresh if the user is not actively typing a search query
        if dialog.search.text().strip():
            return
        def done(res):
            if self._active_online_dialog is dialog and dialog.isVisible() and not dialog.search.text().strip():
                dialog.set_users((res or {}).get("users", []), is_initial=True)
        self.app._run_async(self.app.api.online_users, done, lambda _e: None)

    def open_online_user_actions(self, user: dict, online_dialog: Any) -> None:
        """Open action dialog for an online user."""
        if not isinstance(user, dict) or not user.get("id"):
            return
        actions = OnlineUserActionsDialog(user, online_dialog, can_invite=bool(self.app.current_room))
        if actions.exec() != QDialog.Accepted or not actions.selected_tag:
            return
        tag = actions.selected_tag
        uid = int(user["id"])
        name = str(user.get("display_name") or user.get("username") or "")

        if tag == "profile":
            self.app._run_async(lambda: self.app.api.user_profile(uid), lambda r: ProfileDialog(r, online_dialog).exec(), lambda e: reader.speak(tr(f"تعذر فتح الملف الشخصي: {e}"), interrupt=True))
        elif tag == "add_friend":
            def add_ok(_r):
                user["has_pending_request"] = True
                self.app._pending_outgoing_requests.add(uid)
                reader.speak(tr("تم إرسال طلب الصداقة."), interrupt=True)
            self.app._run_async(lambda: self.app.api.send_friend_request(uid), add_ok, lambda e: reader.speak(tr(f"تعذر إرسال طلب الصداقة: {e}"), interrupt=True))
        elif tag == "cancel_friend_request":
            def cancel_ok(_r):
                user["has_pending_request"] = False
                self.app._pending_outgoing_requests.discard(uid)
                reader.speak(tr("تم إلغاء طلب الصداقة."), interrupt=True)
            self.app._run_async(lambda: self.app.api.cancel_friend_request_to_user(uid), cancel_ok, lambda e: reader.speak(tr(f"تعذر إلغاء طلب الصداقة: {e}"), interrupt=True))
        elif tag == "message":
            dlg = SimpleMessageDialog(tr("إرسال رسالة إلى {name}", name=name), tr("اكتب رسالتك:"), online_dialog)
            if dlg.exec():
                self.app._run_async(lambda: self.app.api.send_private_message(uid, dlg.editor.text().strip()), lambda _r: None, lambda e: reader.speak(tr(f"تعذر إرسال الرسالة: {e}"), interrupt=True))
        elif tag == "join":
            room_id = user.get("room_id")
            if room_id:
                self.app._handle_join_room(room_id)
        elif tag == "h2h":
            self.app._run_async(lambda: self.app.api.head_to_head(uid), lambda r: HeadToHeadDialog(r, online_dialog).exec(), lambda e: reader.speak(tr(f"تعذر تحميل الإحصائيات: {e}"), interrupt=True))
        elif tag == "challenge":
            if not bool(user.get("is_friend")):
                reader.speak(tr("دعوة الطاولة متاحة للأصدقاء فقط."), interrupt=True)
                return
            room_id = (self.app.current_room or {}).get("id")
            if not room_id:
                reader.speak(tr("يجب أن تكون داخل طاولة لإرسال الدعوة."), interrupt=True)
                return
            self.app._run_async(lambda: self.app.api.invite_user_to_room(uid, room_id), lambda _r: reader.speak(tr("تم إرسال دعوة الانضمام للطاولة مقابل عملة واحدة."), interrupt=True), lambda e: reader.speak(tr(f"تعذر إرسال الدعوة: {e}"), interrupt=True))
        elif tag == "block":
            self.app._run_async(lambda: self.app.api.block_user(uid), lambda _r: reader.speak(tr("تم حظر اللاعب."), interrupt=True), lambda e: reader.speak(tr(f"تعذر الحظر: {e}"), interrupt=True))

    def open_private_messages(self) -> None:
        """Open private messages inbox."""
        if not self.app.api.token:
            return
        return_focus = QApplication.focusWidget()

        def done(r):
            rows = r.get("messages", [])
            dlg = PrivateMessagesView(rows, self.app)
            dlg.exec()
            if return_focus is not None and return_focus.isVisible():
                return_focus.setFocus()

        self.app._run_async(self.app.api.private_messages, done, lambda e: reader.speak(tr(f"تعذر تحميل الرسائل: {e}"), interrupt=True))

    def open_notifications(self) -> None:
        """Open notifications center dialog."""
        if not self.app.api.token:
            return
        return_focus = QApplication.focusWidget()

        def done(r):
            rows = r.get("notifications", [])
            dlg = NotificationsView(rows, self.app)
            result = dlg.exec()
            selected = dlg.list.currentItem().data(Qt.UserRole) if dlg.list.currentItem() else None
            if result == 100 and isinstance(selected, dict) and selected.get("event_type") == "CHALLENGE_INVITATION":
                invitation_id = (selected.get("payload") or {}).get("invitation_id") if isinstance(selected.get("payload"), dict) else None
                if invitation_id:
                    menu = ListMenu(self.app, "إجراء على الدعوة", [("قبول", "accept"), ("رفض", "reject")])
                    if menu.exec() and menu.result == "accept":
                        self.app._run_async(
                            lambda: self.app.api.accept_challenge(int(invitation_id)),
                            lambda x: (reader.speak(tr("تم قبول الدعوة."), interrupt=True), self.app._handle_join_room(x.get("room_id")) if isinstance(x, dict) and x.get("room_id") else None),
                            lambda e: reader.speak(tr(f"تعذر قبول الدعوة: {e}"), interrupt=True)
                        )
                    elif menu.result == "reject":
                        self.app._run_async(
                            lambda: self.app.api.reject_challenge(int(invitation_id)),
                            lambda _x: reader.speak(tr("تم رفض الدعوة."), interrupt=True),
                            lambda e: reader.speak(tr(f"تعذر رفض الدعوة: {e}"), interrupt=True)
                        )
            if return_focus is not None and return_focus.isVisible():
                return_focus.setFocus()
            ids = [x.get("id") for x in rows if x.get("id") is not None]
            if ids:
                self.app._run_async(lambda: self.app.api.mark_activity_read(event_id=max(ids)), lambda _r: None, lambda _e: None)

        self.app._run_async(self.app.api.notifications, done, lambda e: reader.speak(tr(f"تعذر تحميل الإشعارات: {e}"), interrupt=True))
