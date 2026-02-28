from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json

from src.models import PostNormalized



def _to_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # 雪球时间戳通常为毫秒
        ts = float(value)
        if ts > 10_000_000_000:
            ts = ts / 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None



def _pick_post_id(raw: dict) -> str | None:
    for key in ("id", "status_id", "snowflake_id", "created_status_id"):
        val = raw.get(key)
        if val is not None:
            return str(val)
    return None



def normalize_post(raw: dict, captured_at: datetime) -> PostNormalized | None:
    post_id = _pick_post_id(raw)
    if not post_id:
        return None

    user = raw.get("user") or raw.get("author") or {}
    retweeted = raw.get("retweeted_status") or raw.get("source_status") or {}

    post_type = "status"
    if raw.get("target") or raw.get("is_long_text"):
        post_type = "long"
    if retweeted:
        post_type = "retweet"

    content_text = (
        raw.get("text")
        or raw.get("description")
        or raw.get("content")
        or raw.get("title")
    )
    content_html = raw.get("text_html") or raw.get("description_html")

    source_post_id = _pick_post_id(retweeted) if retweeted else None
    created_at = _to_datetime(raw.get("created_at") or raw.get("time_before"))

    raw_hash = hashlib.sha256(
        json.dumps(raw, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()

    return PostNormalized(
        post_id=post_id,
        post_type=post_type,
        author_id=str(user.get("id")) if user.get("id") is not None else None,
        author_name=user.get("screen_name") or user.get("name"),
        created_at=created_at,
        captured_at=captured_at,
        content_text=str(content_text) if content_text is not None else None,
        content_html=str(content_html) if content_html is not None else None,
        source_post_id=source_post_id,
        visible_status="visible",
        raw_hash=raw_hash,
    )
