"""Friends, profiles, messaging, moderation, challenges and gifts."""
import time, json, threading, logging
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, update, text, select
from server.app.db.database import get_db, User, Friendship, FriendRequest, NotificationMute, Block, PrivateMessage, ChallengeInvitation, CoinTransaction, ActivityEvent
from server.app.api.users import get_current_user
from server.app.activity import create_event
from server.app.hub.ws_manager import ws_manager
from server.app.hub.room_manager import room_manager
from server.app.social_services import friend_ids, is_blocked, mute_flags, profile_payload, h2h, gift_fee, GAME_LABELS

router = APIRouter(prefix="/api", tags=["social"])
logger = logging.getLogger("tableverse.social_api")
_gift_lock = threading.Lock()
_challenge_accept_lock = threading.Lock()
_pm_send_lock = threading.Lock()

@contextmanager
def _locked_transaction(db, statement):
    """Acquire dialect-specific locks; callers commit their own mutations."""
    try:
        if db.get_bind().dialect.name == "sqlite":
            # End the read transaction opened by authentication before BEGIN.
            db.rollback()
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        else:
            db.execute(statement.with_for_update()).all()
        yield
    except Exception:
        db.rollback()
        raise

def _user_row(u): return {"id":u.id,"username":u.username,"display_name":u.display_name}

def _friend_ids(db,user_id): return friend_ids(db,user_id)

def _enrich_user(u, online_set, friends_set=None):
    d = _user_row(u)
    d["online"] = u.id in online_set
    if friends_set is not None:
        d["is_friend"] = u.id in friends_set
    in_table = False
    room_id = None
    room_private = False
    game_name = None
    with room_manager._lock:
        for r in room_manager.rooms.values():
            if u.id in r.players:
                in_table = True
                room_id = r.room_id
                room_private = bool((r.rules or {}).get("private", False))
                game_name = r.game
                break
    d["in_table"] = in_table
    d["room_id"] = room_id
    d["room_private"] = room_private
    d["game"] = game_name
    return d

@router.get("/users/search")
def search_users(q: str = "", user=Depends(get_current_user), db:Session=Depends(get_db)):
    q=str(q or "").strip()
    if len(q) < 2: return {"users": []}
    rows=db.query(User).filter(User.username.ilike(f"%{q}%"), User.id!=user.id).order_by(func.lower(User.username)).limit(50).all()
    online=set(ws_manager.online_user_ids()); friends_set=_friend_ids(db,user.id)
    return {"users":[_enrich_user(u, online, friends_set) for u in rows]}

@router.get("/notifications")
def notifications(limit:int=100,user=Depends(get_current_user),db:Session=Depends(get_db)):
    rows=db.query(ActivityEvent).filter(ActivityEvent.recipient_id==user.id, ActivityEvent.is_read==0).order_by(ActivityEvent.id.desc()).limit(max(1,min(limit,200))).all()
    return {"notifications":[{"id":e.id,"category":e.category,"event_type":e.event_type,"text":e.text,"actor_id":e.actor_id,"room_id":e.room_id,"payload": json.loads(e.payload) if e.payload else {},"created_at":e.created_at.isoformat()} for e in rows]}

@router.get("/messages")
def private_messages(limit:int=50,user=Depends(get_current_user),db:Session=Depends(get_db)):
    rows=db.query(PrivateMessage).filter((PrivateMessage.sender_id==user.id)|(PrivateMessage.recipient_id==user.id)).order_by(PrivateMessage.id.desc()).limit(max(1,min(limit,200))).all()
    ids={r.sender_id for r in rows}|{r.recipient_id for r in rows}
    users={u.id:u for u in db.query(User).filter(User.id.in_(ids)).all()} if ids else {}
    return {"messages":[{"id":r.id,"sender_id":r.sender_id,"recipient_id":r.recipient_id,"sender":users.get(r.sender_id).display_name if users.get(r.sender_id) else "","recipient":users.get(r.recipient_id).display_name if users.get(r.recipient_id) else "","message":r.message,"created_at":r.created_at.isoformat()} for r in rows]}

