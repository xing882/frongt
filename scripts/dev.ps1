# 一键联调：需已安装 Python 依赖（backend）与前端依赖（frontend: pnpm install）
# 用法：在 building_energy_system 目录执行  .\scripts\dev.ps1
# 或：npm install && npm run dev（推荐，见 package.json）

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "后端: http://127.0.0.1:8765/docs" -ForegroundColor Green
Write-Host "前端: http://127.0.0.1:5173 （Vite 默认端口）" -ForegroundColor Green
Write-Host ""

Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\backend'; py -3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8765"
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\frontend'; pnpm dev"
