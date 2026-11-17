import io

p = 'main.go'
s = io.open(p, encoding='utf-8').read()

# 1) 新增 -enter 参数："mapID,x,y"（对齐雷小伊 Send("2001,0,map,x,y")）
if 'enter := flag.String' not in s:
    s = s.replace(
        'boot := flag.Bool("boot", false, "收到 S2C 1001 后立刻补发引导帧 1002/1016/42494（不等 2001）")',
        'boot := flag.Bool("boot", false, "收到 S2C 1001 后立刻补发引导帧 1002/1016/42494（不等 2001）")\n'
        '\tenter := flag.String("enter", "", "收到 S2C 1001 后主动进图，格式 地图id,x,y（对齐雷小伊 Send(\\"2001,0,map,x,y\\")）")')

# 2) 在 1001 分支里追加：主动发 2001 进图
old_anchor = '''\t\tif cmd == 1001 && *boot && !booted {'''
enter_code = '''\t\tif cmd == 1001 && *enter != "" && !entered {
\t\t\tentered = true
\t\t\tparts := strings.Split(*enter, ",")
\t\t\tif len(parts) >= 1 {
\t\t\t\tm, _ := strconv.ParseUint(strings.TrimSpace(parts[0]), 10, 32)
\t\t\t\tx, y := uint64(0), uint64(0)
\t\t\t\tif len(parts) >= 3 {
\t\t\t\t\tx, _ = strconv.ParseUint(strings.TrimSpace(parts[1]), 10, 32)
\t\t\t\t\ty, _ = strconv.ParseUint(strings.TrimSpace(parts[2]), 10, 32)
\t\t\t\t}
\t\t\t\tbody := make([]byte, 16)
\t\t\t\tbinary.BigEndian.PutUint32(body[0:], 0)
\t\t\t\tbinary.BigEndian.PutUint32(body[4:], uint32(m))
\t\t\t\tbinary.BigEndian.PutUint32(body[8:], uint32(x))
\t\t\t\tbinary.BigEndian.PutUint32(body[12:], uint32(y))
\t\t\t\tfe := frame(2001, info.UID, body, &prev2)
\t\t\t\temitFrame("c2s", fe)
\t\t\t\twsSend(game, fe)
\t\t\t\tfmt.Printf("    >>> 主动进图 map=%d x=%d y=%d\\n", m, x, y)
\t\t\t}
\t\t}

'''
if 'entered := false' not in s:
    s = s.replace('\tbooted := false\n', '\tbooted := false\n\tentered := false\n', 1)
if old_anchor in s:
    s = s.replace(old_anchor, enter_code + old_anchor, 1)

io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('enter flag:', 'enter := flag.String' in s, '| code:', '主动进图' in s, '| entered:', 'entered := false' in s)