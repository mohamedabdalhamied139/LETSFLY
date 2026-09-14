import json, time, threading
from collections import defaultdict
from fastapi import APIRouter, Depends, Query, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from server.app.db.database import get_db, ActivityEvent
from server.app.api.users import get_current_user

router = APIRouter(prefix="/api/activity", tags=["activity"])
_VALID_CATEGORIES = {"TABLE_CHAT", "PRIVATE_MESSAGES", "FRIENDS", "GAMEPLAY", "FRIEND_REQUESTS", "INVITATIONS", "GIFTS"}
_activity_rate_limits = defaultdict(list)
_activity_rate_limit_lock = threading.Lock()

def _check_activity_rate_limit(user_id: int, max_requests: int = 60, window_seconds: float = 60.0) -> None:
    now = time.monotonic()
    key = str(user_id)
    with _activity_rate_limit_lock:
        times = _activity_rate_limits[key]
        while times and now - times[0] >= window_seconds:
            times.pop(0)
        if len(times) >= max_requests:
            raise HTTPException(429, "تم تجاوز حد استعلامات النشاط مؤقتًا. حاول بعد قليل.")
        times.append(now)


class ActivityReadRequest(BaseModel):
    event_id: int | None = None
    category: str | None = None


def _safe_parse_payload(payload_str: str | None) -> dict:
    if not payload_str:
        return {}
    try:
        data = json.loads(payload_str)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _serialize(e):
    return {
        "id": e.id, "category": e.category, "event_type": e.event_type,
        "text": e.text, "actor_id": e.actor_id, "room_id": e.room_id,
        "created_at": e.created_at.isoformat(), "is_read": bool(e.is_read), "payload": _safe_parse_payload(e.payload),
    }


@router.get("")
def activity(
    user=Depends(get_current_user), db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    before_id: int | None = Query(None, ge=1),
    category: str | None = Query(None),
):
    _check_activity_rate_limit(user.id, max_requests=60, window_seconds=60.0)
    category = category.upper().strip() if category else None
    if category == "ALL":
        category = None
    if category and category not in _VALID_CATEGORIES:
        raise HTTPException(400, "Invalid activity category")

    q = db.query(ActivityEvent).filter(ActivityEvent.recipient_id == user.id)
    if before_id:
        q = q.filter(ActivityEvent.id < before_id)
    if category:
        q = q.filter(ActivityEvent.category == category)
    rows = q.order_by(ActivityEvent.id.desc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_before_id = rows[-1].id if has_more and rows else None

    cat_counts = (
        db.query(ActivityEvent.category, func.count(ActivityEvent.id))
        .filter(ActivityEvent.recipient_id == user.id)
        .group_by(ActivityEvent.category)
        .all()
    )
    counts = {cat: int(total) for cat, total in cat_counts}

    unread_counts = (
        db.query(ActivityEvent.category, func.count(ActivityEvent.id))
        .filter(ActivityEvent.recipient_id == user.id, ActivityEvent.is_read == 0)
        .group_by(ActivityEvent.category)
        .all()
    )
    unread = {cat: int(total) for cat, total in unread_counts}

    return {
        "events": [_serialize(e) for e in rows],
        "has_more": has_more,
        "next_before_id": next_before_id,
        "counts": counts,
        "unread": unread,
    }


@router.post("/read")
def mark_read(
    user=Depends(get_current_user), db: Session = Depends(get_db),
    event_id: int | None = Query(None, ge=1),
    category: str | None = Query(None),
    body: ActivityReadRequest | None = Body(None),
):
    # The desktop client sends read markers as JSON. Keep query parameters as a
    # backward-compatible input path while giving the JSON body precedence when
    # a field is present.
    if body is not None:
        if body.event_id is not None:
            event_id = int(body.event_id)
        if body.category is not None:
            category = body.category
    category = category.upper().strip() if category else None
    if category == "ALL":
        category = None
    if category and category not in _VALID_CATEGORIES:
        raise HTTPException(400, "Invalid activity category")
    q = db.query(ActivityEvent).filter(ActivityEvent.recipient_id == user.id, ActivityEvent.is_read == 0)
    if event_id:
        q = q.filter(ActivityEvent.id <= int(event_id))
    if category:
        q = q.filter(ActivityEvent.category == category)
    updated = q.update({ActivityEvent.is_read: 1}, synchronize_session=False)
    db.commit()
    return {"ok": True, "marked": int(updated)}


@router.delete("")
def clear_activity(user=Depends(get_current_user), db: Session = Depends(get_db)):
    deleted = db.query(ActivityEvent).filter(ActivityEvent.recipient_id == user.id).delete(synchronize_session=False)
    db.commit()
    return {"ok": True, "deleted": int(deleted)}
