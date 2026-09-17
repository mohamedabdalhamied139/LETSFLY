"""
Exact port of TennisUserInterface.cs + spatial sound timeline from scify/LeapGame-tennis.

=== AUDIO-FIRST ACCESSIBILITY ===
  Gameplay is 100% audio-driven with spatial 3D stereo panning:
    - Left lane:   95% Left channel in headphones
    - Center lane: 50/50 Balanced center
    - Right lane:  95% Right channel in headphones

  Screen reader (NVDA) is kept completely quiet during active rallies so it does not
  interrupt or drown out the spatial audio cues. Announcements occur only when waiting
  to serve or on match conclusion.

=== KEYBOARD CONTROLS ===
  - Left Arrow (hold): Move Left  (plays jm_left.wav)
  - Right Arrow (hold): Move Right (plays jm_right.wav)
  - Release arrows: Auto-centers (plays jm_center.wav)
  - Any Key: Starts rally (serve)
"""

import time
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem

from client.audio.tennis_sound_engine import TennisSoundEngine
from client.localization import tr

LANE_LEFT   = -1
LANE_CENTER =  0
LANE_RIGHT  =  1


class TennisGameplayWidget(QListWidget):
    """
    Inner widget — captures arrow-key hold/release.
    Mimics Unity Input.GetKey() continuous polling at ~33fps.
    """
    positionChanged = Signal(int)   # emits -1, 0, +1
    keyPressed      = Signal()      # emits on any key press (for serve / anyKeyDown)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAccessibleName("")
        self.setAccessibleDescription("")
        self.setFocusPolicy(Qt.StrongFocus)

        raw_text = "ملعب التنس"
        disp_text = tr(raw_text)
        self._item = QListWidgetItem(disp_text)
        self._item.setData(Qt.UserRole + 1101, raw_text)
        self._item.setData(Qt.UserRole + 1102, disp_text)
        self.addItem(self._item)
        self.setCurrentRow(0)

        self._current_lane = LANE_CENTER

    def start_tracking(self):
        self._emit_position()

    def stop_tracking(self):
        pass

    def current_lane(self) -> int:
        """left=−1, center=0, right=+1."""
        return self._current_lane

    def _set_lane(self, lane: int):
        lane = max(LANE_LEFT, min(LANE_RIGHT, int(lane)))
        if self._current_lane != lane:
            self._current_lane = lane
            self._emit_position()

    def _emit_position(self):
        self.positionChanged.emit(self.current_lane())

    def set_status(self, text: str):
        # Update text without stealing focus
        self._item.setText(text)

    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            event.accept()
            return
        key = event.key()

        # TAB/SHIFT+TAB are intentionally NOT intercepted here.  Focus order
        # belongs to the shared TableView, which links gameplay -> chat ->
        # history -> gameplay for every game.  Intercepting Tab here creates
        # a second focus system and was the reason Tennis required Escape to
        # get back from chat.

        # Pass system keys to the normal widget/application handling.
        if key in (Qt.Key_Tab, Qt.Key_Backtab, Qt.Key_Escape, Qt.Key_Alt, Qt.Key_Control, Qt.Key_Shift, Qt.Key_Menu, Qt.Key_F10):
            super().keyPressEvent(event)
            return

        if key == Qt.Key_Left:
            self._set_lane(self._current_lane - 1)
            self.keyPressed.emit()
            event.accept()
            return
        elif key == Qt.Key_Right:
            self._set_lane(self._current_lane + 1)
            self.keyPressed.emit()
            event.accept()
            return
        elif key in (Qt.Key_Up, Qt.Key_Down):
            self._set_lane(LANE_CENTER)
            self.keyPressed.emit()
            event.accept()
            return

        # Allow default behavior for other keys so chat/shortcuts still work!
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.isAutoRepeat():
            event.accept()
            return
        key = event.key()
        if key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            event.accept()
            return
            
        super().keyReleaseEvent(event)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)

    def contextMenuEvent(self, event):
        win = self.window()
        if win and hasattr(win, "on_apps_key"):
            win.on_apps_key()
            event.accept()
            return
        super().contextMenuEvent(event)


