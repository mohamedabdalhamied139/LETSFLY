"""Table Players dialog and Player Actions context dialog for TableVerse.

Fully accessible keyboard-first dialogs with NVDA screen-reader support.
"""
from typing import Optional, Dict, Any, List
from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem
from PySide6.QtCore import Qt
from client.accessibility.reader import reader
from client.views.table_view import handle_list_boundary_navigation
from client.localization import tr


class _AccessibleListWidget(QListWidget):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner

    def keyPressEvent(self, event):
        if handle_list_boundary_navigation(self, event):
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            item = self.currentItem()
            if item and (item.flags() & Qt.ItemIsEnabled):
                self.owner._activate(item)
            event.accept()
            return
        if event.key() == Qt.Key_Escape:
            self.owner.reject()
            event.accept()
            return
        super().keyPressEvent(event)


class TablePlayerActionsDialog(QDialog):
    """Contextual actions dialog for a single table member."""

    def __init__(self, target_user: dict, is_host: bool, my_user_id: int, is_voice_muted: bool = False, parent=None):
        super().__init__(parent)
        self.target_user = target_user
        self.is_host = is_host
        self.my_user_id = my_user_id
        self.is_voice_muted = is_voice_muted
        self.selected_tag = None

        target_name = str(target_user.get("display_name") or target_user.get("username") or "لاعب")
        title = tr("إجراءات {name}", name=target_name)
        self.setWindowTitle(title)
        self.setAccessibleName(title)
        self.setModal(True)

        layout = QVBoxLayout(self)
        self.list = _AccessibleListWidget(self)
        self.list.setAccessibleName(tr("قائمة الإجراءات"))

        target_id = int(target_user.get("id") or 0)
        is_me = (target_id == my_user_id)
        is_bot = (target_id < 0)
        is_target_host = bool(target_user.get("is_host"))
        is_spectator = bool(target_user.get("is_spectator"))

        # Build list of actions
        actions = []
        if is_host and not is_me and not is_target_host:
            actions.append(("طرد", "kick"))
            actions.append(("حظر من الطاولة", "ban"))

        if is_host and not is_bot and not is_me:
            actions.append(("المحادثة الصوتية", "voice_submenu"))

        if is_host and not is_me and not is_target_host and not is_spectator:
            actions.append(("تحويل إلى متفرج", "make_spectator"))

        if not is_bot:
            actions.append(("زيارة الملف الشخصي", "profile"))
            if not is_me:
                actions.append(("إضافة صديق", "add_friend"))
                actions.append(("إرسال رسالة", "message"))

        for label, tag in actions:
            disp_label = tr(label)
            it = QListWidgetItem(disp_label)
            it.setData(Qt.UserRole, tag)
            if tag == "add_friend" and target_user.get("is_friend"):
                it.setFlags(it.flags() & ~Qt.ItemIsEnabled)
                it.setToolTip(tr("اللاعب صديق بالفعل"))
            self.list.addItem(it)

        layout.addWidget(self.list)
        if self.list.count() > 0:
            self.list.setCurrentRow(0)
        self.list.itemActivated.connect(self._activate)
        self.list.setFocus()

    def _activate(self, item):
        tag = item.data(Qt.UserRole) if item else None
        if tag:
            self.selected_tag = tag
            self.accept()


class TableVoiceSubmenuDialog(QDialog):
    """Submenu for voice actions targeting a specific player."""

    def __init__(self, target_user: dict, is_host: bool, is_muted: bool, parent=None):
        super().__init__(parent)
        self.target_user = target_user
        self.is_host = is_host
        self.selected_tag = None

        target_name = str(target_user.get("display_name") or target_user.get("username") or "لاعب")
        title = tr("المحادثة الصوتية - {name}", name=target_name)
        self.setWindowTitle(title)
        self.setAccessibleName(title)
        self.setModal(True)

        layout = QVBoxLayout(self)
        self.list = _AccessibleListWidget(self)
        self.list.setAccessibleName(tr("خيارات المحادثة الصوتية"))

        mute_label = "إلغاء كتم المايكروفون" if is_muted else "كتم المايكروفون"
        actions = [(mute_label, "voice_mute")]

        if is_host:
            actions.append(("إزالة من المحادثة الصوتية", "voice_kick"))
            actions.append(("حظر من المحادثة الصوتية", "voice_ban"))

        for label, tag in actions:
            disp_label = tr(label)
            it = QListWidgetItem(disp_label)
            it.setData(Qt.UserRole, tag)
            self.list.addItem(it)

        layout.addWidget(self.list)
        if self.list.count() > 0:
            self.list.setCurrentRow(0)
        self.list.itemActivated.connect(self._activate)
        self.list.setFocus()

    def _activate(self, item):
        tag = item.data(Qt.UserRole) if item else None
        if tag:
            self.selected_tag = tag
            self.accept()


