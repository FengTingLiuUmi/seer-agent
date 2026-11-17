"""生成 run-ie.bat（CRLF + ASCII）：IE 宿主 + 本地站点 + 代理"""
lines = [
    '@echo off',
    'setlocal',
    'cd /d "%~dp0"',
    'set "ROOT=C:\\Users\\kmdbn\\Documents\\deepseek-harness\\default-workspace"',
    'set "SEER=%ROOT%\\seer-proto"',
    '',
    'echo [1/4] IE browser emulation (HKCU)',
    'reg add "HKCU\\Software\\Microsoft\\Internet Explorer\\Main\\FeatureControl\\FEATURE_BROWSER_EMULATION" /v powershell.exe /t REG_DWORD /d 11001 /f >nul 2>nul',
    '',
    'echo [2/4] static site :8001',
    'start "" /min cmd /c "cd /d %~dp0 && python serve.py site 8001"',
    '',
    'echo [3/4] tcp proxy :18630 -> 1864',
    'start "" /min cmd /c "cd /d %SEER% && python tools\\tcp_proxy.py --listen 127.0.0.1:18630 --upstream 101.43.19.60:1864 --frames"',
    '',
    'timeout /t 2 /nobreak >nul',
    'echo [4/4] flash host (IE + Flash OCX)',
    'start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0host_ie.ps1"',
    'echo.',
    'echo log: llm-seer/host/host-ie-log.txt',
    'echo frames: seer-proto/proxy-18630.jsonl',
]
data = '\r\n'.join(lines).rstrip('\r\n') + '\r\n'
open('run-ie.bat', 'wb').write(data.encode('ascii'))
print('ok run-ie.bat', len(data), 'bytes')