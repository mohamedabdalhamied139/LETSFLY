"""
Tennis Sound Engine — 3-lane discrete stereo panning and preloaded low-latency audio bank.

All WAV assets are pre-loaded at startup into ready QSoundEffect pools,
enabling rapid response and zero dropped sound effects.

Spatial Panning:
  - Lane -1 (Left):   Plays *_left.wav   (95% Left channel in headphones)
  - Lane  0 (Center): Plays *_center.wav (50/50 Balanced Center)
  - Lane +1 (Right):  Plays *_right.wav  (95% Right channel in headphones)
"""

import os
import random
from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QSoundEffect, QMediaPlayer, QAudioOutput


def _lane_suffix(lane: int) -> str:
    if lane < 0:
        return "left"
    elif lane > 0:
        return "right"
    return "center"


GAMEPLAY_SFX = [
    "jm_left.wav", "jm_center.wav", "jm_right.wav",
    "hit_1_left.wav", "hit_1_center.wav", "hit_1_right.wav",
    "hit_2_left.wav", "hit_2_center.wav", "hit_2_right.wav",
    "air_left.wav", "air_center.wav", "air_right.wav",
    "bounce_left.wav", "bounce_center.wav", "bounce_right.wav",
    "claps_1.wav", "claps_2.wav"
]


