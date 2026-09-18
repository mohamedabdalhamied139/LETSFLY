# Project: TableVerse / LETSFLY Mobile Unification (Phase 1)

## Architecture
- **Framework & Language**: Flutter 3.x / Dart 3.x (`mobile/lib/`).
- **Design Target**: 100% architectural and behavioral parity with the Windows desktop client (`client/`).
- **Visual Shell & Theming**:
  - Background canvas: `#1E1E1E`
  - Panels, cards, and list tiles: `#252526`
  - Headers, appbars, dialog title bars: `#2D2D2D`
  - Outlines, borders, dividers: `#3E3E42`
  - Accent / highlight: `#005FB8`
  - Responsive Shell (`ResponsiveShell`): Wide viewports (>= 720dp) display dual-pane master-detail (content + `ActivityLogWidget`), while compact viewports display stacked or drawer-accessible activity log.
- **State Management**:
  - Built-in Flutter `ChangeNotifier` and `ListenableBuilder` (zero external state management bloat, preserving existing architecture).
  - `ActivityLogService`: Single source of truth for the 8 canonical activity categories, deduplication, and cross-screen broadcast.
  - `AuthStorageService`: Multi-account credential and session persistence via `flutter_secure_storage`.
- **Networking**:
  - REST: `ApiService` (`dio`) with token persistence and saved tables CRUD.
  - WebSocket: Pure WebSocket (`web_socket_channel`) with `Authorization: Bearer <token>` handshake header and dev query param fallback.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Visual Theme System | Global Windows dark theme tokens (`#1E1E1E`, `#252526`, `#2D2D2D`, `#3E3E42`, `#005FB8`) across all widgets | M1 | survey |
| 2 | Responsive Dual-Pane Shell | Adaptive master-detail shell integrating content and ActivityLogWidget across wide/compact displays | M1 | survey |
| 3 | Synchronized ActivityLogService | Centralized reactive event store for the 8 canonical activity categories with deduplication | M1 | survey |
| 4 | ActivityLogWidget Parity | Canonical 8 categories (`TABLE_CHAT`, `PRIVATE_MESSAGES`, `FRIENDS`, `GAMEPLAY`, `ALL`, `FRIEND_REQUESTS`, `INVITATIONS`, `GIFTS`), arrow-key/tap category switching, action activation | M1 | survey |
| 5 | WebSocket Auth Token Fix | Fix token omitted on WS connection in `ws_service.dart` (`IOWebSocketChannel` headers + query param) | M1 | survey |
| 6 | Static Analysis & Lint Config | Establish `analysis_options.yaml` with `flutter_lints` and resolve existing codebase warnings | M1 | survey |
| 7 | AuthStorageService Multi-Account | Secure multi-account credential storage using `flutter_secure_storage` | M2 | survey |
| 8 | AuthView Auto-Login & Switcher | Startup session validation, auto-login into HomeView, and `AccountSwitcherDialog` | M2 | survey |
| 9 | HomeView Canonical 8 Menu Items | Exact 8 items in Windows order with Arabic labels: rooms, friends, online, my_profile, settings, notifications, contact, logout | M3 | survey |
| 10 | HomeView Return Greeting & Live Count | Return greeting event ("مرحبًا بعودتك {name}.") in ActivityLog and live online counter updates | M3 | survey |
| 11 | RoomsMenuView 3-Level Hierarchy | Level 1: Main (إنشاء, انضمام, الطاولات المحفوظة); Level 2: Categories (5 categories); Level 3: Sub-menus for all 9 games | M3 | survey |
| 12 | RoomsMenuView Back & Escape Flow | Hierarchical back navigation preserving cursor/category focus across levels | M3 | survey |
| 13 | ApiService CRUD & Spectator | REST endpoints for saved tables (`list`, `restore`, `delete`) and spectator join query param | M4 | survey |
| 14 | JoinRoomsView Parity & Formatting | Room item formatting `{game} — {host} — {count}/10 لاعبين — {status}` | M4 | survey |
| 15 | JoinRoomsView Dual-Join Actions | Dedicated Player Join and Spectator Join actions (`as_spectator=true`) | M4 | survey |
| 16 | SavedTablesView Implementation | Dedicated saved tables screen with formatted timestamps `%Y-%m-%d %H:%M`, game titles, and Restore / Delete actions | M4 | survey |
| 17 | E2E Testing Suite (Tiers 1-4) | Comprehensive opaque-box and unit/widget test suite in `mobile/test/` | M5 | survey |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Foundation, Visual Shell & Activity Sync | `analysis_options.yaml`, `app_theme.dart`, `ResponsiveShell`, `ActivityLogService`, `ActivityLogWidget` refactor, WS token fix | none | DONE |
| M2 | Authentication Parity & Credentials Storage | `AuthStorageService`, `AccountSwitcherDialog`, `AuthView` auto-login & theme styling | M1 | IN_PROGRESS |
| M3 | Main Screens Parity & 3-Level Rooms Menu | `HomeView` (8 items, greeting, live count), `RoomsMenuView` (3 levels, 5 categories, 9 games, back navigation) | M1 | PLANNED |
| M4 | Room Joining, Spectator Mode & Saved Tables | `ApiService` additions, `JoinRoomsView` (formatting & dual-join), `SavedTablesView` (restore & delete) | M1, M3 | PLANNED |
| M5 | E2E Testing Suite & Quality Hardening | Pass 100% E2E test suite (Tiers 1-4), verify static analysis cleanliness | M1, M2, M3, M4 | PLANNED |

