"""生成 reset-flashcfg.bat：删除我们写入的 Flash mms.cfg（自动提权）"""
lines = [
    '@echo off',
    'setlocal',
    'net session >nul 2>nul',
    'if %errorlevel% neq 0 (',
    '  echo Need Administrator - requesting elevation...',
    '  powershell -NoProfile -Command "Start-Process -FilePath \'%~f0\' -Verb RunAs"',
    '  exit /b',
    ')',
    'set "A=C:\\Windows\\System32\\Macromed\\Flash\\mms.cfg"',
    'set "B=C:\\Windows\\SysWOW64\\Macromed\\Flash\\mms.cfg"',
    'if exist "%A%" del /f /q "%A%" && echo removed %A%',
    'if exist "%B%" del /f /q "%B%" && echo removed %B%',
    'echo done. restart your flash client.',
    'pause',
]
data = '\r\n'.join(lines).rstrip('\r\n') + '\r\n'
open('reset-flashcfg.bat', 'wb').write(data.encode('ascii'))
print('ok reset-flashcfg.bat', len(data), 'bytes')