import json, os, sys, ctypes, ctypes.wintypes as wt
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import flashctl

JS = ("JSON.stringify({focus:document.hasFocus(),"
      "active:(document.activeElement?document.activeElement.tagName+'#'+document.activeElement.id:null),"
      "vis:document.visibilityState,"
      "w:document.documentElement.clientWidth,h:document.documentElement.clientHeight})")
print('JS:', flashctl.post('/eval', {'code': JS}).get('result'))

u = ctypes.windll.user32
fg = u.GetForegroundWindow()
t = ctypes.create_unicode_buffer(256)
u.GetWindowTextW(fg, t, 256)
print('foreground:', fg, t.value[:40])
for hwnd, label in ((u.GetFocus(), 'focus'),):
    cls = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(hwnd, cls, 256)
    print(label, 'class:', cls.value)

# 列出 host 窗口及其子窗口类名（看 IE 控件是否真的在）
host = [w for w in __import__('visual_driver').list_windows('') if 'flash host' in w[1].lower()]
print('host windows:', [(h, t2[:24], w, hh) for h, t2, w, hh in host])
if host:
    kids = []
    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(h, l):
        c = ctypes.create_unicode_buffer(256)
        u.GetClassNameW(h, c, 256)
        r = wt.RECT(); u.GetWindowRect(h, ctypes.byref(r))
        kids.append((c.value, r.right - r.left, r.bottom - r.top))
        return True
    u.EnumChildWindows(host[0][0], cb, 0)
    for k in kids[:8]:
        print('  child', k)