## Interface Contracts

### `ActivityLogService`
```dart
class ActivityLogService extends ChangeNotifier {
  static final ActivityLogService instance;
  static const List<String> categories = [
    'TABLE_CHAT', 'PRIVATE_MESSAGES', 'FRIENDS', 'GAMEPLAY',
    'ALL', 'FRIEND_REQUESTS', 'INVITATIONS', 'GIFTS'
  ];
  List<Map<String, dynamic>> get events;
  String get selectedCategory;
  void addEvent(Map<String, dynamic> event);
  void selectCategory(String category);
  List<Map<String, dynamic>> get filteredEvents;
  void clear();
}
```

### `AuthStorageService`
```dart
class AuthStorageService {
  static final AuthStorageService instance;
  Future<void> saveActiveAccount({required String username, required String password, required String displayName, required String token});
  Future<Map<String, dynamic>?> loadActiveAccount();
  Future<List<Map<String, dynamic>>> loadAllAccounts();
  Future<void> removeAccount(String username);
  Future<void> clearActiveSession();
}
```

### `ApiService` Extensions
```dart
// Additions to ApiService:
Future<List<Map<String, dynamic>>> getSavedTables();
Future<Map<String, dynamic>> restoreSavedTable(int savedId);
Future<void> deleteSavedTable(int savedId);
Future<Map<String, dynamic>> joinRoom(String roomId, {String? password, bool asSpectator = false});
```

### `ResponsiveShell`
```dart
class ResponsiveShell extends StatelessWidget {
  final String title;
  final Widget child;
  final List<Widget>? actions;
  final Widget? floatingActionButton;
  final bool showActivityLog;
  const ResponsiveShell({
    super.key,
    required this.title,
    required this.child,
    this.actions,
    this.floatingActionButton,
    this.showActivityLog = true,
  });
}
```

## Code Layout
```
mobile/lib/
├── core/
│   ├── app_theme.dart          # Windows dark palette tokens and ThemeData
│   ├── localization.dart       # Translation helper tr()
│   └── sound_service.dart      # Sound cues
├── models/
│   ├── room_models.dart        # User, RoomSummary, SavedTable
│   └── activity_event.dart     # Canonical ActivityEvent model
├── services/
│   ├── activity_service.dart   # Centralized ActivityLogService
│   ├── api_service.dart        # Dio REST client with saved tables & spectator
│   ├── auth_storage_service.dart # Multi-account flutter_secure_storage
│   └── ws_service.dart         # WebSocket client with auth header
├── views/
│   ├── activity_log_widget.dart# 8-category synchronized log widget
│   ├── auth_view.dart          # Multi-account login/register
│   ├── home_view.dart          # Canonical 8 items & live counter
│   ├── join_rooms_view.dart    # Formatted room list & dual-join
│   ├── responsive_shell.dart   # Dual-pane adaptive shell
│   ├── rooms_menu_view.dart    # 3-level hierarchical room menu
│   ├── saved_tables_view.dart  # Dedicated saved tables screen
│   └── table_view.dart         # Active table shell
mobile/test/
├── harness/                    # Mock adapters and fixtures
├── tier1_unit/                 # Models, localization, auth storage, activity service
├── tier2_widget/               # Activity log, home, rooms menu, join, saved tables
├── tier3_integration/          # Auth flow, navigation flow, log sync
└── tier4_e2e_conformance/      # Protocol conformance, accessibility
```
