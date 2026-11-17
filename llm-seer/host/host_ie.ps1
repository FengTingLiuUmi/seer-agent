# seer Flash 宿主（IE + Flash OCX），对齐雷小伊的载体方式
# 用法: powershell -ExecutionPolicy Bypass -File host_ie.ps1
param([string]$Base = 'http://127.0.0.1:8001')

$ErrorActionPreference = 'Continue'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$root = 'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace'
$seer = Join-Path $root 'seer-proto'

# 1) 取新 session（密码来自加密凭据，不需要环境变量）
Push-Location $seer
try { node tools\prep_pwd.mjs | Out-Null } catch { }
Pop-Location

$uid = ''; $sid = ''
try {
  $j = Get-Content (Join-Path $seer 'login.json') -Raw | ConvertFrom-Json
  $uid = [string]$j.uid
  $sid = $uid + $j.sessionHex
} catch { }

# 2) IE 控件必须以 IE11 模式跑，否则 Flash 不加载
$key = 'HKCU:\Software\Microsoft\Internet Explorer\Main\FeatureControl\FEATURE_BROWSER_EMULATION'
try {
  if (-not (Test-Path $key)) { New-Item -Path $key -Force | Out-Null }
  foreach ($e in @('powershell.exe','pwsh.exe')) {
    New-ItemProperty -Path $key -Name $e -Value 11001 -PropertyType DWord -Force | Out-Null
  }
} catch { Write-Host "[warn] 注册表写入失败（可能不影响）: $($_.Exception.Message)" }

$url = '{0}/ie.html?uid={1}&sid={2}&tmcid=76' -f $Base, $uid, $sid
Write-Host "[host] $url"

# 3) 窗口 + IE 控件
$form = New-Object System.Windows.Forms.Form
$form.Text = 'seer flash host (IE)'
$form.ClientSize = New-Object System.Drawing.Size(1016, 700)
$form.StartPosition = 'CenterScreen'
$wb = New-Object System.Windows.Forms.WebBrowser
$wb.Dock = 'Fill'
$wb.ScriptErrorsSuppressed = $true
$wb.IsWebBrowserContextMenuEnabled = $false
$wb.WebBrowserShortcutsEnabled = $false
$form.Controls.Add($wb)

$log = Join-Path $root 'llm-seer\host\host-ie-log.txt'
try { Remove-Item $log -Force } catch { }
function Log($m) { try { Add-Content -Path $log -Value ("{0} {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) -Encoding UTF8 } catch { } }

$wb.Navigate($url)

$script:lastTitle = ''
$form.Add_Shown({
  $wb.Focus()
  $t = New-Object System.Windows.Forms.Timer
  $t.Interval = 2000
  $t.Add_Tick({
    try {
      $title = $wb.DocumentTitle
      $has = $false; $pct = -1
      try {
        $o = $wb.Document.getElementById('client')
        if ($o) { $has = [bool]$o.startWebSessionLogin }
        $pct = $wb.Document.InvokeScript("eval", @("(function(){var e=document.getElementById('client');return e&&e.PercentLoaded?e.PercentLoaded():-1})()"))
      } catch { }
      Log ("title={0} cb={1} pct={2}" -f $title, $has, $pct)
      if ($title -and $title -ne $script:lastTitle) { $script:lastTitle = $title; Write-Host "[state] title=$title cb=$has" }
    } catch { }
  })
  $t.Start()
})

[void]$form.ShowDialog()