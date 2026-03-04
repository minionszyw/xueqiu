param(
  [Parameter(Mandatory=$true)]
  [ValidateSet('start','stop','status','restart','logs')]
  [string]$Action
)

$ErrorActionPreference = 'Stop'
$Root = Resolve-Path (Join-Path $PSScriptRoot '..')
$RunDir = Join-Path $Root '.run'
$LogDir = Join-Path $Root 'logs'
$BackupPidFile = Join-Path $RunDir 'backup.pid'
$WebPidFile = Join-Path $RunDir 'web.pid'
$BackupLog = Join-Path $LogDir 'backup.service.log'
$WebLog = Join-Path $LogDir 'web.service.log'
$WebHost = '127.0.0.1'
$WebPort = 8765

New-Item -ItemType Directory -Path $RunDir -Force | Out-Null
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

function Get-PidFromFile([string]$Path) {
  if (Test-Path $Path) {
    return (Get-Content $Path -Raw).Trim()
  }
  return $null
}

function Stop-ByPidFile([string]$Path, [string]$Name) {
  $pidVal = Get-PidFromFile $Path
  if ($pidVal) {
    $proc = Get-Process -Id $pidVal -ErrorAction SilentlyContinue
    if ($proc) {
      Stop-Process -Id $pidVal -Force -ErrorAction SilentlyContinue
      Write-Host "已停止 $Name (pid=$pidVal)"
    }
  }
  if (Test-Path $Path) { Remove-Item $Path -Force }
}

function Stop-WebByPort {
  $line = netstat -ano | Select-String ":$WebPort\s+.*LISTENING\s+(\d+)" | Select-Object -First 1
  if ($line) {
    $m = [regex]::Match($line.ToString(), ":$WebPort\s+.*LISTENING\s+(\d+)")
    if ($m.Success) {
      $pid = $m.Groups[1].Value
      Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
      Write-Host "已释放 Web 端口 $WebPort"
    }
  }
}

function Start-Services {
  Stop-Services | Out-Null

  $backup = Start-Process -FilePath 'uv' -ArgumentList 'run','python','-m','src.cli','run' -WorkingDirectory $Root -RedirectStandardOutput $BackupLog -RedirectStandardError $BackupLog -PassThru
  $backup.Id | Out-File $BackupPidFile -Encoding ascii

  $web = Start-Process -FilePath 'uv' -ArgumentList 'run','python','-m','src.cli','web','--host',$WebHost,'--port',"$WebPort" -WorkingDirectory $Root -RedirectStandardOutput $WebLog -RedirectStandardError $WebLog -PassThru
  $web.Id | Out-File $WebPidFile -Encoding ascii

  Start-Sleep -Seconds 2
  Status-Services
}

function Stop-Services {
  Stop-ByPidFile $BackupPidFile '备份服务'
  Stop-ByPidFile $WebPidFile 'Web 服务'
  Stop-WebByPort
}

function Print-Status([string]$Name, [string]$Path) {
  $pidVal = Get-PidFromFile $Path
  if ($pidVal -and (Get-Process -Id $pidVal -ErrorAction SilentlyContinue)) {
    Write-Host "$Name: 运行中 (pid=$pidVal)"
  }
  else {
    Write-Host "$Name: 未运行"
  }
}

function Status-Services {
  Print-Status '备份服务' $BackupPidFile
  Print-Status 'Web 服务' $WebPidFile
  try {
    $stats = Invoke-RestMethod -Uri "http://$WebHost`:$WebPort/api/stats" -Method Get -TimeoutSec 3
    Write-Host "Web API: 正常 http://$WebHost`:$WebPort/api/stats"
    Write-Host ("统计: " + ($stats | ConvertTo-Json -Compress))
  }
  catch {
    Write-Host 'Web API: 不可用'
  }
}

function Show-Logs {
  Write-Host '== 备份服务日志 (最近 50 行) =='
  if (Test-Path $BackupLog) { Get-Content $BackupLog -Tail 50 } else { Write-Host "暂无日志: $BackupLog" }
  Write-Host ''
  Write-Host '== Web 服务日志 (最近 50 行) =='
  if (Test-Path $WebLog) { Get-Content $WebLog -Tail 50 } else { Write-Host "暂无日志: $WebLog" }
}

switch ($Action) {
  'start' { Start-Services }
  'stop' { Stop-Services }
  'status' { Status-Services }
  'restart' { Stop-Services; Start-Services }
  'logs' { Show-Logs }
}
