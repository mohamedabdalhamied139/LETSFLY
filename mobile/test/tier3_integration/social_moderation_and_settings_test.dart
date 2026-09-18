// Tier 3: Integration Tests for Table Moderation, Social Center, and Settings
// Verifies REST moderation endpoints, 10 canonical friend actions, user search & sort, and privacy/audio settings.

import '../harness/test_engine.dart';
import '../harness/mock_api_adapter.dart';

void defineTests() {
  group('Table Moderation, Social Center, and Settings', () {
    late MockApiAdapter api;

    setUp(() {
      api = MockApiAdapter();
    });

    test('Table Moderation: Transfer Host, Set Co-Host, and Substitute Player', () async {
      final roomId = 'room_mod_1';

      // 1. Transfer Host
      final transferRes = await api.transferHost(roomId, 10);
      expect(transferRes['ok'], isTrue);
      expect(api.hasCalled('POST', '/api/rooms/$roomId/transfer_host'), isTrue);
      final transferCall = api.getLastCall('/api/rooms/$roomId/transfer_host');
      expect(transferCall?['body']?['target_user_id'], equals(10));

      // 2. Set Co-Host
      final coHostRes = await api.setCoHost(roomId, 20);
      expect(coHostRes['ok'], isTrue);
      expect(api.hasCalled('POST', '/api/rooms/$roomId/set_co_host'), isTrue);
      final coHostCall = api.getLastCall('/api/rooms/$roomId/set_co_host');
      expect(coHostCall?['body']?['target_user_id'], equals(20));

      // 3. Substitute with Bot
      final subRes = await api.substitutePlayer(roomId, 30, isBot: true);
      expect(subRes['ok'], isTrue);
      expect(api.hasCalled('POST', '/api/rooms/$roomId/substitute'), isTrue);
      final subCall = api.getLastCall('/api/rooms/$roomId/substitute');
      expect(subCall?['body']?['target_user_id'], equals(30));
      expect(subCall?['body']?['is_bot'], isTrue);
    });

    test('Table Moderation: Kick, Ban, Voice Mute, and Voice Kick', () async {
      final roomId = 'room_mod_2';

      // 1. Kick Player
      final kickRes = await api.kickPlayer(roomId, 15);
      expect(kickRes['ok'], isTrue);
      expect(api.hasCalled('POST', '/api/rooms/$roomId/kick'), isTrue);

      // 2. Ban Player
      final banRes = await api.banPlayer(roomId, 15);
      expect(banRes['ok'], isTrue);
      expect(api.hasCalled('POST', '/api/rooms/$roomId/ban'), isTrue);

      // 3. Voice Mute Player
      final muteRes = await api.voiceMutePlayer(roomId, 15);
      expect(muteRes['ok'], isTrue);
      expect(api.hasCalled('POST', '/api/rooms/$roomId/voice/mute'), isTrue);

      // 4. Voice Kick Player
      final voiceKickRes = await api.voiceKickPlayer(roomId, 15);
      expect(voiceKickRes['ok'], isTrue);
      expect(api.hasCalled('POST', '/api/rooms/$roomId/voice/kick'), isTrue);
    });

    test('Table Moderation: Leave Room and Invite User', () async {
      final roomId = 'room_mod_3';

      // 1. Leave Room
      final leaveRes = await api.leaveRoom(roomId);
      expect(leaveRes['ok'], isTrue);
      expect(api.hasCalled('POST', '/api/rooms/$roomId/leave'), isTrue);

      // 2. Invite User
      final invRes = await api.inviteUserToRoom(roomId, 77);
      expect(invRes['ok'], isTrue);
      expect(api.hasCalled('POST', '/api/rooms/$roomId/invite/77'), isTrue);
    });

    test('Social: User Profile and Head-to-Head Statistics', () async {
      final targetUserId = 42;

      // 1. Profile retrieval
      final profile = await api.getUserProfile(targetUserId);
      expect(profile['id'], equals(targetUserId));
      expect(profile['display_name'], equals('لاعب تجريبي'));
      expect(profile['stats'] is List, isTrue);
      expect(api.hasCalled('GET', '/api/users/$targetUserId/profile'), isTrue);

      // 2. Head-to-Head retrieval
      final h2h = await api.getHeadToHead(targetUserId);
      expect(h2h['total_played'], equals(5));
      expect(h2h['you_wins'], equals(3));
      expect(h2h['other_wins'], equals(2));
      expect(api.hasCalled('GET', '/api/users/$targetUserId/head-to-head'), isTrue);
    });

    test('Social: Private Message and Notification Mutes', () async {
      final targetUserId = 88;

      // 1. Send PM
      final pmRes = await api.sendPrivateMessage(targetUserId, 'مرحبًا بك في اللعبة!');
      expect(pmRes['ok'], isTrue);
      final pmCall = api.getLastCall('/api/users/$targetUserId/messages');
      expect(pmCall?['body']?['message'], equals('مرحبًا بك في اللعبة!'));

      // 2. Notification Mutes GET & PUT
      final mutes = await api.getMutes(targetUserId);
      expect(mutes['all'], equals(0));

      final updateRes = await api.setMutes(targetUserId, {
        'all': true,
        'private_messages': true,
        'invitations': false,
        'presence': false,
      });
      expect(updateRes['ok'], isTrue);
      expect(api.hasCalled('PUT', '/api/users/$targetUserId/mutes'), isTrue);
    });

    test('Social: Direct Challenge and Coin Gifting', () async {
      final targetUserId = 99;

      // 1. Direct Challenge (3 coins cost on backend)
      final challengeRes = await api.challengeUser(targetUserId, game: 'UNO');
      expect(challengeRes['ok'], isTrue);
      expect(challengeRes['game'], equals('UNO'));
      expect(challengeRes['room_id'], equals('challenge_room_123'));
      final chalCall = api.getLastCall('/api/users/$targetUserId/challenge');
      expect(chalCall?['body']?['game'], equals('UNO'));

      // 2. Gift Coins (between 5 and 30)
      final giftRes = await api.giftUser(targetUserId, 20);
      expect(giftRes['ok'], isTrue);
      expect(giftRes['amount'], equals(20));
      final giftCall = api.getLastCall('/api/users/$targetUserId/gift');
      expect(giftCall?['body']?['amount'], equals(20));
    });

    test('Social: Search Users and Sorting (Alpha, Newest, Oldest)', () async {
      // 1. Search endpoint
      final searchRes = await api.searchUsers('test');
      expect(searchRes['users'] is List, isTrue);
      expect((searchRes['users'] as List).isNotEmpty, isTrue);
      expect(api.hasCalled('GET', '/api/users/search?q=test'), isTrue);

      // 2. Sorting logic simulation
      final sampleUsers = [
        {'display_name': 'باسم', 'connected_at': 100.0},
        {'display_name': 'أحمد', 'connected_at': 300.0},
        {'display_name': 'جمال', 'connected_at': 200.0},
      ];

      // Alpha sort
      final alphaList = List<Map<String, dynamic>>.from(sampleUsers);
      alphaList.sort((a, b) => a['display_name'].toString().compareTo(b['display_name'].toString()));
      expect(alphaList[0]['display_name'], equals('أحمد'));
      expect(alphaList[1]['display_name'], equals('باسم'));
      expect(alphaList[2]['display_name'], equals('جمال'));

      // Newest sort
      final newestList = List<Map<String, dynamic>>.from(sampleUsers);
      newestList.sort((a, b) => (b['connected_at'] as double).compareTo(a['connected_at'] as double));
      expect(newestList[0]['display_name'], equals('أحمد'));
      expect(newestList[1]['display_name'], equals('جمال'));
      expect(newestList[2]['display_name'], equals('باسم'));

      // Oldest sort
      final oldestList = List<Map<String, dynamic>>.from(sampleUsers);
      oldestList.sort((a, b) => (a['connected_at'] as double).compareTo(b['connected_at'] as double));
      expect(oldestList[0]['display_name'], equals('باسم'));
      expect(oldestList[1]['display_name'], equals('جمال'));
      expect(oldestList[2]['display_name'], equals('أحمد'));
    });

    test('Social: Unfriend and Block Actions', () async {
      final targetUserId = 55;

      // 1. Unfriend
      final unfriendRes = await api.unfriend(targetUserId);
      expect(unfriendRes['ok'], isTrue);
      expect(api.hasCalled('DELETE', '/api/friends/$targetUserId'), isTrue);

      // 2. Block
      final blockRes = await api.blockUser(targetUserId);
      expect(blockRes['ok'], isTrue);
      expect(api.hasCalled('POST', '/api/users/$targetUserId/block'), isTrue);
    });

    test('Settings: Privacy Policies and Audio Control Updates', () async {
      // 1. Privacy update
      final privRes = await api.updatePrivacy({
        'pm_policy': 'friends',
        'invite_policy': 'everyone',
        'join_policy': 'friends',
      });
      expect(privRes['ok'], isTrue);
      expect(api.hasCalled('PUT', '/api/users/me/privacy'), isTrue);
      final privCall = api.getLastCall('/api/users/me/privacy');
      expect(privCall?['body']?['pm_policy'], equals('friends'));
      expect(privCall?['body']?['join_policy'], equals('friends'));

      // 2. Audio volume calculations
      double vol = 0.8;
      bool isMuted = false;
      double effectiveVol = isMuted ? 0.0 : vol;
      expect(effectiveVol, equals(0.8));

      isMuted = true;
      effectiveVol = isMuted ? 0.0 : vol;
      expect(effectiveVol, equals(0.0));
    });
  });
}

void main() {
  defineTests();
}

