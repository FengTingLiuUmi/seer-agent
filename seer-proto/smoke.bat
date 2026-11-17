@echo off
setlocal
cd /d "%~dp0"
node tools\smoke.mjs
if errorlevel 1 goto fail
echo.
echo SMOKE OK
goto end
:fail
echo SMOKE FAILED
pause
:end
