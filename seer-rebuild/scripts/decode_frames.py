"""分析已抓真实战斗帧：归纳 2503/2504/2505 的字段偏移。"""
import re
import struct

def load_diag(path):
    raw = open(path, 'rb').read()
    try:
        return raw.decode('utf-16')
    except UnicodeDecodeError:
        return raw.decode('utf-8', errors='replace')

def frames_from(text):
    out = []
    for ln in text.splitlines():
        m = re.search(r'cmd=(\d+) result=(\S+) len=(\d+) body=([0-9a-f]+)', ln)
        if m:
            out.append((int(m.group(1)), int(m.group(3), 16) if False else int(m.group(3)), m.group(4)))
    return out

def u32(b, off):
    return struct.unpack_from('>I', b, off)[0] if len(b) >= off + 4 else None

def in_catch_range(v):
    return 0x54000000 <= v <= 0x6C000000

text = load_diag(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\stage5_diag.txt")

# 只收集每个 cmd 的第一个 body 各一帧做样本
seen = set()
samples = {}
for cmd, ln, body_hex in frames_from(text):
    if cmd in seen:
        continue
    if cmd not in (2503, 2504, 2505, 2506):
        continue
    seen.add(cmd)
    samples[cmd] = bytes.fromhex(body_hex)

for cmd in (2503, 2504, 2505, 2506):
    b = samples.get(cmd)
    if not b:
        print(f"== cmd {cmd}: 无样本 ==")
        continue
    print(f"== cmd {cmd} len={len(b)} ==")
    if cmd == 2504:
        # 找 catch_time（unix范围）及其后 8~12 字节的 HP
        for off in range(0, len(b) - 3):
            v = u32(b, off)
            if v is None or not in_catch_range(v):
                continue
            hp1 = u32(b, off + 4)
            hp2 = u32(b, off + 8)
            hp3 = u32(b, off + 12)
            print(f"  catch@0x{off:04x}=0x{v:08x}  +4={hp1} +8={hp2} +12={hp3}")
        # 敌方 species 1364 附近
        for off in range(0, len(b) - 3):
            v = u32(b, off)
            if v == 0x1364:
                print(f"  敌方species@0x{off:04x}; +4={u32(b,off+4)} +8={u32(b,off+8)} +12={u32(b,off+12)} +16={u32(b,off+16)} +20={u32(b,off+20)}")
    if cmd in (2505, 2504):
        # 头部字段
        print(f"  hdr: uid={hex(u32(b,0) or 0)} skill={u32(b,4)} seq={u32(b,8)} catch={hex(u32(b,0xc) or 0)} a@0x14={u32(b,0x14)} dmg@0x18={u32(b,0x18)}")