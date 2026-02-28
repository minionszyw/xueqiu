from datetime import datetime, timezone

from src.parser.normalize import normalize_post



def test_normalize_retweet_post() -> None:
    raw = {
        "id": 123,
        "text": "转发内容",
        "created_at": 1700000000000,
        "user": {"id": 1, "screen_name": "alice"},
        "retweeted_status": {"id": 999},
    }
    captured_at = datetime.now(timezone.utc)

    post = normalize_post(raw, captured_at)

    assert post is not None
    assert post.post_id == "123"
    assert post.post_type == "retweet"
    assert post.source_post_id == "999"
    assert post.author_name == "alice"
    assert post.visible_status == "visible"
    assert len(post.raw_hash) == 64



def test_normalize_missing_id_returns_none() -> None:
    raw = {"text": "no id"}
    captured_at = datetime.now(timezone.utc)

    post = normalize_post(raw, captured_at)

    assert post is None
