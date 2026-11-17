"""生成 install-flashcfg.bat（自动提权，写 Flash 白名单 mms.cfg）"""
lines = [
    '@echo off',
    'setlocal',
    'cd /d "%~dp0"',
    '',
    'net session >nul 2>nul',
    'if %errorlevel% neq 0 (',
    '  echo Need Administrator - requesting elevation...',
    '  powershell -NoProfile -Command "Start-Process -FilePath \'%~f0\' -Verb RunAs"',
    '  exit /b',
    ')',
    '',
    'set "CFG=%~dp0flashcfg\\mms.cfg"',
    'if not exist "%CFG%" ( echo missing %CFG% & pause & exit /b 1 )',
    '',
    'echo [1/2] System32',
    'if not exist "C:\\Windows\\System32\\Macromed\\Flash" mkdir "C:\\Windows\\System32\\Macromed\\Flash"',
    'copy /y "%CFG%" "C:\\Windows\\System32\\Macromed\\Flash\\mms.cfg"',
    '',
    'echo [2/2] SysWOW64',
    'if not exist "C:\\Windows\\SysWOW64\\Macromed\\Flash" mkdir "C:\\Windows\\SysWOW64\\Macromed\\Flash"',
    'copy /y "%CFG%" "C:\\Windows\\SysWOW64\\Macromed\\Flash\\mms.cfg"',
    '',
    'echo.',
    'echo Done. Now run: run-ie.bat',
    'pause',
]
data = '\r\n'.join(lines).rstrip('\r\n') + '\r\n'
open('install-flashcfg.bat', 'wb').write(data.encode('ascii'))
print('ok install-flashcfg.bat', len(data), 'bytes')