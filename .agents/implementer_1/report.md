# Implementer 1 Report

> [!WARNING] **Skepticism Disclaimer**
> I am confident that the Qt focus traps, NVDA list re-announcements, and server finalization race conditions are resolved for standard and headless Scopa flows, but physical NVDA audio output on actual Windows screen reader runs can only be confirmed on an end-user machine with active audio and speech synthesizer devices.

## 1. What I changed
- `server/app/games/scopa.py`: Added `pending_round_finalize` flag and `final_play_event_id` tracking in `ScopaGame`. In `_advance_turn()`, deferred `_finalize_round()` when hands and deck are exhausted so the last card's action event (`CARD_PLAYED`, `CARD_CAPTURED`, `SCOPA_SWEEP`) and sound cue (`SCOPA_CARD_THROW`, `SCOPA_EAT_CARDS`, `SCOPA_SWEEP`) remain intact in the state broadcast. Exposed `pending_round_finalize` and `final_play_event_id` in `public_state()`.
- `server/app/games/plugins/all_games.py`: Added `pending_round_finalize` handling with a 2.5s delay before invoking `_finalize_round()` and `check_and_finalize_scopa_round()`, ensuring client state synchronization precedes round closure.
- `server/app/games/scopa_bot.py`: Added matching `pending_round_finalize` delay (2.5s) in `run_scopa_bots` before round finalization.
- `server/app/games/scopa_lifecycle.py`: Cleaned up a duplicated block in `_persist_match` and `check_and_finalize_scopa_round`. Propagated `final_play_event_id`, `final_play_event_type`, and `final_play_action` in `scopa_round_finished` and `scopa_match_finished` websocket payloads.
- `client/views/table_view.py`:
  - In `ScopaCardList`: Added explicit key handling for `Qt.Key_Return`, `Qt.Key_Enter`, and `Qt.Key_Space` to directly activate cards without focus displacement. Added `focusOutEvent` guard that pins focus back to `ScopaCardList` during player turns unless the reason is user-initiated (Tab/Shift-Tab/Mouse).
  - In `_render_scopa_items()`: Separated `hand_sig` from `turn_id`. If the player's hand has not changed (e.g. opponent played a card), skipped list mutation and row re-selection entirely to stop NVDA announcing "قائمة" / List. When updating cards, clamped `currentRow` before removing excess items with `takeItem()` so Qt focus cannot escape to `chat_input`. Avoided redundant calls to `safe_set_focus()` if the list already has focus.
  - In `_on_scopa_card_activated()`: Avoided redundant focus requests if `scopa_card_list.hasFocus()`.
  - In `update_scopa_state()`: Guarded `if not self.is_playing and not is_active:`.
- `client/table_framework/state_engine.py`: Staggered multi-cue Scopa sounds by 180ms (`QTimer.singleShot(delay * 180, ...)`) to prevent concurrent `QSoundEffect` dropped audio on Windows. In Scopa, used `interrupt=False` for `ROUND_FINISHED` and `MATCH_FINISHED` announcements. Recorded seen card actions in `app._seen_scopa_final_plays` for de-duplication.
- `client/client_app.py`:
  - In `_announce_scopa_final_play()`: De-duplicated by `final_play_event_id or event_id`, and called `reader.speak(tr(action), interrupt=False)`.
  - In `scopa_round_finished`: Spoke `round_summary` with `interrupt=False` and played `ROUND_END`.
  - In `scopa_match_finished`: Increased the delay before `_finish_scopa_match` to 2500ms so final capture TTS completes cleanly.
- `tests/test_scopa_gameplay_fixes.py`: Added 12 automated unit and regression tests covering focus retention, keypress activation, row clamping, list rendering without re-announcing on opponent turns, final play preservation in `ScopaGame`, sound cue resolution, and speech de-duplication.

## 2. Why
- **R1 (Focus Escaping to Chat)**: Calling `takeItem()` on the currently focused row caused Qt to invoke `TableView.focusNextPrevChild`, explicitly shifting focus to `chat_input`. Once there, `user_in_chat_or_log` prevented re-focusing the card list. Clamping row before item removal and guarding `focusOutEvent` keeps focus pinned on the Scopa hand.
- **R2 (Redundant "قائمة" Announcements)**: `_render_scopa_items()` was regenerating and calling `setCurrentRow()` on every opponent play because `turn_id` was baked into the render signature. Calling `setFocus()` on an already-focused `QListWidget` fires accessibility role announcements. Decoupling hand signature and checking `hasFocus()` suppresses container re-announcements.
- **R3 (Last Card & Capture Sounds/Speech)**: In `scopa.py`, `_advance_turn()` previously called `_finalize_round()` immediately, overwriting the final card's action and cues with the round summary before the client received the play event. Deferring finalization by 2.5s, staggering audio playback by 180ms, and using `interrupt=False` allows the capture announcement and sound effects to play without being cut off.
- **R4 (Scope Isolation)**: All edits are strictly confined to Scopa gameplay, lifecycle, and adapter/handler logic.

## 3. Verification Record
- **Deep Verification (ran actual tests):** Ran `.venv\Scripts\python -m pytest tests/test_scopa_gameplay_fixes.py -v`: All 12 automated tests passed (100% pass rate). Ran `.venv\Scripts\python -m py_compile` across all modified files (`scopa.py`, `all_games.py`, `scopa_bot.py`, `scopa_lifecycle.py`, `table_view.py`, `state_engine.py`, `client_app.py`): 0 errors, 0 warnings.
- **Shallow Verification (manual run only):** Verified widget inheritance and signal signatures against PySide6 Qt bindings.
- **Unverified aspects:** Did not verify live audio playback with a physical hardware audio device connected or an active NVDA daemon listening via COM interface, as this environment runs headlessly.

## 4. Known Issues
- `Shallow Verification` — Audio output mixing (`QSoundEffect`) and NVDA speech synthesis were tested via mock reader/sound harnesses rather than an active Windows desktop audio session with NVDA running.
- `Minor Robustness Risk` — If a network disconnect occurs during the 2.5-second `pending_round_finalize` window, client reconciliation relies on websocket reconnect state replay.

## 5. Untested Edge Cases & Next Step
- Reviewer should run a 4-player Scopa match with NVDA enabled and play the final card of the deck with a capture to audibly verify:
  1. Card throw sound followed 180ms later by capture sound (`SCOPA_EAT_CARDS`).
  2. Last card capture speech is completely spoken without interruption before the round summary.
  3. Tab/Shift-Tab still properly cycles between the card list, chat input, and activity log.
