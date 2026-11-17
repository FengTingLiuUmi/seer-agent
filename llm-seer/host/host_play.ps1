# seer Flash host: IE control -> https://seer.61.com/play.shtml?micro=1
# Adds a file-based IPC channel so an LLM/agent can drive the page:
#   llm-seer/ipc/cmd.json  -> executed -> llm-seer/ipc/resp.json
# ops: state | eval(code) | key(keys) | click(x,y) | nav(url) | login
# ASCII only (PowerShell 5.1 reads non-BOM UTF-8 as ANSI and mangles params)
param([string]$PlayUrl = '', [string]$Account = 'ACCOUNT', [switch]$AutoLogin)

$ErrorActionPreference = 'Continue'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$root = 'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace'
$seer = Join-Path $root 'seer-proto'
$ipc  = Join-Path $root 'llm-seer\ipc'
$log  = Join-Path $root 'llm-seer\host\host-play-log.txt'
try { Remove-Item $log -Force -ErrorAction SilentlyContinue } catch { }
try { New-Item -ItemType Directory -Force -Path $ipc | Out-Null } catch { }
$cmdFile  = Join-Path $ipc 'cmd.json'
$respFile = Join-Path $ipc 'resp.json'
$stateFile = Join-Path $ipc 'state.json'
try { Remove-Item $cmdFile,$respFile,$stateFile -Force -ErrorAction SilentlyContinue } catch { }