@router.get("/friends")
def friends(user=Depends(get_current_user), db:Session=Depends(get_db)):
    ids=_friend_ids(db,user.id); rows=db.query(User).filter(User.id.in_(ids)).order_by(func.lower(User.display_name)).all() if ids else []
    incoming=db.query(FriendRequest).filter(FriendRequest.recipient_id==user.id,FriendRequest.status=="pending").order_by(FriendRequest.id.desc()).all()
    outgoing=db.query(FriendRequest).filter(FriendRequest.sender_id==user.id,FriendRequest.status=="pending").order_by(FriendRequest.id.desc()).all()
    all_ids={r.sender_id for r in incoming}|{r.recipient_id for r in outgoing}
    users={u.id:u for u in db.query(User).filter(User.id.in_(all_ids)).all()} if all_ids else {}
    online=set(ws_manager.online_user_ids())
    return {"friends":[_enrich_user(u, online) for u in rows],"requests":[{"request_id":r.id,**_user_row(users[r.sender_id])} for r in incoming if r.sender_id in users],"sent":[{"request_id":r.id,**_user_row(users[r.recipient_id])} for r in outgoing if r.recipient_id in users]}

@router.post("/friends/requests/{recipient_id}")
def send_friend_request(recipient_id:int,user=Depends(get_current_user),db:Session=Depends(get_db)):
    if recipient_id==user.id: raise HTTPException(400,"لا يمكنك إرسال طلب صداقة لنفسك.")
    target=db.query(User).filter(User.id==recipient_id).first()
    if not target: raise HTTPException(404,"المستخدم غير موجود.")
    if is_blocked(db,user.id,recipient_id): raise HTTPException(403,"لا يمكن إرسال الطلب.")
    if recipient_id in _friend_ids(db,user.id): raise HTTPException(409,"أنتم أصدقاء بالفعل.")
    existing=db.query(FriendRequest).filter(FriendRequest.sender_id==user.id,FriendRequest.recipient_id==recipient_id,FriendRequest.status=="pending").first()
    if existing: raise HTTPException(409,"طلب الصداقة موجود بالفعل.")
    reverse=db.query(FriendRequest).filter(FriendRequest.sender_id==recipient_id,FriendRequest.recipient_id==user.id,FriendRequest.status=="pending").first()
    if reverse: raise HTTPException(409,"لديك طلب صداقة وارد من هذا المستخدم.")
    req=FriendRequest(sender_id=user.id,recipient_id=recipient_id,status="pending"); db.add(req); db.flush()
    event = create_event(db,recipient_id,"FRIEND_REQUESTS",f"{user.display_name} أرسل لك طلب صداقة.",event_type="FRIEND_REQUEST",actor_id=user.id,payload={"request_id":req.id}); db.commit()
    flags=mute_flags(db,recipient_id,user.id)
    ws_manager.broadcast_user(recipient_id,{"type":"activity_event","id":int(event.id) if event.id is not None else None,"category":"FRIEND_REQUESTS","event_type":"FRIEND_REQUEST","text":f"{user.display_name} أرسل لك طلب صداقة.","notification_muted":bool(flags["all"])})
    return {"ok":True,"id":req.id}

@router.get("/users/online")
def online_users(user=Depends(get_current_user), db: Session=Depends(get_db)):
    timing = ws_manager.online_users_with_connection_times()
    ids = set(timing)
    rows = db.query(User).filter(User.id.in_(ids)).all() if ids else []
    friend_set = _friend_ids(db, user.id)
    online_set = set(ws_manager.online_user_ids())
    result = []
    for u in rows:
        d = _enrich_user(u, online_set, friend_set)
        d["connected_at"] = timing.get(u.id, time.monotonic())
        result.append(d)
    result.sort(key=lambda x: str(x["display_name"]).casefold())
    return {"count": len(result), "users": result}