class TablePlayersDialog(QDialog):
    """Dialog displaying all table members, with captain first, followed by players, spectators, and bots."""

    def __init__(self, room: dict, my_user_id: int, parent=None):
        super().__init__(parent)
        self.room = room or {}
        self.my_user_id = my_user_id
        self.selected_user = None

        title = tr("قائمة اللاعبين")
        self.setWindowTitle(title)
        self.setAccessibleName(title)
        self.setModal(True)
        self.setMinimumSize(420, 360)

        layout = QVBoxLayout(self)
        self.list = _AccessibleListWidget(self)
        self.list.setAccessibleName(tr("قائمة اللاعبين"))

        self._populate_players()

        layout.addWidget(self.list)
        if self.list.count() > 0:
            self.list.setCurrentRow(0)
        self.list.itemActivated.connect(self._activate)
        self.list.setFocus()

    def _populate_players(self):
        host_id = int(self.room.get("host_id") or 0)
        host_name = str(self.room.get("host_name") or "القائد")
        players = list(self.room.get("players") or [])
        spectators = list(self.room.get("spectators") or [])
        raw_names = self.room.get("player_names") or []
        players_dict = dict(self.room.get("players_dict") or {})

        def get_name(uid):
            suid = str(uid)
            if suid in players_dict and players_dict[suid]:
                return str(players_dict[suid])
            if isinstance(raw_names, dict) and suid in raw_names and raw_names[suid]:
                return str(raw_names[suid])
            if isinstance(raw_names, list):
                # Try matching by index in players list
                try:
                    if uid in players:
                        idx = players.index(uid)
                        if 0 <= idx < len(raw_names) and raw_names[idx]:
                            return str(raw_names[idx])
                except Exception:
                    pass
            # Try fetching from active game states on parent window
            parent_win = self.parent()
            if parent_win:
                for st_attr in ("uno_state", "domino_state", "scopa_state", "snakes_state", "thief_state", "farkle_state"):
                    st = getattr(parent_win, st_attr, None)
                    if isinstance(st, dict):
                        # check st["players"] list of dicts
                        for p in st.get("players") or []:
                            if isinstance(p, dict) and (p.get("id") == uid or str(p.get("id")) == suid):
                                pname = p.get("name") or p.get("display_name")
                                if pname:
                                    return str(pname)
                        # check st["player_names"] dict
                        pnames = st.get("player_names")
                        if isinstance(pnames, dict) and (suid in pnames or uid in pnames):
                            pname = pnames.get(suid) or pnames.get(uid)
                            if pname:
                                return str(pname)
            if uid == host_id:
                return host_name
            return f"لاعب {uid}" if uid > 0 else f"بوت {abs(uid)}"

        # 1. Captain (always first)
        captain_user = {
            "id": host_id,
            "display_name": host_name,
            "is_host": True,
            "is_spectator": host_id in spectators,
            "is_bot": False,
        }
        cap_text = f"{host_name} ({tr('القائد')})"
        if host_id in spectators:
            cap_text += f" - {tr('متفرج')}"
        it = QListWidgetItem(cap_text)
        it.setData(Qt.UserRole, captain_user)
        self.list.addItem(it)

        # 2. Other Active Players
        for uid in players:
            uid = int(uid)
            if uid == host_id or uid < 0:
                continue
            name = get_name(uid)
            user_data = {
                "id": uid,
                "display_name": name,
                "is_host": False,
                "is_spectator": False,
                "is_bot": False,
            }
            it = QListWidgetItem(name)
            it.setData(Qt.UserRole, user_data)
            self.list.addItem(it)

        # 3. Spectators
        for uid in spectators:
            uid = int(uid)
            if uid == host_id:
                continue
            name = get_name(uid)
            user_data = {
                "id": uid,
                "display_name": name,
                "is_host": False,
                "is_spectator": True,
                "is_bot": False,
            }
            spec_text = f"{name} ({tr('متفرج')})"
            it = QListWidgetItem(spec_text)
            it.setData(Qt.UserRole, user_data)
            self.list.addItem(it)

        # 4. Bots
        for uid in players:
            uid = int(uid)
            if uid >= 0:
                continue
            name = get_name(uid)
            user_data = {
                "id": uid,
                "display_name": name,
                "is_host": False,
                "is_spectator": False,
                "is_bot": True,
            }
            bot_text = f"{name} ({tr('بوت')})"
            it = QListWidgetItem(bot_text)
            it.setData(Qt.UserRole, user_data)
            self.list.addItem(it)

    def _activate(self, item):
        user = item.data(Qt.UserRole) if item else None
        if user:
            self.selected_user = user
            self.accept()
