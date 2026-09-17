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

        # Direct table player shortcuts when standing on a player in TablePlayersDialog
        if hasattr(self.owner, "_handle_shortcut_action"):
            if self.owner._handle_shortcut_action(event):
                event.accept()
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

    def __init__(self, target_user: dict, is_host: bool, my_user_id: int, is_voice_muted: bool = False, is_co_host: bool = False, parent=None):
        super().__init__(parent)
        self.target_user = target_user
        self.is_host = is_host
        self.is_co_host = is_co_host
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
        is_target_co_host = bool(target_user.get("is_co_host"))
        is_spectator = bool(target_user.get("is_spectator"))

        # Build list of actions
        actions = []

        # 1. Host transfer (only host can transfer, to another human player)
        if is_host and not is_me and not is_bot and not is_target_host:
            actions.append(("تعيينه كقائد (Ctrl+O)", "transfer_host"))

        # 2. Co-captain / Vice-Captain appointment (only host can appoint/cancel)
        if is_host and not is_me and not is_bot and not is_target_host:
            if is_target_co_host:
                actions.append(("إلغاء تعيين نائب القائد (Shift+O)", "set_co_host"))
            else:
                actions.append(("تعيين نائب كابتن (Shift+O)", "set_co_host"))

        # 3. Substitute (Host or Co-Host can substitute another player or bot)
        if (is_host or is_co_host) and not is_me and not is_target_host:
            actions.append(("استبدال (Ctrl+R)", "substitute"))

        # 4. Kick and Ban (Host or Co-Host, cannot kick/ban host or another co-host if user is co-host)
        can_kick_ban = False
        if is_host and not is_me and not is_target_host:
            can_kick_ban = True
        elif is_co_host and not is_me and not is_target_host and not is_target_co_host:
            can_kick_ban = True

        if can_kick_ban:
            actions.append(("طرد (Ctrl+K)", "kick"))
            actions.append(("حظر من الطاولة (Ctrl+B)", "ban"))

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
    """Submenu for voice actions targeting a specific player (Host only: mute/unmute and remove)."""

    def __init__(self, target_user: dict, is_host: bool, is_muted: bool, parent=None):
        super().__init__(parent)
        self.target_user = target_user
        self.is_host = is_host
        self.selected_tag = None

        target_name = str(target_user.get("display_name") or target_user.get("username") or "لاعب")
        title = tr("التحكم بصوت {name}", name=target_name)
        self.setWindowTitle(title)
        self.setAccessibleName(title)
        self.setModal(True)

        layout = QVBoxLayout(self)
        self.list = _AccessibleListWidget(self)
        self.list.setAccessibleName(title)

        mute_label = "إلغاء كتم المايكروفون" if is_muted else "كتم"
        actions = [(mute_label, "voice_mute")]

        if is_host:
            actions.append(("إزالة من المحادثة الصوتية", "voice_kick"))

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


class TableVoiceModeDialog(QDialog):
    """Dialog for host to select voice conversation mode for the table."""

    def __init__(self, current_mode: str = "all", parent=None):
        super().__init__(parent)
        self.selected_mode = None
        title = tr("تحديد وضع المحادثة الصوتية")
        self.setWindowTitle(title)
        self.setAccessibleName(title)
        self.setModal(True)

        layout = QVBoxLayout(self)
        self.list = _AccessibleListWidget(self)
        self.list.setAccessibleName(title)

        modes = [
            ("متاحة للجميع (الوضع الافتراضي)", "all"),
            ("تعطيل التحدث (استماع فقط - التحدث مقتصر على القائد)", "listen_only"),
            ("تعطيل المحادثة الصوتية تماماً", "owner_only"),
        ]

        cur_idx = 0
        for idx, (label, tag) in enumerate(modes):
            disp = tr(label)
            if tag == current_mode:
                disp += f" ({tr('الحالي')})"
                cur_idx = idx
            it = QListWidgetItem(disp)
            it.setData(Qt.UserRole, tag)
            self.list.addItem(it)

        layout.addWidget(self.list)
        if self.list.count() > 0:
            self.list.setCurrentRow(cur_idx)
        self.list.itemActivated.connect(self._activate)
        self.list.setFocus()

    def _activate(self, item):
        mode = item.data(Qt.UserRole) if item else None
        if mode:
            self.selected_mode = mode
            self.accept()