@router.post("/friends/requests/{request_id}/accept")
def accept_friend_request(request_id: int, user=Depends(get_current_user), db: Session=Depends(get_db)):
    req = db.query(FriendRequest).filter(FriendRequest.id==request_id, FriendRequest.recipient_id==user.id, FriendRequest.status=="pending").first()
    if not req: raise HTTPException(404, "طلب الصداقة غير موجود.")
    if is_blocked(db, user.id, req.sender_id):
        raise HTTPException(403, "لا يمكن قبول طلب الصداقة من مستخدم محظور.")

    # Complete the friendship transaction first. Notification delivery is
    # best-effort and must never turn a successful acceptance into a 500.
    if req.sender_id not in _friend_ids(db, user.id):
        db.add(Friendship(user_id=req.sender_id, friend_id=user.id))
    req.status = "accepted"
    db.commit()

    sender = db.query(User).filter(User.id==req.sender_id).first()
    if sender:
        try:
            event = create_event(db, sender.id, "FRIENDS", f"{user.display_name} قبل طلب صداقتك.", event_type="FRIEND_ACCEPTED", actor_id=user.id)
            db.commit()
            flags = mute_flags(db, sender.id, user.id)
            ws_manager.broadcast_user(sender.id, {"type": "activity_event", "id": int(event.id) if event.id is not None else None, "category": "FRIENDS", "event_type": "FRIEND_ACCEPTED", "text": f"{user.display_name} قبل طلب صداقتك.", "notification_muted": bool(flags["all"])})
        except Exception:
            db.rollback()
            logger.warning("Friend-accept notification failed for request %s", request_id, exc_info=True)

    return {"ok": True}

@router.delete("/friends/requests/{request_id}")
def cancel_friend_request(request_id:int,user=Depends(get_current_user),db:Session=Depends(get_db)):
    req=db.query(FriendRequest).filter(FriendRequest.id==request_id,FriendRequest.sender_id==user.id,FriendRequest.status=="pending").first()
    if not req: raise HTTPException(404,"طلب الصداقة غير موجود.")
    db.delete(req); db.commit(); return {"ok":True}

@router.post("/friends/requests/{request_id}/reject")
def reject_friend_request(request_id:int,user=Depends(get_current_user),db:Session=Depends(get_db)):
    req=db.query(FriendRequest).filter(FriendRequest.id==request_id,FriendRequest.recipient_id==user.id,FriendRequest.status=="pending").first()
    if not req: raise HTTPException(404,"طلب الصداقة غير موجود.")
    req.status="rejected"; db.commit(); return {"ok":True}

@router.put("/users/me/profile")
def update_my_profile(payload:dict,user=Depends(get_current_user),db:Session=Depends(get_db)):
    if "display_name" in (payload or {}):
        display_name=str(payload.get("display_name") or "").strip()
        if not display_name: raise HTTPException(400,"الاسم لا يمكن أن يكون فارغًا.")
        if len(display_name)>80: raise HTTPException(400,"الاسم طويل جدًا.")
        user.display_name=display_name
    if "gender" in (payload or {}):
        gender=str(payload.get("gender") or "").strip()
        if len(gender)>30: raise HTTPException(400,"الجنس غير صالح.")
        user.gender=gender or None
    if "bio" in (payload or {}):
        bio=str(payload.get("bio") or "").strip()
        if len(bio)>1000: raise HTTPException(413,"البايو طويل جدًا.")
        user.bio=bio or None
    db.commit(); return profile_payload(db,user.id,user.id)

@router.get("/users/{user_id}/profile")
def profile(user_id:int,user=Depends(get_current_user),db:Session=Depends(get_db)):
    data=profile_payload(db,user_id,user.id)
    if not data: raise HTTPException(404,"المستخدم غير موجود.")
    return data

@router.get("/users/{user_id}/head-to-head")
def head_to_head(user_id:int,user=Depends(get_current_user),db:Session=Depends(get_db)):
    if user_id==user.id: raise HTTPException(400,"لا يمكن عرض المواجهات مع نفسك.")
    if not db.query(User).filter(User.id==user_id).first(): raise HTTPException(404,"المستخدم غير موجود.")
    return h2h(db,user.id,user_id)

