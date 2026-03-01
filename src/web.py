from __future__ import annotations

from dataclasses import dataclass
import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from src.store.repo import BackupRepo


@dataclass(slots=True)
class WebApp:
    repo: BackupRepo

    def render_index(self, query: dict[str, list[str]]) -> str:
        page = _to_int(_first(query, "page"), default=1, minimum=1)
        per_page = _to_int(_first(query, "per_page"), default=30, minimum=1, maximum=200)
        status = _first(query, "status") or ""
        post_type = _first(query, "type") or ""
        keyword = _first(query, "q") or ""

        offset = (page - 1) * per_page
        rows = self.repo.list_posts(
            limit=per_page,
            offset=offset,
            status=status or None,
            post_type=post_type or None,
            keyword=keyword or None,
        )
        total = self.repo.count_posts(
            status=status or None,
            post_type=post_type or None,
            keyword=keyword or None,
        )
        stats = self.repo.get_stats()

        prev_page = page - 1 if page > 1 else 1
        next_page = page + 1 if offset + per_page < total else page
        q_status = html.escape(status)
        q_type = html.escape(post_type)
        q_keyword = html.escape(keyword)

        table_rows = "\n".join(
            (
                "<tr>"
                f"<td><a href='/post/{html.escape(r['post_id'])}'>{html.escape(r['post_id'])}</a></td>"
                f"<td>{html.escape(r['author_name'] or '-')}</td>"
                f"<td>{_post_type_text(r['post_type'])}</td>"
                f"<td>{_status_badge(r['visible_status'])}</td>"
                f"<td><a href='/post/{html.escape(r['post_id'])}'>{html.escape((r['content_text'] or '')[:80]) or '-'}</a></td>"
                f"<td>{html.escape(r['first_captured_at'] or '-')}</td>"
                f"<td><a href='/post/{html.escape(r['post_id'])}'>查看详情</a></td>"
                "</tr>"
            )
            for r in rows
        )
        if not table_rows:
            table_rows = "<tr><td colspan='7'>暂无数据</td></tr>"

        return f"""
<!doctype html>
<html lang='zh-CN'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>雪球备份查看器</title>
  <style>
    :root {{
      --bg: #f4f7f9;
      --card: #ffffff;
      --text: #1a1f24;
      --muted: #6b7886;
      --line: #dbe3ea;
      --accent: #0f766e;
      --danger: #b42318;
    }}
    body {{ margin: 0; font-family: "PingFang SC", "Microsoft YaHei", sans-serif; background: linear-gradient(135deg, #eef7f8 0%, #f6f8fb 100%); color: var(--text); }}
    .wrap {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
    .card {{ background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 16px; margin-bottom: 16px; box-shadow: 0 4px 16px rgba(19,33,68,0.06); }}
    h1 {{ margin: 0 0 12px; font-size: 24px; }}
    .muted {{ color: var(--muted); font-size: 13px; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 12px; }}
    .kpi {{ border: 1px solid var(--line); border-radius: 10px; padding: 12px; background: #f9fbfc; }}
    .kpi b {{ display: block; font-size: 22px; margin-top: 4px; }}
    form {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
    input, select, button {{ border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; font-size: 14px; }}
    button {{ background: var(--accent); color: #fff; border: 0; cursor: pointer; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid var(--line); text-align: left; padding: 10px 8px; vertical-align: top; }}
    th {{ color: var(--muted); font-weight: 600; }}
    a {{ color: #0b5cab; text-decoration: none; }}
    .pager {{ display: flex; gap: 8px; align-items: center; margin-top: 12px; }}
    .tag-danger {{ color: var(--danger); font-weight: 600; }}
    @media (max-width: 900px) {{ .grid {{ grid-template-columns: repeat(2, minmax(120px, 1fr)); }} }}
  </style>
</head>
<body>
  <div class='wrap'>
    <div class='card'>
      <h1>雪球备份查看器</h1>
      <div class='muted'>本地数据库实时查看，支持关键字筛选与删帖事件追踪</div>
    </div>
    <div class='card grid'>
      <div class='kpi'>帖子总数<b>{stats['posts']}</b></div>
      <div class='kpi'>疑似删除<b>{stats['deletions']}</b></div>
      <div class='kpi'>轮询次数<b>{stats['poll_runs']}</b></div>
      <div class='kpi'>快照总数<b>{stats['snapshots']}</b></div>
    </div>
    <div class='card'>
      <form method='get' action='/'>
        <input type='text' name='q' placeholder='搜索作者或正文关键字' value='{q_keyword}'>
        <select name='status'>
          <option value='' {'selected' if status == '' else ''}>全部状态</option>
          <option value='visible' {'selected' if status == 'visible' else ''}>可见</option>
          <option value='deleted_suspected' {'selected' if status == 'deleted_suspected' else ''}>疑似删除</option>
        </select>
        <select name='type'>
          <option value='' {'selected' if post_type == '' else ''}>全部类型</option>
          <option value='status' {'selected' if post_type == 'status' else ''}>动态</option>
          <option value='long' {'selected' if post_type == 'long' else ''}>长文</option>
          <option value='retweet' {'selected' if post_type == 'retweet' else ''}>转发回复</option>
        </select>
        <input type='number' name='per_page' min='1' max='200' value='{per_page}'>
        <button type='submit'>筛选</button>
      </form>
    </div>
    <div class='card'>
      <table>
        <thead>
          <tr>
            <th>post_id</th>
            <th>作者</th>
            <th>类型</th>
            <th>状态</th>
            <th>内容预览</th>
            <th>首次抓取时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {table_rows}
        </tbody>
      </table>
      <div class='pager'>
        <a href='/?page={prev_page}&per_page={per_page}&status={q_status}&type={q_type}&q={q_keyword}'>上一页</a>
        <span>第 {page} 页 / 共 {max(1, (total + per_page - 1) // per_page)} 页（总 {total} 条）</span>
        <a href='/?page={next_page}&per_page={per_page}&status={q_status}&type={q_type}&q={q_keyword}'>下一页</a>
      </div>
    </div>
  </div>
</body>
</html>
"""

    def render_post(self, post_id: str) -> tuple[int, str]:
        row = self.repo.get_post(post_id)
        if row is None:
            return 404, "<h1>404</h1><p>帖子不存在</p>"

        snapshots = self.repo.list_post_snapshots(post_id, limit=30)
        snap_rows = "\n".join(
            f"<tr><td>{s['id']}</td><td>{html.escape(s['captured_at'])}</td><td>{html.escape(s['raw_hash'])}</td></tr>"
            for s in snapshots
        )
        if not snap_rows:
            snap_rows = "<tr><td colspan='3'>暂无快照</td></tr>"

        content_text = html.escape(row["content_text"] or "")
        content_html = html.escape(row["content_html"] or "")

        body = f"""
<!doctype html>
<html lang='zh-CN'>
<head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
<title>帖子详情 {html.escape(post_id)}</title>
<style>
  body {{ font-family: "PingFang SC", "Microsoft YaHei", sans-serif; margin: 20px; background:#f7f9fc; color:#1a1f24; }}
  .card {{ background:#fff; border:1px solid #dbe3ea; border-radius:12px; padding:16px; margin-bottom:16px; }}
  table {{ width:100%; border-collapse:collapse; }}
  th,td {{ border-bottom:1px solid #dbe3ea; text-align:left; padding:8px; font-size:13px; }}
  pre {{ background:#f6f8fb; padding:10px; border-radius:8px; white-space:pre-wrap; word-break:break-word; }}
</style>
</head>
<body>
  <p><a href='/'>返回列表</a> | <a href='/deletions'>删帖事件</a></p>
  <div class='card'>
    <h2>帖子详情</h2>
    <p><b>post_id:</b> {html.escape(row['post_id'])}</p>
    <p><b>作者:</b> {html.escape(row['author_name'] or '-')}</p>
    <p><b>类型:</b> {_post_type_text(row['post_type'])}</p>
    <p><b>状态:</b> {_status_text(row['visible_status'])}</p>
    <p><b>发布时间:</b> {html.escape(row['created_at'] or '-')}</p>
    <p><b>首次抓取:</b> {html.escape(row['first_captured_at'] or '-')}</p>
    <p><b>最近抓取:</b> {html.escape(row['last_captured_at'] or '-')}</p>
    <p><b>转发源:</b> {html.escape(row['source_post_id'] or '-')}</p>
    <p><b>正文文本:</b></p>
    <pre>{content_text}</pre>
    <p><b>正文HTML:</b></p>
    <pre>{content_html}</pre>
  </div>
  <div class='card'>
    <h3>最近快照</h3>
    <table>
      <thead><tr><th>ID</th><th>抓取时间</th><th>哈希</th></tr></thead>
      <tbody>{snap_rows}</tbody>
    </table>
  </div>
</body>
</html>
"""
        return 200, body

    def render_deletions(self) -> str:
        rows = self.repo.list_deletion_events(limit=200, active_only=True)
        body_rows = "\n".join(
            (
                "<tr>"
                f"<td><a href='/post/{html.escape(r['post_id'])}'>{html.escape(r['post_id'])}</a></td>"
                f"<td>{_reason_text(r['reason'])}</td>"
                f"<td>{html.escape(r['last_seen_at'] or '-')}</td>"
                f"<td>{html.escape(r['detected_at'] or '-')}</td>"
                "</tr>"
            )
            for r in rows
        )
        if not body_rows:
            body_rows = "<tr><td colspan='4'>暂无当前疑似删除事件</td></tr>"
        return f"""
<!doctype html>
<html lang='zh-CN'>
<head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
<title>当前疑似删除事件</title>
<style>
  body {{ font-family: "PingFang SC", "Microsoft YaHei", sans-serif; margin: 20px; background:#f7f9fc; color:#1a1f24; }}
  .card {{ background:#fff; border:1px solid #dbe3ea; border-radius:12px; padding:16px; }}
  table {{ width:100%; border-collapse:collapse; }}
  th,td {{ border-bottom:1px solid #dbe3ea; text-align:left; padding:8px; font-size:13px; }}
</style>
</head>
<body>
  <p><a href='/'>返回列表</a></p>
  <div class='card'>
    <h2>当前疑似删除事件</h2>
    <p style='color:#6b7886;font-size:13px;'>仅展示当前状态仍为“疑似删除”的内容（不含已恢复可见的历史事件）</p>
    <table>
      <thead><tr><th>post_id</th><th>原因</th><th>最后可见时间</th><th>检测时间</th></tr></thead>
      <tbody>{body_rows}</tbody>
    </table>
  </div>
</body>
</html>
"""


