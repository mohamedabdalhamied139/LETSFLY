# Reviewer 2 Report

> [!WARNING] **Skepticism Disclaimer**
> Confidence is high for state synchronization, card list preservation, focus containment, and event cue sequencing across simulated 2-player and 4-player scenarios; physical audio output on a live Windows sound card remains unverified in this headless environment.

## 1. What the prior attempt got wrong
1. **Empty Hand Wipeout on Opponent Play & Batch Deals (`public_state` without `viewer_id` broadcast to room)**:
   - **Input**: Opponent plays a card OR server deals next batch of 3 cards (`_deal_next_batch`).
   - **Expected**: Each player retains or receives their private hand cards in `my_hand`, `scopa_card_list` displays playable cards, focus is retained, and NVDA does not announce "قائمة" / "List" when opponent plays.
   - **Actual**: `ws_manager.broadcast_room` broadcast `game.public_state()` with `viewer_id=None` (so `my_hand: []`), wiping out all cards from every human player's hand widget, replacing their hand with a blank waiting item `['']`, locking players out from playing any cards.
   - **Root cause**: In `server/app/games/plugins/all_games.py` and `server/app/games/scopa_bot.py`, `scopa_state_changed` was broadcast via `broadcast_room` without viewer context. Furthermore, `client_app.py` line 2845 bypassed polling when `state` was present, and `_apply_scopa_state` blindly replaced the user's hand with `state.get("my_hand") or []`.
2. **Focus Escaping to Chat on Card Removal During Turn Transition**:
   - **Input**: Player activates their card; the server advances the turn to the opponent, and `_render_scopa_items` removes the played card via `takeItem`.
   - **Expected**: Focus remains firmly held on `ScopaCardList`.
   - **Actual**: During `takeItem` / row clamping, Qt defocuses the item with `OtherFocusReason`. Because `is_my_turn` had already flipped to `False`, `focusOutEvent` did not refocus `ScopaCardList`, allowing focus to escape to `chat_input`.
   - **Root cause**: `ScopaCardList.focusOutEvent` guarded refocus solely with `if is_my_turn:`, neglecting that card removal and selection adjustments happen right as the turn transitions to the opponent while `_scopa_gameplay_focus` is active.
3. **Simultaneous `ROUND_END` Sound Cue Colliding with Final Play Cues**:
   - **Input**: Final card of round played with capture; `scopa_round_finished` arrives while final play cues are announced.
   - **Expected**: `SCOPA_CARD_THROW` and `SCOPA_EAT_CARDS` play cleanly without being clobbered by the round end sound.
   - **Actual**: `client_app.py` played `sound_engine.play_event("ROUND_END")` immediately at time 0 while `_announce_scopa_final_play` was starting the throw and capture cues.
   - **Root cause**: In `client_app.py` (`scopa_round_finished`), `play_event("ROUND_END")` was executed unconditionally with 0ms delay regardless of whether `_announce_scopa_final_play` had just dispatched sound cues.
4. **False Match Loss Announcement for Winning Team in Team Scopa**:
   - **Input**: Team Scopa match ends with team victory.
   - **Expected**: Winning team players hear `MATCH_WIN` sound and "فزت بالمباراة.".
   - **Actual**: `scopa_match_finished` provided `winning_team` without `winning_ids`, causing `_announce_terminal_result` (`winner_id is None`) to play `MATCH_LOSS` and announce "انتهت المباراة." for all players including the winners.
   - **Root cause**: `scopa_lifecycle.py` did not include `winning_ids` in `scopa_match_finished`, and `client_app.py` did not check team membership in `_announce_terminal_result`.

## 2. What I changed
- `server/app/games/scopa_lifecycle.py`:
  - Added `broadcast_scopa_state` helper function to dispatch personalized `game.public_state(uid)` to each human player and public state to spectators via `ws_manager.broadcast_user`.
  - Added `"winning_ids": winning_ids` to `scopa_match_finished` payload for team games.
  - Used `broadcast_scopa_state` on round restart transition.
- `server/app/games/plugins/all_games.py`:
  - Replaced `ws_manager.broadcast_room` in `scopa_action` with `broadcast_scopa_state(room, game)` for card plays and batch deal transitions.
- `server/app/games/scopa_bot.py`:
  - Replaced `ws_manager.broadcast_room` in `run_scopa_bots` with `broadcast_scopa_state(room, game)` for bot plays and batch deal transitions.
- `client/views/table_view.py`:
  - In `ScopaCardList.focusOutEvent`, updated refocus condition to `should_hold_focus = (is_my_turn or getattr(parent_table, "_scopa_gameplay_focus", False))` so that programmatic card removal during turn transition to opponent never drops focus to `chat_input`.
  - Reset `_scopa_gameplay_focus = False` only upon intentional navigation reasons (`TabFocusReason`, `BacktabFocusReason`, `MouseFocusReason`, `PopupFocusReason`).
- `client/client_app.py`:
  - In `_apply_scopa_state`, added defensive hand preservation: if an unpersonalized state arrives where `my_hand` is empty but `hands_count` indicates cards remain, existing cards are preserved; if a new batch was dealt without cards, `_poll_table_state()` is automatically triggered.
  - In `scopa_round_finished`, delayed `ROUND_END` sound by 600ms if `_announce_scopa_final_play` was active, avoiding sound collision with card throw/capture cues.
  - In `_announce_terminal_result`, added support for `winning_ids` from team games.
- `tests/test_scopa_gameplay_fixes.py`:
  - Added 7 new automated tests covering personalized WebSocket state broadcasts, hand preservation on unpersonalized broadcasts, deal batch polling fallback, focus retention during card removal turn change, Tab navigation focus reset, staggered round end sound, and team game victory resolution (total tests expanded from 21 to 28).

## 3. Verification Record
- **Deep Verification (ran actual tests):**
  - Ran `.venv\Scripts\python.exe -m pytest tests/test_scopa_gameplay_fixes.py -v`: All 28 tests passed (100% pass rate in 1.99s).
  - Ran `.venv\Scripts\python.exe -m pytest tests/`: Full repository test suite passed (28 passed, 0 failed in 1.85s).
  - Ran `.venv\Scripts\python.exe -m py_compile` across all modified files (`scopa_lifecycle.py`, `all_games.py`, `scopa_bot.py`, `table_view.py`, `client_app.py`, `test_scopa_gameplay_fixes.py`): 0 errors, 0 warnings.
  - Executed end-to-end Python simulation of multi-player Scopa game verifying card play, state delivery, hand preservation on waiting players, and turn transitions.
- **Shallow Verification (manual only):**
  - Verified PySide6 event loop handling of `QFocusEvent` reason propagation and `QTimer.singleShot` re-entrant focus safety.
- **Unverified aspects:**
  - Physical NVDA audio driver output on a live Windows desktop with hardware speakers connected (headless environment limitation).

## 4. Known Issues
- `Shallow Verification` — Speech synthesizer and sound engine hooks were verified via test harnesses and mocks due to headless execution environment without a physical sound card.
- `Minor Robustness Risk` — If a network disconnect occurs during the 2.5s server sleep window, client state relies on reconnect snapshot reconciliation.

## 5. Remaining risk & next step
The fix is small, robust, and strictly isolated to Scopa logic. All acceptance criteria for focus retention, NVDA list announcement suppression, card preservation, final play sound and capture speech completion, and scope isolation are verified by automated tests. The task is complete.
