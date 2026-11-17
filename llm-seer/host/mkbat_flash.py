"""生成 run-flash.bat：启动 Flash 宿主 + HTTP 接口（给 agent/大模型用）"""
lines = [
    '@echo off',
    'setlocal',
    'cd /d "%~dp0"',
    'set "PS32=%WINDIR%\\SysWOW64\\WindowsPowerShell\\v1.0\\powershell.exe"',
    'if not exist "%PS32%" set "PS32=powershell.exe"',
    '',
    'echo [1/2] flash host (IE control, 32-bit)',
    'start "" "%PS32%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0host_play.ps1"',
    'timeout /t 3 /nobreak >nul',
    '',
    'echo [2/2] http api on 127.0.0.1:7801',
    'start "" /min cmd /c "cd /d C:\\Users\\kmdbn\\Documents\\deepseek-harness\\default-workspace\seer\\seer-proto && python tools\\flash_api.py --port 7801"',
    'echo.',
    'echo api: http://127.0.0.1:7801/state',
]
data = '\r\n'.join(lines).rstrip('\r\n') + '\r\n'
open('run-flash.bat', 'wb').write(data.encode('ascii'))
print('ok run-flash.bat', len(data), 'bytes')