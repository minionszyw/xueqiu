from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class PostNormalized:
    post_id: str
    post_type: str
    author_id: str | None
    author_name: str | None
    created_at: datetime | None
    captured_at: datetime
    content_text: str | None
    content_html: str | None
    source_post_id: str | None
    visible_status: str
    raw_hash: str


@dataclass(slots=True)
class PollResult:
    fetched_count: int
    new_count: int
    updated_count: int
    cursor: str | None


JSONDict = dict[str, Any]