class TableVoiceManagerDialog(QDialog):
    """Voice manager dialog displaying voice chat controls and player voice status."""

    def __init__(self, room: dict, my_user_id: int, parent=None):
        super().__init__(parent)
        self.room = room or {}
        self.my_user_id = my_user_id
        self.parent_window = parent
        self.selected_action = None  # (action_tag, data)

        title = tr("مدير الصوت")
        self.setWindowTitle(title)
        self.setAccessibleName(title)
        self.setModal(True)
        self.setMinimumSize(420, 360)

        layout = QVBoxLayout(self)
        self.list = _AccessibleListWidget(self)
        self.list.setAccessibleName(title)

        self._populate_options()

        layout.addWidget(self.list)
        if self.list.count() > 0:
            self.list.setCurrentRow(0)
        self.list.itemActivated.connect(self._activate)
        self.list.setFocus()

    def _populate_options(self):
        voice = getattr(self.parent_window, "voice", None)
        in_voice = bool(voice and getattr(voice, "in_voice_chat", False))
        is_muted = bool(voice and getattr(voice, "muted", False))
        host_id = int(self.room.get("host_id") or 0)
        is_host = (self.my_user_id == host_id)

        # Host controls only:
        if is_host:
            # 1. Voice Mode Setting
            current_mode = str(self.room.get("voice_mode") or "all").lower()
            if current_mode == "listen_only":
                mode_label = tr("وضع المحادثة: استماع فقط (تعطيل تحدث اللاعبين)")
            elif current_mode == "owner_only":
                mode_label = tr("وضع المحادثة: معطلة تماماً")
            else:
                mode_label = tr("وضع المحادثة: متاحة للجميع")

            mode_item = QListWidgetItem(mode_label)
            mode_item.setData(Qt.UserRole, {"type": "voice_mode_menu"})
            self.list.addItem(mode_item)

        # Players with voice status (visible to everyone)
        host_name = str(self.room.get("host_name") or "القائد")
        co_host_id = self.room.get("co_host_id")
        co_host_id = int(co_host_id) if co_host_id is not None else None
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
                try:
                    if uid in players:
                        idx = players.index(uid)
                        if 0 <= idx < len(raw_names) and raw_names[idx]:
                            return str(raw_names[idx])
                except Exception:
                    pass
            parent_win = self.parent_window
            if parent_win:
                for st_attr in ("uno_state", "domino_state", "scopa_state", "snakes_state", "thief_state", "farkle_state"):
                    st = getattr(parent_win, st_attr, None)
                    if isinstance(st, dict):
                        for p in st.get("players") or []:
                            if isinstance(p, dict) and (p.get("id") == uid or str(p.get("id")) == suid):
                                pname = p.get("name") or p.get("display_name")
                                if pname:
                                    return str(pname)
                        pnames = st.get("player_names")
                        if isinstance(pnames, dict) and (suid in pnames or uid in pnames):
                            pname = pnames.get(suid) or pnames.get(uid)
                            if pname:
                                return str(pname)
            if uid == host_id:
                return host_name
            return tr("لاعب {0}", uid) if uid > 0 else f"Bot {abs(uid)}"

        # Collect human table members
        all_humans = []
        if host_id > 0 and host_id not in all_humans:
            all_humans.append(host_id)
        if co_host_id is not None and co_host_id > 0 and co_host_id not in all_humans:
            all_humans.append(co_host_id)
        for uid in players:
            uid = int(uid)
            if uid > 0 and uid not in all_humans:
                all_humans.append(uid)
        for uid in spectators:
            uid = int(uid)
            if uid > 0 and uid not in all_humans:
                all_humans.append(uid)

        active_speakers = set(voice.get_active_speaker_ids()) if voice else set()
        room_muted = set(int(u) for u in (self.room.get("voice_muted") or []))
        voice_participants = set(int(u) for u in (self.room.get("voice_participants") or []))
        if in_voice and self.my_user_id > 0:
            voice_participants.add(self.my_user_id)

        for uid in all_humans:
            name = get_name(uid)
            is_me = (uid == self.my_user_id)
            is_target_host = (uid == host_id)
            is_target_co_host = (uid == co_host_id)

            # Determine voice state
            if uid in active_speakers:
                status_str = tr("يتحدث")
            elif uid in room_muted or (is_me and is_muted) or (voice and voice.is_user_locally_muted(uid)):
                status_str = tr("مكتوم")
            elif uid in voice_participants:
                status_str = tr("في المحادثة")
            else:
                status_str = tr("خارج المحادثة")

            item_text = f"{name} ({status_str})"
            user_data = {
                "id": uid,
                "display_name": name,
                "is_host": is_target_host,
                "is_co_host": is_target_co_host,
                "is_spectator": uid in spectators,
                "is_bot": False,
                "is_me": is_me,
                "voice_status": status_str,
                "is_voice_muted": (uid in room_muted),
                "in_voice": (uid in voice_participants or uid in active_speakers),
            }
            it = QListWidgetItem(item_text)
            it.setData(Qt.UserRole, {"type": "player", "user": user_data})
            self.list.addItem(it)

    def _activate(self, item):
        data = item.data(Qt.UserRole) if item else None
        if data:
            self.selected_action = data
            self.accept()


