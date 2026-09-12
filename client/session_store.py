"""Small secure Windows session-token store for automatic login.

Credentials and session tokens are encrypted using Windows DPAPI, binding the
blob to the current Windows user account and machine profile.
"""
from pathlib import Path
import os
import base64
import ctypes
from ctypes import wintypes

APP_DIR = Path(os.getenv("APPDATA") or (Path.home() / ".tableverse")) / "TableVerse"
SESSION_FILE = APP_DIR / "session.dat"

if os.name == "nt":
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]
    _crypt = ctypes.windll.crypt32
    _kernel = ctypes.windll.kernel32

    def _dpapi(data: bytes, decrypt: bool = False) -> bytes:
        src = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)))
        out = DATA_BLOB()
        fn = _crypt.CryptUnprotectData if decrypt else _crypt.CryptProtectData
        if not fn(ctypes.byref(src), None, None, None, None, 0, ctypes.byref(out)):
            raise OSError("Windows data protection failed")
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            _kernel.LocalFree(out.pbData)
else:
    def _dpapi(data: bytes, decrypt: bool = False) -> bytes:
        # Safe fallback for development and non-Windows testing environments
        return data

def _session_file() -> Path:
    if SESSION_FILE.name == "session.dat" and SESSION_FILE.parent != APP_DIR:
        return APP_DIR / "session.dat"
    return SESSION_FILE

def _creds_file() -> Path:
    if CREDS_FILE.name == "credentials.dat" and CREDS_FILE.parent != APP_DIR:
        return APP_DIR / "credentials.dat"
    return CREDS_FILE

def _accounts_file() -> Path:
    if ACCOUNTS_FILE.name == "accounts.dat" and ACCOUNTS_FILE.parent != APP_DIR:
        return APP_DIR / "accounts.dat"
    return ACCOUNTS_FILE

def save_token(token: str) -> None:
    token = str(token or "").strip()
    if not token:
        clear_token(); return
    APP_DIR.mkdir(parents=True, exist_ok=True)
    blob = _dpapi(token.encode("utf-8"), False)
    target = _session_file()
    tmp = target.with_suffix(".tmp")
    tmp.write_bytes(base64.b64encode(blob))
    tmp.replace(target)

def load_token() -> str:
    target = _session_file()
    if not target.exists():
        return ""
    try:
        raw = base64.b64decode(target.read_bytes())
        return _dpapi(raw, True).decode("utf-8").strip()
    except Exception:
        clear_token()
        return ""

def clear_token() -> None:
    try:
        _session_file().unlink(missing_ok=True)
    except OSError:
        pass

CREDS_FILE = APP_DIR / "credentials.dat"
ACCOUNTS_FILE = APP_DIR / "accounts.dat"

# --- Multi-Account DPAPI Credential Store ---
def _load_accounts_data() -> dict:
    target = _accounts_file()
    if target.exists():
        try:
            raw = base64.b64decode(target.read_bytes())
            import json
            data = json.loads(_dpapi(raw, True).decode("utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
    return {"active": None, "accounts": []}

def _save_accounts_data(data: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    import json
    blob = _dpapi(json.dumps(data).encode("utf-8"), False)
    target = _accounts_file()
    tmp = target.with_suffix(".tmp")
    tmp.write_bytes(base64.b64encode(blob))
    tmp.replace(target)

def save_account_profile(username: str, password: str, display_name: str = "", active: bool = True) -> None:
    username = str(username or "").strip().lower()
    password = str(password or "")
    display_name = str(display_name or "").strip() or username
    if not username:
        return
    data = _load_accounts_data()
    accounts = data.get("accounts", [])
    found = False
    for acc in accounts:
        if acc.get("username", "").strip().lower() == username:
            acc["password"] = password
            acc["display_name"] = display_name
            found = True
            break
    if not found:
        accounts.append({
            "username": username,
            "password": password,
            "display_name": display_name
        })
    data["accounts"] = accounts
    if active or not data.get("active"):
        data["active"] = username
    _save_accounts_data(data)
    if active or data.get("active") == username:
        _save_legacy_credentials(username, password)

def load_all_account_profiles() -> list:
    data = _load_accounts_data()
    active_u = data.get("active")
    profiles = []
    for acc in data.get("accounts", []):
        u = acc.get("username", "")
        profiles.append({
            "username": u,
            "password": acc.get("password", ""),
            "display_name": acc.get("display_name", u),
            "is_active": bool(active_u and u.strip().lower() == str(active_u).strip().lower())
        })
    return profiles

def get_active_account_profile() -> dict | None:
    data = _load_accounts_data()
    active_u = data.get("active")
    accounts = data.get("accounts", [])
    if active_u:
        for acc in accounts:
            if acc.get("username", "").strip().lower() == str(active_u).strip().lower():
                return dict(acc)
    if accounts:
        return dict(accounts[0])
    return None

def set_active_account_profile(username: str) -> None:
    username = str(username or "").strip().lower()
    data = _load_accounts_data()
    for acc in data.get("accounts", []):
        if acc.get("username", "").strip().lower() == username:
            data["active"] = acc["username"]
            _save_accounts_data(data)
            _save_legacy_credentials(acc["username"], acc.get("password", ""))
            return

def remove_account_profile(username: str) -> None:
    username = str(username or "").strip().lower()
    data = _load_accounts_data()
    accounts = [acc for acc in data.get("accounts", []) if acc.get("username", "").strip().lower() != username]
    data["accounts"] = accounts
    if str(data.get("active", "")).strip().lower() == username:
        data["active"] = accounts[0]["username"] if accounts else None
    _save_accounts_data(data)
    if not accounts:
        clear_credentials()
    else:
        active_acc = get_active_account_profile()
        if active_acc:
            _save_legacy_credentials(active_acc.get("username", ""), active_acc.get("password", ""))

def clear_all_account_profiles() -> None:
    try:
        _accounts_file().unlink(missing_ok=True)
    except OSError:
        pass
    clear_credentials()

# --- Legacy Single Credential Compatibility API ---
def save_credentials(username: str, password: str) -> None:
    username = str(username or "").strip()
    password = str(password or "")
    if not username or not password:
        clear_credentials(); return
    save_account_profile(username, password, active=True)

def _save_legacy_credentials(username: str, password: str) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    import json
    data = json.dumps({"u": username, "p": password})
    blob = _dpapi(data.encode("utf-8"), False)
    target = _creds_file()
    tmp = target.with_suffix(".tmp")
    tmp.write_bytes(base64.b64encode(blob))
    tmp.replace(target)

def _load_legacy_credentials() -> tuple:
    target = _creds_file()
    if not target.exists():
        return "", ""
    try:
        raw = base64.b64decode(target.read_bytes())
        import json
        data = json.loads(_dpapi(raw, True).decode("utf-8"))
        return data.get("u", ""), data.get("p", "")
    except Exception:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        return "", ""

def load_credentials() -> tuple:
    active = get_active_account_profile()
    if active and active.get("username") and active.get("password"):
        return active.get("username"), active.get("password")
    return _load_legacy_credentials()

def clear_credentials() -> None:
    try:
        _creds_file().unlink(missing_ok=True)
    except OSError:
        pass
    try:
        _accounts_file().unlink(missing_ok=True)
    except OSError:
        pass
