import io

p = 'llm-seer/host/host_play.ps1'
s = io.open(p, encoding='utf-8').read()

# 默认用本地页（file://，本地机器区）+ 远程 Client.swf —— 对齐雷小伊写法
old = "if (-not $PlayUrl -or $PlayUrl -notmatch '^https?://') { $PlayUrl = 'https://seer.61.com/play.shtml' }"
new = ("if (-not $PlayUrl -or $PlayUrl -notmatch '^(https?|file)://') {\n"
       "  $PlayUrl = 'file:///C:/Users/kmdbn/Documents/deepseek-harness/default-workspace/seer/llm-seer/host/site/local.html'\n"
       "}")
s = s.replace(old, new)

# URL 拼接：file:// 页面用 ?uid=&sid=&tmcid=76；http 页面保持 micro=1
old2 = "$url = '{0}?micro=1&uid={1}&sid={2}' -f $PlayUrl, $Account, $sid"
if old2 not in s:
    # 兼容之前的写法
    for cand in ["$url = '{0}?micro=1&uid={1}' -f $PlayUrl, $Account",
                 "$url = '{0}?sid={1}&uid={2}&from=we_seer' -f $PlayUrl, $sid, $uid",
                 "$url = '{0}?sid={1}&from=we_seer' -f $PlayUrl, $sid"]:
        if cand in s:
            old2 = cand
            break
new2 = ("if ($PlayUrl -match '^file://') {\n"
        "  $url = '{0}?uid={1}&sid={2}&tmcid=76' -f $PlayUrl, $Account, $sid\n"
        "} else {\n"
        "  $url = '{0}?micro=1&uid={1}&sid={2}' -f $PlayUrl, $Account, $sid\n"
        "}")
if old2 in s:
    s = s.replace(old2, new2, 1)

io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
d = open(p, 'rb').read()
print('ascii', all(b < 0x80 for b in d),
      'file default', b'site/local.html' in d,
      'url branch', b"^file://" in d)