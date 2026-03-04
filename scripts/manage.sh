#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"
LOG_DIR="$ROOT_DIR/logs"
BACKUP_PID_FILE="$RUN_DIR/backup.pid"
WEB_PID_FILE="$RUN_DIR/web.pid"
BACKUP_LOG="$LOG_DIR/backup.service.log"
WEB_LOG="$LOG_DIR/web.service.log"
WEB_HOST="${WEB_HOST:-127.0.0.1}"
WEB_PORT="${WEB_PORT:-8765}"

mkdir -p "$RUN_DIR" "$LOG_DIR"

has_cmd() { command -v "$1" >/dev/null 2>&1; }

is_pid_running() {
  local pid="$1"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" >/dev/null 2>&1
}

read_pid() {
  local file="$1"
  [[ -f "$file" ]] || return 1
  tr -d '[:space:]' < "$file"
}

stop_pid_file() {
  local file="$1"
  local name="$2"
  local pid
  pid="$(read_pid "$file" || true)"
  if [[ -n "$pid" ]] && is_pid_running "$pid"; then
    kill "$pid" >/dev/null 2>&1 || true
    sleep 1
    if is_pid_running "$pid"; then
      kill -9 "$pid" >/dev/null 2>&1 || true
    fi
    echo "已停止 $name (pid=$pid)"
  fi
  rm -f "$file"
}

stop_web_by_port() {
  if has_cmd lsof; then
    local pids
    pids="$(lsof -tiTCP:"$WEB_PORT" -sTCP:LISTEN || true)"
    if [[ -n "$pids" ]]; then
      kill $pids >/dev/null 2>&1 || true
      sleep 1
      echo "已释放 Web 端口 $WEB_PORT"
    fi
  fi
}

start_services() {
  cd "$ROOT_DIR"
  stop_services >/dev/null 2>&1 || true

  nohup env PYTHONUNBUFFERED=1 uv run python -m src.cli run > "$BACKUP_LOG" 2>&1 &
  echo $! > "$BACKUP_PID_FILE"

  nohup env PYTHONUNBUFFERED=1 uv run python -m src.cli web --host "$WEB_HOST" --port "$WEB_PORT" > "$WEB_LOG" 2>&1 &
  echo $! > "$WEB_PID_FILE"

  sleep 2
  status_services
}

stop_services() {
  stop_pid_file "$BACKUP_PID_FILE" "备份服务"
  stop_pid_file "$WEB_PID_FILE" "Web 服务"
  stop_web_by_port
}

print_status_line() {
  local name="$1"
  local file="$2"
  local pid
  pid="$(read_pid "$file" || true)"
  if [[ -n "$pid" ]] && is_pid_running "$pid"; then
    echo "$name: 运行中 (pid=$pid)"
  else
    echo "$name: 未运行"
  fi
}

status_services() {
  print_status_line "备份服务" "$BACKUP_PID_FILE"
  print_status_line "Web 服务" "$WEB_PID_FILE"

  if has_cmd curl; then
    local stats
    stats="$(curl -sS "http://$WEB_HOST:$WEB_PORT/api/stats" 2>/dev/null || true)"
    if [[ -n "$stats" ]]; then
      echo "Web API: 正常 http://$WEB_HOST:$WEB_PORT/api/stats"
      echo "统计: $stats"
    else
      echo "Web API: 不可用"
    fi
  else
    echo "提示: 未安装 curl，跳过 API 健康检查"
  fi
}

logs_services() {
  echo "== 备份服务日志 (最近 50 行) =="
  tail -n 50 "$BACKUP_LOG" 2>/dev/null || echo "暂无日志: $BACKUP_LOG"
  echo
  echo "== Web 服务日志 (最近 50 行) =="
  tail -n 50 "$WEB_LOG" 2>/dev/null || echo "暂无日志: $WEB_LOG"
}

usage() {
  cat <<USAGE
用法: ./scripts/manage.sh <start|stop|status|restart|logs>
USAGE
}

main() {
  local action="${1:-}"
  case "$action" in
    start) start_services ;;
    stop) stop_services ;;
    status) status_services ;;
    restart) stop_services; start_services ;;
    logs) logs_services ;;
    *) usage; exit 1 ;;
  esac
}

main "$@"
