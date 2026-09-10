"""Security and JWT Authentication utilities using python-jose."""
import os
import secrets
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
if not hasattr(bcrypt, "__about__"):
    bcrypt.__about__ = type("about", (), {"__version__": getattr(bcrypt, "__version__", "4.0.0")})()

from jose import jwt, JWTError
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_SECRET_ENV = os.environ.get("LETSFLY_SECRET_KEY")

_appdata = os.getenv('APPDATA')
if _appdata:
    _APP_DIR = Path(_appdata) / 'LetsFly'
else:
    _APP_DIR = Path.home() / '.letsfly'
_APP_DIR.mkdir(parents=True, exist_ok=True)
_SECRET_FILE = _APP_DIR / "letsfly_secret.key"

def _load_or_create_secret() -> str:
    if _SECRET_ENV:
        value = _SECRET_ENV.strip()
        if len(value) < (64 if os.getenv("LETSFLY_ENV", "development").strip().lower() in {"production", "prod"} else 32):
            required = 64 if os.getenv("LETSFLY_ENV", "development").strip().lower() in {"production", "prod"} else 32
            raise RuntimeError(f"LETSFLY_SECRET_KEY must contain at least {required} characters.")
        return value

    # Never silently generate a production signing secret. Local/development
    # runs may persist a random secret for convenience; production must opt in
    # with an explicit environment variable.
    if os.getenv("LETSFLY_ENV", "development").strip().lower() in {"production", "prod"}:
        raise RuntimeError("LETSFLY_SECRET_KEY must be configured in production.")

    try:
        if _SECRET_FILE.exists():
            value = _SECRET_FILE.read_text(encoding="utf-8").strip()
            if value:
                return value
        value = secrets.token_hex(32)
        _SECRET_FILE.write_text(value, encoding="utf-8")
        try:
            _SECRET_FILE.chmod(0o600)
        except OSError:
            pass
        return value
    except OSError as exc:
        raise RuntimeError(
            "LETSFLY_SECRET_KEY is not configured and the development secret file cannot be created."
        ) from exc

SECRET_KEY = _load_or_create_secret()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("LETSFLY_ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours; revocable server-side
JWT_ISSUER = os.getenv("LETSFLY_JWT_ISSUER", "letsfly")
JWT_AUDIENCE = os.getenv("LETSFLY_JWT_AUDIENCE", "letsfly-client")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None, token_version: Optional[int] = None) -> str:
    to_encode = data.copy()
    if token_version is not None:
        to_encode["ver"] = int(token_version)
    if "ver" not in to_encode or to_encode["ver"] is None:
        raise ValueError("Access tokens require an explicit 'ver' (token_version) claim.")
    to_encode["ver"] = int(to_encode["ver"])
    if not to_encode.get("sub"):
        raise ValueError("Access tokens require a non-empty 'sub' claim.")
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.setdefault("iat", datetime.now(timezone.utc))
    to_encode.setdefault("jti", secrets.token_urlsafe(24))
    to_encode.update({"exp": expire})
    to_encode.setdefault("iss", JWT_ISSUER)
    to_encode.setdefault("aud", JWT_AUDIENCE)
    to_encode.setdefault("typ", "access")
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], issuer=JWT_ISSUER, audience=JWT_AUDIENCE)
    except JWTError:
        return None
