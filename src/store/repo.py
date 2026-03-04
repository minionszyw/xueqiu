from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
import json
from pathlib import Path
import sqlite3

from src.models import PostNormalized
from src.timezone_utils import now_shanghai


def local_now() -> datetime:
    return now_shanghai()


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
        now = local_now().isoformat()
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

    def prune_old_snapshots(self, retention_days: int) -> int:
        if retention_days <= 0:
            return 0
        threshold = (local_now() - timedelta(days=retention_days)).isoformat()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM post_snapshots
                WHERE datetime(captured_at) < datetime(?)
                """,
                (threshold,),
            )
            return int(cursor.rowcount or 0)

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
        threshold = (local_now() - timedelta(minutes=window_minutes)).isoformat()
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
        now = local_now().isoformat()
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

    def get_stats(self) -> dict[str, int]:
        with self.connect() as conn:
            posts = conn.execute("SELECT COUNT(*) AS c FROM posts").fetchone()["c"]
            snapshots = conn.execute("SELECT COUNT(*) AS c FROM post_snapshots").fetchone()["c"]
            deletions = conn.execute(
                "SELECT COUNT(*) AS c FROM posts WHERE visible_status = 'deleted_suspected'"
            ).fetchone()["c"]
            deletion_events_total = conn.execute(
                "SELECT COUNT(*) AS c FROM deletion_events"
            ).fetchone()["c"]
            polls = conn.execute("SELECT COUNT(*) AS c FROM poll_runs").fetchone()["c"]
            return {
                "posts": int(posts),
                "snapshots": int(snapshots),
                "deletions": int(deletions),
                "deletion_events_total": int(deletion_events_total),
                "poll_runs": int(polls),
            }

    def list_posts(
        self,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        post_type: str | None = None,
        keyword: str | None = None,
    ) -> list[sqlite3.Row]:
        sql = """
            SELECT post_id, post_type, author_name, first_captured_at, last_captured_at,
                   visible_status, content_text
            FROM posts
            WHERE 1=1
        """
        params: list[object] = []
        if status:
            sql += " AND visible_status = ?"
            params.append(status)
        if post_type:
            sql += " AND post_type = ?"
            params.append(post_type)
        if keyword:
            sql += " AND (author_name LIKE ? OR content_text LIKE ?)"
            like = f"%{keyword}%"
            params.extend([like, like])
        sql += " ORDER BY first_captured_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return list(rows)

    def count_posts(
        self,
        status: str | None = None,
        post_type: str | None = None,
        keyword: str | None = None,
    ) -> int:
        sql = "SELECT COUNT(*) AS c FROM posts WHERE 1=1"
        params: list[object] = []
        if status:
            sql += " AND visible_status = ?"
            params.append(status)
        if post_type:
            sql += " AND post_type = ?"
            params.append(post_type)
        if keyword:
            sql += " AND (author_name LIKE ? OR content_text LIKE ?)"
            like = f"%{keyword}%"
            params.extend([like, like])
        with self.connect() as conn:
            row = conn.execute(sql, params).fetchone()
            return int(row["c"])

    def get_post(self, post_id: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT post_id, post_type, author_id, author_name, created_at,
                       first_captured_at, last_captured_at, content_text, content_html,
                       source_post_id, visible_status, raw_hash
                FROM posts
                WHERE post_id = ?
                """,
                (post_id,),
            ).fetchone()
            return row

    def list_post_snapshots(self, post_id: str, limit: int = 20) -> list[sqlite3.Row]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, captured_at, raw_hash
                FROM post_snapshots
                WHERE post_id = ?
                ORDER BY captured_at DESC
                LIMIT ?
                """,
                (post_id, limit),
            ).fetchall()
            return list(rows)

    def list_deletion_events(self, limit: int = 100, active_only: bool = True) -> list[sqlite3.Row]:
        sql = """
            SELECT d.post_id, d.detected_at, d.reason, d.last_seen_at, p.visible_status
            FROM deletion_events d
            JOIN posts p ON p.post_id = d.post_id
        """
        params: list[object] = []
        if active_only:
            sql += " WHERE p.visible_status = 'deleted_suspected'"
        sql += " ORDER BY d.detected_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return list(rows)
