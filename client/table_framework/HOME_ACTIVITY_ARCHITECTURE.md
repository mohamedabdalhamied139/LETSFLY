# Home Activity Architecture Contract

The Home screen activity feed is a consumer of the same central event model used by the application. It is not a second per-game history system.

## Categories

- `TABLE_CHAT` — table chat events.
- `PRIVATE_MESSAGES` — private/PM messages.
- `FRIENDS` — friend online/offline and friend-related activity.
- `GAMEPLAY` — gameplay events from every game.
- `FRIEND_REQUESTS` — new friend requests.
- `INVITATIONS` — game/table invitations.
- `ALL` — derived client-side view containing all persisted categories; never stored as a duplicate event.

A category is rendered only when at least one event exists for that category. Empty categories must not enter the keyboard/focus order.

## Event contract

New social or game features must emit one central event with a category and human-readable text. The Home UI must not know game-specific rules. A new game therefore only needs to emit `GAMEPLAY` events; `ALL` and the Home category presentation require no game-specific changes.

## Authentication contract

The client persists only the access/session token using the platform secure store. Passwords are never persisted. Startup validates the saved token with `/api/auth/me`; invalid/expired/revoked sessions are removed and the login screen is shown.

## Table contract

Home activity is intentionally separate from table chat UI. Table `TableView` remains responsible for the live table UI; Home consumes persisted activity events and has no table chat input.