@router.post("/users/{user_id}/messages")
def send_private_message(user_id:int,payload:dict,user=Depends(get_current_user),db:Session=Depends(get_db)):
    text_value=str((payload or {}).get("message") or "").strip()
    if not text_value: raise HTTPException(400,"الرسالة لا يمكن أن تكون فارغة.")
    if len(text_value)>500: raise HTTPException(413,"الرسالة طويلة جدًا. الحد الأقصى 500 حرف.")

    # Serialize the complete PM validation/write path in this process.  Do not
    # issue a raw BEGIN: SQLAlchemy may already have an active transaction.
    with _pm_send_lock:
        pm_window_seconds = 10
        pm_max_in_window = 10
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=pm_window_seconds)
        recent_count = db.query(func.count(PrivateMessage.id)).filter(
            PrivateMessage.sender_id==user.id,
            PrivateMessage.created_at>=cutoff
        ).scalar() or 0
        if int(recent_count) >= pm_max_in_window:
            raise HTTPException(429,"تم تجاوز حد إرسال الرسائل مؤقتًا. حاول مرة أخرى بعد قليل.")

        target=db.query(User).filter(User.id==user_id).first()
        if not target: raise HTTPException(404,"المستخدم غير موجود.")
        if is_blocked(db,user.id,user_id): raise HTTPException(403,"لا يمكن مراسلة هذا المستخدم.")
        if target.pm_policy == "nobody": raise HTTPException(403, "هذا المستخدم لا يستقبل رسائل خاصة.")
        if target.pm_policy == "friends":
            if user.id not in _friend_ids(db, user_id):
                raise HTTPException(403, "هذا المستخدم يستقبل رسائل خاصة من الأصدقاء فقط.")

        # Strictly prohibit storing offline PMs in DB: if recipient is offline, reject immediately
        if not ws_manager.is_user_online(user_id):
            raise HTTPException(400, "المستخدم غير متصل حاليًا. لا يمكن إرسال رسائل خاصة للمستخدمين غير المتصلين.")

        row=PrivateMessage(sender_id=user.id,recipient_id=user_id,message=text_value)
        db.add(row)
        db.flush()
        event_in = create_event(db,user_id,"PRIVATE_MESSAGES",f"رسالة خاصة من {user.display_name}: {text_value}",event_type="PRIVATE_MESSAGE",actor_id=user.id,payload={"message_id":row.id, "sender_id": user.id, "sender": user.display_name, "message": text_value})
        event_out = create_event(db,user.id,"PRIVATE_MESSAGES",f"رسالة خاصة إلى {target.display_name}: {text_value}",event_type="PRIVATE_MESSAGE",actor_id=user.id,payload={"message_id":row.id, "recipient_id": target.id, "recipient": target.display_name, "message": text_value})
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

    # Delivery/notification is best effort and must never convert a persisted
    # message into an HTTP 500 after the database commit succeeded.
    try:
        flags=mute_flags(db,user_id,user.id)
        ws_manager.broadcast_user(user_id,{
            "type":"activity_event",
            "id": int(event_in.id) if event_in.id is not None else None,
            "category":"PRIVATE_MESSAGES",
            "event_type":"PRIVATE_MESSAGE",
            "text":f"رسالة خاصة من {user.display_name}: {text_value}",
            "actor_id":user.id,
            "payload":{"message_id":row.id, "sender_id":user.id, "sender":user.display_name, "message":text_value},
            "notification_muted":bool(flags["all"] or flags["private_messages"])
        })
        ws_manager.broadcast_user(user.id,{
            "type":"activity_event",
            "id": int(event_out.id) if event_out.id is not None else None,
            "category":"PRIVATE_MESSAGES",
            "event_type":"PRIVATE_MESSAGE",
            "text":f"رسالة خاصة إلى {target.display_name}: {text_value}",
            "actor_id":user.id,
            "payload":{"message_id":row.id, "recipient_id":target.id, "recipient":target.display_name, "message":text_value},
            "notification_muted":True
        })
    except Exception:
        logger.warning("Private-message notification delivery failed for message %s", row.id, exc_info=True)
    return {"ok":True,"id":row.id}