class TableSubstituteChoiceDialog(QDialog):
    """Dialog allowing host or vice-captain to choose who to substitute the target player with:
    either a bot or another player/spectator present at the table.
    """

    def __init__(self, target_user: dict, room: dict, my_user_id: int, parent=None):
        super().__init__(parent)
        self.target_user = target_user
        self.room = room or {}
        self.my_user_id = my_user_id
        self.selected_choice = None  # (is_bot: bool, replacement_user: Optional[dict])

        target_name = str(target_user.get("display_name") or target_user.get("username") or "لاعب")
        title = tr("استبدال {name}", name=target_name)
        self.setWindowTitle(title)
        self.setAccessibleName(title)
        self.setModal(True)
        self.setMinimumSize(380, 300)

        layout = QVBoxLayout(self)
        self.list = _AccessibleListWidget(self)
        self.list.setAccessibleName(tr("اختر البديل لـ {name}", name=target_name))

        target_id = int(target_user.get("id") or 0)
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
                try:
                    if uid in players:
                        idx = players.index(uid)
                        if 0 <= idx < len(raw_names) and raw_names[idx]:
                            return str(raw_names[idx])
                except Exception:
                    pass
            if uid == host_id:
                return host_name
            return tr("لاعب {0}", uid) if uid > 0 else tr("بوت {0}", abs(uid))

        # 1. Option: Replace with a bot (only if target is a human player)
        if target_id > 0:
            bot_item = QListWidgetItem(tr("استبدال ببوت"))
            bot_item.setData(Qt.UserRole, {"is_bot": True, "id": None, "display_name": "بوت"})
            self.list.addItem(bot_item)

        # 2. Options: Replace with other human members present at the table (players or spectators)
        all_candidate_ids = []
        for uid in players:
            uid = int(uid)
            if uid > 0 and uid != target_id and uid not in all_candidate_ids:
                all_candidate_ids.append(uid)
        for uid in spectators:
            uid = int(uid)
            if uid > 0 and uid != target_id and uid not in all_candidate_ids:
                all_candidate_ids.append(uid)

        for uid in all_candidate_ids:
            cname = get_name(uid)
            role_label = ""
            if uid == host_id:
                role_label = f" ({tr('القائد')})"
            elif uid in spectators:
                role_label = f" ({tr('متفرج')})"
            disp_text = f"{cname}{role_label}"
            c_data = {
                "is_bot": False,
                "id": uid,
                "display_name": cname,
            }
            it = QListWidgetItem(disp_text)
            it.setData(Qt.UserRole, c_data)
            self.list.addItem(it)

        layout.addWidget(self.list)
        if self.list.count() > 0:
            self.list.setCurrentRow(0)
        self.list.itemActivated.connect(self._activate)
        self.list.setFocus()

    def _activate(self, item):
        data = item.data(Qt.UserRole) if item else None
        if data:
            self.selected_choice = data
            self.accept()


