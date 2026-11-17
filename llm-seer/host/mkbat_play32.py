"""生成 run-play.bat：用 32 位 PowerShell 跑 IE 宿主（命中 Flash32.ocx）"""
lines = [
    '@echo off',
    'setlocal',
    'cd /d "%~dp0"',
    'set "PS32=%WINDIR%\\SysWOW64\\WindowsPowerShell\\v1.0\\powershell.exe"',
    'if not exist "%PS32%" set "PS32=powershell.exe"',
    'echo starting 32-bit flash host ...',
    'start "" "%PS32%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0host_play.ps1"',
    'echo.',
    'echo log: llm-seer/host/host-play-log.txt',
]
data = '\r\n'.join(lines).rstrip('\r\n') + '\r\n'
open('run-play.bat', 'wb').write(data.encode('ascii'))
print('ok run-play.bat', len(data), 'bytes')