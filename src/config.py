from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


@dataclass(slots=True)
class Settings:
    base_url: str
    feed_path: str
    db_path: Path
    raw_archive_dir: Path
    alert_dir: Path
    log_path: Path
    cookie_file: Path
    poll_interval_sec: int
    max_pages_per_poll: int
    http_timeout_sec: int
    http_retry: int
    http_backoff_base_sec: float
    reconcile_interval_sec: int
    recent_window_min: int
    request_jitter_pct: float
    raw_archive_enabled: bool
    user_agent: str



def _as_bool(value: str, default: bool) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}



def load_settings() -> Settings:
    load_dotenv()

    base_url = os.getenv("XUEQIU_BASE_URL", "https://xueqiu.com")
    feed_path = os.getenv("XUEQIU_FEED_PATH", "/statuses/friends/timeline.json")

    settings = Settings(
        base_url=base_url.rstrip("/"),
        feed_path=feed_path,
        db_path=Path(os.getenv("BACKUP_DB_PATH", "data/backup.db")),
        raw_archive_dir=Path(os.getenv("RAW_ARCHIVE_DIR", "data/raw")),
        alert_dir=Path(os.getenv("ALERT_DIR", "data/alerts")),
        log_path=Path(os.getenv("LOG_PATH", "logs/backup.log")),
        cookie_file=Path(os.getenv("COOKIE_FILE", "cookies.json")),
        poll_interval_sec=int(os.getenv("POLL_INTERVAL_SEC", "20")),
        max_pages_per_poll=int(os.getenv("MAX_PAGES_PER_POLL", "3")),
        http_timeout_sec=int(os.getenv("HTTP_TIMEOUT_SEC", "8")),
        http_retry=int(os.getenv("HTTP_RETRY", "3")),
        http_backoff_base_sec=float(os.getenv("HTTP_BACKOFF_BASE_SEC", "0.5")),
        reconcile_interval_sec=int(os.getenv("RECONCILE_INTERVAL_SEC", "120")),
        recent_window_min=int(os.getenv("RECENT_WINDOW_MIN", "30")),
        request_jitter_pct=float(os.getenv("REQUEST_JITTER_PCT", "0.1")),
        raw_archive_enabled=_as_bool(os.getenv("RAW_ARCHIVE_ENABLED"), True),
        user_agent=os.getenv(
            "USER_AGENT",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        ),
    )

    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.raw_archive_dir.mkdir(parents=True, exist_ok=True)
    settings.alert_dir.mkdir(parents=True, exist_ok=True)
    settings.log_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
