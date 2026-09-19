@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0后端\身份网关"
if not exist ".env" (echo 缺少 后端\身份网关\.env，请先根据配置模板创建。& pause & exit /b 1)
conda run -n weixinkouqiang alembic upgrade head
if errorlevel 1 (echo 数据库初始化失败。& pause & exit /b 1)
echo 数据库初始化完成。
pause
