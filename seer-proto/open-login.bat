@echo off
rem Start the login console and open it in the default browser.
cd /d "%~dp0"
start "" run-login.bat
timeout /t 2 >nul
start "" http://127.0.0.1:7820/
