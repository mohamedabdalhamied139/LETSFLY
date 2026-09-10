# Let's Fly v2.0 — Gaming Platform for the Blind

## Project Architecture

### 1. core_shared/
- constants.py: Card colors, types, scores, playroom penalties.
- protocol.py: Pydantic request/response models.
- rules_config.py: Configurable game rule definitions.
- uno_rules.py: Official UNO rule helpers and Arabic card names.

### 2. server/
- Authoritative FastAPI + Asyncio backend with SQLite database and WebSockets.
- games/: Complete authoritative engines for 9 games:
  * uno/: UNO Classic, Flip, and No Mercy.
  * ninety_nine.py: Ninety-Nine (99) card engine.
  * domino.py: Classic Domino (Draw and Block).
  * american_domino.py: American Domino (All Fives).
  * farkle.py: Farkle dice engine.
  * scopa.py: Scopa (Classic, Escoba 15, Scopone, Asso Piglia Tutto, Inverted).
  * snakes_and_ladders.py: Snakes & Ladders engine.
  * thief_hunt.py: Thief Hunt engine.
  * tennis.py: Real Tennis Table engine.
- hub/: Room lifecycle, bot tasks, and WebSocket connection manager.
- api/: REST endpoints for Auth, Users/Wallet, Social Center, and Rooms/Game actions.

### 3. client/
- PySide6 Accessibility-First client.
- accessibility/reader.py: NVDA Controller Client C-types interface (64-bit AMD64/x64 DLL + Braille).
- accessibility/key_filter.py: Hardware Virtual-Key native filter (Windows VK codes).
- audio/: Zero-latency sound engines (SoundEngine and TennisSoundEngine).
- network/: REST and WebSocket networking clients.
- views/: Shared TableView, AuthView, HomeView, RoomsMenuView, JoinRoomsView, ListMenu, and TextHelpViewer.

## Running the Project
Execute START_LETSFLY.bat or run:
1. python server/run_server.py
2. python client/main.py

## Production deployment

The bundled local server is a development launcher. For an online deployment:

- Put a TLS reverse proxy (for example Nginx/Caddy/Apache) in front of FastAPI.
- Keep FastAPI bound to `127.0.0.1` so the application port is not exposed directly to the Internet.
- Set `LETSFLY_ENV=production`.
- Set a high-entropy `LETSFLY_SECRET_KEY` outside the project files.
- Set `LETSFLY_CORS_ORIGINS` to the exact HTTPS frontend origin(s); never use `*`.
- Set `LETSFLY_ALLOWED_HOSTS` to the exact production API hostname(s); never use `*`.
- Set `LETSFLY_FORWARDED_ALLOW_IPS` to the IP address(es) of the trusted reverse proxy, so client IP and HTTPS scheme are derived only from trusted forwarding headers.
- Keep `LETSFLY_REQUIRE_HTTPS=true` in production.
- Use one Uvicorn worker unless a shared rate-limit backend is deployed; the current in-process abuse controls are intentionally process-local. Do not scale this process horizontally until the rate-limit state is moved to a shared backend (for example Redis).
- Do not expose the SQLite database file, secret files, or server logs through the web server.
- Do not run with `--reload` in production.

## Security configuration

- Production deployments must set `LETSFLY_ENV=production` and provide `LETSFLY_SECRET_KEY` with at least 64 characters.
- Access tokens expire after 24 hours by default; override with `LETSFLY_ACCESS_TOKEN_EXPIRE_MINUTES` when required.
- Logout and password changes revoke all previously issued access tokens for that account.
- Login failures are rate-limited per client address and username, with an additional per-address aggregate limit.
- New registrations and password changes require passwords of at least 8 characters. Existing accounts remain compatible and can upgrade through `/api/auth/change-password`.
- Snakes & Ladders mystery-box locations and pending coin rewards are kept server-side and are not exposed in the public game state.
- Authenticated WebSocket connections are capped per user and globally to limit resource exhaustion.
- Paid room/bot operations keep the wallet debit and the in-memory mutation in one database transaction boundary and publish the result only after commit.
- Room list/detail snapshots are serialized against the room mutation lock to avoid mixed-version state under concurrent requests.

## Production security notes
- Run exactly one Uvicorn worker until a shared rate-limiting/state backend is configured.
- Use a cryptographically random production `LETSFLY_SECRET_KEY` of at least 64 characters.
- Set explicit HTTPS CORS origins; production rejects non-HTTPS origins.
- Configure `LETSFLY_FORWARDED_ALLOW_IPS` to trusted reverse-proxy addresses only.
- Configure `LETSFLY_JWT_ISSUER` and `LETSFLY_JWT_AUDIENCE` consistently with the deployed client.