class TennisSoundEngine(QObject):
    def __init__(self, assets_dir: str = ""):
        super().__init__()
        if not assets_dir or not os.path.exists(assets_dir):
            client_dir = os.path.dirname(os.path.dirname(__file__))
            assets_dir = os.path.join(client_dir, "assets")
        self.assets_dir = assets_dir
        self.audio_dir  = os.path.join(assets_dir, "audio", "tennis")

        # Preloaded sound bank: key -> list of 4 preloaded QSoundEffect slots for instant polyphony
        self._banks: dict[str, list[QSoundEffect]] = {}
        self._bank_idx: dict[str, int] = {}
        self._preload_all_assets()

        # Sequential voice announcer
        self._umpire = QMediaPlayer(self)
        self._umpire_out = QAudioOutput(self)
        self._umpire.setAudioOutput(self._umpire_out)
        self._umpire_queue: list[str] = []
        self._umpire.playbackStateChanged.connect(self._umpire_next)

    def _preload_all_assets(self):
        """Pre-load essential WAV gameplay sounds into QSoundEffect pools."""
        if not os.path.exists(self.audio_dir):
            return

        for fname in GAMEPLAY_SFX:
            path = os.path.join(self.audio_dir, fname)
            if not os.path.exists(path):
                # Fallback to base filename without suffix if needed
                base = fname.replace("_left.wav", ".wav").replace("_right.wav", ".wav").replace("_center.wav", ".wav")
                path = os.path.join(self.audio_dir, base)
                if not os.path.exists(path):
                    continue

            url  = QUrl.fromLocalFile(path)

            slots = []
            for _ in range(4):
                eff = QSoundEffect(self)
                eff.setSource(url)
                eff.setVolume(1.0)
                slots.append(eff)

            self._banks[fname] = slots
            self._bank_idx[fname] = 0

    # ------------------------------------------------------------------ #
    # Core Helpers                                                         #
    # ------------------------------------------------------------------ #

    def _path(self, filename: str) -> str:
        return os.path.join(self.audio_dir, filename)

    def _play_sfx(self, filename: str, volume: float = 1.0):
        """Play preloaded sound effect instantly with polyphony and thread safety."""
        if not filename:
            return

        from client.audio.sound_engine import sound_engine
        if sound_engine.is_muted():
            return
        effective_volume = sound_engine.get_volume() * sound_engine._category_volumes.get("game", 1.0) * volume
        effective_volume = max(0.0, min(1.0, float(effective_volume)))

        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QThread, QTimer

        app = QApplication.instance()
        if not app:
            return

        if QThread.currentThread() != app.thread():
            QTimer.singleShot(0, lambda f=filename, v=volume: self._play_sfx(f, v))
            return

        slots = self._banks.get(filename)
        if not slots:
            base = filename.replace("_left.wav", ".wav").replace("_right.wav", ".wav").replace("_center.wav", ".wav")
            slots = self._banks.get(base)

        if not slots:
            p = os.path.join(self.audio_dir, filename)
            if not os.path.exists(p):
                base = filename.replace("_left.wav", ".wav").replace("_right.wav", ".wav").replace("_center.wav", ".wav")
                p = os.path.join(self.audio_dir, base)
            if os.path.exists(p):
                eff = QSoundEffect(self)
                eff.setSource(QUrl.fromLocalFile(p))
                eff.setVolume(effective_volume)
                eff.play()
                self._banks[filename] = [eff]
                self._bank_idx[filename] = 0
            return

        # Find an idle slot or least recently used slot
        target_eff = None
        for eff in slots:
            if not eff.isPlaying():
                target_eff = eff
                break

        if target_eff is None:
            idx = self._bank_idx.get(filename, 0)
            target_eff = slots[idx % len(slots)]
            self._bank_idx[filename] = idx + 1
            target_eff.stop()

        target_eff.setVolume(effective_volume)

        if target_eff.status() == QSoundEffect.Status.Loading:
            def _play_ready(e=target_eff):
                if e.status() == QSoundEffect.Status.Ready:
                    try:
                        e.statusChanged.disconnect(_play_ready)
                    except Exception:
                        pass
                    e.play()
            target_eff.statusChanged.connect(_play_ready)
        else:
            target_eff.play()

    def _queue_umpire(self, *filenames):
        """Queue voice clips to play sequentially without overlap."""
        for f in filenames:
            p = os.path.join(self.audio_dir, f)
            if not os.path.exists(p):
                alt = f.replace(".mp3", ".wav") if f.endswith(".mp3") else f.replace(".wav", ".mp3")
                p_alt = os.path.join(self.audio_dir, alt)
                if os.path.exists(p_alt):
                    p = p_alt
                else:
                    for sub in ("arabic_umpire", "arabic_commentary"):
                        sp = os.path.join(self.audio_dir, sub, f)
                        if os.path.exists(sp):
                            p = sp
                            break
                        sp_alt = os.path.join(self.audio_dir, sub, alt)
                        if os.path.exists(sp_alt):
                            p = sp_alt
                            break
            if os.path.exists(p):
                self._umpire_queue.append(p)
        if self._umpire.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self._umpire_next()

    def _umpire_next(self, state=None):
        if state is not None and state != QMediaPlayer.PlaybackState.StoppedState:
            return
        if self._umpire_queue:
            path = self._umpire_queue.pop(0)
            from client.audio.sound_engine import sound_engine
            if sound_engine.is_muted():
                self._umpire_out.setVolume(0.0)
            else:
                vol = sound_engine.get_volume() * sound_engine._category_volumes.get("game", 1.0)
                self._umpire_out.setVolume(max(0.0, min(1.0, float(vol))))
            self._umpire.setSource(QUrl.fromLocalFile(path))
            self._umpire.play()

    def play_score_announcement(self, p0_pts: str = "0", p1_pts: str = "0", server_idx: int = 0, is_tiebreak: bool = False, tiebreak_points: dict = None):
        """Announce current score in Arabic umpire voice or screen reader for tiebreak."""
        p0 = str(p0_pts).strip().upper()
        p1 = str(p1_pts).strip().upper()

        if is_tiebreak or (tiebreak_points is not None and (p0 == "0" and p1 == "0")):
            if tiebreak_points:
                tb0 = tiebreak_points.get(0, tiebreak_points.get("0", 0))
                tb1 = tiebreak_points.get(1, tiebreak_points.get("1", 0))
                try:
                    from client.accessibility.reader import reader
                    reader.speak(f"{tb0} - {tb1}")
                except Exception:
                    pass
            return

        if p0 == "0" and p1 == "0":
            return  # No score_0_0.wav exists in standard tennis audio assets

        if p0 == "AD" and p1 == "40":
            fname = "advantage_server.wav" if server_idx == 0 else "advantage_receiver.wav"
        elif p1 == "AD" and p0 == "40":
            fname = "advantage_server.wav" if server_idx == 1 else "advantage_receiver.wav"
        elif p0 == "40" and p1 == "40":
            fname = "deuce.wav"
        elif p0 == "15" and p1 == "15":
            fname = "score_15_all.wav"
        elif p0 == "30" and p1 == "30":
            fname = "score_30_all.wav"
        elif (p0, p1) in [
            ("0", "15"), ("0", "30"), ("0", "40"),
            ("15", "0"), ("15", "30"), ("15", "40"),
            ("30", "0"), ("30", "15"), ("30", "40"),
            ("40", "0"), ("40", "15"), ("40", "30")
        ]:
            fname = f"score_{p0}_{p1}.wav"
        else:
            return

        self._queue_umpire(fname)

    def play_game_won(self):
        """Announce game win."""
        self._queue_umpire("game_won.wav")

    def play_match_won(self):
        """Announce match win."""
        self._queue_umpire("match_won.wav")

    def play_set_won(self):
        """Announce set win."""
        self._queue_umpire("set_won.wav")

    # ------------------------------------------------------------------ #
    # Spatial Gameplay Sounds                                              #
    # ------------------------------------------------------------------ #

    def play_move(self, lane: int):
        """'just moved' sound — panned to left, center, or right."""
        suffix = _lane_suffix(lane)
        self._play_sfx(f"jm_{suffix}.wav", 0.75)

    def play_racket_hit(self, lane: int = 0):
        """'player_racket_hit' — player strikes the ball in their current lane."""
        suffix = _lane_suffix(lane)
        self._play_sfx(f"hit_1_{suffix}.wav", 1.0)

    def play_opponent_hit(self, lane: int = 0):
        """'opponent_racket_hit' — opponent/wall returns the ball in the target lane."""
        suffix = _lane_suffix(lane)
        self._play_sfx(f"hit_2_{suffix}.wav", 1.0)

    def play_net_pass(self, lane: int = 0):
        """'net_pass' — ball passes over net at court midpoint in specified lane."""
        suffix = _lane_suffix(lane)
        self._play_sfx(f"air_{suffix}.wav", 0.80)

    def play_floor_hit(self, lane: int = 0, volume: float = 1.0):
        """'floor_hit' — ball bounces on court floor in specified lane."""
        suffix = _lane_suffix(lane)
        self._play_sfx(f"bounce_{suffix}.wav", volume)

    def play_crowd(self, variant: int = 0, volume: float = 1.0):
        """Play crowd applause / cheering sound."""
        if variant == 1:
            fname = "claps_1.wav"
        elif variant == 2:
            fname = "claps_2.wav"
        else:
            fname = random.choice(["claps_1.wav", "claps_2.wav"])
        self._play_sfx(fname, volume)

    def play_point_scored(self, is_local_winner: bool = True):
        """Play crowd applause on every goal/point."""
        self.play_crowd(variant=1 if not is_local_winner else 2, volume=1.0)

    def play_miss(self):
        """Play crowd reaction on missed ball."""
        self.play_crowd(variant=1, volume=1.0)

    def play_win(self):
        """Play crowd applause on point win."""
        self.play_crowd(variant=2, volume=1.0)