class TennisGameWidget(TennisGameplayWidget):
    tennisActionSubmitted = Signal(str, dict)

    def __init__(self, room_id="", ws_manager=None, access_manager=None,
                 app_state=None, assets_dir=""):
        # Tennis is a normal shared-table gameplay control now, just like
        # the card/dice/domino gameplay lists.  There is no nested gameplay
        # window and no second focus layer.
        super().__init__()
        self.room_id   = room_id
        self.app_state = app_state or {}

        self.audio = TennisSoundEngine(assets_dir)

        # Game state
        self.game_state    = "WAITING"
        self.ball          = {}
        self.score         = {}
        self.players       = []
        self.local_idx     = 0
        self._prev_lane    = LANE_CENTER

        self.positionChanged.connect(self._on_position_changed)
        self.keyPressed.connect(self._on_key_pressed)
        # Compatibility alias used by the shared table framework.
        self.game_widget = self

    # ------------------------------------------------------------------ #
    # Key & Position events                                                #
    # ------------------------------------------------------------------ #

    def _on_key_pressed(self):
        """Serve when resting pause ends."""
        if self.game_state in ("SERVING", "WAITING"):
            server_idx = self.score.get("server_idx", 0)
            if server_idx is not None and int(server_idx) != self.local_idx:
                return  # Receiving players moving arrow keys must NOT trigger serve logic or premature UI transition
            if time.time() < getattr(self, "_can_serve_time", 0):
                return  # Still resting / applause in progress
            self.game_state = "IN_PLAY"
            self.tennisActionSubmitted.emit("serve", {"lane": self.current_lane()})

    def _on_position_changed(self, lane: int):
        """Called whenever lane changes or on tick."""
        if lane == self._prev_lane:
            return
        self._prev_lane = lane

        # Play spatial 'just moved' sound (jm_left, jm_center, jm_right)
        self.audio.play_move(lane)

        # Send position update to server so player is tracked during both serving and in-play
        self.tennisActionSubmitted.emit("position", {"lane": lane})

    # ------------------------------------------------------------------ #
    # Server event handler                                                 #
    # ------------------------------------------------------------------ #

    def handle_event(self, event_data: dict):
        if not isinstance(event_data, dict):
            return
        t = event_data.get("type")
        if t == "tennis_state_changed":
            self._sync(event_data.get("state", {}))
        elif t == "tennis_action_result":
            res = event_data.get("result") if "result" in event_data else event_data
            self._handle_action_result(res)
        elif t == "tennis_sound":
            self._handle_timed_sound(event_data)

    def _sync(self, state: dict):
        self.game_state = state.get("state", "WAITING")
        self.ball       = state.get("ball", {})
        self.score      = state.get("score", {})
        self.players    = state.get("players", [])

        win = self.window()
        user = getattr(win, "user", None) if win else None
        my_id = str((user or {}).get("id") or self.app_state.get("user_id", ""))
        for i, p in enumerate(self.players):
            if str(p.get("id")) == my_id:
                self.local_idx = i
                break

    # ------------------------------------------------------------------ #
    # Timed spatial sounds (net_pass, floor_hit) from server timeline      #
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    # Timed spatial sounds (floor_hit) from server timeline                #
    # ------------------------------------------------------------------ #

    def _handle_timed_sound(self, event: dict):
        """
        Server fires floor_hit at 50% midpoint of both player and opponent trips.
        Spatial & depth perspective:
          - Incoming ball (toward you): near loud bounce (vol=1.0) on your court lane.
          - Outgoing ball (toward opponent): distant bounce (vol=0.7) on opponent's court lane.
        """
        sound     = event.get("sound", "")
        lane      = event.get("lane", LANE_CENTER)
        direction = event.get("direction", 1)

        # Spatial perspective
        audio_lane = -lane if self.local_idx == 1 else lane

        if sound == "floor_hit":
            # Is ball coming toward local player or toward opponent?
            is_incoming = (direction == 1 and self.local_idx == 0) or (direction == -1 and self.local_idx == 1)
            # Outgoing bounce is far away on the opponent's side, so it should be much quieter!
            vol = 1.0 if is_incoming else 0.30
            self.audio.play_floor_hit(audio_lane, volume=vol)
        elif sound == "net_pass":
            self.audio.play_net_pass(audio_lane)

    # ------------------------------------------------------------------ #
    # Action result handler                                                #
    # ------------------------------------------------------------------ #

    def _handle_action_result(self, res: dict):
        if not isinstance(res, dict):
            return
        hit_type   = res.get("hit_type", "")
        player_idx = res.get("player_idx", 0)

        # === Serve / initial trajectory ===
        if hit_type == "" and res.get("sender") is not None:
            self._start_incoming_ball(res)
            return

        # === PLAYER HIT (bounce "racket") ===
        if hit_type == "racket":
            # If local player made this hit -> play racket strike
            if player_idx == self.local_idx:
                player_lane = self.current_lane()
                self.audio.play_racket_hit(player_lane)
            else:
                # Opponent made this hit -> play opponent strike (mirror for player 1)
                opp_target = res.get("ball", {}).get("target", 0)
                audio_target = -opp_target if self.local_idx == 1 else opp_target
                self.audio.play_opponent_hit(audio_target)

            self.game_state = "IN_PLAY"

            ball = res.get("ball", {})
            if ball:
                self.ball = ball
            return

        # === WALL BOUNCE (opponent_racket_hit) ===
        if hit_type == "wall":
            self._start_incoming_ball(res)
            return

        # === MISS / POINT SCORED (boundary) ===
        if hit_type == "boundary":
            sc     = res.get("score_result", {}).get("score", {})
            events = res.get("score_result", {}).get("events", [])
            
            pts = sc.get("points", {0: "0", 1: "0"})
            games = sc.get("games", {0: 0, 1: 0})
            sets = sc.get("sets", {0: 0, 1: 0})
            server_idx = sc.get("server_idx", 0)
            
            # Resolve local player index
            win = self.window()
            user = getattr(win, "user", None) if win else None
            my_id = str((user or {}).get("id") or self.app_state.get("user_id", ""))
            for i, p in enumerate(self.players):
                if str(p.get("id")) == my_id:
                    self.local_idx = i
                    break

            is_my_score = (player_idx != self.local_idx)

            p0_score = str(pts.get(0, pts.get("0", "0")))
            p1_score = str(pts.get(1, pts.get("1", "0")))

            is_tiebreak = bool(sc.get("tiebreak", False)) or ("tiebreak_point" in events)
            tb_pts = sc.get("tiebreak_points", {})

            # Play crowd applause / cheering on every goal/point entered
            if "match_won" in events:
                self.audio.play_crowd(2, volume=1.0)
                self.audio.play_match_won()
            elif "set_won" in events:
                self.audio.play_crowd(2, volume=1.0)
                self.audio.play_set_won()
            elif "game_won" in events:
                self.audio.play_crowd(2, volume=1.0)
                self.audio.play_game_won()
            elif is_my_score:
                self.audio.play_win()
                self.audio.play_score_announcement(p0_score, p1_score, server_idx, is_tiebreak=is_tiebreak, tiebreak_points=tb_pts)
            else:
                self.audio.play_miss()
                self.audio.play_score_announcement(p0_score, p1_score, server_idx, is_tiebreak=is_tiebreak, tiebreak_points=tb_pts)
                
            self.game_state = "SERVING"
            self._can_serve_time = time.time() + 4.5  # Rest period during applause

            if "state" in res:
                self._sync(res["state"])
            return

        # === Fallback: any trajectory with sender field ===
        if res.get("sender") is not None:
            self._start_incoming_ball(res)

    def _start_incoming_ball(self, res: dict):
        """
        Ball is heading toward player — plays spatial hit_2 (opponent return hit).
        """
        ball   = res.get("ball", {})
        sender = res.get("sender", 1)
        if ball:
            self.ball = ball
        self.game_state = "IN_PLAY"

        if sender == 1:
            target = ball.get("target", LANE_CENTER) if ball else LANE_CENTER
            audio_target = -target if self.local_idx == 1 else target
            self.audio.play_opponent_hit(audio_target)
