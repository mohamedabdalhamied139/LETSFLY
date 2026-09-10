"""Shared social/profile/stats/wallet services used by the API layer."""
from datetime import datetime, timezone, timedelta
import json
from sqlalchemy import func
from server.app.db.database import (User, Friendship, FriendRequest, NotificationMute, Block,
    PrivateMessage, ChallengeInvitation, MatchRecord, MatchParticipant, CoinTransaction, PlayerRating)
from server.app.activity import create_event

GAME_LABELS = {
    "UNO":"أونو", "SCOPA":"إسكوبا", "NINETY_NINE":"تسعة وتسعون", "FARKLE":"فاركل",
    "SNAKES_LADDERS":"السلم والثعبان", "DOMINO":"الدومينو", "AMERICAN_DOMINO":"الدومينو الأمريكي",
    "THIEF_HUNT":"صيد اللص", "TENNIS":"التنس"
}

def friend_ids(db, user_id):
    rows = db.query(Friendship).filter((Friendship.user_id==user_id)|(Friendship.friend_id==user_id)).all()
    return {r.friend_id if r.user_id==user_id else r.user_id for r in rows}

def is_blocked(db, a, b):
    return db.query(Block).filter(Block.user_id==a, Block.blocked_user_id==b).first() is not None or db.query(Block).filter(Block.user_id==b, Block.blocked_user_id==a).first() is not None

def mute_flags(db, owner_id, target_id):
    row=db.query(NotificationMute).filter_by(user_id=owner_id,target_user_id=target_id).first()
    return {"all":bool(row and row.mute_all),"private_messages":bool(row and row.mute_private_messages),"invitations":bool(row and row.mute_invitations),"presence":bool(row and row.mute_presence)}

def rating_tier(rating):
    rating=int(rating or 1000)
    if rating < 1100: return "Bronze"
    if rating < 1300: return "Silver"
    if rating < 1500: return "Gold"
    if rating < 1800: return "Platinum"
    return "Diamond"

def _rating_row(db, user_id, game):
    row=db.query(PlayerRating).filter_by(user_id=int(user_id), game=str(game)).first()
    if not row:
        row=PlayerRating(user_id=int(user_id), game=str(game), rating=1000)
        db.add(row); db.flush()
    return row

def _apply_ratings(db, game, humans, winners):
    humans=[int(x) for x in humans if int(x)>0]
    winners={int(x) for x in winners if int(x)>0}
    rows={uid:_rating_row(db,uid,game) for uid in humans}
    if len(humans) < 2:
        for uid,row in rows.items(): row.played += 1; row.wins += int(uid in winners); row.losses += int(uid not in winners)
        return
    avg=sum(rows[uid].rating for uid in humans)/len(humans)
    for uid,row in rows.items():
        row.played += 1
        won=uid in winners
        expected=1/(1+10**((avg-row.rating)/400))
        row.rating=max(0, round(row.rating + 32*((1 if won else 0)-expected)))
        row.wins += int(won); row.losses += int(not won)

def record_match(db, game, room_id, participant_ids, winner_ids):
    humans=sorted({int(x) for x in participant_ids if x is not None and int(x)>0})
    winners={int(x) for x in winner_ids if x is not None and int(x)>0}
    if not humans: return None
    if room_id:
        existing = db.query(MatchRecord).filter_by(room_id=room_id).first()
        if existing: return existing
    row=MatchRecord(game=str(game),room_id=room_id,winner_ids=json.dumps(sorted(winners)),human_player_ids=json.dumps(humans))
    try:
        db.add(row); db.flush()
    except Exception:
        db.rollback()
        if room_id:
            existing = db.query(MatchRecord).filter_by(room_id=room_id).first()
            if existing: return existing
        raise
    _apply_ratings(db, game, humans, winners)
    for uid in humans:
        db.add(MatchParticipant(match_id=row.id,user_id=uid,won=1 if uid in winners else 0))
    from server.app.hub.ws_manager import ws_manager
    users={u.id:u for u in db.query(User).filter(User.id.in_(humans)).all()}
    game_name=GAME_LABELS.get(str(game),str(game))
    for uid in humans:
        outcome="فزت" if uid in winners else "خسرت"
        text=f"انتهت مباراة {game_name}: {outcome}."
        event = create_event(db,uid,"GAMEPLAY",text,event_type="MATCH_RESULT",room_id=room_id,payload={"match_id":row.id,"game":game,"outcome":outcome})
        flags={"all": bool(db.query(NotificationMute).filter(NotificationMute.user_id==uid, NotificationMute.mute_all==1).first())}
        ws_manager.broadcast_user(uid,{"type":"activity_event","id":int(event.id) if event.id is not None else None,"category":"GAMEPLAY","event_type":"MATCH_RESULT","text":text,"room_id":room_id,"notification_muted":bool(flags["all"])})
    return row

