"""生成 run-host.bat：设置 IE 浏览器模拟级别 + 起本地 HTTP + 拉起 Flash 宿主"""
lines = [
    '@echo off',
    'setlocal',
    'cd /d "%~dp0"',
    'echo [1/3] set IE browser emulation (HKCU, no admin needed)',
    'reg add "HKCU\\Software\\Microsoft\\Internet Explorer\\Main\\FeatureControl\\FEATURE_BROWSER_EMULATION" /v powershell.exe /t REG_DWORD /d 11001 /f >nul',
    'reg add "HKCU\\Software\\Microsoft\\Internet Explorer\\Main\\FeatureControl\\FEATURE_BROWSER_EMULATION" /v pwsh.exe /t REG_DWORD /d 11001 /f >nul',
    'reg add "HKCU\\Software\\Microsoft\\Internet Explorer\\Main\\FeatureControl\\FEATURE_BLOCK_LMZ_OBJECT" /v powershell.exe /t REG_DWORD /d 0 /f >nul',
    'echo [2/3] start local http server on 8000',
    'start "" /min cmd /c "cd /d %~dp0 && python -m http.server 8000 --bind 127.0.0.1"',
    'timeout /t 2 /nobreak >nul',
    'echo [3/3] launch flash host window',
    'start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0host.ps1" -Url http://127.0.0.1:8000/page.html',
    'echo.',
    'echo If a Flash window appears with a black screen, click once inside it',
    'echo (IE "click to activate" for ActiveX).',
    'echo Then report back what you see.',
    'pause',
]
data = '\r\n'.join(lines).rstrip('\r\n') + '\r\n'
open('run-host.bat', 'wb').write(data.encode('ascii'))
print('ok run-host.bat', len(data), 'bytes')