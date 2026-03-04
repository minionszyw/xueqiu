# 雪球关注内容自动备份

## 项目概述

### 背景

雪球上的动态可能在发布后几分钟内被删除，手工收藏或截图容易遗漏，无法稳定追溯原文。

### 目标

本项目用于自动抓取你账号的关注流内容并本地落盘，尽量在分钟级完成首次备份，降低删帖导致的内容丢失风险。

## 技术栈

- 语言：`Python 3.11+`
- 抓取与请求：`httpx`
- 登录态导出：`Playwright`（仅用于导出 Cookie）
- 存储：`SQLite`（`sqlite3`）
- Web 展示：Python 标准库 `http.server`
- 配置：`python-dotenv`
- 测试：`pytest`、`pytest-cov`
- 依赖管理：`uv`

## 功能介绍

### 1) 关注流

- 数据来源：`/statuses/home_timeline.json`
- 抓取对象：当前登录账号的关注流
- 关注名单管理：在雪球里关注/取关即可生效，无需在项目内配置名单
- 类型说明：
  - `status`：普通动态
  - `long`：长文/长帖
  - `retweet`：转发（部分回复形态会归入该类型）

### 2) 轮询备份

- 默认每 `20` 秒轮询一次（`POLL_INTERVAL_SEC`）
- 每轮最多抓取 `3` 页（`MAX_PAGES_PER_POLL`）
- 入库顺序：先写 `post_snapshots`，再更新 `posts`
- 支持重启续跑（`meta_kv.feed_cursor`）
- 时间统一使用 `Asia/Shanghai`（`+08:00`）时区
- 快照默认只保留最近 `30` 天，可通过 `SNAPSHOT_RETENTION_DAYS` 调整

### 3) 删帖通知

- 回查频率：默认每 `120` 秒（`RECONCILE_INTERVAL_SEC`）
- 回查窗口：最近 `30` 分钟（`RECENT_WINDOW_MIN`）
- 判定逻辑：曾经 `visible`，回查时缺失，标记为 `deleted_suspected`
- 通知落盘：`deletion_events` + `data/alerts/YYYY-MM-DD.log`

### 4) Web 界面

启动后可在浏览器查看备份数据，无需手写 SQL。

- `/`：帖子列表、筛选、分页、统计
- `/post/{post_id}`：帖子详情与快照历史
- `/deletions`：删帖事件列表
- `/api/stats`：JSON 统计接口

## 一键部署（推荐）

适合小白用户：自动检查环境、安装依赖、引导导出 Cookie、校验登录态、初始化数据库、后台启动备份与 Web 服务。

### macOS / Linux

```bash
./scripts/deploy.sh
```

### Windows（PowerShell）

```powershell
powershell -ExecutionPolicy Bypass -File .\\scripts\\deploy.ps1
```

部署完成后默认访问：

- `http://127.0.0.1:8765/`

## 快速开始

### macOS / Linux

1. 安装 Python 3.11+

```bash
brew install python@3.12
```

2. 安装 uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. 安装依赖

```bash
uv sync
```

4. 安装 Cookie 导出依赖（浏览器自动化）

```bash
uv sync --extra browser
```

5. 复制环境变量模板

```bash
cp .env.example .env
```

6. 导出 Cookie（优先使用本机 Chrome）

```bash
uv run python -m src.auth.export_cookies
```

7. 校验登录态

```bash
uv run python -m src.cli check-auth --cookie-file cookies.json
```

8. 初始化数据库

```bash
uv run python -m src.cli init-db
```

9. 启动备份服务

```bash
uv run python -m src.cli run
```

10. 启动 Web 查看

```bash
uv run python -m src.cli web
```

11. 验证抓取是否成功（新开终端）

```bash
sqlite3 data/backup.db "select count(*) as posts from posts; select count(*) as snapshots from post_snapshots;"
```

---

### Windows（PowerShell）

1. 安装 Python 3.11+

```powershell
winget install -e --id Python.Python.3.12
```

2. 安装 uv

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

3. 安装依赖

```powershell
uv sync
```

4. 安装 Cookie 导出依赖（浏览器自动化）

```powershell
uv sync --extra browser
```

5. 复制环境变量模板

```powershell
Copy-Item .env.example .env
```

6. 导出 Cookie（优先使用本机 Chrome）

```powershell
uv run python -m src.auth.export_cookies
```

7. 校验登录态

```powershell
uv run python -m src.cli check-auth --cookie-file cookies.json
```

8. 初始化数据库

```powershell
uv run python -m src.cli init-db
```

9. 启动备份服务

```powershell
uv run python -m src.cli run
```

10. 启动 Web 查看

```powershell
uv run python -m src.cli web
```

11. 验证抓取是否成功

```powershell
sqlite3 data/backup.db "select count(*) as posts from posts; select count(*) as snapshots from post_snapshots;"
```

## 访问地址

默认启动 `uv run python -m src.cli web` 后，可访问：

