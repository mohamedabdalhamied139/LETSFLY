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
