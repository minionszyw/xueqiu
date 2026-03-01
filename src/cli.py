from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
import time

from src.auth.session import build_headers, load_cookie_header, validate_auth
from src.config import load_settings
from src.fetch.client import XueqiuClient
from src.fetch.follow_feed import FollowFeedFetcher
from src.service.backup_worker import BackupWorker
from src.service.reconcile_worker import ReconcileWorker
from src.store.repo import BackupRepo
from src.timezone_utils import now_shanghai
from src.web import run_web_server



def setup_logging(log_path: str) -> None:
    fmt = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )



def cmd_init_db() -> None:
    settings = load_settings()
    repo = BackupRepo(settings.db_path)
    repo.init_db()
    print(f"数据库初始化完成: {settings.db_path}")



def cmd_check_auth(cookie_file: str | None) -> None:
    settings = load_settings()
    target_cookie_file = settings.cookie_file if not cookie_file else Path(cookie_file)
    cookie_header = load_cookie_header(target_cookie_file)
    headers = build_headers(cookie_header, settings.user_agent)
    validate_auth(settings.base_url, headers, settings.http_timeout_sec)
    print("登录态校验通过")



def cmd_run() -> None:
    settings = load_settings()
    setup_logging(str(settings.log_path))
    logger = logging.getLogger("main")

    repo = BackupRepo(settings.db_path)
    repo.init_db()

    cookie_header = load_cookie_header(settings.cookie_file)
    headers = build_headers(cookie_header, settings.user_agent)
    validate_auth(settings.base_url, headers, settings.http_timeout_sec)

    client = XueqiuClient(
        base_url=settings.base_url,
        headers=headers,
        timeout_sec=settings.http_timeout_sec,
        retry_times=settings.http_retry,
        backoff_base_sec=settings.http_backoff_base_sec,
    )
    fetcher = FollowFeedFetcher(client, settings.feed_path)

    backup_worker = BackupWorker(
        repo=repo,
        fetcher=fetcher,
        raw_archive_dir=settings.raw_archive_dir,
        raw_archive_enabled=settings.raw_archive_enabled,
        max_pages_per_poll=settings.max_pages_per_poll,
        request_jitter_pct=settings.request_jitter_pct,
    )
    reconcile_worker = ReconcileWorker(repo=repo, fetcher=fetcher, alert_dir=settings.alert_dir)

    logger.info("服务启动，开始轮询")
    last_reconcile = now_shanghai().timestamp()

    try:
        while True:
            started = now_shanghai()
            try:
                result = backup_worker.run_once()
                logger.info(
                    "轮询完成 fetched=%s new=%s updated=%s cursor=%s",
                    result.fetched_count,
                    result.new_count,
                    result.updated_count,
                    result.cursor,
                )
            except Exception as exc:
                logger.exception("轮询失败: %s", exc)

            now_ts = now_shanghai().timestamp()
            if now_ts - last_reconcile >= settings.reconcile_interval_sec:
                try:
                    detected = reconcile_worker.run_once(settings.recent_window_min)
                    if detected:
                        logger.warning("检测到疑似删除内容 %s 条", detected)
                except Exception as exc:
                    logger.exception("回查失败: %s", exc)
                last_reconcile = now_ts

            elapsed = now_shanghai() - started
            sleep_sec = max(0.0, settings.poll_interval_sec - elapsed.total_seconds())
            time.sleep(sleep_sec)
    finally:
        client.close()



def cmd_export(date_str: str, fmt: str) -> None:
    settings = load_settings()
    repo = BackupRepo(settings.db_path)
    rows = repo.export_posts_by_date(date_str)

    if fmt != "jsonl":
        raise ValueError("当前仅支持 jsonl")

    for row in rows:
        print(json.dumps(dict(row), ensure_ascii=False))


def cmd_web(host: str, port: int) -> None:
    settings = load_settings()
    repo = BackupRepo(settings.db_path)
    repo.init_db()
    run_web_server(repo=repo, host=host, port=port)



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="雪球关注内容备份")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db")

    p_auth = sub.add_parser("check-auth")
    p_auth.add_argument("--cookie-file", default=None)

    sub.add_parser("run")

    p_export = sub.add_parser("export")
    p_export.add_argument("--date", required=True, help="YYYY-MM-DD")
    p_export.add_argument("--format", default="jsonl")

    p_web = sub.add_parser("web")
    p_web.add_argument("--host", default="127.0.0.1")
    p_web.add_argument("--port", type=int, default=8765)

    return parser.parse_args()



def main() -> None:
    args = parse_args()
    if args.cmd == "init-db":
        cmd_init_db()
    elif args.cmd == "check-auth":
        cmd_check_auth(args.cookie_file)
    elif args.cmd == "run":
        cmd_run()
    elif args.cmd == "export":
        cmd_export(args.date, args.format)
    elif args.cmd == "web":
        cmd_web(args.host, args.port)
    else:
        raise ValueError(f"未知命令: {args.cmd}")


if __name__ == "__main__":
    main()
