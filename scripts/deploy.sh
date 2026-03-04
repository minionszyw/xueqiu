#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANAGE_SH="$ROOT_DIR/scripts/manage.sh"

need_cmd() {
  local cmd="$1"
  local hint="$2"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "缺少命令: $cmd"
    echo "安装提示: $hint"
    exit 1
  fi
}

check_python() {
  local version
  version="$(uv run python - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"
  local major="${version%%.*}"
  local minor="${version##*.}"
  if [[ "$major" -lt 3 ]] || [[ "$major" -eq 3 && "$minor" -lt 11 ]]; then
    echo "Python 版本过低: $version (需要 >=3.11)"
    exit 1
  fi
}

prepare_env() {
  cd "$ROOT_DIR"
  if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "已创建 .env（来自 .env.example）"
  fi
  mkdir -p .run logs data
}

ensure_cookie() {
  cd "$ROOT_DIR"
  if [[ ! -f cookies.json ]]; then
    echo "未检测到 cookies.json，开始引导导出 Cookie..."
    uv run python -m src.auth.export_cookies
  fi
}

check_auth_with_retry() {
  local max_try=3
  local n=1
  while (( n <= max_try )); do
    if uv run python -m src.cli check-auth --cookie-file cookies.json; then
      return 0
    fi
    echo "登录态校验失败（第 $n/$max_try 次），3 秒后重试..."
    sleep 3
    ((n++))
  done
  return 1
}

main() {
  need_cmd uv "请安装 uv: https://docs.astral.sh/uv/"
  need_cmd curl "请安装 curl"

  check_python
  prepare_env

  echo "安装依赖..."
  cd "$ROOT_DIR"
  uv sync
  uv sync --extra browser

  ensure_cookie

  echo "校验登录态..."
  check_auth_with_retry

  echo "初始化数据库..."
  uv run python -m src.cli init-db

  echo "启动后台服务..."
  "$MANAGE_SH" restart

  echo
  echo "部署完成。"
  echo "Web 地址: http://127.0.0.1:8765/"
  echo "服务状态:"
  "$MANAGE_SH" status
  echo
  echo "常用命令:"
  echo "  ./scripts/manage.sh status"
  echo "  ./scripts/manage.sh logs"
  echo "  ./scripts/manage.sh stop"
}

main "$@"
