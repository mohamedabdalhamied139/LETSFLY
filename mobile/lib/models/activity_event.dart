/// Canonical representation of an activity or chat event in TableVerse.
class ActivityEvent {
  final String id;
  final String category;
  final String text;
  final String time;
  final String? roomId;
  final String? eventType;
  final dynamic gameEventId;
  final Map<String, dynamic> raw;

  ActivityEvent({
    required this.id,
    required this.category,
    required this.text,
    this.time = '',
    this.roomId,
    this.eventType,
    this.gameEventId,
    Map<String, dynamic>? raw,
  }) : raw = raw ?? {};

  factory ActivityEvent.fromJson(Map<String, dynamic> json) {
    final rawCat = (json['category'] ?? json['type'] ?? 'ALL').toString().trim().toUpperCase();
    final cat = rawCat.isNotEmpty ? rawCat : 'ALL';
    final text = (json['text'] ?? json['message'] ?? '').toString().trim();
    final id = (json['id'] ?? json['event_id'] ?? DateTime.now().millisecondsSinceEpoch).toString();
    final time = (json['time'] ?? json['timestamp'] ?? '').toString();

    return ActivityEvent(
      id: id,
      category: cat,
      text: text,
      time: time,
      roomId: json['room_id']?.toString(),
      eventType: json['event_type']?.toString(),
      gameEventId: json['game_event_id'] ?? json['payload']?['game_event_id'],
      raw: Map<String, dynamic>.from(json),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'category': category,
    'text': text,
    'time': time,
    if (roomId != null) 'room_id': roomId,
    if (eventType != null) 'event_type': eventType,
    if (gameEventId != null) 'game_event_id': gameEventId,
    ...raw,
  };
}
