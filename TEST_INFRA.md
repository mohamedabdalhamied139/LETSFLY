# E2E Test Infra: TableVerse / LETSFLY Mobile Unification (Phase 1)

## Test Philosophy
- **Opaque-box & Requirement-driven**: Derived directly from `ORIGINAL_REQUEST.md` (entry `2026-09-18T12:14:41Z`) and the Windows client specifications.
- **Independence**: Tests are written against public screen interactions, accessibility semantics, and REST/WebSocket contracts.
- **Methodology**: 4-tier systematic approach (Unit/Domain, Widget/Shell, Integration/Navigation, E2E Protocol Conformance).

## Feature Inventory & Test Mapping
| # | Feature | Source (Requirement) | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---------|---------------------|:------:|:------:|:------:|:------:|
| 1 | Visual Theme System | ORIGINAL_REQUEST §R1 | - | ✓ | - | ✓ |
| 2 | Responsive Dual-Pane Shell | ORIGINAL_REQUEST §R1 | - | ✓ | ✓ | - |
| 3 | Centralized ActivityLogService | ORIGINAL_REQUEST §R1 | ✓ | ✓ | ✓ | - |
| 4 | ActivityLogWidget 8 Categories | ORIGINAL_REQUEST §R1 | ✓ | ✓ | ✓ | ✓ |
| 5 | WebSocket Auth Token Header | Server WS Protocol | ✓ | - | - | ✓ |
| 6 | AuthStorageService Multi-Account | ORIGINAL_REQUEST §R2.5 | ✓ | ✓ | ✓ | - |
| 7 | AuthView Auto-Login & Switcher | ORIGINAL_REQUEST §R2.5 | - | ✓ | ✓ | - |
| 8 | HomeView 8 Canonical Items | ORIGINAL_REQUEST §R2.1 | - | ✓ | ✓ | ✓ |
| 9 | HomeView Return Greeting & Live Count | ORIGINAL_REQUEST §R2.1 | ✓ | ✓ | ✓ | - |
| 10 | RoomsMenuView 3-Level Hierarchy | ORIGINAL_REQUEST §R2.2 | - | ✓ | ✓ | ✓ |
| 11 | RoomsMenuView Back & Escape Flow | ORIGINAL_REQUEST §R2.2 | - | ✓ | ✓ | - |
| 12 | JoinRoomsView Formatting Parity | ORIGINAL_REQUEST §R2.3 | ✓ | ✓ | - | ✓ |
| 13 | JoinRoomsView Dual-Join (Player/Spectator) | ORIGINAL_REQUEST §R2.3 | - | ✓ | ✓ | ✓ |
| 14 | SavedTablesView Date Format & CRUD | ORIGINAL_REQUEST §R2.4 | ✓ | ✓ | ✓ | ✓ |
| 15 | ApiService Saved Tables & Spectator | REST Contract | ✓ | - | ✓ | ✓ |

## Test Architecture
- **Location**: `mobile/test/`
- **Framework**: `package:flutter_test/flutter_test.dart`
- **Runner**: `dart test` / `flutter test`
- **Directory Layout**:
  - `mobile/test/harness/`: Mocks (`mock_api_adapter.dart`, `mock_ws_channel.dart`, `test_fixtures.dart`)
  - `mobile/test/tier1_unit/`: Data models, localization, auth storage, activity service logic
  - `mobile/test/tier2_widget/`: Isolated widget tests for each view and component
  - `mobile/test/tier3_integration/`: Screen navigation and reactive state flow tests
  - `mobile/test/tier4_e2e_conformance/`: End-to-end user scenarios and accessibility tests

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Expected Outcome |
|---|----------|--------------------|------------------|
| 1 | Launch App with Saved Account | F6, F7, F8, F9, F3 | Auto-authenticates, navigates to HomeView, renders 8 items in order, adds return greeting to ActivityLog |
| 2 | Navigate Rooms 3 Levels & Back | F10, F11, F2, F4 | Navigates Main -> Categories -> Game, Escapes back smoothly to Level 2 preserving focus, then Level 1, then Home |
| 3 | Join Room as Spectator vs Player | F12, F13, F15, F2 | Displays formatted room title; Player Join sends normal join; Spectator Join sends `as_spectator=true` |
| 4 | Saved Table Lifecycle | F14, F15, F4, F2 | Lists saved games with `YYYY-MM-DD HH:MM` timestamps, allows Restoring to active table and Deleting |
| 5 | Cross-Screen Activity Synchronization | F3, F4, F5, F8, F10 | Incoming WS activity event updates ActivityLogWidget in real-time across Home, Rooms, and Join views |
