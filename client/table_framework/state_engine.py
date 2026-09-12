from client.notification_policy import announce_game_event
from PySide6.QtCore import QTimer
from client.audio.sound_engine import sound_engine
from client.accessibility.reader import reader
from client.localization import tr

class ClientStateEngine:
    @staticmethod
    def process_common_state(app, game_type: str, state: dict, view_update_callback):
        if not state:
            return
            
        # Per-user game state is authoritative for gameplay visibility. Room
        # status can lag one websocket event behind immediately after START or
        # during a round transition; using it here can hide valid gameplay UI.
        is_active = bool(state.get("active"))
        is_round_finished = bool(state.get("round_finished"))
        if game_type == "TENNIS":
            is_active = str(state.get("state", "")).upper() not in ("", "WAITING", "FINISHED")
        # Keep Scopa's existing hand widget mounted during the short end-of-
        # deal transition.  Rebuilding it at this point steals focus from the
        # final card narration and makes NVDA cancel the speech.
        is_match_over = bool(
            state.get("winner_id") is not None
            or state.get("winning_team") is not None
            or (getattr(app, "current_room", None) or {}).get("status") in ("match_finished", "waiting")
        )
        keep_scopa_hand = (
            game_type == "SCOPA"
            and not is_active
            and not is_match_over
            and bool(state.get("final_play_action"))
        )
        app.table_view.set_playing_mode((is_active and not is_round_finished) or keep_scopa_hand)
        view_update_callback(is_active, is_round_finished)

        if is_active and not is_round_finished:
            sound_engine.preload_game_sounds(game_type)

        event_id = int(state.get("event_id", 0) or 0)
        last_event_attr = f"_last_{game_type.lower()}_event_id"
        if game_type == "UNO": last_event_attr = "_last_event_id"
        elif game_type == "NINETY_NINE": last_event_attr = "_last_ninety_nine_event_id"
        
        last_id_raw = getattr(app, last_event_attr, 0)
        try:
            last_id = int(last_id_raw)
        except (ValueError, TypeError):
            last_id = 0

        action_text = state.get("last_action", "")
        et = state.get("event_type", "")
        
        # Only reset last_id if the server actually started a new game/round and the event_id wrapped around to 1,
        # OR if we explicitly need to handle a fresh start. Do NOT reset last_id on every single state update!
        if event_id == 1 and last_id > 1:
            last_id = 0
            app._match_result_sound_played = False

        cue = state.get("sound_cue", "")
        event_cues = sound_engine.event_cues(game_type, et, state)
        spoke_event = False
        if event_id > last_id:
            setattr(app, last_event_attr, event_id)
            et = state.get("event_type", "")
            room_id = str((app.current_room or {}).get("id") or "")
            logical_key = ("game", room_id, str(et or ""), str(event_id))
            seen = getattr(app, "_seen_game_activity_events", None)
            if seen is None:
                seen = set()
                app._seen_game_activity_events = seen
            if action_text and logical_key not in seen:
                app.table_view.add_log(
                    action_text, category="GAMEPLAY", game_event_id=event_id,
                    event_type=et, room_id=room_id
                )
                seen.add(logical_key)
            # Bound this cache; event IDs are monotonically increasing within a game.
            if len(seen) > 512:
                app._seen_game_activity_events = set(list(seen)[-256:])
                seen = app._seen_game_activity_events
            
            et = state.get("event_type", "")
            
            if et in ("GAME_STARTED", "ROUND_START", "ROUND_STARTED"):
                app._match_result_sound_played = False
            
            # Play exactly the sound(s) belonging to this game event.
            # Never resolve a lower-case generic cue such as ``place`` through
            # another game's registry entry. The server cue wins when valid;
            # otherwise use the shared per-game semantic mapping.
            event_cues = sound_engine.event_cues(game_type, et, state)
            # Scopa finalizes a deal in the same server action as its final
            # card.  Deliver that card through one de-duplicated path; the
            # lifecycle frame carries the same data if this snapshot is late.
            final_play_announced = False
            if game_type == "SCOPA":
                final_play_event = state.get("final_play_event_type", "")
                if final_play_event and hasattr(app, "_announce_scopa_final_play"):
                    app._announce_scopa_final_play(state)
                    final_play_announced = True
            if game_type in ("SNAKES_LADDERS", "NINETY_NINE"):
                raw_cues = state.get("sound_cues") or ()
                valid_sequence = tuple(c for c in raw_cues if sound_engine.has_cue(c))
                if et not in ("MATCH_WON", "MATCH_FINISHED") and valid_sequence:
                    event_cues = valid_sequence
            # A ROUND_FINISHED state is only a transport frame for
            # final_play_*.  The lifecycle event owns its delayed summary.
            scopa_round_finished = game_type == "SCOPA" and et in ("ROUND_FINISHED", "ROUND_END", "ROUND_WON")
            if scopa_round_finished:
                event_cues = ()
            elif game_type in ("SCOPA", "NINETY_NINE") and len(event_cues) > 1:
                for delay, event_cue in enumerate(event_cues):
                    if delay == 0:
                        sound_engine.play_event(event_cue)
                    else:
                        QTimer.singleShot(delay * 180, lambda c=event_cue: sound_engine.play_event(c))
            else:
                for event_cue in event_cues:
                    sound_engine.play_event(event_cue)

            if et in ("MATCH_WON", "MATCH_FINISHED"):
                winner_id = state.get("winner_id") or state.get("match_winner_id")
                winning_team = state.get("winning_team")
                teams = state.get("teams") or {}
                my_id = (app.user or {}).get("id")
                if winning_team is not None and my_id is not None and str(my_id) in teams:
                    is_me = (teams.get(str(my_id)) == winning_team)
                elif winner_id is not None and my_id is not None:
                    is_me = (str(winner_id) == str(my_id))
                else:
                    winning_ids = state.get("winning_ids")
                    if isinstance(winning_ids, (list, tuple, set)) and my_id is not None:
                        is_me = any(str(w) == str(my_id) for w in winning_ids)
                    else:
                        is_me = False
                if not getattr(app, "_match_result_sound_played", False):
                    sound_engine.play_event("MATCH_WIN" if is_me else "MATCH_LOSS")
                    app._match_result_sound_played = True
                
                localized_action = tr(action_text)
                if is_me:
                    msg = tr("مبروك! لقد فزت.") + " " + localized_action
                else:
                    msg = tr("حظ أوفر!") + " " + localized_action
                announce_game_event(msg, interrupt=(game_type != "SCOPA"))
                spoke_event = True
            elif et in ("ROUND_FINISHED", "ROUND_END", "ROUND_WON"):
                if game_type == "SCOPA":
                    # Do not interrupt the final capture or duplicate the
                    # summary: scopa_round_finished schedules it once.
                    spoke_event = True
                else:
                    if not event_cues:
                        sound_engine.play_event("ROUND_END")
                    if final_play_announced:
                        QTimer.singleShot(900, lambda text=action_text: announce_game_event(text, interrupt=False))
                    else:
                        announce_game_event(action_text, interrupt=True)
                    spoke_event = True
            elif et in ("ROUND_START", "ROUND_STARTED", "GAME_STARTED"):
                if hasattr(app, "table_view") and app.table_view:
                    app.table_view._focus_target = "gameplay"
                    app.table_view.focus_initial()
                announce_game_event(action_text, interrupt=True)
                spoke_event = True
            else:
                if game_type in ("UNO", "NINETY_NINE"):
                    if et in ("CARD_DRAWN", "CARD_DRAWN_AND_PASSED", "DRAW_PENALTY",
                              "CARD_PLAYED", "SPECIAL_CARD_PLAYED", "BLUFF_CAUGHT",
                              "BLUFF_FALSE", "UNO_CAUGHT", "SEVEN_EXCHANGE",
                              "BUZZER_PENALTY", "PLAYER_ELIMINATED",
                              "PENDING_CHOICE", "CHOICE_CANCELLED"):
                        announce_game_event(action_text, interrupt=True)
                        spoke_event = True
                    elif et == "UNO_CALLED":
                        announce_game_event("UNO", interrupt=True)
                        spoke_event = True
                        
                elif game_type == "FARKLE":
                    announce_game_event(action_text, interrupt=False)
                    spoke_event = True

                elif game_type == "SCOPA":
                    if et in ("CARD_PLAYED", "CARD_CAPTURED", "SCOPA_SCORED", "SCOPA_SWEEP"):
                        announce_game_event(action_text, interrupt=False)
                        spoke_event = True
                        if hasattr(app, "_seen_scopa_final_plays"):
                            room_id = str((app.current_room or {}).get("id") or "")
                            app._seen_scopa_final_plays.add((room_id, str(event_id), et, action_text))

                elif game_type not in ("THIEF_HUNT", "SNAKES_LADDERS"):
                    announce_game_event(action_text, interrupt=False)
                    spoke_event = True

        # Canonical turn announcement: Strictly gated to active gameplay
        current_name = (state.get("current_player_name") or state.get("current_turn_name") or "غير معروف")
        curr_id = state.get("current_turn_id")
        if curr_id is None:
            curr_id = state.get("current_player_id")
            
        my_id = (app.user or {}).get("id")
        was_my_turn_attr = f"_was_my_turn_{game_type.lower()}"
        # The final card remains technically active until the server has
        # emitted its final snapshot.  It is not a new turn and must never
        # produce "دورك" / another player's turn announcement.
        is_turn_allowed = (
            is_active and not is_round_finished
            and not state.get("pending_deal_batch")
            and not state.get("pending_round_finalize")
            and state.get("event_type") not in ("MATCH_WON", "MATCH_FINISHED", "ROUND_FINISHED", "ROUND_END")
        )
            
        if is_turn_allowed and curr_id is not None:
            curr_id_str = str(curr_id)
            last_turn_attr = f"_last_announced_turn_id_{game_type.lower()}"
            last_announced_turn = getattr(app, last_turn_attr, None)
            is_my_turn = (curr_id_str == str(my_id)) if my_id is not None else False
            
            if curr_id_str != str(last_announced_turn):
                setattr(app, last_turn_attr, curr_id_str)
                setattr(app, f"_last_turn_{game_type.lower()}", curr_id_str)
                setattr(app, was_my_turn_attr, is_my_turn)
                if is_my_turn:
                    sound_engine.play_event("TURN_START")
                    if not spoke_event:
                        announce_game_event("دورك", interrupt=False)
                else:
                    is_new_deal_batch = (game_type == "SCOPA" and et == "DEAL_BATCH")
                    if not spoke_event and not is_new_deal_batch:
                        announce_game_event(f"دور {current_name}", interrupt=False)
        elif state.get("event_type") in ("MATCH_WON", "MATCH_FINISHED", "ROUND_FINISHED", "ROUND_END"):
            setattr(app, was_my_turn_attr, False)
            setattr(app, f"_last_turn_{game_type.lower()}", None)
            setattr(app, f"_last_announced_turn_id_{game_type.lower()}", None)
