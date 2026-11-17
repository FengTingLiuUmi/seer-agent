#!/usr/bin/env python3
"""读进程内存（代替识图的第一条通道）：字符串扫描 / 数值扫描

用途：从 Flash/浏览器/客户端进程里直接读出"当前地图名、昵称、坐标、面板文本"，
不截图、不比模板。

用法:
  python mem_read.py procs [过滤词]                        # 列出进程
  python mem_read.py find <pid|名称> <文本> [--utf16]     # 找字符串，打印地址与上下文
  python mem_read.py scan <pid|名称> <整数> [--range 0-999999]
"""
import ctypes, ctypes.wintypes as wt, sys, struct, re

k32 = ctypes.windll.kernel32

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_READABLE = (0x02, 0x04, 0x20, 0x40, 0x80)  # RO / RW / EXEC_READ ...


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [('BaseAddress', ctypes.c_void_p), ('AllocationBase', ctypes.c_void_p),
                ('AllocationProtect', wt.DWORD), ('RegionSize', ctypes.c_size_t),
                ('State', wt.DWORD), ('Protect', wt.DWORD), ('Type', wt.DWORD)]


def procs(filt=''):
    out = []
    psapi = ctypes.windll.psapi
    arr = (wt.DWORD * 4096)()
    used = wt.DWORD()
    if not psapi.EnumProcesses(ctypes.byref(arr), ctypes.sizeof(arr), ctypes.byref(used)):
        return out
    n = used.value // ctypes.sizeof(wt.DWORD)
    for i in range(n):
        pid = arr[i]
        h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not h:
            continue
        buf = ctypes.create_unicode_buffer(260)
        size = wt.DWORD(260)
        if ctypes.windll.kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            name = buf.value
            if filt.lower() in name.lower():
                out.append((pid, name))
        k32.CloseHandle(h)
    return out


def resolve(target):
    try:
        return int(target, 0)
    except ValueError:
        pass
    lst = procs(target)
    if not lst:
        raise SystemExit('没有匹配的进程: %s' % target)
    print('匹配到 %d 个，用第一个: %s' % (len(lst), lst[0]))
    return lst[0][0]


def regions(h):
    addr = 0
    mbi = MEMORY_BASIC_INFORMATION()
    while k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        base, size, state, prot = mbi.BaseAddress or 0, mbi.RegionSize, mbi.State, mbi.Protect
        if state == MEM_COMMIT and (prot & 0xFF) in PAGE_READABLE and size < 512 * 1024 * 1024:
            yield base, size
        addr = base + size
        if addr <= base:
            break


def find(pid, needle, utf16=False):
    h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not h:
        raise SystemExit('OpenProcess 失败（权限/位数问题）pid=%d' % pid)
    pat = needle.encode('utf-16-le') if utf16 else needle.encode('utf-8')
    hits = []
    buf = ctypes.create_string_buffer(1 << 20)
    read = ctypes.c_size_t()
    for base, size in regions(h):
        off = 0
        while off < size:
            chunk = min(1 << 20, size - off)
            ok = k32.ReadProcessMemory(h, ctypes.c_void_p(base + off), buf, chunk, ctypes.byref(read))
            if ok and read.value:
                data = buf.raw[:read.value]
                start = 0
                while True:
                    i = data.find(pat, start)
                    if i < 0:
                        break
                    ctx = data[max(0, i - 24):i + len(pat) + 24]
                    hits.append((base + off + i, ctx))
                    start = i + 1
                    if len(hits) >= 20:
                        break
            off += chunk
        if len(hits) >= 20:
            break
    k32.CloseHandle(h)
    return hits


def main():
    try:
        sys.stdout.reconfigure(errors='replace')
    except Exception:
        pass
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == 'procs':
        for pid, name in procs(sys.argv[2] if len(sys.argv) > 2 else ''):
            print('%7d  %s' % (pid, name))
    elif cmd == 'find':
        pid = resolve(sys.argv[2])
        needle = sys.argv[3]
        utf16 = '--utf16' in sys.argv
        hits = find(pid, needle, utf16)
        print('hits:', len(hits))
        for addr, ctx in hits[:10]:
            print('  0x%016x  %r' % (addr, ctx))
    else:
        print(__doc__)


if __name__ == '__main__':
    main()