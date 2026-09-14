"""Standalone Uvicorn launcher.

For production, place a TLS reverse proxy in front of this process and set:
TABLEVERSE_ENV=production, TABLEVERSE_SECRET_KEY, TABLEVERSE_CORS_ORIGINS,
and TABLEVERSE_FORWARDED_ALLOW_IPS to the proxy address(es).
"""
import os
import sys
import uvicorn

def _env(name: str, default: str = "") -> str:
    """Read TABLEVERSE_* settings, with legacy LETSFLY_* fallback."""
    return os.getenv(name) or os.getenv(name.replace("TABLEVERSE_", "LETSFLY_"), default)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

if __name__ == "__main__":
    environment = _env("TABLEVERSE_ENV", "development").strip().lower()
    host = _env("TABLEVERSE_BIND_HOST", "127.0.0.1")
    port = int(_env("TABLEVERSE_PORT", "8000"))
    proxy_headers = environment in {"production", "prod"} or _env("TABLEVERSE_PROXY_HEADERS", "false").strip().lower() in {"1", "true", "yes", "on"}
    workers = int(_env("TABLEVERSE_WORKERS", "1"))
    if workers != 1:
        raise RuntimeError("TableVerse currently uses in-process rate limiting and room state; production must run exactly one worker until a shared backend is configured.")
    forwarded_allow_ips = _env("TABLEVERSE_FORWARDED_ALLOW_IPS", "127.0.0.1")
    uvicorn.run(
        "server.app.main:app",
        host=host,
        port=port,
        log_level=_env("TABLEVERSE_LOG_LEVEL", "info"),
        proxy_headers=proxy_headers,
        forwarded_allow_ips=forwarded_allow_ips,
        workers=workers,
    )