@router.get("/users/{user_id}/mutes")
def get_mutes(user_id:int,user=Depends(get_current_user),db:Session=Depends(get_db)):
    return mute_flags(db,user.id,user_id)

@router.put("/users/{user_id}/mutes")
def set_mutes(user_id:int,payload:dict,user=Depends(get_current_user),db:Session=Depends(get_db)):
    if user_id==user.id: raise HTTPException(400,"لا يمكن كتم نفسك.")
    if not db.query(User).filter(User.id==user_id).first(): raise HTTPException(404,"المستخدم غير موجود.")
    row=db.query(NotificationMute).filter_by(user_id=user.id,target_user_id=user_id).first()
    if not row: row=NotificationMute(user_id=user.id,target_user_id=user_id); db.add(row)
    for src,dst in (("all","mute_all"),("private_messages","mute_private_messages"),("invitations","mute_invitations"),("presence","mute_presence")):
        if src in (payload or {}): setattr(row,dst,1 if bool(payload[src]) else 0)
    db.commit(); return mute_flags(db,user.id,user_id)

@router.delete("/friends/{user_id}")
def remove_friend(user_id:int,user=Depends(get_current_user),db:Session=Depends(get_db)):
    rows=db.query(Friendship).filter(((Friendship.user_id==user.id)&(Friendship.friend_id==user_id))|((Friendship.user_id==user_id)&(Friendship.friend_id==user.id))).all()
    if not rows: raise HTTPException(404,"ليست هناك صداقة.")
    for r in rows: db.delete(r)
    db.commit(); return {"ok":True}

@router.post("/users/{user_id}/block")
def block_user(user_id:int,user=Depends(get_current_user),db:Session=Depends(get_db)):
    if user_id==user.id: raise HTTPException(400,"لا يمكنك حظر نفسك.")
    if not db.query(User).filter(User.id==user_id).first(): raise HTTPException(404,"المستخدم غير موجود.")
    if not db.query(Block).filter_by(user_id=user.id,blocked_user_id=user_id).first(): db.add(Block(user_id=user.id,blocked_user_id=user_id))
    for r in db.query(Friendship).filter(((Friendship.user_id==user.id)&(Friendship.friend_id==user_id))|((Friendship.user_id==user_id)&(Friendship.friend_id==user.id))).all(): db.delete(r)
    for fr in db.query(FriendRequest).filter(
        ((FriendRequest.sender_id==user.id) & (FriendRequest.recipient_id==user_id)) |
        ((FriendRequest.sender_id==user_id) & (FriendRequest.recipient_id==user.id)),
        FriendRequest.status == "pending"
    ).all():
        db.delete(fr)
    db.commit(); return {"ok": True}

@router.delete("/users/{user_id}/block")
def unblock_user(user_id: int, user=Depends(get_current_user), db: Session=Depends(get_db)):
    if user_id == user.id:
        raise HTTPException(400, "لا يمكنك إلغاء حظر نفسك.")
    b = db.query(Block).filter_by(user_id=user.id, blocked_user_id=user_id).first()
    if not b:
        raise HTTPException(404, "المستخدم ليس محظورًا.")
    db.delete(b)
    db.commit()
    return {"ok": True}

@router.get("/users/blocked")
def get_blocked_users(user=Depends(get_current_user), db: Session=Depends(get_db)):
    blocks = db.query(Block).filter_by(user_id=user.id).all()
    blocked_ids = [b.blocked_user_id for b in blocks]
    users = db.query(User).filter(User.id.in_(blocked_ids)).all() if blocked_ids else []
    return {"blocked": [_user_row(u) for u in users]}

