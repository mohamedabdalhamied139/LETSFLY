"""Security and JWT Authentication utilities."""
import base64
import hashlib
import hmac
import logging
import os
import secrets
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger("tableverse.security")

try:  # Preferred production dependency from requirements.txt
    import jwt as _pyjwt  # type: ignore

    jwt = _pyjwt
    JWTError = getattr(_pyjwt, "PyJWTError", Exception)
except Exception:  # pragma: no cover - fallback to python-jose if present
    try:
        from jose import jwt, JWTError  # type: ignore
    except Exception:
        import jwt as _pyjwt  # type: ignore
        jwt = _pyjwt
        JWTError = getattr(_pyjwt, "PyJWTError", Exception)

try:  # Preferred production password context from requirements.txt
    import bcrypt as _bcrypt  # type: ignore
except Exception:  # pragma: no cover - depends on optional dependency presence
    _bcrypt = None

try:
    if _bcrypt is not None and not hasattr(_bcrypt, "__about__"):
        _bcrypt.__about__ = type("about", (), {"__version__": getattr(_bcrypt, "__version__", "4.0.0")})()
    from passlib.context import CryptContext  # type: ignore
except Exception:  # pragma: no cover - exercised when optional dependency is absent
    CryptContext = None


class _BcryptPasswordContext:
    """Small bcrypt-only fallback when passlib is unavailable."""

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        if _bcrypt is None:
            return False
        try:
            return bool(_bcrypt.checkpw(_bcrypt_bytes(plain_password), hashed_password.encode("utf-8")))
        except Exception:
            return False

    def hash(self, password: str) -> str:
        if _bcrypt is None:
            raise RuntimeError("bcrypt/passlib is required to hash passwords securely.")
        return _bcrypt.hashpw(_bcrypt_bytes(password), _bcrypt.gensalt(rounds=12)).decode("utf-8")


class _PBKDF2PasswordContext:
    """Last-resort development/test fallback when bcrypt is not installed.

    Production deployments should install the pinned requirements and therefore
    use passlib/bcrypt. This fallback keeps diagnostics and unit tests importable
    in minimal environments; it does not change behavior when requirements are
    installed.
    """

    _prefix = "pbkdf2_sha256$"
    _rounds = 390_000

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        try:
            if not str(hashed_password).startswith(self._prefix):
                return False
            _, rounds, salt_b64, digest_b64 = str(hashed_password).split("$", 3)
            salt = base64.b64decode(salt_b64.encode("ascii"))
            expected = base64.b64decode(digest_b64.encode("ascii"))
            actual = hashlib.pbkdf2_hmac("sha256", _utf8_bytes(plain_password), salt, int(rounds))
            return hmac.compare_digest(actual, expected)
        except Exception:
            return False

    def hash(self, password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", _utf8_bytes(password), salt, self._rounds)
        return "$".join((
            self._prefix.rstrip("$"),
            str(self._rounds),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        ))


def _utf8_bytes(value: str) -> bytes:
    return str(value or "").encode("utf-8")


def _bcrypt_bytes(value: str) -> bytes:
    # bcrypt uses at most 72 bytes. Keeping the truncation explicit makes the
    # fallback deterministic and avoids dependency-specific surprises.
    return _utf8_bytes(value)[:72]


if CryptContext is not None:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
elif _bcrypt is not None:
    pwd_context = _BcryptPasswordContext()
else:
    logger.warning("passlib/bcrypt are not installed; using PBKDF2 fallback for local diagnostics only.")
    pwd_context = _PBKDF2PasswordContext()


def _env(name: str, default: str = "") -> str:
    """Read TABLEVERSE_* settings, with legacy LETSFLY_* fallback."""
    return os.getenv(name) or os.getenv(name.replace("TABLEVERSE_", "LETSFLY_"), default)


_SECRET_ENV = _env("TABLEVERSE_SECRET_KEY")

_appdata = os.getenv('APPDATA')
if _appdata:
    _APP_DIR = Path(_appdata) / 'TableVerse'
else:
    _APP_DIR = Path.home() / '.tableverse'
_APP_DIR.mkdir(parents=True, exist_ok=True)
_SECRET_FILE = _APP_DIR / "tableverse_secret.key"


def _load_or_create_secret() -> str:
    if _SECRET_ENV:
        value = _SECRET_ENV.strip()
        if len(value) < (64 if _env("TABLEVERSE_ENV", "development").strip().lower() in {"production", "prod"} else 32):
            required = 64 if _env("TABLEVERSE_ENV", "development").strip().lower() in {"production", "prod"} else 32
            raise RuntimeError(f"TABLEVERSE_SECRET_KEY must contain at least {required} characters.")
        return value

    # Never silently generate a production signing secret. Local/development
    # runs may persist a random secret for convenience; production must opt in
    # with an explicit environment variable.
    if _env("TABLEVERSE_ENV", "development").strip().lower() in {"production", "prod"}:
        raise RuntimeError("TABLEVERSE_SECRET_KEY must be configured in production.")

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
            "TABLEVERSE_SECRET_KEY is not configured and the development secret file cannot be created."
        ) from exc


SECRET_KEY = _load_or_create_secret()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(_env("TABLEVERSE_ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours; revocable server-side
JWT_ISSUER = _env("TABLEVERSE_JWT_ISSUER", "tableverse")
JWT_AUDIENCE = _env("TABLEVERSE_JWT_AUDIENCE", "tableverse-client")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bool(pwd_context.verify(plain_password, hashed_password))


def get_password_hash(password: str) -> str:
    return str(pwd_context.hash(password))


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
