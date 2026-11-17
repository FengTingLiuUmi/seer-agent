import io

p = 'main.go'
s = io.open(p, encoding='utf-8').read()

if 'boot := flag.Bool' not in s:
    s = s.replace(
        'catchIDs := flag.String("catch", "", "要捕捉的野怪 id（逗号分隔），命中 2004 槽位后自动发 2408,slot")',
        'catchIDs := flag.String("catch", "", "要捕捉的野怪 id（逗号分隔），命中 2004 槽位后自动发 2408,slot")\n'
        '\tboot := flag.Bool("boot", false, "收到 S2C 1001 后立刻补发引导帧 1002/1016/42494（不等 2001）")')

anchor = '\t\tif cmd == 2004 && len(catchWant) > 0 {'
boot_code = '''\t\tif cmd == 1001 && *boot && !booted {
\t\t\tbooted = true
\t\t\tfor _, bc := range []struct {
\t\t\t\tcmd  uint32
\t\t\t\tbody []byte
\t\t\t}{{1002, nil}, {1016, []byte{0, 0, 0, 2}}, {42494, nil}} {
\t\t\t\tfb := frame(bc.cmd, info.UID, bc.body, &prev2)
\t\t\t\temitFrame("c2s", fb)
\t\t\t\twsSend(game, fb)
\t\t\t\tfmt.Printf("    >>> boot %d\\n", bc.cmd)
\t\t\t\ttime.Sleep(200 * time.Millisecond)
\t\t\t}
\t\t}

'''
if anchor in s and 'booted := false' not in s:
    s = s.replace(anchor, boot_code + anchor, 1)
    s = s.replace('\tacked := 0\n', '\tacked := 0\n\tbooted := false\n', 1)

io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('boot flag', 'boot := flag.Bool' in s, '| booted', 'booted := false' in s, '| code', '>>> boot' in s)