@echo off
rem 启动新登录界面 + MCP 后端（常驻）。关闭窗口即停止会话。
setlocal
cd /d "%~dp0"
title seer login console
echo.
echo   seer-service : http://127.0.0.1:7820
echo     - 登录界面 = 浏览器打开上面的地址
echo     - MCP 客户端会复用同一个会话（不会互相顶号）
echo.
python tools\seer_service.py --port 7820 --serve-port 7811 --view-port 7812 %*
if errorlevel 1 pause