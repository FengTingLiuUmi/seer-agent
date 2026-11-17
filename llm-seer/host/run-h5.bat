@echo off
setlocal
cd /d "%~dp0"
echo [1/2] prep session (seer-proto/tools/prep_pwd.mjs)
pushd "C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto"
node tools\prep_pwd.mjs
popd
timeout /t 1 /nobreak >nul
echo [2/2] launch H5 host (Electron)
start "" "%~dp0electron11-32\electron.exe" "%~dp0h5-main.js"
echo.
echo log: llm-seer/host/host-h5-log.txt
