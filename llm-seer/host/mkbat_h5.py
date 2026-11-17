"""生成 run-h5.bat：Electron 加载 seerh5.61.com/?sid= 并注入 JS"""
lines = [
    '@echo off',
    'setlocal',
    'cd /d "%~dp0"',
    'echo [1/2] prep session (seer-proto/tools/prep_pwd.mjs)',
    'pushd "C:\\Users\\kmdbn\\Documents\\deepseek-harness\\default-workspace\seer\\seer-proto"',
    'node tools\\prep_pwd.mjs',
    'popd',
    'timeout /t 1 /nobreak >nul',
    'echo [2/2] launch H5 host (Electron)',
    'start "" "%~dp0electron11-32\\electron.exe" "%~dp0h5-main.js"',
    'echo.',
    'echo log: llm-seer/host/host-h5-log.txt',
]
data = '\r\n'.join(lines).rstrip('\r\n') + '\r\n'
open('run-h5.bat', 'wb').write(data.encode('ascii'))
print('ok run-h5.bat', len(data), 'bytes')