@echo off
setlocal
cd /d "%~dp0"
if exist ".seerproto.lock" del /q ".seerproto.lock"
echo [1/3] prep login (password / cred.enc.json)
node tools\prep_pwd.mjs
if errorlevel 1 goto fail
echo [2/3] start client + live panel
start "" http://127.0.0.1:7800
.\seerproto.exe -info login.json -steps steps_run.json -seconds 240 -view 127.0.0.1:7800
echo [3/3] report
python tools\report.py session.jsonl report.html
start "" report.html
goto end
:fail
echo.
echo login failed - check secrets/cred.enc.json or SEER_PASSWORD
pause
:end
