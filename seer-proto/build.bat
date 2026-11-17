@echo off
setlocal
cd /d "%~dp0"
rem Use a local Go toolchain if the system one is absent.
set "GOBIN_HINT=%~dp0..\.tools\go\bin"
if exist "%GOBIN_HINT%\go.exe" set "PATH=%GOBIN_HINT%;%PATH%"
set "GOBIN_HINT2=%~dp0..\re\tools\go\go\bin"
if exist "%GOBIN_HINT2%\go.exe" set "PATH=%GOBIN_HINT2%;%PATH%"
set "GOCACHE=%~dp0..\llm-seer\cache\go"
set "GOMODCACHE=%~dp0..\llm-seer\cache\gomod"
set "GOPATH=%~dp0..\llm-seer\cache\gopath"
set "GOPROXY=off"
go build -o seerproto.exe .
if errorlevel 1 goto fail
echo build OK: seerproto.exe
goto end
:fail
echo build FAILED
pause
:end
