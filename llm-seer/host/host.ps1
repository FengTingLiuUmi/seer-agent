# 最小 Flash 宿主：WinForms + WebBrowser(IE) + Flash ActiveX
# 用法: powershell -File host.ps1 -Url http://127.0.0.1:8000/page.html
param(
  [string]$Url = 'http://127.0.0.1:8000/page.html',
  [int]$W = 1000,
  [int]$H = 680
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$form = New-Object System.Windows.Forms.Form
$form.Text = 'seer flash host'
$form.ClientSize = New-Object System.Drawing.Size($W, $H)
$form.StartPosition = 'CenterScreen'
$form.BackColor = [System.Drawing.Color]::Black

$wb = New-Object System.Windows.Forms.WebBrowser
$wb.Dock = 'Fill'
$wb.ScriptErrorsSuppressed = $true
$wb.IsWebBrowserContextMenuEnabled = $false
$wb.WebBrowserShortcutsEnabled = $false
$form.Controls.Add($wb)

# 让 IE 控件以 IE11 模式渲染（否则 Flash 不加载）——键名必须是宿主进程名
$feat = 'FEATURE_BROWSER_EMULATION'
$exes = @('powershell.exe', 'pwsh.exe', 'explorer.exe')
$key = "HKCU:\Software\Microsoft\Internet Explorer\Main\FeatureControl\$feat"
try {
  if (-not (Test-Path $key)) { New-Item -Path $key -Force | Out-Null }
  foreach ($e in $exes) {
    New-ItemProperty -Path $key -Name $e -Value 11001 -PropertyType DWord -Force | Out-Null
  }
} catch { Write-Host "reg warn: $($_.Exception.Message)" }

$wb.Navigate($Url)

$script:lastTitle = ''
$script:statusPath = Join-Path $PSScriptRoot '_status.txt'
$form.Add_Shown({
  $wb.Focus()
  $timer = New-Object System.Windows.Forms.Timer
  $timer.Interval = 1500
  $timer.Add_Tick({
    $lines = @()
    try { $lines += 'title=' + $wb.DocumentTitle } catch { $lines += 'title=ERR' }
    try { $lines += 'docLen=' + ($wb.Document.Body.InnerHtml).Length } catch { $lines += 'docLen=ERR' }
    try {
      $o = $wb.Document.getElementById('swf')
      $lines += 'swf=' + $(if ($o) { $o.GetType().Name } else { 'null' })
      $lines += 'callback=' + $(if ($o -and $o.startWebSessionLogin) { 'yes' } else { 'no' })
    } catch { $lines += 'swf=ERR ' + $_.Exception.Message }
    try { $lines += 'url=' + $wb.Url } catch { }
    try { $lines += 'readyState=' + $wb.ReadyState } catch { }
    $lines | Set-Content -Path $script:statusPath -Encoding UTF8
    $t = $wb.DocumentTitle
    if ($t -and $t -ne $script:lastTitle) {
      $script:lastTitle = $t
      Write-Host ("[{0}] title={1}" -f (Get-Date -Format 'HH:mm:ss'), $t)
    }
  })
  $timer.Start()
})

[void]$form.ShowDialog()