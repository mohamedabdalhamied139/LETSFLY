# LETSFLY Mobile Migration: Comprehensive Master Plan (Flutter Architecture)

## Executive Summary
This document serves as the permanent authoritative architectural specification and migration roadmap for porting the multiplayer game platform **LETSFLY** from desktop (Python/PySide6/Qt6) to a production-grade mobile application (Android & iOS) using **Flutter**.

---

## 1. Core Architectural Decisions

### Framework & Language: Flutter (Dart)
- **UI & Layouts**: Pixel-perfect rendering matching desktop box/table architecture (`ListView`, `Row`, `Column`, `Stack`).
- **Target Platforms**: Android & iOS from a single unified codebase.
- **BiDi / RTL Support**: Native first-class Arabic support using `shared_i18n/app_ar.arb` and `app_en.arb`.
- **Accessibility Engine**: Semantic trees (`Semantics`, `SemanticsAction`, `Announce`) specifically tailored for **TalkBack** and **VoiceOver**.
- **Audio Pipeline**: Native low-latency audio player (C++ backend such as `soloud` or `just_audio`) reading semantic cues from `shared_i18n/sound_manifest.json`.
- **Backend Compatibility**: 100% reusable FastAPI + WebSockets backend; zero breaking changes to existing desktop clients.

---

## 2. Pillar-by-Pillar Technical Specifications

### Pillar 1: Low-Latency Multi-Channel Audio
- **Asset Manifest**: Direct ingestion of `shared_i18n/sound_manifest.json` containing 82 semantic sound cues.
- **Preloading Strategy**: Preload shared lifecycle cues on launch; preload game-specific sounds on room join.
- **Audio Ducking**: Automatically reduce ambient loops and non-critical sound effects by 50-60% while TalkBack or VoiceOver is actively announcing.
- **Spatial Audio**: Stereo panning for card play and table seats.
- **Haptic Feedback**: Mapped parallel vibrations (`HapticFeedback`) for turns, card placements, invalid actions, and wins.

### Pillar 2: Deep Accessibility (TalkBack & VoiceOver First)
- **Deterministic Focus Routing**: Prevent focus loss during rapid server state updates via stable `Key` and `ValueKey` identifiers.
- **Custom Accessibility Actions**:
  - Cards in hand support custom actions (Play, Inspect, Capture Target Selection).
  - Domino tiles support (Play Left, Play Right, Draw).
- **Semantic Regions**:
  1. Room Status & Round Info
  2. Current Turn Banner
  3. Hand / Player Tiles
  4. Table / Shared Board
  5. Scoreboard
  6. Action Bar
  7. In-game Chat & Activity Log

### Pillar 3: Real-Time Networking & Mobile Lifecycle
- **JSON-over-WebSocket Protocol**: Direct parity with server event types (`room_snapshot`, `action`, `turn_start`, `match_won`, etc.).
- **Lifecycle Management**:
  - *Foreground*: Persistent WebSocket with 25-second ping-pong heartbeats.
  - *Background / Suspended*: Graceful disconnection without crashing; reliance on APNs / FCM push notifications.
  - *Reconnection & Rehydration*: Exponential backoff with jitter; automatic snapshot reconciliation via `/api/rooms/{id}`.

### Pillar 4: Canonical Localization (English Base + Arabic Native)
- **Single Source of Truth**: `shared_i18n/canonical_en_ar.json` (1,611 key pairs).
- **ARB Files**: Flutter localization generated files (`app_en.arb`, `app_ar.arb`).
- **Dynamic Formatting**: Parametric templates such as `{name}'s turn` -> `دور {name}`.

---

## 3. Phased Implementation Roadmap

### Phase 1: Mobile Core Foundation
- Flutter project setup with modular clean architecture (Domain, Data, Presentation).
- WebSocket client & reconnection state machine.
- Local storage (Tokens, preferences via `flutter_secure_storage`).
- Audio Engine wrapper with sound manifest preloader.
- Main Menu, Lobby, and Room list screens.

### Phase 2: Accessibility Engine & Flagship Card Game (Scopa & Uno)
- Card carousel with TalkBack/VoiceOver custom actions.
- Scopa table view with full capture logic and scoreboards.
- Uno fast turn transitions and color selection modals.
- Turn announcements, haptics, and speech ducking.

### Phase 3: Board & Dice Games (Domino, Farkle, 99, Snakes & Ladders)
- Domino board layout with left/right placement semantics.
- Farkle dice rolling animations, score banking, and hot dice cues.
- Ninety-Nine point countdown and card action prompts.
- Snakes & Ladders stepped moves and traps.

### Phase 4: Social, Chat, Spectator & Specialty Games
- In-game chat sheet / drawer that doesn't disrupt game focus.
- Friends, direct messages, and table invitations.
- Spectator mode with accessible live narrations.
- Remaining games (Thief Hunt, Tennis).

### Phase 5: Polish, Compliance & App Store / Google Play Release
- Battery and memory leak profiling (60-minute continuous stress test).
- TalkBack and VoiceOver compliance certification.
- APNs / FCM push notification integration.
- Final release to Google Play and Apple App Store.

---

## 4. Risk Mitigation Matrix

| Risk | Impact | Mitigation Strategy |
| :--- | :--- | :--- |
| **Screen reader focus jump on state updates** | High | Use stable keys for widgets; avoid rebuilding semantic nodes during minor state diffs. |
| **Mobile OS kills WebSocket in background** | High | Push-first rehydration; fetch room snapshot on resume. |
| **Audio latency on low-end Android devices** | Medium | Use C++ based audio backend (`soloud`), cache decoded sound buffers in memory. |
| **RTL layout mirroring glitches** | Low | Native Flutter `Directionality` widgets; Arabic-first visual QA. |
