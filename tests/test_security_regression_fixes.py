import os
import json
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from server.app.main import app
from server.app.db.database import User, Friendship, SavedTable, ChallengeInvitation, SessionLocal
from server.app.hub.room_manager import room_manager
from server.app.core.security import create_access_token
from server.app.api.rooms import _can_access_private_room
from server.app.api.social import _check_rate_limit, _rate_limits

client = TestClient(app)

def get_auth_headers(user_id: int, username: str = 'testuser'):
    token = create_access_token({'sub': str(user_id), 'username': username, 'ver': 0})
    return {'Authorization': f'Bearer {token}'}

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_private_room_access_control(db_session):
    user_host = db_session.query(User).filter_by(id=101).first()
    if not user_host:
        user_host = User(id=101, username='host_user', display_name='Host', hashed_password='pw', coins=100, token_version=0)
        db_session.add(user_host)
    
    user_stranger = db_session.query(User).filter_by(id=102).first()
    if not user_stranger:
        user_stranger = User(id=102, username='stranger_user', display_name='Stranger', hashed_password='pw', coins=100, token_version=0)
        db_session.add(user_stranger)

    user_invited = db_session.query(User).filter_by(id=103).first()
    if not user_invited:
        user_invited = User(id=103, username='invited_user', display_name='Invited', hashed_password='pw', coins=100, token_version=0)
        db_session.add(user_invited)
    db_session.commit()

    room = room_manager.create_room(host_id=101, host_name='Host', game='SCOPA')
    room.rules['private'] = True
    
    try:
        assert not _can_access_private_room(room, user_stranger, db_session)
        assert _can_access_private_room(room, user_host, db_session)

        invite = ChallengeInvitation(
            sender_id=101,
            recipient_id=103,
            game='SCOPA',
            room_id=room.room_id,
            status='pending'
        )
        db_session.add(invite)
        db_session.commit()

        assert _can_access_private_room(room, user_invited, db_session)

        headers_stranger = get_auth_headers(102, 'stranger_user')
        res = client.post(f'/api/rooms/{room.room_id}/join', params={'as_spectator': False}, headers=headers_stranger)
        assert res.status_code == 403

        res_get = client.get(f'/api/rooms/{room.room_id}', headers=headers_stranger)
        assert res_get.status_code == 403

    finally:
        room_manager.delete_room(room.room_id)
        db_session.query(ChallengeInvitation).filter_by(room_id=room.room_id).delete()
        db_session.commit()

def test_atomic_challenge_creation_and_compensation(db_session):
    user1 = db_session.query(User).filter_by(id=201).first()
    if not user1:
        user1 = User(id=201, username='c_user1', display_name='C1', hashed_password='pw', coins=500, token_version=0)
        db_session.add(user1)
    else:
        user1.coins = 500
    user2 = db_session.query(User).filter_by(id=202).first()
    if not user2:
        user2 = User(id=202, username='c_user2', display_name='C2', hashed_password='pw', coins=500, token_version=0)
        db_session.add(user2)
    
    # Establish friendship so challenge is permitted
    f = db_session.query(Friendship).filter_by(user_id=201, friend_id=202).first()
    if not f:
        db_session.add(Friendship(user_id=201, friend_id=202))
        db_session.add(Friendship(user_id=202, friend_id=201))
    db_session.commit()

    from server.app.hub.ws_manager import ws_manager
    import asyncio
    class MockWs:
        async def send_json(self, msg):
            pass
    mock_sock = MockWs()
    with ws_manager._state_lock:
        ws_manager.connection_users[mock_sock] = 202
        ws_manager._ws_locks[mock_sock] = asyncio.Lock()

    headers = get_auth_headers(201, 'c_user1')
    try:
        # 1. Successful challenge path
        res = client.post('/api/users/202/challenge', json={'game': 'SCOPA'}, headers=headers)
        assert res.status_code == 200
        data = res.json()
        room_id = data['room_id']
        assert room_id in room_manager.rooms
        room_manager.delete_room(room_id)

        # 2. Insufficient coins path: no room should be created or leaked
        user1.coins = 2
        db_session.commit()
        res_poor = client.post('/api/users/202/challenge', json={'game': 'SCOPA'}, headers=headers)
        assert res_poor.status_code == 400
        assert not any(r.host_id == 201 for r in room_manager.rooms.values())

        # 3. DB commit failure path: in-memory room must be cleaned up and coins preserved
        user1.coins = 500
        db_session.commit()
        initial_room_count = len(room_manager.rooms)
        from unittest.mock import patch
        with patch('sqlalchemy.orm.Session.commit', side_effect=Exception('Simulated commit failure')):
            try:
                client.post('/api/users/202/challenge', json={'game': 'SCOPA'}, headers=headers)
            except Exception:
                pass
        assert len(room_manager.rooms) == initial_room_count
        db_session.refresh(user1)
        assert user1.coins == 500
    finally:
        with ws_manager._state_lock:
            ws_manager.connection_users.pop(mock_sock, None)
            ws_manager._ws_locks.pop(mock_sock, None)

