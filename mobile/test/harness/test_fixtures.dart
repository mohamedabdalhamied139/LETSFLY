// Test fixtures and authoritative data matching Windows desktop client specifications.

export '../../lib/models/room_models.dart' show SavedTable;

class TestFixtures {
  // Canonical 8 Menu Items in Windows Order
  static const List<Map<String, String>> canonicalMenuItems = [
    {'tag': 'rooms', 'title': 'الطاولات'},
    {'tag': 'friends', 'title': 'الأصدقاء'},
    {'tag': 'online', 'title': 'المتصلون ({count})'},
    {'tag': 'my_profile', 'title': 'ملفي الشخصي'},
    {'tag': 'settings', 'title': 'الإعدادات'},
    {'tag': 'notifications', 'title': 'الإشعارات'},
    {'tag': 'contact', 'title': 'تحدث معنا'},
    {'tag': 'logout', 'title': 'تسجيل الخروج'},
  ];

  // Canonical 8 Activity Categories
  static const List<String> canonicalActivityCategories = [
    'TABLE_CHAT',
    'PRIVATE_MESSAGES',
    'FRIENDS',
    'GAMEPLAY',
    'ALL',
    'FRIEND_REQUESTS',
    'INVITATIONS',
    'GIFTS',
  ];

  static const Map<String, String> categoryLabels = {
    'ALL': 'الجميع',
    'TABLE_CHAT': 'دردشة الطاولات',
    'PRIVATE_MESSAGES': 'الرسائل الخاصة',
    'FRIENDS': 'الأصدقاء',
    'GAMEPLAY': 'اللعب',
    'FRIEND_REQUESTS': 'طلبات الصداقة',
    'INVITATIONS': 'الدعوات',
    'GIFTS': 'الهدايا',
  };

  // 9 Canonical Games Specification
  static const List<Map<String, String>> canonicalGames = [
    {'id': 'UNO', 'name': 'أونو', 'category': 'category_cards', 'mode': 'cards_games'},
    {'id': 'SCOPA', 'name': 'إسكوبا', 'category': 'category_cards', 'mode': 'cards_games'},
    {'id': 'NINETY_NINE', 'name': 'تسعة وتسعون', 'category': 'category_cards', 'mode': 'cards_games'},
    {'id': 'FARKLE', 'name': 'فاركل', 'category': 'category_dice', 'mode': 'dice_games'},
    {'id': 'SNAKES_LADDERS', 'name': 'السلم والثعبان', 'category': 'category_dice', 'mode': 'dice_games'},
    {'id': 'DOMINO', 'name': 'دومينو', 'category': 'category_domino', 'mode': 'domino_games'},
    {'id': 'AMERICAN_DOMINO', 'name': 'دومينو أمريكي', 'category': 'category_domino', 'mode': 'domino_games'},
    {'id': 'THIEF_HUNT', 'name': 'صيد اللص', 'category': 'category_memory', 'mode': 'memory_games'},
    {'id': 'TENNIS', 'name': 'تنس', 'category': 'category_sports', 'mode': 'sports_games'},
  ];

  // 5 Categories for Level 2 Menu
  static const List<Map<String, String>> canonicalGameCategories = [
    {'tag': 'category_cards', 'label': 'ألعاب الكروت'},
    {'tag': 'category_dice', 'label': 'ألعاب النرد'},
    {'tag': 'category_domino', 'label': 'ألعاب الدومينو'},
    {'tag': 'category_memory', 'label': 'ألعاب الذاكرة'},
    {'tag': 'category_sports', 'label': 'ألعاب الرياضة'},
  ];

  // Sample Users
  static final Map<String, dynamic> sampleUserJson = {
    'id': 42,
    'username': 'ahmed_player',
    'display_name': 'أحمد البطل',
  };

  static final Map<String, dynamic> sampleReturningUserJson = {
    'id': 105,
    'username': 'sara_vip',
    'display_name': 'سارة',
    'current_room_id': 'room_uno_101',
  };