def profile_payload(db, target_id, viewer_id=None):
    u=db.query(User).filter(User.id==target_id).first()
    if not u: return None
    stats=[]
    games=db.query(MatchRecord.game, func.count(MatchParticipant.id)).join(MatchParticipant, MatchParticipant.match_id==MatchRecord.id).filter(MatchParticipant.user_id==target_id).group_by(MatchRecord.game).all()
    for game,count in games:
        wins=db.query(func.count(MatchParticipant.id)).filter(MatchParticipant.user_id==target_id, MatchParticipant.won==1).join(MatchRecord, MatchRecord.id==MatchParticipant.match_id).filter(MatchRecord.game==game).scalar() or 0
        losses=int(count)-int(wins)
        rr=db.query(PlayerRating).filter_by(user_id=target_id,game=game).first()
        rating=int(rr.rating) if rr else 1000
        stats.append({"game":game,"game_name":GAME_LABELS.get(game,game),"played":int(count),"wins":int(wins),"losses":int(losses),"rating":rating,"tier":rating_tier(rating)})
    from server.app.hub.ws_manager import ws_manager
    online = int(u.id) in set(ws_manager.online_user_ids())
    total_played=sum(int(x["played"]) for x in stats); total_wins=sum(int(x["wins"]) for x in stats); total_losses=sum(int(x["losses"]) for x in stats)
    for item in stats:
        rating=int(item.get("rating",1000))
        item["rank"]=int(db.query(func.count(PlayerRating.id)).filter(PlayerRating.game==item["game"],PlayerRating.rating>rating).scalar() or 0)+1
    strongest=max(stats,key=lambda x:int(x.get("played",0))) if stats else None
    return {"id":u.id,"username":u.username,"display_name":u.display_name,"gender":u.gender or "غير محدد","bio":u.bio or "","online":online,"last_seen_at":u.last_seen_at.isoformat() if u.last_seen_at else None,"stats":stats,"total_played":total_played,"total_wins":total_wins,"total_losses":total_losses,"top_game":strongest.get("game_name") if strongest else None,"coins":u.coins if viewer_id==u.id else None}

def h2h(db, a, b):
    matches=(db.query(MatchRecord).join(MatchParticipant,MatchParticipant.match_id==MatchRecord.id)
        .filter(MatchParticipant.user_id==a).all())
    result=[]
    for m in matches:
        ids=set(json.loads(m.human_player_ids or "[]"))
        if b not in ids: continue
        p={x.user_id:bool(x.won) for x in db.query(MatchParticipant).filter(MatchParticipant.match_id==m.id).all()}
        result.append({"game":m.game,"game_name":GAME_LABELS.get(m.game,m.game),"played":1,"you_won":bool(p.get(a,False)),"other_won":bool(p.get(b,False)),"date":m.created_at.isoformat()})
    summary={}
    for r in result:
        s=summary.setdefault(r["game"],{"game":r["game"],"game_name":r["game_name"],"played":0,"you_wins":0,"other_wins":0})
        s["played"]+=1; s["you_wins"]+=int(r["you_won"]); s["other_wins"]+=int(r["other_won"])
    return {"matches":result,"summary":list(summary.values()),"total_played":len(result),"you_wins":sum(r["you_won"] for r in result),"other_wins":sum(r["other_won"] for r in result)}

def gift_fee(amount):
    amount=int(amount)
    if 5<=amount<=10: return 2
    if 11<=amount<=20: return 10
    if 21<=amount<=30: return 15
    raise ValueError("قيمة الهدية يجب أن تكون من 5 إلى 30 عملة.")
