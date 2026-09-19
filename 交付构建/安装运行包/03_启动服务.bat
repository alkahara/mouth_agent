@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if not exist "后端\Agent\.env" (echo 缺少 Agent .env 配置。& pause & exit /b 1)
if not exist "后端\身份网关\.env" (echo 缺少身份网关 .env 配置。& pause & exit /b 1)
start "口腔智能体 Agent" /min cmd /k "cd /d "%~dp0后端\Agent" && conda run -n weixinkouqiang python run_server.py"
timeout /t 3 /nobreak >nul
start "口腔智能体身份网关" /min cmd /k "cd /d "%~dp0后端\身份网关" && conda run -n weixinkouqiang python -m uvicorn server:app --host 127.0.0.1 --port 8001"
echo Agent 与身份网关已启动，请保留两个命令窗口。
pause