@router.post("/users/{user_id}/challenge")
def challenge(user_id:int,payload:dict|None=None,user=Depends(get_current_user),db:Session=Depends(get_db)):
    if user_id==user.id: raise HTTPException(400,"لا يمكنك تحدي نفسك.")
    target=db.query(User).filter(User.id==user_id).first()
    if not target: raise HTTPException(404,"المستخدم غير موجود.")
    if not ws_manager.is_user_online(user_id):
        raise HTTPException(409, "لا يمكن إرسال دعوة تحدي للاعب غير متصل.")
    if user_id not in _friend_ids(db,user.id): raise HTTPException(403,"دعوة التحدي متاحة للأصدقاء فقط.")
    if is_blocked(db,user.id,user_id): raise HTTPException(403,"لا يمكن إرسال دعوة تحدي.")
    if target.invite_policy == "nobody":
        raise HTTPException(403, "هذا المستخدم لا يستقبل دعوات للعب.")
    if room_manager.user_in_any_room(user.id): raise HTTPException(409,"أنت داخل طاولة حاليًا.")
    if room_manager.user_in_any_room(user_id): raise HTTPException(409,"اللاعب موجود حاليًا في طاولة.")
    game=str((payload or {}).get("game") or "UNO").upper()
    from server.app.games.registry import get_plugin
    if not get_plugin(game): raise HTTPException(400,"اللعبة غير متاحة.")
    # Challenge cost is exactly 3 coins: 2 to open the table + 1 invitation fee.
    from sqlalchemy import update
    result=db.execute(update(User).where(User.id==user.id).where(User.coins>=3).values(coins=User.coins-3))
    if result.rowcount != 1: raise HTTPException(400,"رصيدك غير كافٍ. تحتاج إلى 3 عملات.")
    db.add(CoinTransaction(user_id=user.id,amount=-2,reason="challenge:open_table"))
    db.add(CoinTransaction(user_id=user.id,amount=-1,reason="challenge:invite"))
    room=room_manager.build_room(host_id=user.id,host_name=user.display_name,game=game)
    inv=ChallengeInvitation(sender_id=user.id,recipient_id=user_id,status="pending",room_id=room.room_id,game=game); db.add(inv); db.flush()
    event = create_event(db,user_id,"INVITATIONS",f"{user.display_name} دعاك للعب {GAME_LABELS.get(game,game)}.",event_type="CHALLENGE_INVITATION",actor_id=user.id,room_id=room.room_id,payload={"invitation_id":inv.id,"room_id":room.room_id,"game":game,"sender_id":user.id,"sender":user.display_name})
    db.commit()
    room_manager.register_room(room)
    ws_manager.broadcast_lobby({"type":"room_created","room_id":room.room_id,"game":game})
    flags=mute_flags(db,user_id,user.id)
    ws_manager.broadcast_user(user_id,{
        "type":"activity_event",
        "id": int(event.id) if event.id is not None else None,
        "category":"INVITATIONS",
        "event_type":"CHALLENGE_INVITATION",
        "text":f"{user.display_name} دعاك للعب {GAME_LABELS.get(game,game)}.",
        "actor_id":user.id,
        "room_id":room.room_id,
        "payload":{"invitation_id":inv.id, "room_id":room.room_id, "game":game, "sender_id":user.id, "sender":user.display_name},
        "notification_muted":bool(flags["all"] or flags["invitations"])
    })
    return {"ok":True,"id":inv.id,"room_id":room.room_id,"game":game,"coins_charged":3}

