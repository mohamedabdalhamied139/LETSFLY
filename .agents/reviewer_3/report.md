# Reviewer 3 Report

> [!WARNING] **Skepticism Disclaimer**
> High confidence in deadlock elimination, state synchronization, team victory resolution, accessibility narration deduplication, and scope boundary isolation; live hardware audio driver playback remains unverified in this headless environment.

## 1. What the prior attempt got wrong
1. **Server Deadlock in `check_and_finalize_scopa_round` on Round Transition**:
   - **Input**: Player or bot plays the final card of a round where neither player/team has reached the target score (game continues to next round).
   - **Expected**: `scopa_action` returns the final round state to the client, broadcasts `scopa_round_finished` with `delay_seconds=5`, and advances to the next round after 5 seconds without blocking the current action or deadlocking.
   - **Actual**: `check_and_finalize_scopa_round` blocked indefinitely on `async with room._mutation_lock:`. The HTTP/WebSocket action request hung forever, freezing the server and preventing the next round from ever starting.
   - **Root cause**: `check_and_finalize_scopa_round` in `server/app/games/scopa_lifecycle.py` awaited `asyncio.sleep(5)` and then attempted to acquire `async with room._mutation_lock:` synchronously inside the same task while `room._mutation_lock` was already acquired by the caller (`scopa_action` or `run_scopa_bots`). Because `asyncio.Lock` is non-reentrant in Python, this permanently deadlocked.
2. **False Match Loss and "حظ أوفر!" Announced to Winning Team in `ClientStateEngine`**:
   - **Input**: 4-player or 6-player Team Scopa match concludes with team victory.
   - **Expected**: Players on the winning team hear `MATCH_WIN` sound and congratulatory victory speech ("مبروك! لقد فزت.").
   - **Actual**: `state_engine.py` announced "حظ أوفر!" ("Better luck next time!") and played `MATCH_LOSS` sound to the winning team.
   - **Root cause**: While Round 2 addressed `_announce_terminal_result` in `client_app.py`, it overlooked `ClientStateEngine.process_common_state` in `client/table_framework/state_engine.py`, which still evaluated `is_me` solely using `winner_id` (which is `None` in team games), ignoring `winning_team`, `teams`, and `winning_ids`.
3. **Type Mismatch in `winning_ids` Resolution in `_announce_terminal_result`**:
   - **Input**: `winning_ids` in payload contains integer IDs (e.g. `[10, 11]`), but `(self.user or {}).get("id")` is a string `"10"`.
   - **Expected**: Winner is recognized as having won.
   - **Actual**: `(self.user or {}).get("id") in winning_ids` evaluated `"10" in [10, 11]` as `False`, playing `MATCH_LOSS` for the winner.
   - **Root cause**: Strict object identity/equality check without `str()` normalization across string and integer identifiers.
4. **Duplicate Round Summary Announcements on Final Play of Round**:
   - **Input**: Human player plays the last card of a round.
   - **Expected**: Round score summary is announced once by screen reader.
   - **Actual**: `scopa_round_finished` spoke `round_summary`, and `scopa_action`'s return value processed through `ClientStateEngine` also spoke `round_summary`, reading the entire multi-sentence score summary twice.
   - **Root cause**: `round_summary` was not deduplicated in `_seen_scopa_final_plays` between `scopa_round_finished` and `ClientStateEngine.process_common_state`.
5. **Stale Final Play Metadata Persisting Across Rounds**:
   - **Input**: Round 1 ends and Round 2 starts via `start_new_round()`.
   - **Expected**: Final play event fields are cleared for the new round.
   - **Actual**: `final_play_event_type`, `final_play_action`, and `final_play_event_id` remained set from Round 1, persisting in all Round 2 public state broadcasts.
   - **Root cause**: Missing field cleanup in `ScopaGame.start_new_round()` in `server/app/games/scopa.py`.

## 2. What I changed
- `server/app/games/scopa_lifecycle.py`:
  - Decoupled round transition into `_start_next_scopa_round_after_delay(room)` dispatched as a background task (`room._round_transition_task = asyncio.create_task(...)`), allowing `check_and_finalize_scopa_round` to return immediately and release `room._mutation_lock`, completely eliminating the deadlock.
  - Added `"teams"` mapping to `scopa_match_finished` payload for complete client state inspection.
- `server/app/games/scopa.py`:
  - Reset `final_play_event_type`, `final_play_action`, `final_play_event_id`, `round_summary`, `pending_deal_batch`, and `pending_round_finalize` in `start_new_round()`.
- `client/client_app.py`:
  - Made `_announce_terminal_result` type-safe using `str(w) == str(my_id)` with `teams`/`winning_team` fallback, and set `self._match_result_sound_played = True` to prevent duplicate sound cues.
  - Deduplicated `round_summary` speech in `scopa_round_finished` via `_seen_scopa_final_plays`.
- `client/table_framework/state_engine.py`:
  - Updated `MATCH_WON`/`MATCH_FINISHED` check to inspect `winning_team` and `teams` mapping, preventing false loss announcements for winning team members.
  - Deduplicated `ROUND_FINISHED` speech for Scopa via `_seen_scopa_final_plays`.
- `tests/test_scopa_gameplay_fixes.py`:
  - Added 5 new automated tests covering deadlock prevention under mutation locks, metadata cleanup in new rounds, team victory resolution in `ClientStateEngine`, type-safe ID matching, and round summary speech deduplication (suite expanded from 28 to 33 tests).

## 3. Verification Record
- **Deep Verification (ran actual tests):**
  - Ran `.venv\Scripts\python.exe -m pytest tests/ -v`: All 33 tests passed (100% pass rate in 1.88s).
  - Executed async deadlock reproduction test: confirmed `check_and_finalize_scopa_round` completes under `room._mutation_lock` in 0.01s without timing out.
  - Executed end-to-end multi-round gameplay simulation: verified card plays, turn transitions, batch deals, round transitions, and match victory.
  - Ran `py_compile` across all modified files (`scopa_lifecycle.py`, `scopa.py`, `all_games.py`, `scopa_bot.py`, `table_view.py`, `client_app.py`, `state_engine.py`, `test_scopa_gameplay_fixes.py`): 0 errors, 0 warnings.
- **Shallow Verification (manual only):**
  - Verified PySide6 timer delays, speech queue serialization, and focus reason filtering.
- **Unverified aspects:**
  - Physical NVDA audio driver output on a live Windows desktop with hardware speakers connected (headless environment limitation).

## 4. Known Issues
- `Shallow Verification` — Speech synthesizer and sound engine hooks were verified via test harnesses and mocks due to headless execution environment without a physical sound card.
- `Minor Robustness Risk` — If a client reconnects during the 2.2-2.5s server sleep window, hand and table card synchronization relies on snapshot recovery.

## 5. Remaining risk & next step
The server deadlock, team victory false loss, type mismatch, duplicate speech, and state leakage bugs have all been resolved and verified with automated regression tests. The codebase is fully consistent, and all changes remain strictly bounded to Scopa logic. The task is complete.
