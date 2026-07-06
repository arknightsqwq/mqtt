# 一键启动 IoT 设备监测系统（后端 + 用户前端 + 管理前端）
# 用法：右键 → 使用 PowerShell 运行，或在终端输入 .\start_all.ps1

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "==============================" -ForegroundColor Cyan
Write-Host "  IoT 设备监测系统 — 一键启动" -ForegroundColor Cyan
Write-Host "==============================" -ForegroundColor Cyan
Write-Host ""

# ── 1. 启动后端 ──
Write-Host "[1/3] 启动后端 (FastAPI :8000)" -ForegroundColor Yellow
$backendDir = Join-Path $root "mqtt_backend"
$pythonExe = Join-Path $backendDir ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Host "  错误: 未找到 Python 虚拟环境 $pythonExe" -ForegroundColor Red
    Write-Host "  请先在 mqtt_backend 目录执行: python -m venv .venv && .venv\Scripts\pip install -r requirements.txt" -ForegroundColor Red
    exit 1
}

$backendJob = Start-Process -FilePath $pythonExe -ArgumentList "main.py" -WorkingDirectory $backendDir -PassThru -WindowStyle Minimized
Write-Host "  后端 PID: $($backendJob.Id)" -ForegroundColor Green

# ── 2. 启动管理前端 ──
Write-Host "[2/3] 启动管理前端 (Vite :5175)" -ForegroundColor Yellow
$adminDir = Join-Path $root "mqtt_frontend_admin"

if (-not (Test-Path (Join-Path $adminDir "node_modules"))) {
    Write-Host "  正在安装依赖..." -ForegroundColor Gray
    cmd /c "npm --prefix `"$adminDir`" install" 2>&1 | Out-Null
}

$adminJob = Start-Process -FilePath "cmd" -ArgumentList "/c npx vite --port 5175 --host 0.0.0.0" -WorkingDirectory $adminDir -PassThru -WindowStyle Minimized
Write-Host "  管理前端 PID: $($adminJob.Id)" -ForegroundColor Green

# ── 3. 启动用户前端 ──
Write-Host "[3/3] 启动用户前端 (Vite :5176)" -ForegroundColor Yellow
$userDir = Join-Path $root "mqtt_frontend_user"

if (-not (Test-Path (Join-Path $userDir "node_modules"))) {
    Write-Host "  正在安装依赖..." -ForegroundColor Gray
    cmd /c "npm --prefix `"$userDir`" install" 2>&1 | Out-Null
}

$userJob = Start-Process -FilePath "cmd" -ArgumentList "/c npx vite --port 5176 --host 0.0.0.0" -WorkingDirectory $userDir -PassThru -WindowStyle Minimized
Write-Host "  用户前端 PID: $($userJob.Id)" -ForegroundColor Green

# ── 完成 ──
Write-Host ""
Write-Host "==============================" -ForegroundColor Cyan
Write-Host "  所有服务已启动！" -ForegroundColor Cyan
Write-Host "==============================" -ForegroundColor Cyan
Write-Host "  后端 API:    http://localhost:8000" -ForegroundColor White
Write-Host "  API 文档:    http://localhost:8000/docs" -ForegroundColor White
Write-Host "  管理前端:    http://localhost:5175" -ForegroundColor White
Write-Host "  用户前端:    http://localhost:5176" -ForegroundColor White
Write-Host ""
Write-Host "  停止所有服务: .\stop_all.ps1" -ForegroundColor Gray
Write-Host ""

# 等待用户按键关闭（可选）
Write-Host "按任意键停止所有服务..." -ForegroundColor DarkYellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

# 清理
Write-Host "正在停止..." -ForegroundColor Yellow
Stop-Process -Id $backendJob.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $adminJob.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $userJob.Id -Force -ErrorAction SilentlyContinue
Write-Host "已停止。" -ForegroundColor Green
