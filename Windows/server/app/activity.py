"""Central activity/event store shared by lobby, social features and games."""
from datetime import datetime, timezone
import json
from typing import Any, Optional
from sqlalchemy.orm import Session
from server.app.db.database import ActivityEvent

CATEGORIES = {
    "TABLE_CHAT": "دردشة الطاولات",
    "PRIVATE_MESSAGES": "الرسائل الخاصة",
    "FRIENDS": "الأصدقاء",
    "GAMEPLAY": "اللعب",
    "ALL": "الجميع",
    "FRIEND_REQUESTS": "طلبات الصداقة",
    "INVITATIONS": "الدعوات",
    "GIFTS": "الهدايا",
}


def create_event(db: Session, recipient_id: int, category: str, text: str,
                 event_type: str = "generic", actor_id: Optional[int] = None,
                 room_id: Optional[str] = None, payload: Optional[dict] = None) -> ActivityEvent:
    category = str(category).upper()
    if category not in CATEGORIES or category == "ALL":
        raise ValueError("Invalid activity category")
    event = ActivityEvent(
        recipient_id=int(recipient_id), category=category, event_type=str(event_type),
        text=str(text)[:1000], actor_id=actor_id, room_id=room_id,
        payload=json.dumps(payload or {}, ensure_ascii=False),
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.flush()
    return event


record_activity = create_event


def list_events(db: Session, user_id: int, limit: int = 200, before_id: Optional[int] = None):
    q = db.query(ActivityEvent).filter(ActivityEvent.recipient_id == int(user_id))
    if before_id:
        q = q.filter(ActivityEvent.id < int(before_id))
    return q.order_by(ActivityEvent.id.desc()).limit(max(1, min(int(limit), 500))).all()