class BackupWebHandler(BaseHTTPRequestHandler):
    app: WebApp

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path == "/":
            page = self.app.render_index(query)
            self._html(200, page)
            return
        if parsed.path.startswith("/post/"):
            post_id = parsed.path.removeprefix("/post/")
            status, page = self.app.render_post(post_id)
            self._html(status, page)
            return
        if parsed.path == "/deletions":
            page = self.app.render_deletions()
            self._html(200, page)
            return
        if parsed.path == "/api/stats":
            self._json(200, self.app.repo.get_stats())
            return
        self._html(404, "<h1>404</h1><p>页面不存在</p>")

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _html(self, status: int, body: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, status: int, data: Any) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def run_web_server(repo: BackupRepo, host: str = "127.0.0.1", port: int = 8765) -> None:
    BackupWebHandler.app = WebApp(repo=repo)
    server = ThreadingHTTPServer((host, port), BackupWebHandler)
    print(f"Web 查看器已启动: http://{host}:{port}")
    print("按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _first(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    if not values:
        return None
    return values[0]


def _to_int(
    value: str | None,
    default: int,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    try:
        n = int(value) if value is not None else default
    except ValueError:
        n = default
    if minimum is not None:
        n = max(minimum, n)
    if maximum is not None:
        n = min(maximum, n)
    return n


def _status_text(status: str | None) -> str:
    mapping = {
        "visible": "可见",
        "deleted_suspected": "疑似删除",
    }
    if not status:
        return "-"
    return mapping.get(status, status)


def _post_type_text(post_type: str | None) -> str:
    mapping = {
        "status": "动态",
        "long": "长文",
        "retweet": "转发回复",
    }
    if not post_type:
        return "-"
    return html.escape(mapping.get(post_type, post_type))


def _status_badge(status: str | None) -> str:
    label = html.escape(_status_text(status))
    cls = "tag-danger" if status == "deleted_suspected" else ""
    return f"<span class='{cls}'>{label}</span>"


def _reason_text(reason: str | None) -> str:
    mapping = {
        "missing_from_feed": "关注流缺失",
    }
    if not reason:
        return "-"
    return html.escape(mapping.get(reason, reason))
