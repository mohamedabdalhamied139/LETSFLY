"""Notification policy mapping based on user settings."""
from client import settings_store

def handle_event(category: str, text: str, cue: str, interrupt: bool = False):
    from client.localization import tr
    """
    Handle an event based on user speech settings.
    category must be one of:
    - friends
    - invitations
    - table_chat
    - private_messages
    - game_events
    """
    settings = settings_store.load_settings()
    speech_cfg = settings.get("speech", {})
    mute_speech = bool(speech_cfg.get("mute_all", False))

    modes = speech_cfg.get("modes", {})
    mode = modes.get(category, "speech_and_sound")

    if not mute_speech and mode in ("speech", "speech_and_sound"):
        if text:
            from client.accessibility.reader import reader
            reader.speak(tr(text), interrupt=interrupt)

    if mode in ("sound_only", "speech_and_sound"):
        if cue:
            from client.audio.sound_engine import sound_engine
            sound_engine.play(cue)

def handle_template_event(category: str, template: str, cue: str = "", interrupt: bool = False, **params):
    """Speak a localized template while keeping dynamic values untouched."""
    from client.localization import tr
    localized = tr(template, **params)
    settings = settings_store.load_settings()
    speech_cfg = settings.get("speech", {})
    if speech_cfg.get("mute_all", False):
        # Sounds still follow the configured mode below.
        mode = speech_cfg.get("modes", {}).get(category, "speech_and_sound")
    else:
        mode = speech_cfg.get("modes", {}).get(category, "speech_and_sound")
    if not speech_cfg.get("mute_all", False) and mode in ("speech", "speech_and_sound"):
        from client.accessibility.reader import reader
        if localized:
            reader.speak(localized, interrupt=interrupt)
    if mode in ("sound_only", "speech_and_sound") and cue:
        from client.audio.sound_engine import sound_engine
        sound_engine.play(cue)


def announce_game_event(text: str, cue: str = "", interrupt: bool = False):
    handle_event("game_events", text, cue, interrupt=interrupt)