function Log($m) { try { Add-Content -Path $log -Value ("{0} {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) -Encoding UTF8 } catch { } }

if (-not $PlayUrl -or $PlayUrl -notmatch '^(https?|file)://') {
  $PlayUrl = 'file:///C:/Users/kmdbn/Documents/deepseek-harness/default-workspace/seer/llm-seer/host/site/local.html'
}

$pwd = ''
$tmp = Join-Path $seer '.pwd.tmp'
Push-Location $seer
try {
  & node tools\dumpcred.mjs '.pwd.tmp' $Account | Out-Null
  if (Test-Path $tmp) { $pwd = (Get-Content $tmp -Raw).Trim() }
} catch { }
Pop-Location
try { Remove-Item $tmp -Force -ErrorAction SilentlyContinue } catch { }

if ($PlayUrl -match '^file://') {
  $url = '{0}?uid={1}&sid={2}&tmcid=76' -f $PlayUrl, $Account, $sid
} else {
  $url = '{0}?micro=1&uid={1}&sid={2}' -f $PlayUrl, $Account, $sid
}
Log "url=$url"

$key = 'HKCU:\Software\Microsoft\Internet Explorer\Main\FeatureControl\FEATURE_BROWSER_EMULATION'
try {
  if (-not (Test-Path $key)) { New-Item -Path $key -Force | Out-Null }
  foreach ($e in @('powershell.exe','pwsh.exe')) {
    New-ItemProperty -Path $key -Name $e -Value 11001 -PropertyType DWord -Force | Out-Null
  }
} catch { }

$form = New-Object System.Windows.Forms.Form
$form.Text = 'seer flash host (micro=1)'
$form.ClientSize = New-Object System.Drawing.Size(996, 700)
$form.StartPosition = 'CenterScreen'
$wb = New-Object System.Windows.Forms.WebBrowser
$wb.Dock = 'Fill'
$wb.ScriptErrorsSuppressed = $true
$form.Controls.Add($wb)
$wb.Navigate([Uri]$url)
$wb.Add_DocumentCompleted({
  param($sender, $ev)
  if ($ev.Url -notmatch 'play\.shtml') { return }
  try { [void]$wb.Document.InvokeScript("eval", @("document.documentElement.style.overflow='hidden';document.body.style.overflow='hidden';document.body.style.margin='0';")) } catch { }
})

$probe = @"
(function(){
  var out={frames:[],flash:null,forAs:null,sid:null,err:null,title:document.title,url:location.href};
  function scan(win, path, depth){
    if(depth>3) return;
    try{
      var d=win.document;
      var o=d.querySelector('object[id],embed[id],object,embed');
      if(o && !out.flash){ out.flash={id:o.id,tag:o.tagName,pct:(o.PercentLoaded?o.PercentLoaded():-1)}; }
      var gp=win.gamePublic;
      if(gp && gp.forAs){
        if(!out.forAs) out.forAs=Object.keys(gp.forAs);
        try{ out.sid=String(gp.forAs.getSessionID()); }catch(e){}
      }
      for(var i=0;i<win.frames.length;i++){ out.frames.push(path+'/'+i); scan(win.frames[i], path+'/'+i, depth+1); }
    }catch(e){ if(!out.err) out.err=String(e.message); }
  }
  scan(window,'',0);
  return JSON.stringify(out);
})()
"@

function EvalJs([string]$code) {
  try { return $wb.Document.InvokeScript("eval", @($code)) } catch { return "ERR: $($_.Exception.Message)" }
}

function SendKeysSafe([string]$keys) {
  try {
    $form.Activate(); $wb.Focus()
    Start-Sleep -Milliseconds 150
    [System.Windows.Forms.SendKeys]::SendWait($keys)
    return 'ok'
  } catch { return "ERR: $($_.Exception.Message)" }
}

function ClickAt([int]$x, [int]$y) {
  try {
    Add-Type -MemberDefinition '[DllImport("user32.dll")] public static extern void mouse_event(uint f,uint dx,uint dy,uint d,int e);' -Name U2 -Namespace W2 -PassThru | Out-Null
    $pos = $form.PointToScreen((New-Object System.Drawing.Point($x, $y)))
    [System.Windows.Forms.Cursor]::Position = $pos
    Start-Sleep -Milliseconds 120
    [W2.U2]::mouse_event(0x0002, 0, 0, 0, 0)
    [W2.U2]::mouse_event(0x0004, 0, 0, 0, 0)
    return 'ok'
  } catch { return "ERR: $($_.Exception.Message)" }
}

$script:flashHwnd = [IntPtr]::Zero

function FindFlashHwnd() {
  if ($script:flashHwnd -ne [IntPtr]::Zero -and $script:flashHwnd -ne $null) { return $script:flashHwnd }
  if (-not ('W3.Enum' -as [type])) {
    Add-Type -Namespace W3 -Name Enum -MemberDefinition @"
[DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
public delegate bool EnumProc(IntPtr h, IntPtr l);
[DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassNameW(IntPtr h, System.Text.StringBuilder sb, int n);
[DllImport("user32.dll")] public static extern IntPtr PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
"@
  }
  $found = [IntPtr]::Zero
  $cb = [W3.Enum+EnumProc]{
    param($h, $l)
    $sb = New-Object System.Text.StringBuilder 256
    [void][W3.Enum]::GetClassNameW($h, $sb, 256)
    $cls = $sb.ToString()
    if ($cls -match 'Flash|Shockwave') { $script:flashHwnd = $h; }
    return $true
  }
  [void][W3.Enum]::EnumChildWindows($form.Handle, $cb, [IntPtr]::Zero)
  return $script:flashHwnd
}

function SendMsgKeys([string]$keys) {
  $h = FindFlashHwnd
  if ($h -eq [IntPtr]::Zero) { return $false }
  $WM_CHAR = 0x0102; $WM_KEYDOWN = 0x0100; $WM_KEYUP = 0x0101
  $i = 0
  while ($i -lt $keys.Length) {
    if ($keys[$i] -eq '{') {
      $j = $keys.IndexOf('}', $i)
      if ($j -gt $i) {
        $tok = $keys.Substring($i + 1, $j - $i - 1).ToUpper()
        if ($tok -eq 'TAB') {
          [void][W3.Enum]::PostMessage($h, $WM_KEYDOWN, [IntPtr]0x09, [IntPtr]0)
          [void][W3.Enum]::PostMessage($h, $WM_KEYUP, [IntPtr]0x09, [IntPtr]0)
        } elseif ($tok -eq 'ENTER') {
          [void][W3.Enum]::PostMessage($h, $WM_KEYDOWN, [IntPtr]0x0D, [IntPtr]0)
          [void][W3.Enum]::PostMessage($h, $WM_KEYUP, [IntPtr]0x0D, [IntPtr]0)
        } elseif ($tok -eq 'DEL') {
          [void][W3.Enum]::PostMessage($h, $WM_KEYDOWN, [IntPtr]0x2E, [IntPtr]0)
          [void][W3.Enum]::PostMessage($h, $WM_KEYUP, [IntPtr]0x2E, [IntPtr]0)
        }
        Start-Sleep -Milliseconds 60
        $i = $j + 1
        continue
      }
    }
    [void][W3.Enum]::PostMessage($h, $WM_CHAR, [IntPtr][int]$keys[$i], [IntPtr]0)
    Start-Sleep -Milliseconds 40
    $i++
  }
  return $true
}

function BlindLogin() {
  ClickAt 512 330 | Out-Null
  Start-Sleep -Milliseconds 500
  SendKeysSafe("{TAB}") | Out-Null
  Start-Sleep -Milliseconds 200
  SendKeysSafe($Account) | Out-Null
  Start-Sleep -Milliseconds 200
  SendKeysSafe("{TAB}") | Out-Null
  Start-Sleep -Milliseconds 200
  if ($pwd) { SendKeysSafe($pwd) | Out-Null }
  Start-Sleep -Milliseconds 200
  SendKeysSafe("{ENTER}") | Out-Null
  return 'login-keys-sent'
}

function GameConnected() {
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
  $sent = $false
  try { $sent = SendMsgKeys $keys } catch { $sent = $false }
  if (-not $sent) { SendKeysSafe($keys) | Out-Null; Log "keys via SendKeys" } else { Log "keys via PostMessage" }
  return (WaitGame $waitSec)
}

function AutoLogin() {
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

function Invoke-Ipc([string]$raw) {
  $req = $null
  try { $req = $raw | ConvertFrom-Json } catch { return (@{ ok = $false; error = 'bad json' } | ConvertTo-Json -Compress) }
  $op = [string]$req.op
  $result = $null
  switch ($op) {
    'state' { $result = EvalJs $probe }
    'eval'  { $result = EvalJs ([string]$req.code) }
    'key'   { $result = SendKeysSafe ([string]$req.keys) }
    'click' { $result = ClickAt ([int]$req.x) ([int]$req.y) }
    'nav'   { try { $wb.Navigate([Uri]([string]$req.url)); $result = 'ok' } catch { $result = "ERR: $($_.Exception.Message)" } }
    'login' { $result = BlindLogin }
    'autologin' { $result = AutoLogin }
    'net' { $result = (Get-NetTCPConnection -ErrorAction SilentlyContinue | Where-Object { $_.RemotePort -in @(1863,1864) -or $_.LocalPort -in @(1863,1864) } | Select-Object -First 10 | ForEach-Object { "$($_.State) $($_.RemoteAddress):$($_.RemotePort)" }) -join '; ' }
    default { $result = "unknown op: $op" }
  }
  return (@{ id = $req.id; op = $op; ok = $true; result = $result } | ConvertTo-Json -Depth 6 -Compress)
}

# timers at script scope (avoid "cannot call method on null")
$script:timerPoll = New-Object System.Windows.Forms.Timer
$script:timerPoll.Interval = 250
$script:timerState = New-Object System.Windows.Forms.Timer
$script:timerState.Interval = 3000

$form.Add_Shown({
  $script:timerPoll.Add_Tick({
    if (-not (Test-Path $cmdFile)) { return }
    $raw = $null
    try { $raw = Get-Content $cmdFile -Raw -ErrorAction Stop } catch { return }
    try { Remove-Item $cmdFile -Force -ErrorAction SilentlyContinue } catch { }
    if (-not $raw) { return }
    $resp = Invoke-Ipc $raw
    try { Set-Content -Path $respFile -Value $resp -Encoding UTF8 } catch { }
    Log "ipc: $resp"
  })
  $script:timerPoll.Start()

  $script:timerState.Add_Tick({
    try { Set-Content -Path $stateFile -Value (EvalJs $probe) -Encoding UTF8 } catch { }
  })
  $script:timerState.Start()

  # auto blind-login only when -AutoLogin is passed explicitly
  if ($AutoLogin) {
    $script:timerLogin = New-Object System.Windows.Forms.Timer
    $script:timerLogin.Interval = 20000
    $script:timerLogin.Add_Tick({
      $script:timerLogin.Stop()
      try { Log ("auto " + (BlindLogin)) } catch { Log "auto login ERR $($_.Exception.Message)" }
    })
    $script:timerLogin.Start()
  }
})

[void]$form.ShowDialog()