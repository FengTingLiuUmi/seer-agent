import io

p = 'llm-seer/host/host_play.ps1'
s = io.open(p, encoding='utf-8').read()

repl = {
    '# \u5bc6\u7801\uff1a\u4ece\u52a0\u5bc6\u51ed\u636e\u89e3\u51fa\uff0c\u4e0d\u843d\u76d8':
        '# password: read from encrypted credential into a temp file, deleted right after',
    '# 20 \u79d2\u540e\u5f00\u59cb\u76f2\u6ce8\u952e\u76d8\u767b\u5f55':
        '# after 20s: blind keyboard login',
    '# \u70b9\u4e00\u4e0b Flash \u533a\u57df\u4e2d\u5fc3\uff0c\u8ba9\u5b83\u62ff\u5230\u7126\u70b9\uff08\u5750\u6807\u76f2\u70b9\uff0c\u4e0d\u8bfb\u50cf\u7d20\uff09':
        '# click flash center to take focus (blind coordinates, no pixel reading)',
    '# \u5e8f\u5217 A\uff1aTab \u2192 \u8d26\u53f7 \u2192 Tab \u2192 \u5bc6\u7801 \u2192 Enter':
        '# sequence A: Tab -> account -> Tab -> password -> Enter',
}
for k, v in repl.items():
    s = s.replace(k, v)

old = "$pwd = ''\nPush-Location $seer\ntry { $pwd = (& node tools\\loadcred.mjs 2>$null | Out-String).Trim() } catch { }\nPop-Location"
new = ("$pwd = ''\n$tmp = Join-Path $seer '.pwd.tmp'\nPush-Location $seer\n"
       "try {\n  & node tools\\dumpcred.mjs '.pwd.tmp' $Account | Out-Null\n"
       "  if (Test-Path $tmp) { $pwd = (Get-Content $tmp -Raw).Trim() }\n} catch { }\n"
       "Pop-Location\ntry { Remove-Item $tmp -Force -ErrorAction SilentlyContinue } catch { }")
if old in s:
    s = s.replace(old, new)

io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
d = open(p, 'rb').read()
print('ascii', all(b < 0x80 for b in d), 'bytes', len(d), 'dumpcred', b'dumpcred.mjs' in d)