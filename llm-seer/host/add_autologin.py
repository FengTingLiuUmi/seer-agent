import io

p = 'llm-seer/host/host_play.ps1'
s = io.open(p, encoding='utf-8').read()

# 1) 在 BlindLogin 之后插入等待/搜索函数
anchor = "function Invoke-Ipc([string]$raw) {"
helpers = r'''function GameConnected() {
  try {
    $c = Get-NetTCPConnection -RemotePort 1864 -ErrorAction SilentlyContinue |
         Where-Object { $_.State -in @('Established','SynSent','TimeWait','CloseWait') }
    return (($c | Measure-Object).Count -gt 0)
  } catch { return $false }
}

function WaitGame([int]$sec) {
  $t0 = Get-Date
  while (((Get-Date) - $t0).TotalSeconds -lt $sec) {
    if (GameConnected) { return $true }
    Start-Sleep -Milliseconds 500
  }
  return $false
}

function ClearField() {
  SendKeysSafe("{TAB}") | Out-Null
  Start-Sleep -Milliseconds 120
  SendKeysSafe("^a") | Out-Null
  Start-Sleep -Milliseconds 80
  SendKeysSafe("{DEL}") | Out-Null
  Start-Sleep -Milliseconds 80
}

function TrySequence([string]$keys, [int]$waitSec) {
  ClickAt 512 330 | Out-Null
  Start-Sleep -Milliseconds 400
  SendKeysSafe($keys) | Out-Null
  return (WaitGame $waitSec)
}

function AutoLogin() {
  # 候选焦点序列（命中即停，把结果写进 ipc/login_seq.json）
  $seqs = @(
    @{ name = 'tab_uid_tab_pwd_enter'; keys = ("{TAB}" + $Account + "{TAB}" + $pwd + "{ENTER}") },
    @{ name = 'uid_tab_pwd_enter';     keys = ($Account + "{TAB}" + $pwd + "{ENTER}") },
    @{ name = 'clear_tab_uid_tab_pwd_enter'; keys = ("{TAB}^a{DEL}" + $Account + "{TAB}^a{DEL}" + $pwd + "{ENTER}") },
    @{ name = 'tab2_uid_tab_pwd_enter'; keys = ("{TAB}{TAB}" + $Account + "{TAB}" + $pwd + "{ENTER}") },
    @{ name = 'uid_tab_tab_pwd_enter'; keys = ($Account + "{TAB}{TAB}" + $pwd + "{ENTER}") },
    @{ name = 'uid_tab_pwd_tab_enter'; keys = ($Account + "{TAB}" + $pwd + "{TAB}{ENTER}") }
  )
  foreach ($s in $seqs) {
    Log ("try " + $s.name)
    $ok = TrySequence $s.keys 8
    if ($ok) {
      $hit = @{ name = $s.name; keys = $s.keys; at = (Get-Date -Format 's') } | ConvertTo-Json -Compress
      try { Set-Content -Path (Join-Path $ipc 'login_seq.json') -Value $hit -Encoding UTF8 } catch { }
      Log ("HIT " + $s.name)
      return ("ok:" + $s.name)
    }
    Start-Sleep -Milliseconds 300
  }
  return 'no-sequence-matched'
}

'''
if anchor in s and 'function AutoLogin' not in s:
    s = s.replace(anchor, helpers + anchor, 1)

# 2) 在 switch 里加 autologin
s = s.replace("    'login' { $result = BlindLogin }",
              "    'login' { $result = BlindLogin }\n    'autologin' { $result = AutoLogin }\n    'net' { $result = (Get-NetTCPConnection -ErrorAction SilentlyContinue | Where-Object { $_.RemotePort -in @(1863,1864) -or $_.LocalPort -in @(1863,1864) } | Select-Object -First 10 | ForEach-Object { \"$($_.State) $($_.RemoteAddress):$($_.RemotePort)\" }) -join '; ' }")

io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
d = open(p, 'rb').read()
print('ascii', all(b < 0x80 for b in d), 'bytes', len(d), 'autologin', b"'autologin'" in d)