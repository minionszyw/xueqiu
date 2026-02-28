# 雪球关注内容自动备份

目标：分钟级抓取雪球关注流并备份到本地 SQLite，降低删帖导致的数据丢失。

## 快速开始

1. 安装依赖

```bash
uv sync
```

如需使用浏览器导出 Cookie：

```bash
uv sync --extra browser
```

2. 配置环境变量（可复制 `.env.example` 到 `.env`）

3. 初始化数据库

```bash
uv run python -m src.cli init-db
```

4. 导入 Cookie 并检查登录态

```bash
uv run python -m src.cli check-auth --cookie-file cookies.json
```

5. 启动服务

```bash
uv run python -m src.cli run
```

## 目录

- `src/` 业务代码
- `data/backup.db` SQLite 数据库
- `data/raw/` 原始快照
- `data/alerts/` 删除事件摘要
- `logs/backup.log` 运行日志
