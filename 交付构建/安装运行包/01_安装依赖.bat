@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
where conda >nul 2>nul || (echo 未找到 Conda，请先安装 Anaconda 或 Miniconda。& pause & exit /b 1)
conda env list | findstr /I /C:"weixinkouqiang" >nul || conda create -n weixinkouqiang python=3.11 -y || goto :error
conda run -n weixinkouqiang python -m pip install -r "后端\Agent\requirements.txt" || goto :error
conda run -n weixinkouqiang python -m pip install -r "后端\身份网关\requirements.txt" || goto :error
echo.
echo 依赖安装完成。
pause
exit /b 0
:error
echo.
echo 安装失败，请查看上方错误信息。
pause
exit /b 1
