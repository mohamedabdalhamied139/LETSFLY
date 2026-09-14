from client.localization import tr
import os
import json
import httpx
from typing import Optional, Any

def _env(name: str, default: str = "") -> str:
    """Read TABLEVERSE_* settings, with legacy LETSFLY_* fallback."""
    return os.getenv(name) or os.getenv(name.replace("TABLEVERSE_", "LETSFLY_"), default)


class ApiClient:
    def __init__(self, base_url: Optional[str] = None):
        if base_url is None:
            base_url = _env("TABLEVERSE_SERVER_URL", "https://letsfly.onrender.com").strip() or "https://letsfly.onrender.com"
        self.base_url = base_url.rstrip("/")
        self.token: Optional[str] = None
        # Keep one pooled HTTP client for the lifetime of the desktop app.
        # urllib.request creates a fresh connection for each call, which can
        # repeatedly pay TCP/TLS setup latency on every game action.
        self._http = httpx.Client(timeout=10.0, follow_redirects=False, headers={"Content-Type": "application/json"})

    def get_ws_url(self, path: str = "") -> str:
        """Derive the matching ws:// or wss:// URL from the configured HTTP base URL."""
        base = self.base_url
        if base.startswith("https://"):
            ws_base = "wss://" + base[8:]
        elif base.startswith("http://"):
            ws_base = "ws://" + base[7:]
        elif base.startswith("wss://") or base.startswith("ws://"):
            ws_base = base
        else:
            ws_base = "ws://" + base
        p = "/" + path.lstrip("/") if path else ""
        return f"{ws_base}{p}"

    def _request(self, method: str, path: str, payload: Optional[dict] = None, timeout: float = 10) -> Any:
        url = f"{self.base_url}{path}"
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            response = self._http.request(method, url, json=payload, headers=headers, timeout=timeout)
            raw = response.text
            if response.status_code >= 400:
                msg = f"HTTP {response.status_code}"
                try:
                    data = response.json()
                    msg = data.get("detail", msg)
                except Exception:
                    pass
                raise RuntimeError(str(tr(msg)))
            return response.json() if raw else {}
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(str(tr("فشل الاتصال بالخادم: {error}", error=exc)))

    def close(self):
        try:
            self._http.close()
        except Exception:
            pass

    def register(self, username, display_name, password):
        return self._request("POST", "/api/auth/register", {"username": username, "display_name": display_name, "password": password})

    def login(self, username, password):
        return self._request("POST", "/api/auth/login", {"username": username, "password": password})

    def logout(self):
        result = self._request("POST", "/api/auth/logout")
        self.token = None
        return result

    def change_password(self, current_password, new_password):
        return self._request("POST", "/api/auth/change-password", {"current_password": current_password, "new_password": new_password})

    def health(self):
        return self._request("GET", "/api/health")

    def me(self):
        return self._request("GET", "/api/auth/me")

    def activity(self, limit=100, before_id=None, category=None):
        path = f"/api/activity?limit={int(limit)}"
        if before_id:
            path += f"&before_id={int(before_id)}"
        if category:
            from urllib.parse import quote
            path += f"&category={quote(str(category).upper())}"
        return self._request("GET", path)

    def mark_activity_read(self, category=None, event_id=None):
        payload = {}
        if category:
            payload["category"] = str(category).upper()
        if event_id is not None:
            payload["event_id"] = int(event_id)
        return self._request("POST", "/api/activity/read", payload)

    def clear_activity(self, timeout=2):
        return self._request("DELETE", "/api/activity", timeout=timeout)

    def friends(self):
        return self._request("GET", "/api/friends")

    def online_users(self):
        return self._request("GET", "/api/users/online")

    def send_feedback(self, message):
        return self._request("POST", "/api/feedback", {"message": str(message)})

    def send_friend_request(self, recipient_id):
        return self._request("POST", f"/api/friends/requests/{int(recipient_id)}")
    def accept_friend_request(self, request_id): return self._request("POST", f"/api/friends/requests/{int(request_id)}/accept")
    def reject_friend_request(self, request_id): return self._request("POST", f"/api/friends/requests/{int(request_id)}/reject")
    def cancel_friend_request(self, request_id): return self._request("DELETE", f"/api/friends/requests/{int(request_id)}")

    def wallet(self):
        return self._request("GET", "/api/wallet")

    def list_rooms(self):
        return self._request("GET", "/api/rooms")

    def create_room(self, game="UNO"):
        return self._request("POST", "/api/rooms", {"game": game})

    def get_room(self, room_id):
        return self._request("GET", f"/api/rooms/{room_id}")

    def join_room(self, room_id, as_spectator: bool = False):
        url = f"/api/rooms/{room_id}/join"
        if as_spectator:
            url += "?as_spectator=true"
        return self._request("POST", url)

    def leave_room(self, room_id):
        return self._request("POST", f"/api/rooms/{room_id}/leave")

    def add_bot(self, room_id):
        return self._request("POST", f"/api/rooms/{room_id}/bot")

    def remove_bot(self, room_id):
        return self._request("POST", f"/api/rooms/{room_id}/bot/remove")

    def start_game(self, room_id, target_score=500, rules=None):
        return self._request("POST", f"/api/rooms/{room_id}/start", {"target_score": int(target_score), "rules": dict(rules or {})})

    def stop_game(self, room_id):
        return self._request("POST", f"/api/rooms/{room_id}/stop")

    def kick_player(self, room_id: str, target_user_id: int):
        return self._request("POST", f"/api/rooms/{room_id}/kick", {"target_user_id": int(target_user_id)})

    def ban_player(self, room_id: str, target_user_id: int):
        return self._request("POST", f"/api/rooms/{room_id}/ban", {"target_user_id": int(target_user_id)})

    def transfer_host(self, room_id: str, target_user_id: int):
        return self._request("POST", f"/api/rooms/{room_id}/transfer_host", {"target_user_id": int(target_user_id)})

    def set_co_host(self, room_id: str, target_user_id: int):
        return self._request("POST", f"/api/rooms/{room_id}/set_co_host", {"target_user_id": int(target_user_id)})

    def substitute_player(self, room_id: str, target_user_id: int, replacement_user_id: Optional[int] = None, is_bot: bool = False):
        payload = {"target_user_id": int(target_user_id), "is_bot": bool(is_bot)}
        if replacement_user_id is not None:
            payload["replacement_user_id"] = int(replacement_user_id)
        return self._request("POST", f"/api/rooms/{room_id}/substitute", payload)

    def voice_mute_player(self, room_id: str, target_user_id: int):
        return self._request("POST", f"/api/rooms/{room_id}/voice/mute", {"target_user_id": int(target_user_id)})

    def voice_kick_player(self, room_id: str, target_user_id: int):
        return self._request("POST", f"/api/rooms/{room_id}/voice/kick", {"target_user_id": int(target_user_id)})

    def voice_ban_player(self, room_id: str, target_user_id: int):
        return self._request("POST", f"/api/rooms/{room_id}/voice/ban", {"target_user_id": int(target_user_id)})

    def set_voice_mode(self, room_id: str, mode: str):
        return self._request("POST", f"/api/rooms/{room_id}/voice/mode", {"mode": str(mode)})

    def toggle_spectator(self, room_id: str, target_user_id: Optional[int] = None):
        payload = {"target_user_id": int(target_user_id)} if target_user_id is not None else {}
        return self._request("POST", f"/api/rooms/{room_id}/spectator", payload)

    def toggle_room_privacy(self, room_id: str):
        return self._request("POST", f"/api/rooms/{room_id}/privacy")

    def save_room(self, room_id: str):
        return self._request("POST", f"/api/rooms/{room_id}/save")

    def list_saved_tables(self):
        return self._request("GET", "/api/rooms/saved")

    def delete_saved_table(self, saved_id: int):
        return self._request("DELETE", f"/api/rooms/saved/{int(saved_id)}")

    def restore_saved_table(self, saved_id: int):
        return self._request("POST", f"/api/rooms/saved/{int(saved_id)}/restore")

    def game_state(self, room_id: str):
        return self._request("GET", f"/api/rooms/{room_id}/game/state")

    def game_action(self, room_id: str, action: str, data: dict = None, card_id: str = "", chosen_color: str = "", target_player_id: str = ""):
        payload = {"action": action, "data": data or {}, "card_id": card_id, "chosen_color": chosen_color, "target_player_id": target_player_id}
        return self._request("POST", f"/api/rooms/{room_id}/game/action", payload=payload)

    # --- Unified Architecture Aliases ---
    def uno_state(self, room_id: str): return self.game_state(room_id)
    def thief_state(self, room_id: str): return self.game_state(room_id)
    def farkle_state(self, room_id: str): return self.game_state(room_id)
    def domino_state(self, room_id: str): return self.game_state(room_id)
    def american_domino_state(self, room_id: str): return self.game_state(room_id)
    def snakes_state(self, room_id: str): return self.game_state(room_id)
    def scopa_state(self, room_id: str): return self.game_state(room_id)
    def tennis_state(self, room_id: str): return self.game_state(room_id)
    def ninety_nine_state(self, room_id: str): return self.game_state(room_id)

    def uno_action(self, room_id: str, action: str, card_id: str = "", chosen_color: str = ""):
        return self.game_action(room_id, action, card_id=card_id, chosen_color=chosen_color)
    def thief_action(self, room_id: str, action: str, card_id: str = ""):
        return self.game_action(room_id, action, card_id=card_id)
    def farkle_action(self, room_id: str, action: str, value: str = ""):
        # farkle uses action='roll' or 'bank', no card_id, but the signature from client app passes value?
        # self.api.farkle_action(rid, action, value) - wait, value is ignored in backend, let's just pass it in data
        return self.game_action(room_id, action, data={"value": value})
    def domino_action(self, room_id: str, action: str, card_id: str = "", chosen_color: str = ""):
        # Client passes side in chosen_color parameter for domino
        return self.game_action(room_id, action, card_id=card_id, data={"side": chosen_color})
    def american_domino_action(self, room_id: str, action: str, card_id: str = "", chosen_color: str = ""):
        return self.game_action(room_id, action, card_id=card_id, data={"side": chosen_color})
    def scopa_action(self, room_id: str, action: str, card_index: str = "", choice_idx: str = ""):
        return self.game_action(room_id, action, card_id=card_index, data={"choice_idx": choice_idx})
    def snakes_action(self, room_id: str, action: str):
        return self.game_action(room_id, action)
    def tennis_action(self, room_id: str, action: str, data: dict = None):
        return self.game_action(room_id, action, data=data)
    def ninety_nine_action(self, room_id: str, action: str, card_id: str = "", target_player_id: str = ""):
        return self.game_action(room_id, action, card_id=card_id, target_player_id=target_player_id)
    def user_profile(self, user_id): return self._request("GET", f"/api/users/{int(user_id)}/profile")
    def update_my_profile(self, display_name=None, gender=None, bio=None): return self._request("PUT", "/api/users/me/profile", {"display_name": display_name, "gender": gender, "bio": bio})
    def delete_my_account(self): return self._request("DELETE", "/api/users/me")
    def head_to_head(self, user_id): return self._request("GET", f"/api/users/{int(user_id)}/head-to-head")
    def send_private_message(self, user_id, message): return self._request("POST", f"/api/users/{int(user_id)}/messages", {"message": str(message)})
    def get_mutes(self, user_id): return self._request("GET", f"/api/users/{int(user_id)}/mutes")
    def set_mutes(self, user_id, flags): return self._request("PUT", f"/api/users/{int(user_id)}/mutes", dict(flags or {}))
    def unfriend(self, user_id): return self._request("DELETE", f"/api/friends/{int(user_id)}")
    def block_user(self, user_id): return self._request("POST", f"/api/users/{int(user_id)}/block")
    def unblock_user(self, user_id): return self._request("DELETE", f"/api/users/{int(user_id)}/block")
    def blocked_users(self): return self._request("GET", "/api/users/blocked")
    def update_privacy(self, payload: dict): return self._request("PUT", "/api/users/me/privacy", dict(payload or {}))
    def _put(self, path: str, json: Optional[dict] = None):
        p = path if path.startswith("/api") else f"/api{path}"
        return self._request("PUT", p, json)
    def challenge_user(self, user_id, game="UNO"): return self._request("POST", f"/api/users/{int(user_id)}/challenge", {"game": str(game)})
    def invite_user_to_room(self, user_id, room_id): return self._request("POST", f"/api/rooms/{str(room_id)}/invite/{int(user_id)}")
    def gift_user(self, user_id, amount): return self._request("POST", f"/api/users/{int(user_id)}/gift", {"amount": int(amount)})
    def search_users(self, username):
        from urllib.parse import quote
        return self._request("GET", f"/api/users/search?q={quote(str(username))}")
    def private_messages(self, limit=100): return self._request("GET", f"/api/messages?limit={int(limit)}")
    def notifications(self, limit=100): return self._request("GET", f"/api/notifications?limit={int(limit)}")
    def accept_challenge(self, invitation_id): return self._request("POST", f"/api/invitations/{int(invitation_id)}/accept")
    def reject_challenge(self, invitation_id): return self._request("POST", f"/api/invitations/{int(invitation_id)}/reject")
