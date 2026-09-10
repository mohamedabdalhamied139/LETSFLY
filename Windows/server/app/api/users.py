"""User profile, wallet and health endpoints."""
import logging
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from server.app.db.database import (
    get_db, User, CoinTransaction, ActivityEvent, Friendship, FriendRequest,
    NotificationMute, Block, PrivateMessage, ChallengeInvitation,
    PlayerRating, MatchParticipant, Feedback
)
from server.app.core.security import decode_access_token
from server.app.hub.ws_manager import ws_manager
from server.app.hub.room_manager import room_manager
from core_shared.version import BUILD

router = APIRouter(prefix="/api", tags=["users"])
logger = logging.getLogger("tableverse.users_api")

def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Unauthorized")
    parts = authorization.strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(401, "Unauthorized")
    token = parts[1].strip()
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(401, "Invalid token")
    try:
        user_id = int(payload.get("sub", 0))
    except (TypeError, ValueError):
        raise HTTPException(401, "Invalid token")
    if user_id <= 0:
        raise HTTPException(401, "Invalid token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(401, "User not found")
    try:
        token_version = int(payload.get("ver"))
    except (TypeError, ValueError):
        raise HTTPException(401, "Invalid token")
    if token_version != int(user.token_version or 0):
        raise HTTPException(401, "Token revoked")
    if payload.get("typ") != "access":
        raise HTTPException(401, "Invalid token type")
    return user

@router.get("/health")
def health():
    return {"status": "ok", "service": "TableVerse Server", "build": BUILD}

@router.get("/wallet")
def wallet(user: User = Depends(get_current_user)):
    return {"coins": user.coins, "balance": user.coins}

@router.get("/auth/me")
def get_me(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username, "display_name": user.display_name, "gender": user.gender or "", "bio": user.bio or "", "coins": user.coins}

@router.delete("/users/me")
@router.delete("/me")
async def delete_my_account(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    uid = user.id
    try:
        # Snapshot the registry under its thread lock, then serialize each
        # room mutation with the same asyncio lock used by game actions. This
        # prevents account deletion from racing a live move/round transition.
        with room_manager._lock:
            rooms = [r for r in list(room_manager.rooms.values()) if uid in r.players]
        for r in rooms:
            async with r._mutation_lock:
                if uid in r.players:
                    r.remove_player(uid)
            if not r.players:
                room_manager.delete_room(r.room_id)
    except Exception:
        logger.warning("Room cleanup failed while deleting account %s", uid, exc_info=True)

    try:
        await ws_manager.disconnect_user(uid, "Account deleted")
    except Exception:
        logger.warning("WebSocket cleanup failed while deleting account %s", uid, exc_info=True)

    try:
        db.query(CoinTransaction).filter(CoinTransaction.user_id == uid).delete(synchronize_session=False)
        db.query(ActivityEvent).filter((ActivityEvent.recipient_id == uid) | (ActivityEvent.actor_id == uid)).delete(synchronize_session=False)
        db.query(Friendship).filter((Friendship.user_id == uid) | (Friendship.friend_id == uid)).delete(synchronize_session=False)
        db.query(FriendRequest).filter((FriendRequest.sender_id == uid) | (FriendRequest.recipient_id == uid)).delete(synchronize_session=False)
        db.query(NotificationMute).filter((NotificationMute.user_id == uid) | (NotificationMute.target_user_id == uid)).delete(synchronize_session=False)
        db.query(Block).filter((Block.user_id == uid) | (Block.blocked_user_id == uid)).delete(synchronize_session=False)
        db.query(PrivateMessage).filter((PrivateMessage.sender_id == uid) | (PrivateMessage.recipient_id == uid)).delete(synchronize_session=False)
        db.query(ChallengeInvitation).filter((ChallengeInvitation.sender_id == uid) | (ChallengeInvitation.recipient_id == uid)).delete(synchronize_session=False)
        db.query(PlayerRating).filter(PlayerRating.user_id == uid).delete(synchronize_session=False)
        db.query(MatchParticipant).filter(MatchParticipant.user_id == uid).delete(synchronize_session=False)
        db.query(Feedback).filter(Feedback.user_id == uid).delete(synchronize_session=False)
        db.delete(user)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"ok": True, "message": "تم حذف الحساب بنجاح."}
