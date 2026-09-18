// Tier 2 Widget Test: RoomsMenuView (3-Level Hierarchy & Back/Escape Navigation)

import '../harness/test_engine.dart';

/// Testable state harness for RoomsMenuView matching mobile/lib/views/rooms_menu_view.dart
class RoomsMenuViewStateHarness {
  String mode = 'main';
  String? focusedTag;
  String? lastCreatedGame;
  String? lastNavigatedRoute;

  List<Map<String, String>> getItems() {
    if (mode == 'cards_games') {
      return [
        {'label': 'أونو', 'tag': 'UNO'},
        {'label': 'إسكوبا', 'tag': 'SCOPA'},
        {'label': 'تسعة وتسعون', 'tag': 'NINETY_NINE'},
      ];
    } else if (mode == 'dice_games') {
      return [
        {'label': 'فاركل', 'tag': 'FARKLE'},
        {'label': 'السلم والثعبان', 'tag': 'SNAKES_LADDERS'},
      ];
    } else if (mode == 'domino_games') {
      return [
        {'label': 'دومينو', 'tag': 'DOMINO'},
        {'label': 'دومينو أمريكي', 'tag': 'AMERICAN_DOMINO'},
      ];
    } else if (mode == 'memory_games') {
      return [
        {'label': 'صيد اللص', 'tag': 'THIEF_HUNT'},
      ];
    } else if (mode == 'sports_games') {
      return [
        {'label': 'تنس', 'tag': 'TENNIS'},
      ];
    } else if (mode == 'games') {
      return [
        {'label': 'ألعاب الكروت', 'tag': 'category_cards'},
        {'label': 'ألعاب النرد', 'tag': 'category_dice'},
        {'label': 'ألعاب الدومينو', 'tag': 'category_domino'},
        {'label': 'ألعاب الذاكرة', 'tag': 'category_memory'},
        {'label': 'ألعاب الرياضة', 'tag': 'category_sports'},
      ];
    } else {
      // Level 1: Main
      return [
        {'label': 'إنشاء', 'tag': 'create'},
        {'label': 'انضمام', 'tag': 'join'},
        {'label': 'الطاولات المحفوظة', 'tag': 'saved_tables'},
      ];
    }
  }

  String getTitle() {
    if (mode == 'cards_games') return 'ألعاب الورق';
    if (mode == 'dice_games') return 'ألعاب النرد';
    if (mode == 'domino_games') return 'ألعاب الدومينو';
    if (mode == 'memory_games') return 'ألعاب الذاكرة والتركيز';
    if (mode == 'sports_games') return 'ألعاب رياضية';
    if (mode == 'games') return 'تصنيفات الألعاب لإنشاء الطاولة';
    return 'الطاولات';
  }

  void onItemTapped(String tag) {
    if (tag == 'create') {
      mode = 'games';
      focusedTag = 'category_cards';
    } else if (tag == 'join') {
      lastNavigatedRoute = 'JoinRoomsView';
    } else if (tag == 'saved_tables') {
      lastNavigatedRoute = 'SavedTablesView';
    } else if (tag == 'category_cards') {
      mode = 'cards_games';
      focusedTag = 'UNO';
    } else if (tag == 'category_dice') {
      mode = 'dice_games';
      focusedTag = 'FARKLE';
    } else if (tag == 'category_domino') {
      mode = 'domino_games';
      focusedTag = 'DOMINO';
    } else if (tag == 'category_memory') {
      mode = 'memory_games';
      focusedTag = 'THIEF_HUNT';
    } else if (tag == 'category_sports') {
      mode = 'sports_games';
      focusedTag = 'TENNIS';
    } else {
      // Game creation: tag is Game ID
      lastCreatedGame = tag;
      lastNavigatedRoute = 'TableView';
    }
  }

  /// Returns true if screen should pop back to HomeView, false if handled internally
  bool handleBack() {
    final categoryParentMap = {
      'cards_games': 'category_cards',
      'dice_games': 'category_dice',
      'domino_games': 'category_domino',
      'memory_games': 'category_memory',
      'sports_games': 'category_sports',
    };

    if (categoryParentMap.containsKey(mode)) {
      focusedTag = categoryParentMap[mode];
      mode = 'games';
      return false; // Handled internally, back to Level 2
    } else if (mode == 'games') {
      focusedTag = 'create';
      mode = 'main';
      return false; // Handled internally, back to Level 1
    }
    return true; // Pop screen back to HomeView
  }
}

void main() async {
  defineTests();
  await runSuite('Tier 2 Widget: Rooms Menu View Tests');
}

