#!/usr/bin/env python3
"""极简"看图操作"驱动（Flash/Unity 客户端通用）：列举窗口 / 截图 / 模板匹配 / 点击。

不依赖大漠(dm.dll) 与 COM，只用 ctypes + PIL + numpy，普通权限即可。

用法:
  python visual_driver.py list [过滤词]
  python visual_driver.py capture <hwnd|标题> out.png
  python visual_driver.py find <hwnd|标题> tpl.png [阈值=0.85]
  python visual_driver.py click <hwnd|标题> <x> <y>            # 窗口客户区坐标
  python visual_driver.py clicktpl <hwnd|标题> tpl.png [阈值]   # 找到就点中心
"""
import ctypes, ctypes.wintypes as wt, sys, os
import numpy as np
from PIL import Image

u32 = ctypes.windll.user32
g32 = ctypes.windll.gdi32

SW_RESTORE = 9
PW_CLIENTONLY = 1
PW_RENDERFULLCONTENT = 2


def list_windows(filt=''):
    out = []
    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(h, l):
        if not u32.IsWindowVisible(h):
            return True
        n = u32.GetWindowTextLengthW(h)
        if n == 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        u32.GetWindowTextW(h, buf, n + 1)
        title = buf.value
        if filt.lower() in title.lower():
            r = wt.RECT()
            u32.GetWindowRect(h, ctypes.byref(r))
            out.append((h, title, r.right - r.left, r.bottom - r.top))
        return True
    u32.EnumWindows(cb, 0)
    return out


def resolve(target):
    """hwnd 或标题子串 → hwnd"""
    try:
        h = int(target, 0)
        if u32.IsWindow(h):
            return h
    except ValueError:
        pass
    for h, title, w, hh in list_windows(target):
        return h
    raise SystemExit('找不到窗口: %s' % target)


def client_rect(h):
    r = wt.RECT()
    u32.GetClientRect(h, ctypes.byref(r))
    p = wt.POINT(0, 0)
    u32.ClientToScreen(h, ctypes.byref(p))
    return p.x, p.y, r.right, r.bottom


def capture(h):
    """PrintWindow 抓窗口客户区（可抓后台窗口）"""
    u32.SetForegroundWindow(h)
    x, y, w, hgt = client_rect(h)
    hdc = u32.GetDC(h)
    mdc = g32.CreateCompatibleDC(hdc)
    bmp = g32.CreateCompatibleBitmap(hdc, w, hgt)
    g32.SelectObject(mdc, bmp)
    ok = u32.PrintWindow(h, mdc, PW_CLIENTONLY | PW_RENDERFULLCONTENT)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [('biSize', wt.DWORD), ('biWidth', wt.LONG), ('biHeight', wt.LONG),
                    ('biPlanes', wt.WORD), ('biBitCount', wt.WORD), ('biCompression', wt.DWORD),
                    ('biSizeImage', wt.DWORD), ('biXPelsPerMeter', wt.LONG),
                    ('biYPelsPerMeter', wt.LONG), ('biClrUsed', wt.DWORD), ('biClrImportant', wt.DWORD)]

    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth, bi.biHeight = w, -hgt
    bi.biPlanes, bi.biBitCount = 1, 32
    buf = ctypes.create_string_buffer(w * hgt * 4)
    g32.GetDIBits(mdc, bmp, 0, hgt, buf, ctypes.byref(bi), 0)
    g32.DeleteObject(bmp)
    g32.DeleteDC(mdc)
    u32.ReleaseDC(h, hdc)
    if not ok:
        # 兜底：屏幕截取
        from PIL import ImageGrab
        return ImageGrab.grab(bbox=(x, y, x + w, y + hgt)).convert('RGB')
    arr = np.frombuffer(buf, dtype=np.uint8).reshape(hgt, w, 4)[:, :, [2, 1, 0]]
    return Image.fromarray(arr, 'RGB')


def ncc_find(img, tpl, thresh=0.85):
    """归一化互相关模板匹配（灰度, 暴力, 适合小模板）"""
    a = np.asarray(img.convert('L'), dtype=np.float32)
    t = np.asarray(tpl.convert('L'), dtype=np.float32)
    if t.shape[0] > a.shape[0] or t.shape[1] > a.shape[1]:
        return None, 0.0
    tm, am = t.mean(), None
    t0 = t - tm
    tn = np.sqrt((t0 ** 2).sum())
    best, bestval = None, -1.0
    step = 1
    H, W = a.shape
    th, tw = t.shape
    t0f = t0
    for yy in range(0, H - th + 1, step):
        for xx in range(0, W - tw + 1, step):
            w = a[yy:yy + th, xx:xx + tw]
            w0 = w - w.mean()
            d = np.sqrt((w0 ** 2).sum()) * tn
            if d <= 0:
                continue
            v = float((w0 * t0f).sum() / d)
            if v > bestval:
                bestval, best = v, (xx + tw // 2, yy + th // 2)
                if v > 0.995:
                    return best, v
    return (best if bestval >= thresh else None), bestval


def click(h, cx, cy):
    u32.SetForegroundWindow(h)
    bx, by, _, _ = client_rect(h)
    u32.SetCursorPos(bx + cx, by + cy)
    u32.mouse_event(0x0002, 0, 0, 0, 0)   # LEFTDOWN
    u32.mouse_event(0x0004, 0, 0, 0, 0)   # LEFTUP


def main():
    try:
        sys.stdout.reconfigure(errors='replace')   # 中文标题在 GBK 控制台不炸
    except Exception:
        pass
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == 'list':
        filt = sys.argv[2] if len(sys.argv) > 2 else ''
        for h, title, w, hh in list_windows(filt):
            print('%8d  %-4dx%-4d  %s' % (h, w, hh, title))
    elif cmd == 'capture':
        h = resolve(sys.argv[2])
        img = capture(h)
        img.save(sys.argv[3])
        print('saved', sys.argv[3], img.size)
    elif cmd == 'find':
        h = resolve(sys.argv[2])
        tpl = Image.open(sys.argv[3])
        th = float(sys.argv[4]) if len(sys.argv) > 4 else 0.85
        pos, score = ncc_find(capture(h), tpl, th)
        print('found' if pos else 'not found', pos, 'score=%.3f' % score)
    elif cmd == 'click':
        h = resolve(sys.argv[2])
        click(h, int(sys.argv[3]), int(sys.argv[4]))
        print('clicked', sys.argv[3], sys.argv[4])
    elif cmd == 'clicktpl':
        h = resolve(sys.argv[2])
        tpl = Image.open(sys.argv[3])
        th = float(sys.argv[4]) if len(sys.argv) > 4 else 0.85
        pos, score = ncc_find(capture(h), tpl, th)
        print('score=%.3f' % score, pos)
        if pos:
            click(h, pos[0], pos[1])
            print('clicked', pos)
    else:
        print(__doc__)


if __name__ == '__main__':
    main()