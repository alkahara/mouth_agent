@echo off
chcp 65001 >nul
powershell -NoProfile -Command "$ports=8000,8001; Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object LocalPort -in $ports | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -ErrorAction SilentlyContinue }"
echo 已停止 8000 和 8001 端口的服务。
pause
