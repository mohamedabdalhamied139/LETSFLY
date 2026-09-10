# Shared Table Gameplay Contract

Every game client must be mounted inside the existing `TableView` through a `ClientGameAdapter`.

## Required architecture

`TableView` owns the shared shell: players/table status, chat, history, context menu, start/stop lifecycle, room lifecycle, WebSocket/polling integration, and the canonical keyboard focus cycle.

A game may provide only its gameplay control/container and game-specific state/action handling. The gameplay control is mounted with `TableView.mount_game_ui(...)`.

## Forbidden architecture

A game must not create a separate top-level game window, a second `TableView`, or a nested game window/focus layer. Game-specific controls must not intercept Tab/Shift+Tab to implement their own navigation.

## Focus contract

The shared order is: `gameplay -> chat -> activity log -> gameplay`. Game controls may handle gameplay keys (for example arrows), but Tab navigation remains owned by Qt/TableView.

## Tennis

Tennis uses `TennisGameWidget` directly as the gameplay control. It is not a nested `TennisView` or independent window.
