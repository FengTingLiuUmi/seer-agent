#!/usr/bin/env python3
"""从反编译 AS3 里抽取 SocketConnection.send(CommandID.X, ...) 调用表

输出: docs/COMMANDS.md（命令 → 参数表达式 → 出处）+ tools/cmd_send_table.json
"""
import json, os, re, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(ROOT)  # workspace root
DIRS = [os.path.join(WS, 'llm-seer', 'patch', d) for d in ('core_dec_as', 'app_as', 'app2_as', 'login_as')]

# 1) 读 CommandID 常量表
names = {}
cid = os.path.join(WS, 'llm-seer', 'patch', 'core_dec_as', 'scripts', 'com', 'robot', 'core', 'CommandID.as')
if os.path.exists(cid):
    for m in re.finditer(r'const\s+(\w+)\s*:\s*uint\s*=\s*(\d+)\s*;', open(cid, encoding='utf-8', errors='replace').read()):
        names[m.group(1)] = int(m.group(2))

send_re = re.compile(r'SocketConnection\.send\(\s*CommandID\.(\w+)\s*((?:,\s*[^;]*?)?)\)\s*;')
rows = []
for d in DIRS:
    for dp, _, fns in os.walk(d):
        for fn in fns:
            if not fn.endswith('.as'):
                continue
            p = os.path.join(dp, fn)
            try:
                txt = open(p, encoding='utf-8', errors='replace').read()
            except Exception:
                continue
            for ln, line in enumerate(txt.splitlines(), 1):
                for m in send_re.finditer(line):
                    const = m.group(1)
                    args = (m.group(2) or '').strip().lstrip(',').strip()
                    rows.append({'cmd': names.get(const, 0), 'const': const, 'args': args,
                                 'file': os.path.relpath(p, WS).replace('\\', '/'), 'line': ln})
                # 允许跨行：单独匹配行首的 send(...)
                if '.send(' in line and 'CommandID.' in line and not send_re.search(line):
                    m2 = re.search(r'\.send\(\s*CommandID\.(\w+)', line)
                    if m2:
                        rows.append({'cmd': names.get(m2.group(1), 0), 'const': m2.group(1),
                                     'args': '(跨行,需人工看)', 'file': os.path.relpath(p, WS).replace('\\', '/'), 'line': ln})

# 去重
seen = set()
uniq = []
for r in rows:
    key = (r['cmd'], r['args'], r['file'], r['line'])
    if key in seen:
        continue
    seen.add(key)
    uniq.append(r)
uniq.sort(key=lambda r: (r['cmd'], r['file'], r['line']))

os.makedirs(os.path.join(ROOT, 'docs'), exist_ok=True)
json.dump(uniq, open(os.path.join(ROOT, 'tools', 'cmd_send_table.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

by_cmd = collections.defaultdict(list)
for r in uniq:
    by_cmd[r['cmd']].append(r)

focus = [2414, 2415, 2416, 2411, 2483, 2486, 1021, 2409, 9756, 2169, 2021]
lines = ['# 命令发送表（从反编译 AS3 提取）', '',
         '来源：`SocketConnection.send(CommandID.X, args…)`，args 为 AS3 实参表达式；body 编码规则见 PROBES.md（若干 u32 大端）。', '',
         '## 重点关注', '']
for c in focus:
    if c not in by_cmd:
        continue
    lines.append('### %d %s' % (c, by_cmd[c][0]['const']))
    for r in by_cmd[c][:6]:
        lines.append('- `%s`  ← `%s:%d`' % (r['args'] or '(无参)', r['file'], r['line']))
    lines.append('')
lines += ['## 全部（按 cmd 排序）', '', '| cmd | 常量 | 参数 | 出处 |', '|---|---|---|---|']
for r in uniq[:400]:
    lines.append('| %d | %s | `%s` | %s:%d |' % (r['cmd'], r['const'], (r['args'] or '')[:70], os.path.basename(r['file']), r['line']))

open(os.path.join(ROOT, 'docs', 'COMMANDS.md'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
print('calls', len(uniq), 'unique cmds', len(by_cmd))
for c in focus:
    print('  cmd %-6d sites %d  %s' % (c, len(by_cmd.get(c, [])), by_cmd[c][0]['const'] if c in by_cmd else 'NOT-FOUND'))