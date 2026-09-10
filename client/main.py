"""Client Application Bootstrap with Embedded Server Auto-Start."""
import sys
import os
import threading
import time
import urllib.request
import urllib.error
import json
import subprocess
import faulthandler



sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core_shared.version import BUILD as EXPECTED_BUILD

def is_remote_server_configured() -> bool:
    url = os.getenv("LETSFLY_SERVER_URL", "https://letsfly.onrender.com").strip() or "https://letsfly.onrender.com"
    if not url:
        return False
    from urllib.parse import urlparse
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    return hostname not in ("127.0.0.1", "localhost", "::1", "")

def start_embedded_server_if_needed():
    if is_remote_server_configured():
        return
    expected_build = EXPECTED_BUILD
    health_url = "http://127.0.0.1:8000/api/health"

    def health_payload():
        req = urllib.request.Request(health_url)
        with urllib.request.urlopen(req, timeout=1) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8"))

    try:
        payload = health_payload()
        if payload and payload.get("service") == "LetsFly Server":
            if payload.get("build") == expected_build:
                return
            # Never kill an arbitrary process just because it owns port 8000.
            # Only stop a process whose command line identifies it as a Let's Fly server.
            if os.name == "nt":
                script = (
                    "$c=Get-CimInstance Win32_Process | Where-Object { "
                    "($_.ProcessId -in (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | "
                    "Select-Object -ExpandProperty OwningProcess)) -and "
                    "($_.CommandLine -match 'server\\.app\\.main|run_server\\.py|LetsFly') }; "
                    "$c | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
                )
                subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            else:
                raise RuntimeError("يوجد خادم Let's Fly بإصدار مختلف على المنفذ 8000.")
        elif payload:
            raise RuntimeError("المنفذ 8000 مستخدم بواسطة خدمة أخرى؛ لن يتم إيقافها تلقائيًا.")
    except urllib.error.HTTPError:
        pass
    except urllib.error.URLError:
        pass
    except RuntimeError:
        raise
    except Exception:
        pass

    def _run():
        import uvicorn
        from server.app.main import app
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        try:
            payload = health_payload()
            if payload and payload.get("build") == expected_build:
                return
        except Exception:
            pass
        time.sleep(0.2)
    raise RuntimeError("تعذر تشغيل خادم Let's Fly على المنفذ 8000.")

from PySide6.QtWidgets import QApplication
from client.client_app import LetsFlyApp

def _setup_excepthook():
    import traceback
    crash_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(crash_dir, exist_ok=True)
    crash_path = os.path.join(crash_dir, "client_crash.log")

    # Keep a persistent diagnostic trail even when the launcher window closes
    # immediately after an unhandled Qt/Python exception.
    try:
        fault_path = os.path.join(crash_dir, "client_faulthandler.log")
        _fault_file = open(fault_path, "a", encoding="utf-8")
        faulthandler.enable(_fault_file)
    except Exception:
        _fault_file = None

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        formatted = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        message = "[CRITICAL EXCEPTION]\n" + formatted
        print(message, file=sys.stderr)
        try:
            with open(crash_path, "a", encoding="utf-8") as fh:
                fh.write(message)
                fh.write("\n---\n")
        except Exception:
            pass
    sys.excepthook = handle_exception

def main():
    _setup_excepthook()
    start_embedded_server_if_needed()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Let's Fly")
    import client.localization as loc
    loc.install(app)
    window = LetsFlyApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
