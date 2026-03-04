$ErrorActionPreference = 'Stop'

$Root = Resolve-Path (Join-Path $PSScriptRoot '..')
$ManageScript = Join-Path $PSScriptRoot 'manage.ps1'

function Require-Command([string]$cmd, [string]$hint) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
    Write-Host "缺少命令: $cmd"
    Write-Host "安装提示: $hint"
    exit 1
  }
}

function Check-PythonVersion {
  $v = python -c "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')"
  $parts = $v.Split('.')
  $major = [int]$parts[0]
  $minor = [int]$parts[1]
  if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 11)) {
    Write-Host "Python 版本过低: $v (需要 >= 3.11)"
    exit 1
  }
}

function Prepare-Env {
  Set-Location $Root
  if (-not (Test-Path '.env')) {
    Copy-Item '.env.example' '.env'
    Write-Host '已创建 .env（来自 .env.example）'
  }
  New-Item -ItemType Directory -Path '.run' -Force | Out-Null
  New-Item -ItemType Directory -Path 'logs' -Force | Out-Null
  New-Item -ItemType Directory -Path 'data' -Force | Out-Null
}

function Ensure-Cookie {
  Set-Location $Root
  if (-not (Test-Path 'cookies.json')) {
    Write-Host '未检测到 cookies.json，开始引导导出 Cookie...'
    uv run python -m src.auth.export_cookies
  }
}

function Check-AuthWithRetry {
  $maxTry = 3
  for ($i = 1; $i -le $maxTry; $i++) {
    try {
      uv run python -m src.cli check-auth --cookie-file cookies.json
      return
    }
    catch {
      if ($i -ge $maxTry) { throw }
      Write-Host "登录态校验失败（第 $i/$maxTry 次），3 秒后重试..."
      Start-Sleep -Seconds 3
    }
  }
}

Require-Command 'python' '请安装 Python 3.11+'
Require-Command 'uv' '请安装 uv: https://docs.astral.sh/uv/'
Check-PythonVersion
Prepare-Env

Set-Location $Root
Write-Host '安装依赖...'
uv sync
uv sync --extra browser

Ensure-Cookie

Write-Host '校验登录态...'
Check-AuthWithRetry

Write-Host '初始化数据库...'
uv run python -m src.cli init-db

Write-Host '启动后台服务...'
powershell -ExecutionPolicy Bypass -File $ManageScript restart

Write-Host ''
Write-Host '部署完成。'
Write-Host 'Web 地址: http://127.0.0.1:8765/'
Write-Host '服务状态:'
powershell -ExecutionPolicy Bypass -File $ManageScript status
Write-Host ''
Write-Host '常用命令:'
Write-Host '  powershell -ExecutionPolicy Bypass -File .\scripts\manage.ps1 status'
Write-Host '  powershell -ExecutionPolicy Bypass -File .\scripts\manage.ps1 logs'
Write-Host '  powershell -ExecutionPolicy Bypass -File .\scripts\manage.ps1 stop'
