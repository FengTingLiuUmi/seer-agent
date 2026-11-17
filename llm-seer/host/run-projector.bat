@echo off
setlocal
cd /d "%~dp0"
set "PROJ=%~dp0flashproj.exe"

echo [1/3] static site :8001
start "" /min cmd /c "cd /d %~dp0 && python serve.py site 8001"
timeout /t 2 /nobreak >nul

echo [2/3] tcp proxy :18630 -> 1864
start "" /min cmd /c "cd /d C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto && python tools\tcp_proxy.py --listen 127.0.0.1:18630 --upstream 101.43.19.60:1864 --frames"
timeout /t 1 /nobreak >nul

echo [3/3] launch projector with Client.swf
start "" "%PROJ%" "http://127.0.0.1:8001/Client.swf"
echo.
echo If projector asks for network/file access, click ALLOW.
echo logs: llm-seer/host/site-requests.log  and  seer-proto/proxy-18630.jsonl
