# Reviewer 1 Report

> [!WARNING] **Skepticism Disclaimer**
> Confidence is moderate-to-high across state synchronization, widget focus trapping, and sound engine dispatch, but true physical NVDA accessibility audio output on an active Windows sound card remains unverified in this headless environment.

## 1. What the prior attempt got wrong
1. **DEAL_BATCH Turn Announcement Silencing**:
   - **Input**: `event_type == "DEAL_BATCH"` broadcast after dealing a new batch of 3 cards.
   - **Expected**: Active player's turn announced ("دورك" or "دور فلان") so the screen reader informs players who plays first in the new deal.
   - **Actual**: Completely silent; neither event action nor turn was announced.
   - **Root cause**: Prior implementer added `suppress_turn_announcement = (game_type == "SCOPA" and et == "DEAL_BATCH")` in `state_engine.py`, which unconditionally silenced turn narration on batch deals.
2. **`is_my_turn` False-Positive Trap on None**:
   - **Input**: `my_id = None` (e.g. before login, spectator, or disconnected) and `current_turn_id = None` (e.g. round finished or between rounds).
   - **Expected**: `is_my_turn` evaluates to `False`.
   - **Actual**: `is_my_turn` evaluated to `True` because `str(None) == str(None)` is truthy in Python.
   - **Root cause**: In `table_view.py` (`ScopaCardList.focusOutEvent` and `_render_scopa_items`), `str(curr_turn_id) == str(my_id)` lacked null guards, trapping focus on `ScopaCardList` even when no player was active.
3. **Stale `active=True` Returned After `pending_round_finalize`**:
   - **Input**: Player plays the final card of the round; server initiates 2.5s delay before `_finalize_round()`.
   - **Expected**: REST/WS action response returns finalized state with `active=False` and updated round summary/scores.
   - **Actual**: Client action callback `done(state)` received old snapshot taken before `_finalize_round()` with `active=True`, causing `_apply_scopa_state` to erroneously reactivate gameplay mode.
   - **Root cause**: `scopa_action` in `all_games.py` evaluated `viewer_state = game.public_state(user_id)` before `await asyncio.sleep(2.5)` and returned that stale reference instead of re-reading `game.public_state(user_id)` after `_finalize_round()`.
4. **`game_finished` Broadcast Preempting Scopa Match Finish Delay**:
   - **Input**: Scopa match finishes and broadcasts both `scopa_match_finished` and `game_finished`.
   - **Expected**: `_finish_scopa_match` delay (2500ms) completes cleanly so final capture TTS and cues finish speaking.
   - **Actual**: `game_finished` arrived within milliseconds and immediately called `set_playing_mode(False)` and focused `main_table_widget`, cutting off Scopa's match finish sequence.
   - **Root cause**: `client_app.py` line 2832 unconditionally handled `game_finished` without checking if `game == "SCOPA"`, which has its own dedicated `scopa_match_finished` lifecycle handler.
5. **Redundant `setFocus()` in `focus_scopa` Triggering Screen Reader Role Announcements**:
   - **Input**: Table initial focus requested during round start or gameplay state update while `scopa_card_list` already has focus.
   - **Expected**: No accessibility focus announcement fired if already focused.
   - **Actual**: `focus_scopa` called `setFocus()` unconditionally, forcing Qt accessibility to re-announce "قائمة".
   - **Root cause**: In `client/games/adapters/all_adapters.py`, `focus_scopa` did not check `not table_view.scopa_card_list.hasFocus()` before invoking `setFocus()`.
6. **`keep_scopa_hand` Leaking Past Match End**:
   - **Input**: Match finished with a winner (`winner_id` or `winning_team` set).
   - **Expected**: Hand widget unmounted and playing mode set to `False`.
   - **Actual**: `keep_scopa_hand` evaluated to `True` because `final_play_action` was present, keeping playing mode `True`.
   - **Root cause**: `state_engine.py` and `table_view.py` did not check if the match was over before preserving the hand container.

