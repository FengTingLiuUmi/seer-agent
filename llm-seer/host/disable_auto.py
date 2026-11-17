import io

p = 'llm-seer/host/host_play.ps1'
s = io.open(p, encoding='utf-8').read()

# 1) 自动登录改为必须显式传 -AutoLogin
s = s.replace("param([string]$PlayUrl = '', [string]$Account = 'ACCOUNT')",
              "param([string]$PlayUrl = '', [string]$Account = 'ACCOUNT', [switch]$AutoLogin)")

old_auto = """  # auto blind-login once after 20s (disable with -Account '')
  if ($Account) {"""
new_auto = """  # auto blind-login only when -AutoLogin is passed explicitly
  if ($AutoLogin) {"""
s = s.replace(old_auto, new_auto)

io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
d = open(p, 'rb').read()
print('ascii', all(b < 0x80 for b in d), 'AutoLogin switch', b'[switch]$AutoLogin' in d, 'disabled default', b'if ($AutoLogin)' in d)