"""Database models and session setup."""
import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Text, LargeBinary, DateTime, ForeignKey, event, inspect, text, UniqueConstraint, Index
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker

appdata = os.getenv('APPDATA')
if appdata:
    APP_DIR = os.path.join(appdata, 'TableVerse')
else:
    APP_DIR = os.path.join(os.path.expanduser('~'), '.tableverse')

os.makedirs(APP_DIR, exist_ok=True)
DB_PATH = os.path.join(APP_DIR, "tableverse_v2.db")

def _env(name: str, default: str = "") -> str:
    """Read TABLEVERSE_* settings, with legacy LETSFLY_* fallback."""
    return os.getenv(name) or os.getenv(name.replace("TABLEVERSE_", "LETSFLY_"), default)

def _database_url():
    configured = os.getenv("DATABASE_URL", "").strip()
    environment = _env("TABLEVERSE_ENV", "development").strip().lower()
    if configured:
        # Render/Postgres providers sometimes expose the legacy postgres:// form.
        if configured.startswith("postgres://"):
            configured = "postgresql+psycopg://" + configured[len("postgres://"): ]
        elif configured.startswith("postgresql://"):
            configured = "postgresql+psycopg://" + configured[len("postgresql://"): ]
        return configured
    if environment in {"production", "prod"}:
        raise RuntimeError("DATABASE_URL must be configured in production; SQLite on the Render filesystem is not persistent.")
    return f"sqlite:///{DB_PATH}"

DATABASE_URL = _database_url()
_is_sqlite = DATABASE_URL.startswith("sqlite:")

if _is_sqlite:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 30},
        pool_pre_ping=True,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=int(_env("TABLEVERSE_DB_POOL_SIZE", "5")),
        max_overflow=int(_env("TABLEVERSE_DB_MAX_OVERFLOW", "10")),
    )


