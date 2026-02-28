from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from src.fetch.follow_feed import FollowFeedFetcher
from src.store.repo import BackupRepo


class ReconcileWorker:
    def __init__(self, repo: BackupRepo, fetcher: FollowFeedFetcher, alert_dir: Path):
        self.repo = repo
        self.fetcher = fetcher
        self.alert_dir = alert_dir

    def run_once(self, recent_window_min: int) -> int:
        recent_posts = self.repo.list_recent_visible_posts(recent_window_min)
        if not recent_posts:
            return 0

        # 拉取一页最新关注流作为轻量可见性参考
        latest_items, _ = self.fetcher.fetch_page(cursor=None, count=100)
        visible_ids = {str(item.get("id")) for item in latest_items if item.get("id") is not None}

        detected = 0
        for row in recent_posts:
            post_id = row["post_id"]
            if post_id not in visible_ids:
                inserted = self.repo.mark_missing(post_id)
                if inserted:
                    self._append_alert(post_id)
                    detected += 1
        return detected

    def _append_alert(self, post_id: str) -> None:
        now = datetime.now(timezone.utc)
        path = self.alert_dir / f"{now.strftime('%Y-%m-%d')}.log"
        payload = {
            "detected_at": now.isoformat(),
            "post_id": post_id,
            "reason": "missing_from_feed",
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
