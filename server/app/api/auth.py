"""Authentication endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from core_shared.protocol import UserRegister, UserLogin, ChangePasswordRequest, TokenResponse
from server.app.db.database import get_db, User
from server.app.api.users import get_current_user
from server.app.core.security import get_password_hash, verify_password, create_access_token
from server.app.hub.ws_manager import ws_manager

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Small in-process login-failure limiter. This intentionally avoids a new
# dependency and is appropriate for the project's single-process desktop/local
# server. Production deployments should put a shared rate limiter at the edge.
import threading
import time
from collections import defaultdict

_LOGIN_WINDOW_SECONDS = 15 * 60
_LOGIN_MAX_FAILURES = 5
_LOGIN_MAX_TRACKED_KEYS = 10_000
_LOGIN_GLOBAL_IP_MAX_FAILURES = 25
_REGISTER_WINDOW_SECONDS = 15 * 60
_REGISTER_MAX_ATTEMPTS = 3
_REGISTER_MAX_TRACKED_KEYS = 5_000
_login_failures = defaultdict(list)
_register_attempts = defaultdict(list)
_login_lock = threading.Lock()
_register_lock = threading.Lock()

# Perform a password-hash verification even when a username does not exist.
# This avoids making account enumeration trivial through response timing.
_DUMMY_PASSWORD_HASH = "$2y$12$HPm0ovnkaIDxmcHwjrP/1.TVd1xJYXBnKUZyMG0P8XnZO1IqJiP1u"

def _login_key(request: Request, username: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}:{username}"

def _login_rate_limited(key: str) -> bool:
    now = time.monotonic()
    with _login_lock:
        stale = [k for k, values in _login_failures.items() if not values or now - values[-1] >= _LOGIN_WINDOW_SECONDS]
        for stale_key in stale:
            _login_failures.pop(stale_key, None)
        # Do not create an unbounded dictionary entry just by probing a new key.
        values = _login_failures.get(key, [])
        recent = [t for t in values if now - t < _LOGIN_WINDOW_SECONDS]
        if recent:
            _login_failures[key] = recent
        elif key in _login_failures:
            _login_failures.pop(key, None)
        return len(recent) >= _LOGIN_MAX_FAILURES

def _record_login_failure(key: str) -> None:
    now = time.monotonic()
    with _login_lock:
        if key not in _login_failures and len(_login_failures) >= _LOGIN_MAX_TRACKED_KEYS:
            oldest = min(_login_failures, key=lambda k: _login_failures[k][-1] if _login_failures[k] else 0)
            _login_failures.pop(oldest, None)
        recent = [t for t in _login_failures[key] if now - t < _LOGIN_WINDOW_SECONDS]
        recent.append(now)
        _login_failures[key] = recent

def _clear_login_failures(key: str) -> None:
    with _login_lock:
        _login_failures.pop(key, None)


def _login_global_ip_key(request: Request) -> str:
    return f"ip:{_client_host(request)}"


def _global_ip_rate_limited(request: Request) -> bool:
    key = _login_global_ip_key(request)
    now = time.monotonic()
    with _login_lock:
        values = _login_failures.get(key, [])
        recent = [t for t in values if now - t < _LOGIN_WINDOW_SECONDS]
        if recent:
            _login_failures[key] = recent
        elif key in _login_failures:
            _login_failures.pop(key, None)
        return len(recent) >= _LOGIN_GLOBAL_IP_MAX_FAILURES


def _record_global_ip_failure(request: Request) -> None:
    key = _login_global_ip_key(request)
    now = time.monotonic()
    with _login_lock:
        if key not in _login_failures and len(_login_failures) >= _LOGIN_MAX_TRACKED_KEYS:
            oldest = min(_login_failures, key=lambda k: _login_failures[k][-1] if _login_failures[k] else 0)
            _login_failures.pop(oldest, None)
        recent = [t for t in _login_failures.get(key, []) if now - t < _LOGIN_WINDOW_SECONDS]
        if len(recent) < _LOGIN_GLOBAL_IP_MAX_FAILURES:
            recent.append(now)
        _login_failures[key] = recent


def _client_host(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # The first IP in the chain is the original client IP
        client_ip = forwarded.split(",")[0].strip()
        if client_ip:
            return client_ip
    return request.client.host if request.client else "unknown"

def _registration_rate_limited(host: str) -> bool:
    now = time.monotonic()
    with _register_lock:
        values = _register_attempts.get(host, [])
        recent = [t for t in values if now - t < _REGISTER_WINDOW_SECONDS]
        if recent:
            _register_attempts[host] = recent
        elif host in _register_attempts:
            _register_attempts.pop(host, None)
        return len(recent) >= _REGISTER_MAX_ATTEMPTS

def _record_registration_attempt(host: str) -> None:
    now = time.monotonic()
    with _register_lock:
        if host not in _register_attempts and len(_register_attempts) >= _REGISTER_MAX_TRACKED_KEYS:
            oldest = min(_register_attempts, key=lambda k: _register_attempts[k][-1] if _register_attempts[k] else 0)
            _register_attempts.pop(oldest, None)
        recent = [t for t in _register_attempts[host] if now - t < _REGISTER_WINDOW_SECONDS]
        recent.append(now)
        _register_attempts[host] = recent


@router.post("/register", response_model=TokenResponse)
def register(request: Request, req: UserRegister, db: Session = Depends(get_db)):
    host = _client_host(request)
    if _registration_rate_limited(host):
        raise HTTPException(429, "محاولات إنشاء الحساب كثيرة جدًا. حاول مرة أخرى بعد قليل.", headers={"Retry-After": str(_REGISTER_WINDOW_SECONDS)})
    _record_registration_attempt(host)
    username = req.username.strip().lower()
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(400, "اسم المستخدم مسجل بالفعل.")
    user = User(
        username=username,
        display_name=req.display_name.strip(),
        hashed_password=get_password_hash(req.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "اسم المستخدم مسجل بالفعل.")
    db.refresh(user)
    token = create_access_token({"sub": str(user.id), "username": user.username, "ver": int(user.token_version or 0)})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "username": user.username, "display_name": user.display_name, "coins": user.coins},
    }

@router.post("/login", response_model=TokenResponse)
def login(request: Request, req: UserLogin, db: Session = Depends(get_db)):
    username = req.username.strip().lower()
    key = _login_key(request, username)
    if _global_ip_rate_limited(request):
        raise HTTPException(429, "محاولات تسجيل الدخول كثيرة جدًا من هذا المصدر. حاول مرة أخرى بعد قليل.", headers={"Retry-After": str(_LOGIN_WINDOW_SECONDS)})
    if _login_rate_limited(key):
        raise HTTPException(429, "محاولات تسجيل الدخول كثيرة جدًا. حاول مرة أخرى بعد قليل.", headers={"Retry-After": str(_LOGIN_WINDOW_SECONDS)})
    user = db.query(User).filter(User.username == username).first()
    password_hash = user.hashed_password if user else _DUMMY_PASSWORD_HASH
    password_ok = verify_password(req.password, password_hash)
    if not user or not password_ok:
        _record_login_failure(key)
        _record_global_ip_failure(request)
        raise HTTPException(400, "اسم المستخدم أو كلمة المرور غير صحيحة.")
    _clear_login_failures(key)
    with _login_lock:
        _login_failures.pop(_login_global_ip_key(request), None)
    token = create_access_token({"sub": str(user.id), "username": user.username, "ver": int(user.token_version or 0)})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "username": user.username, "display_name": user.display_name, "coins": user.coins},
    }

@router.post("/logout")
async def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.token_version = int(user.token_version or 0) + 1
    db.commit()
    await ws_manager.disconnect_user(user.id, "Authentication state changed")
    return {"ok": True}

@router.post("/change-password")
async def change_password(req: ChangePasswordRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(req.current_password, user.hashed_password):
        raise HTTPException(400, "كلمة المرور الحالية غير صحيحة.")
    user.hashed_password = get_password_hash(req.new_password)
    user.token_version = int(user.token_version or 0) + 1
    db.commit()
    await ws_manager.disconnect_user(user.id, "Authentication state changed")
    return {"ok": True}