@router.post("/invitations/{invitation_id}/accept")
async def accept_challenge(invitation_id:int,user=Depends(get_current_user),db:Session=Depends(get_db)):
    accepting_user_id = user.id
    # Serialize invitation acceptance at the database level so two concurrent
    # accepts cannot both consume the same pending invitation.
    with _challenge_accept_lock, _locked_transaction(
        db, select(ChallengeInvitation).where(
            ChallengeInvitation.id == invitation_id,
            ChallengeInvitation.recipient_id == user.id,
        )
    ):
        inv=db.query(ChallengeInvitation).filter_by(id=invitation_id,recipient_id=user.id,status="pending").first()
        if not inv: raise HTTPException(404,"الدعوة غير موجودة.")
        if room_manager.user_in_any_room(user.id): raise HTTPException(409,"أنت داخل طاولة حاليًا.")
        room=room_manager.get_room(inv.room_id) if inv.room_id else None
        if room is None:
            ev=db.query(ActivityEvent).filter(ActivityEvent.recipient_id==user.id,ActivityEvent.event_type=="CHALLENGE_INVITATION").order_by(ActivityEvent.id.desc()).first()
            if ev:
                try: room=room_manager.get_room(json.loads(ev.payload).get("room_id"))
                except Exception:
                    logger.warning("Failed to recover challenge room from invitation event %s", invitation_id, exc_info=True)
                    room=None
        if room is None: raise HTTPException(410,"الطاولة لم تعد متاحة.")
        async with room._mutation_lock:
            if room.status != "waiting" or len(room.players) >= 10:
                raise HTTPException(410,"الطاولة لم تعد متاحة.")
            if room_manager.user_in_any_room(user.id):
                raise HTTPException(409,"أنت داخل طاولة حاليًا.")
            inv.status="accepted"
            try:
                db.commit()
                joined = room_manager.add_player_exclusive(room, user.id, user.display_name)
                if not joined:
                    raise HTTPException(409,"أنت داخل طاولة حاليًا.")
            except Exception:
                db.rollback()
                raise
        ws_manager.broadcast_lobby({"type":"room_updated","room_id":room.room_id})
        return {"ok":True,"room_id":room.room_id}


@router.post("/invitations/{invitation_id}/reject")
async def reject_challenge(invitation_id:int,user=Depends(get_current_user),db:Session=Depends(get_db)):
    deleted_room_id = None
    with _challenge_accept_lock, _locked_transaction(db, select(ChallengeInvitation).where(ChallengeInvitation.id == invitation_id, ChallengeInvitation.recipient_id == user.id)):
        inv=db.query(ChallengeInvitation).filter_by(id=invitation_id,recipient_id=user.id,status="pending").first()
        if not inv: raise HTTPException(404,"الدعوة غير موجودة.")
        room = room_manager.get_room(inv.room_id) if inv.room_id else None
        if room:
            async with room._mutation_lock:
                inv.status="rejected"
                sender = db.query(User).filter(User.id == inv.sender_id).first()
                if sender:
                    sender.coins += 3
                    db.add(CoinTransaction(user_id=sender.id, amount=3, reason="challenge_refund:rejected"))
                db.commit()
                if room.status == "waiting":
                    room_manager.delete_room(room.room_id)
                    deleted_room_id = room.room_id
        else:
            inv.status="rejected"
            sender = db.query(User).filter(User.id == inv.sender_id).first()
            if sender:
                sender.coins += 3
                db.add(CoinTransaction(user_id=sender.id, amount=3, reason="challenge_refund:rejected"))
            db.commit()
    if deleted_room_id:
        ws_manager.broadcast_lobby({"type": "room_deleted", "room_id": deleted_room_id})
    return {"ok":True}