def test_save_room_preconditions_and_hmac_integrity(db_session):
    user = db_session.query(User).filter_by(id=301).first()
    if not user:
        user = User(id=301, username='save_user', display_name='SaveUser', hashed_password='pw', coins=100, token_version=0)
        db_session.add(user)
    else:
        user.coins = 100
    db_session.commit()

    headers = get_auth_headers(301, 'save_user')
    
    # Precondition check: invalid room does not spend coins
    res = client.post('/api/rooms/nonexistent_room_xyz/save', headers=headers)
    assert res.status_code == 404
    db_session.refresh(user)
    assert user.coins == 100

    from server.app.core.security import SECRET_KEY
    from server.app.games.scopa import ScopaGame
    import pickle, hmac, hashlib
    
    # Build a real pickled ScopaGame engine
    real_game = ScopaGame([(301, 'SaveUser'), (999, 'BotPlayer')], target_score=11)
    real_engine_payload = pickle.dumps(real_game)
    correct_sig = hmac.new(SECRET_KEY.encode('utf-8'), real_engine_payload, hashlib.sha256).digest()
    
    # 1. Tampered signature must be strictly rejected with 400
    tampered_sig = b'X' * 32
    tampered_blob = tampered_sig + real_engine_payload

    now = datetime.now(timezone.utc)
    players = [{'user_id': 301, 'name': 'SaveUser', 'is_bot': False}, {'user_id': 999, 'name': 'BotPlayer', 'is_bot': True}]
    saved = SavedTable(
        user_id=301,
        game='SCOPA',
        serialized_engine=tampered_blob,
        rules_json='{}',
        scores_json='{}',
        players_json=json.dumps(players),
        opponents_summary='BotPlayer',
        saved_at=now,
        expires_at=now + timedelta(days=7)
    )
    db_session.add(saved)
    db_session.commit()

    res_tamper = client.post(f'/api/rooms/saved/{saved.id}/restore', headers=headers)
    assert res_tamper.status_code == 400
    assert 'غير صالحة أو تم التلاعب بها' in res_tamper.json().get('detail', '')

    # 2. Legacy unsigned pickle data must ALSO be rejected (no unsafe legacy fallback)
    saved.serialized_engine = real_engine_payload
    db_session.commit()
    res_legacy = client.post(f'/api/rooms/saved/{saved.id}/restore', headers=headers)
    assert res_legacy.status_code == 400

    # 3. Validly signed blob restores successfully into a real room
    valid_blob = correct_sig + real_engine_payload
    saved.serialized_engine = valid_blob
    db_session.commit()

    res_valid = client.post(f'/api/rooms/saved/{saved.id}/restore', headers=headers)
    assert res_valid.status_code == 200
    data = res_valid.json()
    assert data.get('ok') is True
    restored_room_id = data.get('room_id')
    assert restored_room_id in room_manager.rooms
    restored_room = room_manager.get_room(restored_room_id)
    assert restored_room.scopa_game is not None
    assert 301 in restored_room.players
    room_manager.delete_room(restored_room_id)

    # Clean up DB record
    db_session.query(SavedTable).filter_by(id=saved.id).delete()
    db_session.commit()

