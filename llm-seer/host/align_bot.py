import io

p = 'llm-seer/host/host_play.ps1'
s = io.open(p, encoding='utf-8').read()

# 1) 窗口尺寸对齐雷小伊的 IE 控件：996x700
s = s.replace('$form.ClientSize = New-Object System.Drawing.Size(960, 560)',
              '$form.ClientSize = New-Object System.Drawing.Size(996, 700)')

# 2) 导航完成后只做一件事：隐藏滚动条（不强制尺寸）
if 'DocumentCompleted' not in s:
    anchor = '$wb.Navigate([Uri]$url)'
    hook = """$wb.Navigate([Uri]$url)
$wb.Add_DocumentCompleted({
  param($sender, $ev)
  if ($ev.Url -notmatch 'play\\.shtml') { return }
  try { [void]$wb.Document.InvokeScript("eval", @("document.documentElement.style.overflow='hidden';document.body.style.overflow='hidden';document.body.style.margin='0';")) } catch { }
})"""
    s = s.replace(anchor, hook, 1)

io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
d = open(p, 'rb').read()
print('ascii', all(b < 0x80 for b in d), 'size996', b'996, 700' in d, 'hook', b'DocumentCompleted' in d)