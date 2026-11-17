@echo off
setlocal
net session >nul 2>nul
if %errorlevel% neq 0 (
  echo Need Administrator - requesting elevation...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
set "A=C:\Windows\System32\Macromed\Flash\mms.cfg"
set "B=C:\Windows\SysWOW64\Macromed\Flash\mms.cfg"
if exist "%A%" del /f /q "%A%" && echo removed %A%
if exist "%B%" del /f /q "%B%" && echo removed %B%
echo done. restart your flash client.
pause
