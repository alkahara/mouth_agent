@echo off
chcp 65001 >nul
setlocal
set "DEVTOOLS=C:\Program Files (x86)\Tencent\微信web开发者工具\cli.bat"
if not exist "%DEVTOOLS%" set "DEVTOOLS=C:\Program Files\Tencent\微信web开发者工具\cli.bat"
if not exist "%DEVTOOLS%" (echo 未找到微信开发者工具，请手动导入“小程序”文件夹。& pause & exit /b 1)
call "%DEVTOOLS%" open --project "%~dp0小程序"
if errorlevel 1 echo 如提示服务端口关闭，请在微信开发者工具：设置 - 安全设置 中开启服务端口。
pause
