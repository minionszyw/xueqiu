from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
import random
import time

from src.fetch.follow_feed import FollowFeedFetcher
from src.models import PollResult
from src.parser.normalize import normalize_post
from src.store.repo import BackupRepo
from src.timezone_utils import now_shanghai


class BackupWorker:
    def __init__(
        self,
        repo: BackupRepo,
        fetcher: FollowFeedFetcher,
        raw_archive_dir: Path,
        raw_archive_enabled: bool,
        max_pages_per_poll: int,
        request_jitter_pct: float,
    ):
        self.repo = repo
        self.fetcher = fetcher
        self.raw_archive_dir = raw_archive_dir
        self.raw_archive_enabled = raw_archive_enabled
        self.max_pages_per_poll = max_pages_per_poll
        self.request_jitter_pct = request_jitter_pct
        self.logger = logging.getLogger("backup")

    def run_once(self) -> PollResult:
        start = now_shanghai()
        cursor = self.repo.get_meta("feed_cursor")

        fetched_count = 0
        new_count = 0
        updated_count = 0
        next_cursor = cursor

        try:
            for page in range(self.max_pages_per_poll):
                items, fetched_cursor = self.fetcher.fetch_page(cursor=next_cursor, count=20)
                if fetched_cursor:
                    next_cursor = fetched_cursor

                if not items:
                    break

                now = now_shanghai()
                for raw in items:
                    normalized = normalize_post(raw, captured_at=now)
                    if not normalized:
                        continue

                    fetched_count += 1
                    self.repo.write_snapshot(normalized.post_id, now, raw, normalized.raw_hash)
                    created, updated = self.repo.upsert_post(normalized)
                    if created:
                        new_count += 1
                    elif updated:
                        updated_count += 1
                    if self.raw_archive_enabled:
                        self._archive_raw(normalized.post_id, now, raw)

                if page < self.max_pages_per_poll - 1:
                    self._sleep_with_jitter(0.2)

            if next_cursor:
                self.repo.set_meta("feed_cursor", next_cursor)

            finished = now_shanghai()
            self.repo.add_poll_run(start, finished, fetched_count, new_count, updated_count, True)
            return PollResult(fetched_count, new_count, updated_count, next_cursor)
        except Exception as exc:
            finished = now_shanghai()
            self.repo.add_poll_run(start, finished, fetched_count, new_count, updated_count, False, str(exc))
            raise

    def _archive_raw(self, post_id: str, captured_at: datetime, raw: dict) -> None:
        day = captured_at.strftime("%Y-%m-%d")
        folder = self.raw_archive_dir / day
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{captured_at.strftime('%H%M%S')}_{post_id}.json"
        path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    def _sleep_with_jitter(self, base_sec: float) -> None:
        jitter = 1 + random.uniform(-self.request_jitter_pct, self.request_jitter_pct)
        time.sleep(max(0.05, base_sec * jitter))
