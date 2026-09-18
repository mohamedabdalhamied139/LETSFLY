class User {
  final int id;
  final String username;
  final String displayName;

  User({
    required this.id,
    required this.username,
    required this.displayName,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'] is int ? json['id'] : int.tryParse(json['id'].toString()) ?? 0,
      username: json['username'] ?? '',
      displayName: json['display_name'] ?? json['name'] ?? json['username'] ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'username': username,
    'display_name': displayName,
  };
}

class RoomSummary {
  final String id;
  final String name;
  final String gameType;
  final String hostName;
  final int currentPlayers;
  final int maxPlayers;
  final bool hasPassword;
  final String status;

  RoomSummary({
    required this.id,
    required this.name,
    required this.gameType,
    required this.hostName,
    required this.currentPlayers,
    required this.maxPlayers,
    required this.hasPassword,
    required this.status,
  });

  factory RoomSummary.fromJson(Map<String, dynamic> json) {
    return RoomSummary(
      id: json['id']?.toString() ?? '',
      name: json['name'] ?? '',
      gameType: json['game_type'] ?? '',
      hostName: json['host_name'] ?? '',
      currentPlayers: json['current_players'] is int
          ? json['current_players']
          : (json['players'] is List ? (json['players'] as List).length : 0),
      maxPlayers: json['max_players'] is int ? json['max_players'] : 4,
      hasPassword: json['has_password'] == true || json['is_locked'] == true,
      status: json['status'] ?? 'waiting',
    );
  }
}

class SavedTable {
  final int id;
  final int userId;
  final String roomId;
  final String game;
  final String gameLabel;
  final List<String> opponents;
  final String opponentsSummary;
  final dynamic savedAt;
  final dynamic expiresAt;
  final Map<String, dynamic> rawData;

  SavedTable({
    required this.id,
    this.userId = 0,
    this.roomId = '',
    required this.game,
    String? gameLabel,
    List<String>? opponents,
    String? opponentsSummary,
    required this.savedAt,
    this.expiresAt,
    Map<String, dynamic>? data,
    Map<String, dynamic>? rawData,
  })  : gameLabel = gameLabel ?? _resolveGameLabel(game),
        opponents = opponents ?? (opponentsSummary != null ? _parseOpponents(opponentsSummary) : []),
        opponentsSummary = opponentsSummary ??
            (opponents != null && opponents.isNotEmpty ? opponents.join('، ') : 'لا يوجد'),
        rawData = rawData ?? data ?? {};

  Map<String, dynamic>? get data => rawData.isNotEmpty ? rawData : null;

  DateTime get savedAtDateTime {
    if (savedAt is DateTime) return savedAt as DateTime;
    return DateTime.tryParse(savedAt?.toString() ?? '') ?? DateTime.now();
  }

  DateTime? get expiresAtDateTime {
    if (expiresAt == null) return null;
    if (expiresAt is DateTime) return expiresAt as DateTime;
    return DateTime.tryParse(expiresAt.toString());
  }

  factory SavedTable.fromJson(Map<String, dynamic> json) {
    final rawId = json['id'];
    final id = rawId is int ? rawId : int.tryParse(rawId?.toString() ?? '0') ?? 0;

    final rawUserId = json['user_id'];
    final userId = rawUserId is int ? rawUserId : int.tryParse(rawUserId?.toString() ?? '0') ?? 0;

    final roomId = json['room_id']?.toString() ?? '';
    final game = json['game']?.toString() ?? json['game_type']?.toString() ?? '';
    final gameLabel = json['game_label']?.toString() ?? _resolveGameLabel(game);

    List<String> opponents = [];
    String opponentsSummary = 'لا يوجد';

    if (json['opponents'] is List) {
      opponents = (json['opponents'] as List).map((e) => e.toString()).toList();
      opponentsSummary = opponents.isNotEmpty ? opponents.join('، ') : 'لا يوجد';
    } else if (json['opponents_summary'] != null && json['opponents_summary'].toString().isNotEmpty) {
      opponentsSummary = json['opponents_summary'].toString();
      opponents = _parseOpponents(opponentsSummary);
    } else if (json['opponents'] != null && json['opponents'].toString().isNotEmpty) {
      opponentsSummary = json['opponents'].toString();
      opponents = _parseOpponents(opponentsSummary);
    }

    final rawSaved = json['saved_at'] ?? json['saved_time'] ?? json['savedAt'] ?? '';
    final rawExpires = json['expires_at'] ?? json['expires_time'] ?? json['expiresAt'];

    Map<String, dynamic> rawData = {};
    if (json['data'] is Map<String, dynamic>) {
      rawData = Map<String, dynamic>.from(json['data'] as Map);
    } else if (json['rawData'] is Map<String, dynamic>) {
      rawData = Map<String, dynamic>.from(json['rawData'] as Map);
    }

    return SavedTable(
      id: id,
      userId: userId,
      roomId: roomId,
      game: game,
      gameLabel: gameLabel,
      opponents: opponents,
      opponentsSummary: opponentsSummary,
      savedAt: rawSaved,
      expiresAt: rawExpires,
      rawData: rawData,
      data: rawData.isNotEmpty ? rawData : null,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'user_id': userId,
        'room_id': roomId,
        'game': game,
        'game_label': gameLabel,
        'opponents': opponents,
        'opponents_summary': opponentsSummary,
        'saved_at': savedAt is DateTime ? (savedAt as DateTime).toIso8601String() : savedAt?.toString() ?? '',
        'expires_at': expiresAt is DateTime
            ? (expiresAt as DateTime).toIso8601String()
            : expiresAt?.toString() ?? '',
        if (rawData.isNotEmpty) 'data': rawData,
      };

  static List<String> _parseOpponents(String summary) {
    if (summary.trim() == 'لا يوجد' || summary.trim().isEmpty) return [];
    return summary
        .split(RegExp(r'[,،]\s*'))
        .map((s) => s.trim())
        .where((s) => s.isNotEmpty && s != 'لا يوجد')
        .toList();
  }

  static String _resolveGameLabel(String game) {
    switch (game.toUpperCase()) {
      case 'UNO':
        return 'أونو';
      case 'SCOPA':
        return 'إسكوبا';
      case 'NINETY_NINE':
        return 'تسعة وتسعون';
      case 'FARKLE':
        return 'فاركل';
      case 'SNAKES_LADDERS':
        return 'السلم والثعبان';
      case 'DOMINO':
        return 'دومينو كلاسيك';
      case 'AMERICAN_DOMINO':
        return 'دومينو أمريكاني';
      case 'THIEF_HUNT':
        return 'مطاردة اللص';
      case 'TENNIS':
        return 'التنس';
      default:
        return game.isNotEmpty ? game : 'لعبة';
    }
  }
}
