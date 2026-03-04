from src.models import PostNormalized
from src.store.repo import BackupRepo
from src.timezone_utils import now_shanghai
from datetime import timedelta



def _post(post_id: str, raw_hash: str) -> PostNormalized:
    now = now_shanghai()
    return PostNormalized(
        post_id=post_id,
        post_type="status",
        author_id="1",
        author_name="alice",
        created_at=now,
        captured_at=now,
        content_text="hello",
        content_html=None,
        source_post_id=None,
        visible_status="visible",
        raw_hash=raw_hash,
    )



def test_repo_upsert_idempotent(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    repo = BackupRepo(db_path)
    repo.init_db()

    p1 = _post("p-1", "hash-a")
    created, updated = repo.upsert_post(p1)
    assert created is True
    assert updated is False

    p2 = _post("p-1", "hash-a")
    created2, updated2 = repo.upsert_post(p2)
    assert created2 is False
    assert updated2 is False

    p3 = _post("p-1", "hash-b")
    created3, updated3 = repo.upsert_post(p3)
    assert created3 is False
    assert updated3 is True



def test_mark_missing_once(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    repo = BackupRepo(db_path)
    repo.init_db()

    repo.upsert_post(_post("p-2", "hash-x"))
    inserted1 = repo.mark_missing("p-2")
    inserted2 = repo.mark_missing("p-2")

    assert inserted1 is True
    assert inserted2 is False


def test_prune_old_snapshots(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    repo = BackupRepo(db_path)
    repo.init_db()

    now = now_shanghai()
    old_ts = now - timedelta(days=31)
    new_ts = now - timedelta(days=1)

    repo.write_snapshot("p-old", old_ts, {"id": "p-old"}, "h1")
    repo.write_snapshot("p-new", new_ts, {"id": "p-new"}, "h2")

    deleted = repo.prune_old_snapshots(30)
    assert deleted == 1

    with repo.connect() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM post_snapshots").fetchone()["c"]
        assert count == 1