- Web 首页：`http://127.0.0.1:8765/`
- 帖子详情：`http://127.0.0.1:8765/post/{post_id}`
- 删帖事件：`http://127.0.0.1:8765/deletions`
- 统计接口：`http://127.0.0.1:8765/api/stats`

如果使用了自定义 `--host` 或 `--port`，请按实际地址替换。

## 目录结构

```text
xueqiu/
├── src/              # 核心业务代码（抓取、解析、存储、服务、Web）
├── tests/            # 单元测试
├── scripts/          # 一键部署与服务管理脚本（sh/ps1）
├── data/             # 本地数据目录（SQLite、原始快照、删帖告警）
├── logs/             # 运行日志
├── .env.example      # 环境变量模板
├── pyproject.toml    # 项目依赖与配置
├── uv.lock           # 依赖锁文件
└── README.md         # 使用文档
```

## 数据模型

数据库使用 `SQLite`，完整建表语句见 `src/store/schema.sql`。

### posts（规范化主表）

- 用途：保存每条内容的当前最新状态
- 关键字段：`post_id`（主键）、`post_type`、`author_id`、`author_name`、`created_at`
- 状态字段：`visible_status`（如 `visible` / `deleted_suspected`）
- 时间字段：`first_captured_at`、`last_captured_at`
- 变更检测：`raw_hash`

### post_snapshots（原始快照历史）

- 用途：保存每次抓取到的原始 JSON 快照
- 关键字段：`id`（自增主键）、`post_id`、`captured_at`、`raw_json`、`raw_hash`
- 索引：`(post_id, captured_at DESC)`

### poll_runs（轮询运行记录）

- 用途：记录每轮轮询执行结果
- 关键字段：`started_at`、`finished_at`、`fetched_count`、`new_count`、`updated_count`、`success`、`error_message`

### deletion_events（疑似删帖事件）

- 用途：记录检测到的疑似删帖事件
- 关键字段：`post_id`、`detected_at`、`reason`、`last_seen_at`
- 约束：`UNIQUE(post_id, reason)`

### meta_kv（系统元数据）

- 用途：保存系统运行状态（如游标）
- 关键字段：`key`、`value`、`updated_at`
- 当前主要用于：`feed_cursor`

## 服务管理命令

### macOS / Linux

```bash
./scripts/manage.sh status
./scripts/manage.sh start
./scripts/manage.sh stop
./scripts/manage.sh restart
./scripts/manage.sh logs
```

### Windows（PowerShell）

```powershell
powershell -ExecutionPolicy Bypass -File .\\scripts\\manage.ps1 status
powershell -ExecutionPolicy Bypass -File .\\scripts\\manage.ps1 start
powershell -ExecutionPolicy Bypass -File .\\scripts\\manage.ps1 stop
powershell -ExecutionPolicy Bypass -File .\\scripts\\manage.ps1 restart
powershell -ExecutionPolicy Bypass -File .\\scripts\\manage.ps1 logs
```

## 常用命令

```bash
# 初始化数据库
uv run python -m src.cli init-db

# 校验登录态
uv run python -m src.cli check-auth --cookie-file cookies.json

# 启动备份服务
uv run python -m src.cli run

# 启动 Web 查看（默认 127.0.0.1:8765）
uv run python -m src.cli web

# 自定义 Web 地址
uv run python -m src.cli web --host 0.0.0.0 --port 8765

# 导出指定日期帖子（JSONL）
uv run python -m src.cli export --date 2026-03-01 --format jsonl

# 运行测试
uv run --extra dev python -m pytest -q
```

## 常见问题

### 1) 报错：`Cookie 文件不存在: cookies.json`

先执行导出 Cookie：

```bash
uv run python -m src.auth.export_cookies
```

在弹出的浏览器完成登录后回车，会在项目根目录生成 `cookies.json`。

### 2) 报错：关注流接口 404

确认 `.env` 中配置为：

```bash
XUEQIU_FEED_PATH=/statuses/home_timeline.json
```

### 3) 报错：Playwright 找不到浏览器

脚本会优先使用本机 Chrome。若本机无可用 Chrome，再执行：

```bash
uv run playwright install chromium
```

### 4) 登录态昨天可用，今天失效

这是正常现象（Cookie 过期或账号状态变化）。重新导出 `cookies.json` 后再 `check-auth`。

### 5) Web 页面打不开

- 先确认 Web 已启动：`uv run python -m src.cli web`
- 检查地址是否正确：`http://127.0.0.1:8765`
- 若端口冲突，换端口：`uv run python -m src.cli web --port 8877`

### 6) 一键部署提示 `uv` 或 `python` 不存在

- 先安装 Python 3.11+
- 再安装 uv
- 安装后重新打开终端，再执行：
  - macOS/Linux：`./scripts/deploy.sh`
  - Windows：`powershell -ExecutionPolicy Bypass -File .\\scripts\\deploy.ps1`
