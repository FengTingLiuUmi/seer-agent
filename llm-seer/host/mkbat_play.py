"""生成 run-play.bat：IE 控件打开官方 play.shtml?sid=（雷小伊同款通道）"""
lines = [
    '@echo off',
    'setlocal',
    'cd /d "%~dp0"',
    'echo starting flash host (IE control) ...',
    'start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0host_play.ps1"',
    'echo.',
    'echo log: llm-seer/host/host-play-log.txt',
]
data = '\r\n'.join(lines).rstrip('\r\n') + '\r\n'
open('run-play.bat', 'wb').write(data.encode('ascii'))
print('ok run-play.bat', len(data), 'bytes')