@router.post("/users/{user_id}/gift")
def gift(user_id:int,payload:dict,user=Depends(get_current_user),db:Session=Depends(get_db)):
    if user_id==user.id: raise HTTPException(400,"لا يمكنك إرسال هدية لنفسك.")
    if user_id not in _friend_ids(db,user.id): raise HTTPException(403,"تحويل العملات متاح بين الأصدقاء فقط.")
    target=db.query(User).filter(User.id==user_id).first()
    if not target: raise HTTPException(404,"المستخدم غير موجود.")
    if is_blocked(db,user.id,user_id): raise HTTPException(403,"لا يمكن إرسال الهدية.")
    try: amount=int((payload or {}).get("amount"))
    except Exception: raise HTTPException(400,"قيمة الهدية غير صحيحة.")
    try: fee=gift_fee(amount)
    except ValueError as e: raise HTTPException(400,str(e))
    now=datetime.now(timezone.utc); day_start=now.replace(hour=0,minute=0,second=0,microsecond=0); month_start=now.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    with _gift_lock, _locked_transaction(
        db, select(User).where(User.id.in_([user.id, user_id])).order_by(User.id)
    ):
        # Serialize the complete wallet-limit check + balance mutation at the
        # database level too. The process-local lock alone is not enough when
        # multiple API workers/processes handle requests concurrently. SQLite
        # BEGIN IMMEDIATE gives SQLite a single writer; PostgreSQL locks both
        # wallets in ID order to avoid deadlocks for reciprocal transfers.
        # Only the actual gift debit counts toward the transfer limits.
        # gift_fee:* must never be included in the daily/monthly allowance.
        daily_debit=db.query(func.coalesce(func.sum(CoinTransaction.amount),0)).filter(
            CoinTransaction.user_id==user.id,
            CoinTransaction.reason.like("gift:%"),
            CoinTransaction.created_at>=day_start
        ).scalar() or 0
        monthly_debit=db.query(func.coalesce(func.sum(CoinTransaction.amount),0)).filter(
            CoinTransaction.user_id==user.id,
            CoinTransaction.reason.like("gift:%"),
            CoinTransaction.created_at>=month_start
        ).scalar() or 0
        daily_used=max(0, -int(daily_debit))
        monthly_used=max(0, -int(monthly_debit))
        if daily_used+amount>30: raise HTTPException(400,"تجاوزت حد الهدايا اليومي البالغ 30 عملة للحساب.")
        if monthly_used+amount>150: raise HTTPException(400,"تجاوزت حد الهدايا الشهري البالغ 150 عملة للحساب.")
        total=amount+fee
        result = db.execute(update(User).where(User.id == user.id).where(User.coins >= total).values(coins=User.coins - total))
        if result.rowcount != 1: raise HTTPException(400,f"رصيدك غير كافٍ. تحتاج {total} عملة.")
        db.execute(update(User).where(User.id == user_id).values(coins=User.coins + amount))
        db.add(CoinTransaction(user_id=user.id,amount=-amount,reason=f"gift:{user_id}")); db.add(CoinTransaction(user_id=user.id,amount=-fee,reason=f"gift_fee:{user_id}"))
        db.add(CoinTransaction(user_id=user_id,amount=amount,reason=f"gift_received:{user.id}"))
        event = create_event(db,user_id,"GIFTS",f"أرسل لك {user.display_name} هدية قدرها {amount} عملة.",event_type="GIFT_RECEIVED",actor_id=user.id,payload={"amount":amount,"fee":fee,"sender_id":user.id,"sender":user.display_name})
        db.commit()
    flags=mute_flags(db,user_id,user.id); ws_manager.broadcast_user(user_id,{"type":"activity_event","id":int(event.id) if event.id is not None else None,"category":"GIFTS","event_type":"GIFT_RECEIVED","text":f"أرسل لك {user.display_name} هدية قدرها {amount} عملة.","actor_id":user.id,"payload":{"amount":amount,"fee":fee,"sender_id":user.id,"sender":user.display_name},"notification_muted":bool(flags["all"])})
    return {"ok":True,"amount":amount,"fee":fee,"total_charged":total,"daily_used":daily_used+amount,"monthly_used":monthly_used+amount}

@router.post("/feedback")
def send_feedback(payload:dict,user=Depends(get_current_user),db:Session=Depends(get_db)):
    from server.app.db.database import Feedback
    message=str((payload or {}).get("message") or "").strip()
    if not message: raise HTTPException(400,"الرسالة لا يمكن أن تكون فارغة.")
    if len(message)>4000: raise HTTPException(413,"الرسالة طويلة جدًا.")
    db.add(Feedback(user_id=user.id,message=message)); db.commit(); return {"ok":True}


@router.put("/users/me/privacy")
def update_privacy(payload: dict, user=Depends(get_current_user), db: Session=Depends(get_db)):
    u = db.query(User).filter(User.id == user.id).first()
    valid_policies = ["everyone", "friends", "nobody"]
    pm = payload.get("pm_policy")
    inv = payload.get("invite_policy")
    join = payload.get("join_policy")
    if pm in valid_policies: u.pm_policy = pm
    if inv in valid_policies: u.invite_policy = inv
    if join in valid_policies: u.join_policy = join
    db.commit()
    return {"ok": True}
