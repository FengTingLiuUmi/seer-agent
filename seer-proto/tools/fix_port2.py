import io

p = 'main.go'
s = io.open(p, encoding='utf-8').read()

# 1) 调用点改为 dialGame
s = s.replace('game, err := dialWS(info.Host, 443, info.Path)',
              'game, err := dialGame(info.Host, info.Port, info.Path)')

# 2) 新增 dialGame（端口优先，失败回退 443）
if 'func dialGame(' not in s:
    helper = '''// dialGame：gate 返回的 serverId 同时当作端口试一次，失败回退 443
func dialGame(host string, port int, path string) (net.Conn, error) {
	if port != 0 && port != 443 {
		if c, err := dialWS(host, port, path); err == nil {
			fmt.Printf("    [ok] 使用端口 %d\\n", port)
			return c, nil
		} else {
			fmt.Printf("    [warn] 端口 %d 失败，回退 443: %v\\n", port, err)
		}
	}
	return dialWS(host, 443, path)
}

'''
    s = s.replace('func dialWS(host string, port int, path string) (net.Conn, error) {',
                  helper + 'func dialWS(host string, port int, path string) (net.Conn, error) {')

io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('dialGame:', 'func dialGame(' in s, '| call:', 'dialGame(info.Host, info.Port, info.Path)' in s)