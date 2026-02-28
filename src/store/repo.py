from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3

from src.models import PostNormalized


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BackupRepo:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        schema_path = Path(__file__).with_name("schema.sql")
        schema = schema_path.read_text(encoding="utf-8")
        with self.connect() as conn:
            conn.executescript(schema)

    def get_meta(self, key: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM meta_kv WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        now = utc_now().isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO meta_kv(key, value, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    updated_at=excluded.updated_at
                """,
                (key, value, now),
            )

    def write_snapshot(self, post_id: str, captured_at: datetime, raw: dict, raw_hash: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO post_snapshots(post_id, captured_at, raw_json, raw_hash)
                VALUES(?, ?, ?, ?)
                """,
                (post_id, captured_at.isoformat(), json.dumps(raw, ensure_ascii=False), raw_hash),
            )

    def upsert_post(self, post: PostNormalized) -> tuple[bool, bool]:
        payload = asdict(post)
        with self.connect() as conn:
            current = conn.execute(
                "SELECT post_id, raw_hash FROM posts WHERE post_id = ?", (post.post_id,)
            ).fetchone()
            created = current is None
            updated = current is not None and current["raw_hash"] != post.raw_hash

            first_captured_at = post.captured_at.isoformat()
            if current:
                first = conn.execute(
                    "SELECT first_captured_at FROM posts WHERE post_id = ?", (post.post_id,)
                ).fetchone()
                first_captured_at = first["first_captured_at"]

            conn.execute(
                """
                INSERT INTO posts(
                    post_id, post_type, author_id, author_name, created_at,
                    first_captured_at, last_captured_at,
                    content_text, content_html, source_post_id,
                    visible_status, raw_hash
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(post_id) DO UPDATE SET
                    post_type=excluded.post_type,
                    author_id=excluded.author_id,
                    author_name=excluded.author_name,
                    created_at=excluded.created_at,
                    last_captured_at=excluded.last_captured_at,
                    content_text=excluded.content_text,
                    content_html=excluded.content_html,
                    source_post_id=excluded.source_post_id,
                    visible_status=excluded.visible_status,
                    raw_hash=excluded.raw_hash
                """,
                (
                    payload["post_id"],
                    payload["post_type"],
                    payload["author_id"],
                    payload["author_name"],
                    payload["created_at"].isoformat() if payload["created_at"] else None,
                    first_captured_at,
                    payload["captured_at"].isoformat(),
                    payload["content_text"],
                    payload["content_html"],
                    payload["source_post_id"],
                    payload["visible_status"],
                    payload["raw_hash"],
                ),
            )
            return created, updated

    def add_poll_run(
        self,
        started_at: datetime,
        finished_at: datetime,
        fetched_count: int,
        new_count: int,
        updated_count: int,
        success: bool,
        error_message: str | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO poll_runs(
                    started_at, finished_at, fetched_count, new_count, updated_count, success, error_message
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    started_at.isoformat(),
                    finished_at.isoformat(),
                    fetched_count,
                    new_count,
                    updated_count,
                    1 if success else 0,
                    error_message,
                ),
            )

    def list_recent_visible_posts(self, window_minutes: int) -> list[sqlite3.Row]:
        threshold = (utc_now() - timedelta(minutes=window_minutes)).isoformat()
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT post_id, last_captured_at, visible_status
                FROM posts
                WHERE last_captured_at >= ? AND visible_status = 'visible'
                ORDER BY last_captured_at DESC
                """,
                (threshold,),
            ).fetchall()
            return list(rows)

    def mark_missing(self, post_id: str, reason: str = "missing_from_feed") -> bool:
        now = utc_now().isoformat()
        with self.connect() as conn:
            conn.execute(
                "UPDATE posts SET visible_status = 'deleted_suspected' WHERE post_id = ?",
                (post_id,),
            )
            cursor = conn.execute(
                """
                INSERT INTO deletion_events(post_id, detected_at, reason, last_seen_at)
                VALUES(?, ?, ?, (SELECT last_captured_at FROM posts WHERE post_id = ?))
                ON CONFLICT(post_id, reason) DO NOTHING
                """,
                (post_id, now, reason, post_id),
            )
            return cursor.rowcount > 0

    def export_posts_by_date(self, date_str: str) -> list[sqlite3.Row]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM posts
                WHERE DATE(first_captured_at) = DATE(?)
                ORDER BY first_captured_at ASC
                """,
                (date_str,),
            ).fetchall()
            return list(rows)