def test_target_user_request_null_handling(db_session):
    user = db_session.query(User).filter_by(id=1).first()
    if not user:
        user = User(id=1, username='admin', display_name='Admin', hashed_password='pw', coins=100, token_version=0)
        db_session.add(user)
        db_session.commit()
    
    room = room_manager.create_room(host_id=1, host_name='Admin', game='SCOPA')
    try:
        headers = get_auth_headers(1, 'admin')
        res = client.post(f'/api/rooms/{room.room_id}/kick', json={}, headers=headers)
        assert res.status_code == 400
        assert 'يجب تحديد معرف اللاعب' in res.json().get('detail', '')
    finally:
        room_manager.delete_room(room.room_id)

def test_websocket_query_token_in_production():
    from server.app.main import _ws_user_id
    from starlette.datastructures import Headers, QueryParams
    from unittest.mock import MagicMock

    token_admin = create_access_token({'sub': '1', 'username': 'admin', 'ver': 0})
    
    mock_ws = MagicMock()
    mock_ws.headers = Headers({})
    mock_ws.query_params = QueryParams(f'token={token_admin}')

    old_tv_env = os.environ.get('TABLEVERSE_ENV')
    old_lf_env = os.environ.get('LETSFLY_ENV')
    old_tv_flag = os.environ.get('TABLEVERSE_ALLOW_QUERY_TOKEN')
    old_lf_flag = os.environ.get('LETSFLY_ALLOW_QUERY_TOKEN')
    try:
        # Test TABLEVERSE_ENV=production blocks query token
        os.environ['TABLEVERSE_ENV'] = 'production'
        os.environ.pop('LETSFLY_ENV', None)
        os.environ.pop('TABLEVERSE_ALLOW_QUERY_TOKEN', None)
        os.environ.pop('LETSFLY_ALLOW_QUERY_TOKEN', None)
        assert _ws_user_id(mock_ws) is None

        # Test TABLEVERSE_ALLOW_QUERY_TOKEN=1 allows query token
        os.environ['TABLEVERSE_ALLOW_QUERY_TOKEN'] = '1'
        assert _ws_user_id(mock_ws) == 1

        # Test development mode allows query token
        os.environ['TABLEVERSE_ENV'] = 'development'
        os.environ.pop('TABLEVERSE_ALLOW_QUERY_TOKEN', None)
        assert _ws_user_id(mock_ws) == 1
    finally:
        if old_tv_env:
            os.environ['TABLEVERSE_ENV'] = old_tv_env
        else:
            os.environ.pop('TABLEVERSE_ENV', None)
        if old_lf_env:
            os.environ['LETSFLY_ENV'] = old_lf_env
        else:
            os.environ.pop('LETSFLY_ENV', None)
        if old_tv_flag:
            os.environ['TABLEVERSE_ALLOW_QUERY_TOKEN'] = old_tv_flag
        else:
            os.environ.pop('TABLEVERSE_ALLOW_QUERY_TOKEN', None)
        if old_lf_flag:
            os.environ['LETSFLY_ALLOW_QUERY_TOKEN'] = old_lf_flag
        else:
            os.environ.pop('LETSFLY_ALLOW_QUERY_TOKEN', None)

def test_rate_limiting():
    _rate_limits.clear()
    user_id = 9999
    for _ in range(5):
        _check_rate_limit(user_id, 'test_action', max_requests=5, window_seconds=10)
    
    with pytest.raises(Exception) as excinfo:
        _check_rate_limit(user_id, 'test_action', max_requests=5, window_seconds=10)
    assert excinfo.value.status_code == 429

def test_activity_event_text_neutralization(db_session):
    from server.app.activity import create_event
    user = db_session.query(User).filter_by(id=501).first()
    if not user:
        user = User(id=501, username='act_user', display_name='ActUser', hashed_password='pw', coins=10, token_version=0)
        db_session.add(user)
        db_session.commit()

    dirty_text = 'Line 1\r\nLine 2\x00\x08Evil Payload'
    event = create_event(db_session, recipient_id=501, category='TABLE_CHAT', text=dirty_text)
    assert '\r' not in event.text
    assert '\n' not in event.text
    assert '\x00' not in event.text
    assert 'Line 1 Line 2 Evil Payload' == event.text
