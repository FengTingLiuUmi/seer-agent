import ctypes, ctypes.wintypes as wt

u = ctypes.windll.user32
order = []
@ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
def cb(h, l):
    if not u.IsWindowVisible(h):
        return True
    t = ctypes.create_unicode_buffer(256); u.GetWindowTextW(h, t, 256)
    if not t.value:
        return True
    cls = ctypes.create_unicode_buffer(256); u.GetClassNameW(h, cls, 256)
    if 'WTWindow' in cls.value or 'WindowsForms10' in cls.value:
        r = wt.RECT(); u.GetWindowRect(h, ctypes.byref(r))
        order.append((h, cls.value[:28], t.value[:28], r.left, r.top, r.right - r.left, r.bottom - r.top))
    return True
u.EnumWindows(cb, 0)
print('z-order (top first):')
for o in order:
    print('  ', o)
print('foreground:', u.GetForegroundWindow())