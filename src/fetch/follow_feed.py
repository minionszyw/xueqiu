from __future__ import annotations

from typing import Any

from src.fetch.client import XueqiuClient


class FollowFeedFetcher:
    def __init__(self, client: XueqiuClient, feed_path: str):
        self.client = client
        self.feed_path = feed_path

    def fetch_page(self, cursor: str | None = None, count: int = 20) -> tuple[list[dict[str, Any]], str | None]:
        params: dict[str, Any] = {"count": count}
        if cursor:
            params["max_id"] = cursor

        payload = self.client.get_json(self.feed_path, params=params)
        items = payload.get("list") or payload.get("statuses") or []
        if not isinstance(items, list):
            items = []

        next_cursor = (
            payload.get("next_max_id")
            or payload.get("max_id")
            or payload.get("next_id")
        )
        if next_cursor is not None:
            next_cursor = str(next_cursor)
        return items, next_cursor