class TablePlayersDialog(QDialog):
    """Dialog displaying all table members, with captain first, followed by vice-captain, players, spectators, and bots."""

    def __init__(self, room: dict, my_user_id: int, parent=None):
        super().__init__(parent)
        self.room = room or {}
        self.my_user_id = my_user_id
        self.selected_user = None
        self.quick_action = None  # (action_tag, user_dict) when triggered via shortcut

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
        co_host_id = self.room.get("co_host_id")
        co_host_id = int(co_host_id) if co_host_id is not None else None
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
            return tr("لاعب {0}", uid) if uid > 0 else f"Bot {abs(uid)}"

        # 1. Captain (always first)
        captain_user = {
            "id": host_id,
            "display_name": host_name,
            "is_host": True,
            "is_co_host": False,
            "is_spectator": host_id in spectators,
            "is_bot": False,
        }
        cap_text = f"{host_name} ({tr('القائد')})"
        if host_id in spectators:
            cap_text += f" - {tr('متفرج')}"
        it = QListWidgetItem(cap_text)
        it.setData(Qt.UserRole, captain_user)
        self.list.addItem(it)

        # 2. Vice-Captain / Co-Captain (second if present and not captain)
        if co_host_id is not None and co_host_id != host_id and (co_host_id in players or co_host_id in spectators):
            co_name = get_name(co_host_id)
            co_user = {
                "id": co_host_id,
                "display_name": co_name,
                "is_host": False,
                "is_co_host": True,
                "is_spectator": co_host_id in spectators,
                "is_bot": False,
            }
            co_text = f"{co_name} ({tr('نائب القائد')})"
            if co_host_id in spectators:
                co_text += f" - {tr('متفرج')}"
            it = QListWidgetItem(co_text)
            it.setData(Qt.UserRole, co_user)
            self.list.addItem(it)

        # 3. Other Active Players
        for uid in players:
            uid = int(uid)
            if uid == host_id or uid == co_host_id or uid < 0:
                continue
            name = get_name(uid)
            user_data = {
                "id": uid,
                "display_name": name,
                "is_host": False,
                "is_co_host": False,
                "is_spectator": False,
                "is_bot": False,
            }
            it = QListWidgetItem(name)
            it.setData(Qt.UserRole, user_data)
            self.list.addItem(it)

        # 4. Spectators (excluding host and co-host already listed)
        for uid in spectators:
            uid = int(uid)
            if uid == host_id or uid == co_host_id:
                continue
            name = get_name(uid)
            user_data = {
                "id": uid,
                "display_name": name,
                "is_host": False,
                "is_co_host": False,
                "is_spectator": True,
                "is_bot": False,
            }
            spec_text = f"{name} ({tr('متفرج')})"
            it = QListWidgetItem(spec_text)
            it.setData(Qt.UserRole, user_data)
            self.list.addItem(it)

        # 5. Bots
        for uid in players:
            uid = int(uid)
            if uid >= 0:
                continue
            name = get_name(uid)
            user_data = {
                "id": uid,
                "display_name": name,
                "is_host": False,
                "is_co_host": False,
                "is_spectator": False,
                "is_bot": True,
            }
            bot_text = f"{name} (Bot)"
            it = QListWidgetItem(bot_text)
            it.setData(Qt.UserRole, user_data)
            self.list.addItem(it)

        # 6. Voice Manager (مدير الصوت)
        vm_text = tr("مدير الصوت (Ctrl+M)")
        vm_data = {
            "type": "open_voice_manager",
        }
        vm_item = QListWidgetItem(vm_text)
        vm_item.setData(Qt.UserRole, vm_data)
        self.list.addItem(vm_item)

    def _activate(self, item):
        data = item.data(Qt.UserRole) if item else None
        if data:
            if isinstance(data, dict) and data.get("type") == "open_voice_manager":
                self.selected_user = data
            else:
                self.selected_user = data
            self.accept()

    def _handle_shortcut_action(self, event) -> bool:
        """Handle shortcuts directly from the players list:
        - Ctrl+K: Kick (طرد)
        - Ctrl+B: Ban (حظر)
        - Ctrl+O: Make Captain / Transfer Host (نقل القيادة)
        - Shift+O: Appoint / Toggle Vice-Captain (تعيين نائب القائد)
        - Ctrl+R: Substitute (استبدال)
        """
        item = self.list.currentItem()
        if not item:
            return False
        user = item.data(Qt.UserRole)
        if not user or not isinstance(user, dict):
            return False

        mods = event.modifiers()
        key = event.key()
        action_tag = None

        has_ctrl = bool(mods & Qt.ControlModifier)
        has_shift = bool(mods & Qt.ShiftModifier)
        has_alt = bool(mods & Qt.AltModifier)

        if has_ctrl and not has_shift and not has_alt:
            if key == Qt.Key_K:
                action_tag = "kick"
            elif key == Qt.Key_B:
                action_tag = "ban"
            elif key == Qt.Key_O:
                action_tag = "transfer_host"
            elif key == Qt.Key_R:
                action_tag = "substitute"
        elif has_shift and not has_ctrl and not has_alt:
            if key == Qt.Key_O:
                action_tag = "set_co_host"

        if action_tag:
            self.quick_action = (action_tag, user)
            self.accept()
            return True

        return False


