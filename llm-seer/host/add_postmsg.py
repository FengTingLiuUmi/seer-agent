import io

p = 'llm-seer/host/host_play.ps1'
s = io.open(p, encoding='utf-8').read()

# 1) 在 ClickAt 之后插入：找 Flash 子窗口 + PostMessage 发键
anchor = 'function BlindLogin() {'
helper = r'''$script:flashHwnd = [IntPtr]::Zero

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

'''
if 'function SendMsgKeys' not in s and anchor in s:
    s = s.replace(anchor, helper + anchor, 1)

# 2) TrySequence 优先用 PostMessage，失败再退回 SendKeys
s = s.replace(
"""  ClickAt 512 330 | Out-Null
  Start-Sleep -Milliseconds 400
  SendKeysSafe($keys) | Out-Null
  return (WaitGame $waitSec)""",
"""  ClickAt 512 330 | Out-Null
  Start-Sleep -Milliseconds 400
  $sent = $false
  try { $sent = SendMsgKeys $keys } catch { $sent = $false }
  if (-not $sent) { SendKeysSafe($keys) | Out-Null; Log "keys via SendKeys" } else { Log "keys via PostMessage" }
  return (WaitGame $waitSec)""")

io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
d = open(p, 'rb').read()
print('ascii', all(b < 0x80 for b in d), 'bytes', len(d), 'SendMsgKeys', b'function SendMsgKeys' in d)