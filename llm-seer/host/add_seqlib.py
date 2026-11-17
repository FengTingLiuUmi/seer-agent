import io

p = 'llm-seer/host/host_play.ps1'
s = io.open(p, encoding='utf-8').read()

start = s.find('function AutoLogin() {')
end = s.find('function Invoke-Ipc(')
if start < 0 or end < 0 or end < start:
    raise SystemExit('anchors not found')

new_fn = r'''function AutoLogin() {
  # sequences come from ipc/seqlib.json if present (so we can iterate without restarting)
  $seqFile = Join-Path $ipc 'seqlib.json'
  $seqs = @()
  if (Test-Path $seqFile) {
    try {
      $arr = Get-Content $seqFile -Raw | ConvertFrom-Json
      foreach ($a in $arr) { $seqs += @{ name = [string]$a.name; keys = [string]$a.keys } }
    } catch { Log "seqlib parse fail" }
  }
  if ($seqs.Count -eq 0) {
    $seqs = @(
      @{ name = 'pw_tab_enter';   keys = ($pwd + "{TAB}{ENTER}") },
      @{ name = 'tab_pw_enter';   keys = ("{TAB}" + $pwd + "{ENTER}") },
      @{ name = 'tab2_pw_enter';  keys = ("{TAB}{TAB}" + $pwd + "{ENTER}") },
      @{ name = 'pw_enter';       keys = ($pwd + "{ENTER}") },
      @{ name = 'tab_pw_only';    keys = ("{TAB}" + $pwd) }
    )
  }
  foreach ($s2 in $seqs) {
    Log ("try " + $s2.name)
    $keys = $s2.keys
    $keys = $keys.Replace('{PWD}', $pwd).Replace('{UID}', $Account)
    $ok = TrySequence $keys 8
    if ($ok) {
      $hit = @{ name = $s2.name; keys = $keys; at = (Get-Date -Format 's') } | ConvertTo-Json -Compress
      try { Set-Content -Path (Join-Path $ipc 'login_seq.json') -Value $hit -Encoding UTF8 } catch { }
      Log ("HIT " + $s2.name)
      return ("ok:" + $s2.name)
    }
    Start-Sleep -Milliseconds 300
  }
  return 'no-sequence-matched'
}

'''
s = s[:start] + new_fn + s[end:]
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
d = open(p, 'rb').read()
print('ascii', all(b < 0x80 for b in d), 'bytes', len(d), 'seqlib', b'seqlib.json' in d)