@event.listens_for(engine, "connect")
def _configure_sqlite(dbapi_connection, connection_record):
    if not _is_sqlite:
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()



Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    display_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    coins = Column(Integer, default=1000)
    token_version = Column(Integer, nullable=False, default=0, server_default="0")
    gender = Column(String(30), nullable=True)
    bio = Column(String(1000), nullable=True)
    pm_policy = Column(String(20), default="everyone", server_default="everyone")
    invite_policy = Column(String(20), default="everyone", server_default="everyone")
    join_policy = Column(String(20), default="everyone", server_default="everyone")
    last_seen_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CoinTransaction(Base):
    __tablename__ = "coin_transactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    reason = Column(String(120), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class RewardRecord(Base):
    __tablename__ = "reward_records"
    id = Column(Integer, primary_key=True, index=True)
    reward_id = Column(String(120), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ActivityEvent(Base):
    __tablename__ = "activity_events"
    id = Column(Integer, primary_key=True, index=True)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category = Column(String(40), nullable=False, index=True)
    event_type = Column(String(80), nullable=False, default="generic")
    text = Column(String(1000), nullable=False)
    actor_id = Column(Integer, nullable=True, index=True)
    room_id = Column(String(120), nullable=True, index=True)
    payload = Column(String(4000), nullable=False, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    is_read = Column(Integer, nullable=False, default=0, server_default="0")
    __table_args__ = (
        Index("ix_activity_recipient_cat", "recipient_id", "category"),
        Index("ix_activity_recipient_read", "recipient_id", "is_read"),
    )



class Friendship(Base):
    __tablename__ = "friendships"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    friend_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    __table_args__ = (UniqueConstraint("user_id", "friend_id", name="uq_friendship_user_friend"),)


class FriendRequest(Base):
    __tablename__ = "friend_requests"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    __table_args__ = (UniqueConstraint("sender_id", "recipient_id", "status", name="uq_friend_request_pair_status"),)



class NotificationMute(Base):
    __tablename__ = "notification_mutes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    mute_all = Column(Integer, nullable=False, default=0, server_default="0")
    mute_private_messages = Column(Integer, nullable=False, default=0, server_default="0")
    mute_invitations = Column(Integer, nullable=False, default=0, server_default="0")
    mute_presence = Column(Integer, nullable=False, default=0, server_default="0")
    __table_args__ = (UniqueConstraint("user_id", "target_user_id", name="uq_notification_mute_user_target"),)


class Block(Base):
    __tablename__ = "blocks"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    blocked_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    __table_args__ = (UniqueConstraint("user_id", "blocked_user_id", name="uq_block_user_target"),)


class PrivateMessage(Base):
    __tablename__ = "private_messages"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    message = Column(String(4000), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class ChallengeInvitation(Base):
    __tablename__ = "challenge_invitations"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    room_id = Column(String(120), nullable=True, index=True)
    game = Column(String(40), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    __table_args__ = (Index("uq_pending_challenge_invitation", "sender_id", "recipient_id", "room_id", unique=True,
                            sqlite_where=text("status = 'pending'"), postgresql_where=text("status = 'pending'")),)


class MatchRecord(Base):
    __tablename__ = "match_records"
    id = Column(Integer, primary_key=True, index=True)
    game = Column(String(40), nullable=False, index=True)
    room_id = Column(String(120), nullable=True, index=True)
    match_key = Column(String(64), nullable=True, unique=True, index=True)
    winner_ids = Column(String(1000), nullable=False, default="[]")
    human_player_ids = Column(String(1000), nullable=False, default="[]")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class PlayerRating(Base):
    __tablename__ = "player_ratings"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    game = Column(String(40), nullable=False, index=True)
    rating = Column(Integer, nullable=False, default=1000, server_default="1000")
    played = Column(Integer, nullable=False, default=0, server_default="0")
    wins = Column(Integer, nullable=False, default=0, server_default="0")
    losses = Column(Integer, nullable=False, default=0, server_default="0")
    __table_args__ = (UniqueConstraint("user_id", "game", name="uq_player_rating_user_game"),)


class MatchParticipant(Base):
    __tablename__ = "match_participants"
    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("match_records.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    won = Column(Integer, nullable=False, default=0, server_default="0")
    __table_args__ = (UniqueConstraint("match_id", "user_id", name="uq_match_participant"),)


class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    message = Column(String(4000), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

class SavedTable(Base):
    __tablename__ = "saved_tables"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    game = Column(String(40), nullable=False, index=True)
    target_score = Column(Integer, nullable=True)
    rules_json = Column(Text, nullable=False, default="{}")
    scores_json = Column(Text, nullable=False, default="{}")
    players_json = Column(Text, nullable=False, default="[]")
    opponents_summary = Column(String(255), nullable=False, default="")
    serialized_engine = Column(LargeBinary, nullable=False)
    saved_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    expires_at = Column(DateTime, nullable=False, index=True)


Base.metadata.create_all(bind=engine)

# Lightweight SQLite migration for existing installations. SQLAlchemy's
# create_all() does not add columns to an existing table. Keep this migration
# idempotent so old databases can adopt token revocation without data loss.
def _migrate_existing_schema():
    if not _is_sqlite:
        return
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("users")}
    additions = {
        "token_version": "ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0",
        "gender": "ALTER TABLE users ADD COLUMN gender VARCHAR(30)",
        "bio": "ALTER TABLE users ADD COLUMN bio VARCHAR(1000)",
        "last_seen_at": "ALTER TABLE users ADD COLUMN last_seen_at DATETIME",
        "pm_policy": "ALTER TABLE users ADD COLUMN pm_policy VARCHAR(20) DEFAULT 'everyone'",
        "invite_policy": "ALTER TABLE users ADD COLUMN invite_policy VARCHAR(20) DEFAULT 'everyone'",
        "join_policy": "ALTER TABLE users ADD COLUMN join_policy VARCHAR(20) DEFAULT 'everyone'",
    }
    for name, ddl in additions.items():
        if name not in columns:
            try:
                with engine.begin() as conn:
                    conn.execute(text(ddl))
            except OperationalError as exc:
                if "duplicate column" not in str(exc).lower():
                    raise

_migrate_existing_schema()

# Idempotent migration for challenge metadata used by challenge invitations.
def _migrate_social_schema():
    if not _is_sqlite:
        return
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("challenge_invitations")}
    additions = {
        "room_id": "ALTER TABLE challenge_invitations ADD COLUMN room_id VARCHAR(120)",
        "game": "ALTER TABLE challenge_invitations ADD COLUMN game VARCHAR(40)",
    }
    for name, ddl in additions.items():
        if name not in columns:
            try:
                with engine.begin() as conn: conn.execute(text(ddl))
            except OperationalError as exc:
                if "duplicate column" not in str(exc).lower(): raise
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_pending_challenge_invitation_idx ON challenge_invitations(sender_id, recipient_id, room_id) WHERE status = 'pending'"))
    except OperationalError:
        pass

_migrate_social_schema()

def _create_reward_records_table():
    if not _is_sqlite:
        return
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE IF NOT EXISTS reward_records (id INTEGER PRIMARY KEY, reward_id VARCHAR(120) UNIQUE NOT NULL, created_at DATETIME)"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_match_records_match_key ON match_records(match_key) WHERE match_key IS NOT NULL"))
    except OperationalError: pass

_create_reward_records_table()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
