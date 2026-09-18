import 'package:flutter/material.dart';
import '../core/localization.dart';
import '../models/room_models.dart';
import '../services/api_service.dart';

class FriendsView extends StatefulWidget {
  const FriendsView({super.key});

  @override
  State<FriendsView> createState() => _FriendsViewState();
}

class _FriendsViewState extends State<FriendsView> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  List<User> _friends = [];
  List<User> _onlineUsers = [];
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() => _isLoading = true);
    try {
      final friendsRes = await ApiService.instance.getFriends();
      final onlineRes = await ApiService.instance.getOnlineUsers();

      if (mounted) {
        setState(() {
          if (friendsRes is List) {
            _friends = friendsRes.map((f) => User.fromJson(f)).toList();
          }
          if (onlineRes is List) {
            _onlineUsers = onlineRes.map((u) => User.fromJson(u)).toList();
          }
        });
      }
    } catch (_) {}
    if (mounted) setState(() => _isLoading = false);
  }

  void _sendOrCancelFriendRequest(User user, bool isPending) async {
    try {
      if (isPending) {
        await ApiService.instance.cancelFriendRequest(user.id);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(tr('تم إلغاء طلب الصداقة المرسل إلى {name}', {'name': user.displayName}))),
          );
        }
      } else {
        await ApiService.instance.sendFriendRequest(user.id);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(tr('تم إرسال طلب صداقة إلى {name}', {'name': user.displayName}))),
          );
        }
      }
      _loadData();
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(tr('الأصدقاء والمتواجدون')),
        bottom: TabBar(
          controller: _tabController,
          tabs: [
            Tab(text: tr('الأصدقاء (${_friends.length})')),
            Tab(text: tr('المتواجدون (${_onlineUsers.length})')),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : TabBarView(
              controller: _tabController,
              children: [
                // Friends List
                _friends.isEmpty
                    ? Center(child: Text(tr('لا يوجد أصدقاء حالياً.')))
                    : ListView.builder(
                        itemCount: _friends.length,
                        itemBuilder: (context, index) {
                          final friend = _friends[index];
                          return ListTile(
                            leading: const CircleAvatar(child: Icon(Icons.person)),
                            title: Text(friend.displayName),
                            subtitle: Text(friend.username),
                          );
                        },
                      ),
                // Online Users List
                _onlineUsers.isEmpty
                    ? Center(child: Text(tr('لا يوجد مستخدمون متواجدون الآن.')))
                    : ListView.builder(
                        itemCount: _onlineUsers.length,
                        itemBuilder: (context, index) {
                          final user = _onlineUsers[index];
                          final isFriend = _friends.any((f) => f.id == user.id);

                          return ListTile(
                            leading: const CircleAvatar(
                              backgroundColor: Colors.green,
                              child: Icon(Icons.person, color: Colors.white),
                            ),
                            title: Text(user.displayName),
                            subtitle: Text(user.username),
                            trailing: isFriend
                                ? const Icon(Icons.check, color: Colors.green)
                                : IconButton(
                                    tooltip: tr('إضافة صديق'),
                                    icon: const Icon(Icons.person_add),
                                    onPressed: () => _sendOrCancelFriendRequest(user, false),
                                  ),
                          );
                        },
                      ),
              ],
            ),
    );
  }
}