class TableTeamSelectionDialog(QDialog):
    """Accessible dialog for host to select teammate and immediately start the match."""

    def __init__(self, players: List[Tuple[int, str]], current_user_id: int, parent=None):
        super().__init__(parent)
        self.players = list(players)
        self.current_user_id = current_user_id
        self.team_assignments: Dict[int, int] = {}

        # Candidates are other players (excluding current user / host)
        self.candidate_players = [(uid, name) for uid, name in self.players if uid != self.current_user_id]
        if not self.candidate_players:
            self.candidate_players = list(self.players)

        title = tr("اختيار الفريق")
        self.setWindowTitle(title)
        self.setAccessibleName(title)
        self.setModal(True)
        self.setMinimumSize(400, 300)

        layout = QVBoxLayout(self)
        self.list = _AccessibleListWidget(self)
        self.list.setAccessibleName(title)
        layout.addWidget(self.list)

        for uid, name in self.candidate_players:
            it = QListWidgetItem(name)
            it.setData(Qt.UserRole, uid)
            self.list.addItem(it)

        if self.list.count() > 0:
            self.list.setCurrentRow(0)
            self.list.setFocus()

    def _activate(self, item):
        chosen_uid = item.data(Qt.UserRole)
        if chosen_uid is None:
            return

        # Build teams: Host + chosen partner = Team 0, others = Team 1
        self.team_assignments = {}
        # Team 0: Host and selected teammate
        self.team_assignments[self.current_user_id] = 0
        self.team_assignments[chosen_uid] = 0

        # Team 1: Remaining players
        for uid, _ in self.players:
            if uid != self.current_user_id and uid != chosen_uid:
                self.team_assignments[uid] = 1

        self.accept()

    def get_custom_teams(self) -> Dict[str, int]:
        """Return mapping of str(user_id) -> team_id."""
        return {str(uid): tid for uid, tid in self.team_assignments.items()}