  // Sample Rooms
  static final List<Map<String, dynamic>> sampleRoomsJson = [
    {
      'id': 'room_1',
      'name': 'طاولة أونو الكبرى',
      'game_type': 'UNO',
      'game_label': 'أونو',
      'host_name': 'أحمد',
      'players': ['أحمد', 'محمد', 'سارة'],
      'max_players': 10,
      'status': 'waiting',
      'has_password': false,
    },
    {
      'id': 'room_2',
      'name': 'تحدي إسكوبا السريع',
      'game_type': 'SCOPA',
      'game_label': 'إسكوبا',
      'host_name': 'خالد',
      'players': ['خالد', 'عمر'],
      'max_players': 10,
      'status': 'playing',
      'has_password': true,
    },
    {
      'id': 'room_3',
      'name': 'بطولة الدومينو',
      'game_type': 'DOMINO',
      'game_label': 'دومينو',
      'host_name': 'سامي',
      'players': ['سامي'],
      'max_players': 10,
      'status': 'waiting',
      'has_password': false,
    },
  ];

  // Sample Saved Tables
  static final List<Map<String, dynamic>> sampleSavedTablesJson = [
    {
      'id': 101,
      'user_id': 42,
      'room_id': 'saved_room_uno',
      'game': 'UNO',
      'opponents_summary': 'محمد، سارة',
      'saved_at': '2026-09-18T14:30:00Z',
      'expires_at': '2026-09-25T14:30:00Z',
      'data': {'scores': {'42': 120, '43': 95}},
    },
    {
      'id': 102,
      'user_id': 42,
      'room_id': 'saved_room_domino',
      'game': 'DOMINO',
      'opponents_summary': 'خالد',
      'saved_at': '2026-09-17T18:15:00Z',
      'expires_at': '2026-09-24T18:15:00Z',
      'data': {'rounds_won': {'42': 2, '44': 1}},
    },
    {
      'id': 103,
      'user_id': 42,
      'room_id': 'saved_room_tennis',
      'game': 'TENNIS',
      'opponents_summary': 'عمر',
      'saved_at': '2026-09-16T10:00:00Z',
      'expires_at': '2026-09-23T10:00:00Z',
      'data': {'sets': [6, 4]},
    },
  ];

  // Sample Activity Events
  static final List<Map<String, dynamic>> sampleActivityEvents = [
    {
      'id': 1001,
      'category': 'GAMEPLAY',
      'event_type': 'card_played',
      'room_id': 'room_1',
      'game_event_id': 'ge_501',
      'text': 'لعب أحمد بطاقة 5 حمراء',
      'time': '14:31',
    },
    {
      'id': 1002,
      'category': 'TABLE_CHAT',
      'event_type': 'chat_message',
      'room_id': 'room_1',
      'text': 'محمد: بالتوفيق للجميع!',
      'time': '14:32',
    },
    {
      'id': 1003,
      'category': 'FRIENDS',
      'event_type': 'friend_online',
      'text': 'سارة الآن متصلة',
      'time': '14:33',
    },
    {
      'id': 1004,
      'category': 'PRIVATE_MESSAGES',
      'event_type': 'pm_received',
      'text': 'رسالة خاصة من خالد: هل تلعب جولة جديدة؟',
      'time': '14:34',
    },
    {
      'id': 1005,
      'category': 'INVITATIONS',
      'event_type': 'room_invite',
      'invitation_id': 88,
      'room_id': 'room_2',
      'text': 'دعاك خالد للانضمام إلى طاولة إسكوبا',
      'time': '14:35',
    },
    {
      'id': 1006,
      'category': 'GIFTS',
      'event_type': 'coins_received',
      'text': 'لقد استلمت 500 قطعة نقدية من سامي',
      'time': '14:36',
    },
    {
      'id': 1007,
      'category': 'FRIEND_REQUESTS',
      'event_type': 'request_received',
      'text': 'أرسل عمر طلب صداقة إليك',
      'time': '14:37',
    },
  ];
}
