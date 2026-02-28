from datetime import datetime, timezone

from src.models import PostNormalized
from src.service.reconcile_worker import ReconcileWorker
from src.store.repo import BackupRepo


class DummyFetcher:
    def __init__(self, items):
        self.items = items

    def fetch_page(self, cursor=None, count=100):
        return self.items, None



def _post(post_id: str) -> PostNormalized:
    now = datetime.now(timezone.utc)
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
        raw_hash="h",
    )



def test_reconcile_detect_missing(tmp_path) -> None:
    repo = BackupRepo(tmp_path / "t.db")
    repo.init_db()
    repo.upsert_post(_post("100"))

    worker = ReconcileWorker(repo=repo, fetcher=DummyFetcher(items=[]), alert_dir=tmp_path)
    detected = worker.run_once(30)

    assert detected == 1
