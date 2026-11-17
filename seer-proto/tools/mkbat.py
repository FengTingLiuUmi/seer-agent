"""生成 .bat（CRLF + 纯 ASCII，避免 cmd 解析问题）"""


def write_bat(path, lines):
    data = '\r\n'.join(lines).rstrip('\r\n') + '\r\n'
    open(path, 'wb').write(data.encode('ascii'))
    print('ok', path, len(data), 'bytes; ascii; crlf')


run_live = [
    '@echo off',
    'setlocal',
    'cd /d "%~dp0"',
    'if exist ".seerproto.lock" del /q ".seerproto.lock"',
    'echo [1/3] prep login (password / cred.enc.json)',
    'node tools\\prep_pwd.mjs',
    'if errorlevel 1 goto fail',
    'echo [2/3] start client + live panel',
    'start "" http://127.0.0.1:7800',
    '.\\seerproto.exe -info login.json -steps steps_run.json -seconds 240 -view 127.0.0.1:7800',
    'echo [3/3] report',
    'python tools\\report.py session.jsonl report.html',
    'start "" report.html',
    'goto end',
    ':fail',
    'echo.',
    'echo login failed - check secrets/cred.enc.json or SEER_PASSWORD',
    'pause',
    ':end',
]

build = [
    '@echo off',
    'setlocal',
    'cd /d "%~dp0"',
    'set "GOBIN_HINT=%~dp0..\\re\\tools\\go\\go\\bin"',
    'if exist "%GOBIN_HINT%\\go.exe" set "PATH=%GOBIN_HINT%;%PATH%"',
    'set "GOCACHE=%~dp0..\\llm-seer\\cache\\go"',
    'set "GOMODCACHE=%~dp0..\\llm-seer\\cache\\gomod"',
    'set "GOPATH=%~dp0..\\llm-seer\\cache\\gopath"',
    'set "GOPROXY=https://goproxy.cn,direct"',
    'go build -o seerproto.exe .',
    'if errorlevel 1 goto fail',
    'echo build OK: seerproto.exe',
    'goto end',
    ':fail',
    'echo build FAILED',
    'pause',
    ':end',
]

write_bat('run-live.bat', run_live)
write_bat('build.bat', build)

smoke = [
    '@echo off',
    'setlocal',
    'cd /d "%~dp0"',
    'node tools\\smoke.mjs',
    'if errorlevel 1 goto fail',
    'echo.',
    'echo SMOKE OK',
    'goto end',
    ':fail',
    'echo SMOKE FAILED',
    'pause',
    ':end',
]
write_bat('smoke.bat', smoke)