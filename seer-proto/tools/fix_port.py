import io, re

# 1) prep_pwd.mjs：把 gate 返回的端口单独写进 login.json
p = 'tools/prep_pwd.mjs'
s = io.open(p, encoding='utf-8').read()
if 'port:' not in s:
    s = s.replace("  host: g?.[1] ?? 'h5gy.61.com',",
                  "  host: g?.[1] ?? 'h5gy.61.com',\n  port: Number(g?.[3] ?? 443),")
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('prep port field:', 'port:' in s)

# 2) main.go：loginInfo 增加 Port，dialWS 使用端口
p = 'main.go'
s = io.open(p, encoding='utf-8').read()

if 'Port     int' not in s:
    s = s.replace('\tServerID uint16 `json:"serverId"`',
                  '\tServerID uint16 `json:"serverId"`\n\tPort     int    `json:"port"`')

if 'func dialWS(host, path string)' in s:
    s = s.replace('func dialWS(host, path string) (net.Conn, error) {',
                  'func dialWS(host string, port int, path string) (net.Conn, error) {')
    s = s.replace('\tconn, err := net.Dial("tcp", host+":443")',
                  '\tif port == 0 {\n\t\tport = 443\n\t}\n\tconn, err := net.Dial("tcp", fmt.Sprintf("%s:%d", host, port))')

# 调用点：game 连接用 info.Port；gate 连接保持 443
s = s.replace('game, err := dialWS(info.Host, info.Path)',
              'game, err := dialWS(info.Host, info.Port, info.Path)')
s = s.replace('gate, err := dialWS("seerh5login.61.com", "/login_gate_webgl")',
              'gate, err := dialWS("seerh5login.61.com", 443, "/login_gate_webgl")')

io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('main dialWS port:', 'dialWS(info.Host, info.Port, info.Path)' in s,
      '| struct:', 'Port     int' in s)