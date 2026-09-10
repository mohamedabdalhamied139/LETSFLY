# Startup and gameplay repair notes

- Restored the missing `TableView` gameplay methods for Farkle and Domino, including Domino side selection.
- Restored the shared `_update_tab_order`, `focusNextPrevChild`, and modal-state helpers that were accidentally absent from the repaired `table_view.py`.
- Kept the Pure-List `ThiefFloorList` implementation.
- Updated `START_TABLEVERSE.bat` to show each environment step and removed the PowerShell `Get-FileHash` startup dependency.
- The launcher now verifies desktop/server imports before launching and records crash logs under `logs`.