## 2. What I changed
- `client/table_framework/state_engine.py`:
  - Removed `suppress_turn_announcement = (game_type == "SCOPA" and et == "DEAL_BATCH")`; ensured `DEAL_BATCH` triggers turn announcement ("دورك" / "دور فلان") with `interrupt=False`.
  - Added `is_match_over` guard to `keep_scopa_hand` so completed matches unmount the hand container.
- `client/views/table_view.py`:
  - Fixed `is_my_turn` evaluations in `ScopaCardList.focusOutEvent` and `_render_scopa_items` to `bool(my_id is not None and curr_id is not None and str(curr_id) == str(my_id))`.
  - In `update_scopa_state()`, added `is_match_over` guard before keeping `scopa_container` visible.
- `client/games/adapters/all_adapters.py`:
  - In `focus_scopa()`, guarded `setFocus()` with `if not table_view.scopa_card_list.hasFocus():` to prevent re-announcements when already focused.
- `server/app/games/plugins/all_games.py`:
  - In `scopa_action()`, evaluated `final_state = game.public_state(user_id)` after `_finalize_round()` so action callbacks receive `active: False` and finalized scores.
- `server/app/games/scopa_bot.py`:
  - Guarded `_deal_next_batch()` in bot execution with `if room.scopa_game and room.scopa_game.active:`.
- `client/client_app.py`:
  - In `_handle_ws_event()`, ignored `game_finished` when `event.get("game") == "SCOPA"` to avoid aborting `scopa_match_finished`'s capture announcement window.
- `tests/test_scopa_gameplay_fixes.py`:
  - Added 9 comprehensive automated unit tests covering `DEAL_BATCH` player and opponent turn announcements, `is_my_turn` None guards, adapter focus idempotency, `game_finished` isolation, match-over container dismantling, 4-player Scopa full deal-batch-to-capture simulation, Tab/Shift-Tab focus cycling, and inactive action response validation (bringing total test count from 12 to 21).

## 3. Verification Record
- **Deep Verification (ran actual tests):**
  - Ran `.venv\Scripts\python.exe -m pytest tests/test_scopa_gameplay_fixes.py -v`: All 21 tests passed (100% pass rate in 1.88s).
  - Ran `.venv\Scripts\python.exe -m pytest tests/`: Full repository test suite passed (21 passed, 0 failed).
  - Ran `.venv\Scripts\python.exe -m py_compile` across all modified files (`scopa.py`, `all_games.py`, `scopa_bot.py`, `scopa_lifecycle.py`, `table_view.py`, `state_engine.py`, `client_app.py`, `all_adapters.py`, `test_scopa_gameplay_fixes.py`): 0 errors, 0 warnings.
  - Executed headless Python simulation of full 4-player Scopa match across multiple 12-card deal batches to verify deck counts (40 -> 24 -> 12 -> 0), batch deal transitions, capture sound cues (`SCOPA_CARD_THROW` + `SCOPA_EAT_CARDS`), final card preservation, and score calculation.
- **Shallow Verification (manual only):**
  - Validated PySide6 signal/slot and `focusNextPrevChild` logic against Qt event loop rules.
- **Unverified aspects:**
  - Physical NVDA audio driver output on a live Windows desktop with hardware speakers connected.

## 4. Known Issues
- `Shallow Verification` — Actual acoustic speaker output and NVDA COM speech driver hooks were verified via Qt mock reader and sound engine harnesses due to headless execution environment.
- `Minor Robustness Risk` — If a network disconnect occurs during the 2.5s server sleep window, client state relies on reconnect snapshot reconciliation.

## 5. Remaining risk & next step
The fix is complete, small, and strictly isolated to Scopa logic. All acceptance criteria for focus retention, NVDA list announcement suppression, final play sound and capture speech completion, and scope isolation are verified by automated tests. No further code edits are required for Round 1.
