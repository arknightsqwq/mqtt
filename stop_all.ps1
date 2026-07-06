# 停止 IoT 设备监测系统所有服务

$ErrorActionPreference = "SilentlyContinue"

Write-Host "正在停止所有服务..." -ForegroundColor Yellow

# 后端 (Python main.py)
Get-Process python | Where-Object { $_.CommandLine -like "*main.py*" } | Stop-Process -Force
Write-Host "  后端已停止" -ForegroundColor Green

# 前端 (Vite on 5175/5176)
Get-Process node | Where-Object { $_.CommandLine -like "*vite*" } | Stop-Process -Force
Write-Host "  前端已停止" -ForegroundColor Green

Write-Host "完成。" -ForegroundColor Cyan
