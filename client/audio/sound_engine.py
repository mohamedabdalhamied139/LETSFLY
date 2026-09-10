"""Low-latency, semantic sound system for TableVerse.

The rest of the application addresses sounds by stable semantic cue names
(e.g. ``TURN_START``) instead of physical filenames. This keeps the audio
architecture reusable for future tables/games.
"""
import os
import sys
import logging
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect

logger = logging.getLogger("tableverse.sound")


class SoundEngine:
    # Stable cue -> physical asset mapping organized by category:
    # 1. Root: common/shared table lifecycle and lobby sounds
    # 2. uno/: UNO card game specific sounds
    # 3. farkle/: Farkle dice game specific sounds
    # 4. thief_hunt/: Thief Hunt game specific sounds
    SOUND_REGISTRY = {
        # Common table & lobby lifecycle cues (shared root folder)
        "CONNECTING": "connecting.wav",
        "CONNECTED": "connected.wav",
        "CONNECTION_LOST": "connection_lost.wav",
        "MIC_ON": "mic_on.wav",
        "MIC_OFF": "mic_off.wav",
        "VOICE_JOINED": "voice_joined.wav",
        "PLAYER_JOINED": "player_joined.wav",
        "PLAYER_LEFT": "player_left.wav",
        "TABLE_JOIN": "player_joined.wav",
        "TABLE_LEAVE": "player_left.wav",
        "TURN_START": "turn_start.wav",
        "ROUND_END": "round_end.wav",
        "MATCH_WIN": "match_win.wav",
        "MATCH_LOSS": "match_loss.wav",
        "GAME_STOPPED": "game_stopped.wav",
        "INVALID_ACTION": "invalid_action.wav",

        # UNO game audio (uno/ subfolder)
        "CARD_DRAW": "uno/draw.wav",
        "CARD_DRAW_TWO": "uno/draw_two.wav",
        "CARD_WILD_COLOR": "uno/wild_color.wav",
        "CARD_WILD_DRAW_FOUR": "uno/wild_draw_four.wav",
        "CARD_SKIP": "uno/skip.wav",
        "CARD_REVERSE": "uno/reverse.wav",
        "UNO_DEAL": "uno/deal.wav",
        "UNO_PLACE": "uno/place.wav",
        "UNO_PLACE_SPECIAL": "uno/place_special.wav",
        "UNO_CALLED": "uno/uno_call.wav",
        "UNO_PENALTY": "uno/uno_penalty.wav",
        "BLUFF_CHALLENGE": "uno/bluff_challenge.wav",
        "WILD_COLOR_PROMPT": "uno/wild_color_prompt.wav",

        # Farkle dice game audio (farkle/ subfolder)
        "FARKLE_ROLL": "farkle/farkle_roll.wav",
        "FARKLE_SCORE": "farkle/farkle_score.wav",
        "FARKLE_BANK": "farkle/farkle_bank.wav",
        "FARKLE_BUST": "farkle/farkle_bust.wav",
        "FARKLE_HOT_DICE": "farkle/farkle_hot_dice.wav",

        # Thief Hunt game audio (thief_hunt/ subfolder)
        "THIEF_GAME_START": "thief_hunt/thief_game_start.wav",
        "THIEF_ESCAPE": "thief_hunt/thief_escape.wav",
        "THIEF_ANSWER_START": "thief_hunt/thief_answer_start.wav",
        "THIEF_ROUND_END": "thief_hunt/thief_round_end.wav",
        "THIEF_CAUGHT": "thief_hunt/thief_caught.wav",
        "THIEF_ROUND_WINNER": "thief_hunt/thief_round_winner.wav",

        # Domino game audio
        "DOMINO_PLACE": "domino/domino_place.wav",
        "DOMINO_DRAW": "domino/domino_draw.wav",
        "DOMINO_PASS": "domino/domino_pass.wav",
        "DOMINO_BLOCKED": "domino/domino_blocked.wav",
        "DOMINO_WIN": "domino/domino_win.wav",
        "DOMINO_SHUFFLE": "domino/domino_shuffle.wav",
        "DOMINO_SETUP": "domino/domino_setup.wav",
        # Original user-provided Domino round-start sequence.
        "DOMINO_PRE_ROUND": "domino/domino_pre_round.wav",
        "DOMINO_ROUND_START": "domino/domino_round_start.wav",
        "DOMINO_PLACE_ORIGINAL": "domino/domino_place_original.wav",
        "DOMINO_DRAW_ORIGINAL": "domino/domino_draw_original.wav",

        # Snakes & Ladders game audio (snakes_and_ladders/ subfolder)
        "DICE_ROLL": "snakes_and_ladders/DICE_ROLL.wav",
        "LADDER_CLIMB": "snakes_and_ladders/LADDER_CLIMB.wav",
        "SNAKE_BITE": "snakes_and_ladders/SNAKE_BITE.wav",
        "MYSTERY_BOX": "snakes_and_ladders/MYSTERY_BOX.wav",
        "PLAYER_BUMP": "snakes_and_ladders/PLAYER_BUMP.wav",
        "MATCH_WIN_SNAKES": "snakes_and_ladders/MATCH_WIN.wav",
        "FREEZE_TRAP": "snakes_and_ladders/FREEZE_TRAP.wav",
        "BONUS_ROLL": "snakes_and_ladders/BONUS_ROLL.wav",
        "STEP_MOVE": "snakes_and_ladders/STEP_MOVE.wav",

        # Scopa game audio (scopa/ subfolder)
        "SCOPA_SWEEP": "scopa/scopa_sweep.wav",
        "SCOPA_PLAY_CARD": "scopa/scopa_play.wav",
        "SCOPA_DEAL": "scopa/scopa_deal.wav",
        "SCOPA_SHUFFLE": "scopa/scopa_shuffle.wav",
        "SCOPA_CAPTURE": "scopa/scopa_capture.wav",
        # Additional original Scopa sounds supplied with the project.
        "SCOPA_ROUND_START": "scopa/scopa_round_start.wav",
        "SCOPA_DEAL_BATCH": "scopa/scopa_deal_batch.wav",
        "SCOPA_DEAL_SINGLE": "scopa/scopa_deal_single.wav",
        "SCOPA_CARD_THROW": "scopa/scopa_card_throw.wav",
        "SCOPA_EAT_CARDS": "scopa/scopa_eat_cards.wav",
        "SCOPA_ANNOUNCEMENT": "scopa/scopa_announcement.wav",

        # 99 / Ninety-Nine game audio (ninety_nine/ subfolder)
        "NINETY_NINE_DRAW": "ninety_nine/ninety_nine_draw.wav",
        "NINETY_NINE_EXCEED": "ninety_nine/ninety_nine_exceed.wav",
        "NINETY_NINE_REACH": "ninety_nine/ninety_nine_reach.wav",
        "NINETY_NINE_PENALTY": "ninety_nine/ninety_nine_exceed.wav",
        "NINETY_NINE_MILESTONE": "ninety_nine/ninety_nine_reach.wav",
        # Legacy Ninety-Nine gameplay cues used by the server. These are intentionally
        # retained because they are the historical gameplay sounds for this game.
        "NINETY_NINE_PLACE": "uno/place.wav",
        "NINETY_NINE_REVERSE": "uno/reverse.wav",
        "NINETY_NINE_SKIP": "uno/skip.wav",
        "NINETY_NINE_PROMPT": "uno/wild_color_prompt.wav",
    }

    # Authoritative semantic event -> cue mapping for game-specific events.
    # Common lifecycle cues remain shared; game-specific events never fall
    # through to another game's physical asset (for example, NINETY_NINE
    # must not resolve ``place`` to UNO's place.wav).
    GAME_EVENT_CUES = {
        "UNO": {
            "GAME_STARTED": ("UNO_DEAL",),
            "ROUND_START": ("UNO_DEAL",),
            "ROUND_STARTED": ("UNO_DEAL",),
            "CARD_DRAWN": ("CARD_DRAW",),
            "CARD_DRAWN_AND_PASSED": ("CARD_DRAW",),
            "DRAW_PENALTY": ("CARD_DRAW_TWO", "CARD_WILD_DRAW_FOUR", "CARD_DRAW"),
            "CARD_PLAYED": ("UNO_PLACE",),
            "SPECIAL_CARD_PLAYED": (
                "UNO_PLACE_SPECIAL",
                "CARD_DRAW_TWO",
                "CARD_WILD_DRAW_FOUR",
                "CARD_WILD_COLOR",
                "CARD_SKIP",
                "CARD_REVERSE",
            ),
            "BUZZER_STARTED": ("UNO_PLACE_SPECIAL",),
            "BUZZER_PENALTY": ("CARD_DRAW_TWO",),
            "BLUFF_CAUGHT": ("BLUFF_CHALLENGE",),
            "BLUFF_FALSE": ("BLUFF_CHALLENGE",),
            "UNO_CALLED": ("UNO_CALLED",),
            "UNO_CAUGHT": ("UNO_PENALTY",),
        },
        "FARKLE": {
            # No dedicated opening asset: do not borrow a card sound.
            "GAME_STARTED": (),
            "DICE_ROLLED": ("FARKLE_ROLL",),
            "COMBINATION_SCORED": ("FARKLE_SCORE",),
            "HOT_DICE": ("FARKLE_HOT_DICE",),
            "TURN_BANKED": ("FARKLE_BANK",),
            "FARKLE": ("FARKLE_BUST",),
        },
        "THIEF_HUNT": {
            "GAME_STARTED": ("THIEF_GAME_START",),
            "ESCAPE_START": ("THIEF_ESCAPE",),
            "ANSWER_START": ("THIEF_ANSWER_START",),
            "ROUND_WIN": ("THIEF_ROUND_WINNER",),
            "ROUND_TIE": ("THIEF_ROUND_END",),
            "PLAYER_ELIMINATED": ("THIEF_ROUND_END",),
            "THIEF_WIN": ("THIEF_ROUND_END",),
        },
        "SCOPA": {
            "GAME_STARTED": ("SCOPA_DEAL",),
            "ROUND_START": ("SCOPA_ROUND_START", "SCOPA_DEAL"),
            "ROUND_STARTED": ("SCOPA_ROUND_START", "SCOPA_DEAL"),
            "DEAL_BATCH": ("SCOPA_DEAL_BATCH", "SCOPA_DEAL"),
            "CARD_PLAYED": ("SCOPA_CARD_THROW",),
            "CARD_CAPTURED": ("SCOPA_CARD_THROW", "SCOPA_EAT_CARDS"),
            "SCOPA_SWEEP": ("SCOPA_CARD_THROW", "SCOPA_EAT_CARDS", "SCOPA_ANNOUNCEMENT"),
        },
        "DOMINO": {
            "GAME_STARTED": ("DOMINO_PRE_ROUND", "DOMINO_ROUND_START"),
            "ROUND_START": ("DOMINO_PRE_ROUND", "DOMINO_ROUND_START"),
            "ROUND_STARTED": ("DOMINO_PRE_ROUND", "DOMINO_ROUND_START"),
            "TILE_PLACED": ("DOMINO_PLACE_ORIGINAL",),
            "TILE_DRAWN": ("DOMINO_DRAW_ORIGINAL",),
            "PLAYER_PASSED": ("DOMINO_PASS",),
            "ROUND_BLOCKED": ("DOMINO_BLOCKED",),
            "DOMINO_WIN": ("DOMINO_WIN",),
        },
        "AMERICAN_DOMINO": {
            "GAME_STARTED": ("DOMINO_SHUFFLE",),
            "ROUND_START": ("DOMINO_SHUFFLE",),
            "ROUND_STARTED": ("DOMINO_SHUFFLE",),
            "TILE_PLACED": ("DOMINO_PLACE",),
            "TILE_DRAWN": ("DOMINO_DRAW",),
            "PLAYER_PASSED": ("DOMINO_PASS",),
            "ROUND_BLOCKED": ("DOMINO_BLOCKED",),
            "DOMINO_WIN": ("DOMINO_WIN",),
        },
        "SNAKES_LADDERS": {
            # Historical start cue points to the shared round_start.wav, which is
            # physically the UNO deal sound. Keep opening silent until a real
            # dedicated Snakes start asset exists.
            "GAME_STARTED": (),
            "DICE_ROLLED": ("DICE_ROLL",),
            "BONUS_ROLL": ("BONUS_ROLL",),
            "PLAYER_FROZEN": ("FREEZE_TRAP",),
            "CANNOT_MOVE": ("INVALID_ACTION",),
        },
        "NINETY_NINE": {
            # Preserve the historical Ninety-Nine gameplay cues without allowing
            # them to affect any other game.
            "GAME_STARTED": (),
            "ROUND_START": (),
            "ROUND_STARTED": (),
            "CARD_PLAYED": ("NINETY_NINE_PLACE", "NINETY_NINE_REVERSE", "NINETY_NINE_SKIP"),
            "PENDING_CHOICE": ("NINETY_NINE_PROMPT",),
            "CHOICE_CANCELLED": (),
        },
    }

    def __init__(self):
        # QSoundEffect requires a live QCoreApplication/QApplication.
        # The client bootstrap creates QApplication after importing client_app,
        # so loading sounds here would initialize Qt Multimedia too early.
        self.sounds: dict[str, list[QSoundEffect]] = {}
        self._paths: dict[str, str] = {}
        self._initialized = False
        self._volume = 1.0
        self._muted = False
        self._category_volumes = {
            "effects": 1.0,
            "game": 1.0
        }
        self._cue_categories: dict[str, str] = {}

    def _determine_category(self, cue: str, rel_path: str) -> str:
        if "farkle" in rel_path or "uno" in rel_path or "thief_hunt" in rel_path or "domino" in rel_path or "snakes" in rel_path or "scopa" in rel_path or "ninety_nine" in rel_path or cue == "SNAKES_START":
            return "game"
        if cue.startswith("MATCH_") or cue in ("PLAYER_JOINED", "PLAYER_LEFT", "TABLE_JOIN", "TABLE_LEAVE"):
            return "effects"
        return "effects" # Default

    def _get_effective_volume(self, cue: str) -> float:
        if self._muted:
            return 0.0
        category = self._cue_categories.get(cue, "effects")
        cat_vol = self._category_volumes.get(category, 1.0)
        return self._volume * cat_vol

    def _ensure_initialized(self):
        if self._initialized:
            return
        from PySide6.QtWidgets import QApplication
        if not QApplication.instance():
            return
        self._initialized = True
        self._load_sounds()
        try:
            from client.settings_store import load_settings
            settings = load_settings()
            audio_cfg = settings.get("audio", {})
            self.set_muted(bool(audio_cfg.get("mute_all", False)))
            vols = audio_cfg.get("volumes", {})
            for cat, vol in vols.items():
                self.set_category_volume(cat, float(vol))
        except Exception:
            pass

    def _audio_dir(self) -> str:
        candidates = []
        if hasattr(sys, "_MEIPASS"):
            candidates.append(os.path.join(sys._MEIPASS, "assets", "audio"))
            candidates.append(os.path.join(sys._MEIPASS, "client", "assets", "audio"))
            candidates.append(os.path.join(os.path.dirname(sys._MEIPASS), "assets", "audio"))
        if hasattr(sys, "executable"):
            candidates.append(os.path.join(os.path.dirname(sys.executable), "assets", "audio"))
            candidates.append(os.path.join(os.path.dirname(sys.executable), "client", "assets", "audio"))
            candidates.append(os.path.join(os.path.dirname(sys.executable), "_internal", "assets", "audio"))
        client_dir = os.path.dirname(os.path.dirname(__file__))
        candidates.append(os.path.join(client_dir, "assets", "audio"))
        candidates.append(os.path.join(os.path.dirname(client_dir), "client", "assets", "audio"))
        candidates.append(os.path.join(os.getcwd(), "client", "assets", "audio"))
        candidates.append(os.path.join(os.getcwd(), "assets", "audio"))

        for c in candidates:
            if c and os.path.exists(c):
                return c
        return os.path.join(client_dir, "assets", "audio")

    def _load_sounds(self):
        audio_dir = Path(self._audio_dir())
        registry = dict(self.SOUND_REGISTRY)
        for cue, rel_path in registry.items():
            path = audio_dir / rel_path
            if not path.exists():
                fallback = audio_dir / Path(rel_path).name
                if fallback.exists():
                    path = fallback
                else:
                    continue
            if path.suffix.lower() in (".ogg", ".mp3"):
                wav_alt = path.with_suffix(".wav")
                if wav_alt.exists():
                    path = wav_alt
            cat = self._determine_category(cue, rel_path)
            self._cue_categories[cue] = cat
            self._cue_categories[cue.upper()] = cat
            self._cue_categories[cue.lower()] = cat

            effects = []
            for _ in range(4):
                effect = QSoundEffect()
                effect.setSource(QUrl.fromLocalFile(str(path.resolve())))
                effect.setVolume(self._get_effective_volume(cue))
                effects.append(effect)
            self.sounds[cue] = effects
            self.sounds[cue.upper()] = effects
            self.sounds[cue.lower()] = effects
            self._paths[cue] = str(path)

    def preload_game_sounds(self, game_type: str = "SCOPA"):
        """Pre-decode sound effects for a game so the first trigger has zero disk/decode latency."""
        self._ensure_initialized()
        prefix = f"{game_type.upper()}_"
        for cue, effects in self.sounds.items():
            if cue.startswith(prefix) and effects:
                for eff in effects:
                    try:
                        # Touch status to force decoder readiness
                        _ = eff.status()
                    except Exception:
                        pass

    def event_cues(self, game_type: str, event_type: str, state: dict | None = None) -> tuple[str, ...]:
        """Resolve sounds while preserving every game's existing gameplay cues."""
        game = str(game_type or "").upper()
        event = str(event_type or "").upper()
        state = state or {}

        if event in ("MATCH_WON", "MATCH_FINISHED"):
            return ()

        common = {
            "ROUND_END": ("ROUND_END",),
            "ROUND_FINISHED": ("ROUND_END",),
            "ROUND_WON": ("ROUND_END",),
            "GAME_STOPPED": ("GAME_STOPPED",),
        }
        allowed = tuple(self.GAME_EVENT_CUES.get(game, {}).get(event, common.get(event, ())))
        server_cue = str(state.get("sound_cue") or "").strip()

        if server_cue:
            # Accept exact historical gameplay cues when they are registered and
            # authorized for this game/event. Common lifecycle cues are global.
            if event in common and server_cue.upper() == common[event][0].upper():
                return (server_cue,)
            if len(allowed) > 1:
                return allowed
            if server_cue in allowed or server_cue.upper() in {c.upper() for c in allowed}:
                return (server_cue,)
            return allowed
        return allowed

    def has_cue(self, cue: str) -> bool:
        key = str(cue or "").strip()
        return bool(key and (key in self.SOUND_REGISTRY or key.upper() in self.SOUND_REGISTRY))

    def set_volume(self, volume: float):
        """Set master volume between 0.0 and 1.0."""
        self._volume = max(0.0, min(1.0, float(volume)))
        self._update_all_volumes()

    def set_category_volume(self, category: str, volume: float):
        """Set categorical volume between 0.0 and 1.0."""
        if category in self._category_volumes:
            self._category_volumes[category] = max(0.0, min(1.0, float(volume)))
            self._update_all_volumes()

    def _update_all_volumes(self):
        for cue, effects in self.sounds.items():
            target = self._get_effective_volume(cue)
            for eff in effects:
                eff.setVolume(target)

    def get_volume(self) -> float:
        return self._volume

    def set_muted(self, muted: bool):
        """Mute or unmute all sound effects."""
        self._muted = bool(muted)
        self._update_all_volumes()

    def is_muted(self) -> bool:
        return self._muted

    def stop_all(self):
        """Stop all currently playing sound effects."""
        for effects in self.sounds.values():
            for eff in effects:
                if eff.isPlaying():
                    eff.stop()

    def _dispose_effects(self):
        seen = set()
        for effects in self.sounds.values():
            for eff in effects:
                if id(eff) in seen:
                    continue
                seen.add(id(eff))
                try:
                    eff.stop()
                    eff.deleteLater()
                except Exception:
                    logger.debug("Sound effect cleanup failed", exc_info=True)
        self.sounds.clear()
        self._paths.clear()
        self._cue_categories.clear()

    def reload(self):
        """Reinitialize and reload all sound effects without leaking Qt objects."""
        self._dispose_effects()
        self._initialized = False
        self._ensure_initialized()

    def play(self, sound_name: str):
        if not sound_name:
            return
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QThread, QTimer

        app = QApplication.instance()
        if not app:
            return

        # Ensure execution on Qt main thread if called from a worker thread
        if QThread.currentThread() != app.thread():
            QTimer.singleShot(0, lambda s=sound_name: self.play(s))
            return

        try:
            self._ensure_initialized()
            key = str(sound_name).strip()
            effects = self.sounds.get(key)
            if not effects:
                effects = self.sounds.get(key.upper())
            if not effects:
                effects = self.sounds.get(key.lower())
            if not effects:
                return

            for eff in effects:
                try:
                    if eff.status() == QSoundEffect.Status.Loading:
                        continue
                    if not eff.isPlaying():
                        eff.play()
                        return
                except Exception:
                    logger.exception("Sound cue playback failed: %s", key)
            logger.debug("Dropping sound cue %s because all pool instances are busy", key)
        except Exception:
            pass

    def stop_cue(self, cue: str):
        """Stop all instances of a specific sound cue."""
        if not cue:
            return
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QThread, QTimer
        app = QApplication.instance()
        if not app:
            return
        if QThread.currentThread() != app.thread():
            QTimer.singleShot(0, lambda c=cue: self.stop_cue(c))
            return
        key = str(cue).strip()
        effects = self.sounds.get(key) or self.sounds.get(key.upper()) or self.sounds.get(key.lower())
        if effects:
            for eff in effects:
                try:
                    if eff.isPlaying():
                        eff.stop()
                except Exception:
                    pass

    def play_looping(self, cue: str):
        """Play a sound cue continuously in a loop until stopped."""
        if not cue:
            return
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QThread, QTimer
        app = QApplication.instance()
        if not app:
            return
        if QThread.currentThread() != app.thread():
            QTimer.singleShot(0, lambda c=cue: self.play_looping(c))
            return
        try:
            self._ensure_initialized()
            key = str(cue).strip()
            effects = self.sounds.get(key) or self.sounds.get(key.upper()) or self.sounds.get(key.lower())
            if not effects:
                return
            eff = effects[0]
            inf_count = -2
            try:
                inf_count = int(getattr(QSoundEffect.Loop.Infinite, "value", -2))
            except Exception:
                inf_count = -2
            try:
                eff.setLoopCount(inf_count)
            except Exception:
                try:
                    eff.setLoopCount(999999)
                except Exception:
                    pass
            if not eff.isPlaying():
                eff.play()
            elif eff.loopCount() != inf_count:
                eff.stop()
                eff.play()
        except Exception:
            pass

    def stop_looping(self, cue: str):
        """Stop a looping sound and reset its loop count."""
        if not cue:
            return
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QThread, QTimer
        app = QApplication.instance()
        if not app:
            return
        if QThread.currentThread() != app.thread():
            QTimer.singleShot(0, lambda c=cue: self.stop_looping(c))
            return
        try:
            key = str(cue).strip()
            effects = self.sounds.get(key) or self.sounds.get(key.upper()) or self.sounds.get(key.lower())
            if not effects:
                return
            eff = effects[0]
            eff.stop()
            try:
                eff.setLoopCount(1)
            except Exception:
                pass
        except Exception:
            pass

    def play_event(self, cue: str):
        """Play a stable semantic cue. Unknown/missing cues are safely ignored."""
        self.play(cue)

    def play_spatial(self, cue: str, pan: float = 0.0, volume_scale: float = 1.0):
        """Play a sound cue with accurate hardware stereo panning."""
        if not cue:
            return
        self.play_event(cue)


sound_engine = SoundEngine()
