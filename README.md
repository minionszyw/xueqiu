# 雪球关注内容自动备份

目标：分钟级抓取雪球关注流并备份到本地 SQLite，降低删帖导致的数据丢失。

## 快速开始

### 0. 安装 Python 和 uv

#### macOS

1. 安装 Python 3.11+

```bash
brew install python@3.12
```

2. 安装 uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Windows（PowerShell）

1. 安装 Python 3.11+（使用 winget）

```powershell
winget install -e --id Python.Python.3.12
```

2. 安装 uv

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

> 安装完成后，重新打开终端，确认版本：`python --version`、`uv --version`

### 1. 安装依赖

```bash
uv sync
```

安装导出 Cookie 依赖：

```bash
uv sync --extra browser
```

### 2. 配置环境变量（可复制 `.env.example` 到 `.env`）

macOS / Linux:

```bash
cp .env.example .env
```

Windows（PowerShell）:

```powershell
Copy-Item .env.example .env
```

### 3. 初始化数据库

```bash
uv run python -m src.cli init-db
```

### 4. 导入 Cookie 并检查登录态

先导出 Cookie（已支持优先使用本机 Chrome）：

```bash
uv run python -m src.auth.export_cookies
```

再检查登录态：

```bash
uv run python -m src.cli check-auth --cookie-file cookies.json
```

### 5. 启动服务

```bash
uv run python -m src.cli run
```

### 6. 验证是否抓取成功

新开一个终端执行：

```bash
sqlite3 data/backup.db "select count(*) as posts from posts; select count(*) as snapshots from post_snapshots;"
```

如果 `posts > 0` 且 `snapshots > 0`，说明抓取和落盘正常。

## 目录

- `src/` 业务代码
- `data/backup.db` SQLite 数据库
- `data/raw/` 原始快照
- `data/alerts/` 删除事件摘要
- `logs/backup.log` 运行日志

## 数据模型

数据库使用 `SQLite`，建表定义见 `src/store/schema.sql`。

### posts（规范化主表）

- `post_id`：主键，内容唯一 ID
- `post_type`：内容类型（如 `status` / `long` / `retweet`）
- `author_id` / `author_name`：作者信息
- `created_at`：平台发布时间
- `first_captured_at`：首次抓取时间
- `last_captured_at`：最近一次抓取时间
- `content_text` / `content_html`：正文内容
- `source_post_id`：转发源内容 ID
- `visible_status`：可见性状态（`visible` / `deleted_suspected`）
- `raw_hash`：原始数据哈希（用于变更检测）

### post_snapshots（原始快照历史）

- `id`：自增主键
- `post_id`：关联 `posts.post_id`
- `captured_at`：本次快照抓取时间
- `raw_json`：原始 JSON 内容
- `raw_hash`：本次快照哈希
- 索引：`(post_id, captured_at DESC)`，用于快速回溯历史版本

### poll_runs（轮询运行记录）

- `id`：自增主键
- `started_at` / `finished_at`：本轮开始与结束时间
- `fetched_count`：抓取到的内容条数
- `new_count`：新增内容条数
- `updated_count`：已有内容更新条数
- `success`：本轮是否成功（1/0）
- `error_message`：失败时的错误信息

### deletion_events（疑似删除事件）

- `id`：自增主键
- `post_id`：被标记疑似删除的内容 ID
- `detected_at`：检测时间
- `reason`：原因（当前为 `missing_from_feed`）
- `last_seen_at`：最后一次可见时间
- 唯一约束：`UNIQUE(post_id, reason)`（避免重复记录）

### meta_kv（系统元数据）

- `key`：主键
- `value`：配置值
- `updated_at`：更新时间
- 当前用于保存轮询游标，如 `feed_cursor`

## 关注流

### 数据来源

- 使用登录账号的关注流接口：`/statuses/home_timeline.json`
- 不需要在项目内单独维护关注名单
- 关注对象由雪球账号本身决定（在雪球里关注/取关即可生效）

### 抓取策略

- 默认每 `20` 秒轮询一次（`POLL_INTERVAL_SEC`）
- 每轮最多抓取 `3` 页（`MAX_PAGES_PER_POLL`）
- 使用 `meta_kv.feed_cursor` 保存游标，支持重启后续跑
- 新内容先写快照，再写主表，确保尽快落盘

### 回查与删除检测

- 默认每 `120` 秒执行一次回查（`RECONCILE_INTERVAL_SEC`）
- 回查最近 `30` 分钟内容（`RECENT_WINDOW_MIN`）
- 若“曾可见内容”在最新关注流中缺失，标记为 `deleted_suspected`
- 同步写入 `deletion_events` 与 `data/alerts/YYYY-MM-DD.log`

## 删帖通知

### 触发规则

- 内容曾经被抓取并处于 `visible`
- 在回查窗口内，该内容不再出现在最新关注流
- 系统将其标记为 `deleted_suspected`

### 通知与记录位置

- 数据库事件表：`deletion_events`
- 内容状态字段：`posts.visible_status`
- 本地通知日志：`data/alerts/YYYY-MM-DD.log`（每行一条 JSON）

### 快速查看

查看最近删帖事件：

```bash
sqlite3 data/backup.db "select post_id, detected_at, reason from deletion_events order by detected_at desc limit 20;"
```

查看今日告警日志：

```bash
tail -n 20 data/alerts/$(date +%F).log
```

Windows（PowerShell）查看今日告警日志：

```powershell
Get-Content .\\data\\alerts\\$(Get-Date -Format yyyy-MM-dd).log -Tail 20
```

## 常见问题

### 1) `Cookie 文件不存在: cookies.json`

先执行：

```bash
uv run python -m src.auth.export_cookies
```

登录后回车生成 `cookies.json`，再执行 `check-auth`。

### 2) 运行时报接口 404

确认 `.env` 里是：

```bash
XUEQIU_FEED_PATH=/statuses/home_timeline.json
```

### 3) Playwright 提示找不到浏览器

脚本会优先使用本机 Chrome。若本机没有可用 Chrome，再安装浏览器内核：

```bash
uv run playwright install chromium
```