void defineTests() {
  group('RoomsMenuView 3-Level Hierarchy & Navigation Parity', () {
    late RoomsMenuViewStateHarness harness;

    setUp(() {
      harness = RoomsMenuViewStateHarness();
    });

    test('Level 1 Main menu: Contains exactly 3 items with correct labels and tags', () {
      expect(harness.mode, equals('main'));
      expect(harness.getTitle(), equals('الطاولات'));

      final items = harness.getItems();
      expect(items, hasLength(3));

      expect(items[0]['tag'], equals('create'));
      expect(items[0]['label'], equals('إنشاء'));

      expect(items[1]['tag'], equals('join'));
      expect(items[1]['label'], equals('انضمام'));

      expect(items[2]['tag'], equals('saved_tables'));
      expect(items[2]['label'], equals('الطاولات المحفوظة'));
    });

    test('Selecting create transitions to Level 2 (5 game categories)', () {
      harness.onItemTapped('create');

      expect(harness.mode, equals('games'));
      expect(harness.getTitle(), equals('تصنيفات الألعاب لإنشاء الطاولة'));

      final categories = harness.getItems();
      expect(categories, hasLength(5));

      expect(categories[0]['tag'], equals('category_cards'));
      expect(categories[0]['label'], equals('ألعاب الكروت'));

      expect(categories[1]['tag'], equals('category_dice'));
      expect(categories[1]['label'], equals('ألعاب النرد'));

      expect(categories[2]['tag'], equals('category_domino'));
      expect(categories[2]['label'], equals('ألعاب الدومينو'));

      expect(categories[3]['tag'], equals('category_memory'));
      expect(categories[3]['label'], equals('ألعاب الذاكرة'));

      expect(categories[4]['tag'], equals('category_sports'));
      expect(categories[4]['label'], equals('ألعاب الرياضة'));
    });

    test('Level 3 Sub-menus: Covers all 9 canonical games across all 5 categories', () {
      final allGamesEncountered = <String>[];

      // 1. Cards
      harness.mode = 'games';
      harness.onItemTapped('category_cards');
      expect(harness.mode, equals('cards_games'));
      expect(harness.getTitle(), equals('ألعاب الورق'));
      final cards = harness.getItems();
      expect(cards, hasLength(3));
      allGamesEncountered.addAll(cards.map((e) => e['tag']!));

      // 2. Dice
      harness.mode = 'games';
      harness.onItemTapped('category_dice');
      expect(harness.mode, equals('dice_games'));
      expect(harness.getTitle(), equals('ألعاب النرد'));
      final dice = harness.getItems();
      expect(dice, hasLength(2));
      allGamesEncountered.addAll(dice.map((e) => e['tag']!));

      // 3. Domino
      harness.mode = 'games';
      harness.onItemTapped('category_domino');
      expect(harness.mode, equals('domino_games'));
      expect(harness.getTitle(), equals('ألعاب الدومينو'));
      final domino = harness.getItems();
      expect(domino, hasLength(2));
      allGamesEncountered.addAll(domino.map((e) => e['tag']!));

      // 4. Memory
      harness.mode = 'games';
      harness.onItemTapped('category_memory');
      expect(harness.mode, equals('memory_games'));
      expect(harness.getTitle(), equals('ألعاب الذاكرة والتركيز'));
      final memory = harness.getItems();
      expect(memory, hasLength(1));
      allGamesEncountered.addAll(memory.map((e) => e['tag']!));

      // 5. Sports
      harness.mode = 'games';
      harness.onItemTapped('category_sports');
      expect(harness.mode, equals('sports_games'));
      expect(harness.getTitle(), equals('ألعاب رياضية'));
      final sports = harness.getItems();
      expect(sports, hasLength(1));
      allGamesEncountered.addAll(sports.map((e) => e['tag']!));

      // Verify total 9 canonical games
      expect(allGamesEncountered, hasLength(9));
      expect(allGamesEncountered, equals([
        'UNO',
        'SCOPA',
        'NINETY_NINE',
        'FARKLE',
        'SNAKES_LADDERS',
        'DOMINO',
        'AMERICAN_DOMINO',
        'THIEF_HUNT',
        'TENNIS',
      ]));
    });

    test('Hierarchical Back: From Level 3 returns to Level 2 preserving category focus', () {
      harness.mode = 'cards_games';

      final shouldPop = harness.handleBack();
      expect(shouldPop, isFalse); // Handled internally
      expect(harness.mode, equals('games'));
      expect(harness.focusedTag, equals('category_cards'));
    });

    test('Hierarchical Back: From Level 2 returns to Level 1 preserving create focus', () {
      harness.mode = 'games';

      final shouldPop = harness.handleBack();
      expect(shouldPop, isFalse); // Handled internally
      expect(harness.mode, equals('main'));
      expect(harness.focusedTag, equals('create'));
    });

    test('Hierarchical Back: From Level 1 pops screen back to HomeView', () {
      harness.mode = 'main';

      final shouldPop = harness.handleBack();
      expect(shouldPop, isTrue); // Pops to parent
    });

    test('Selecting a game in Level 3 triggers TableView creation', () {
      harness.mode = 'cards_games';
      harness.onItemTapped('UNO');

      expect(harness.lastCreatedGame, equals('UNO'));
      expect(harness.lastNavigatedRoute, equals('TableView'));
    });
  });
}
