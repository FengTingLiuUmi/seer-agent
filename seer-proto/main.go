// seerproto：复刻客户端（uTLS 指纹 + 17B 协议 + login_gate + 游戏网关）
// 用法：seerproto.exe -info login.json
package main

import (
	"bufio"
	"crypto/rand"
	"encoding/base64"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net"
	"os"
	"strconv"
	"strings"
	"time"

	utls "github.com/refraction-networking/utls"
)

type loginInfo struct {
	UID      uint32 `json:"uid"`
	Session  string `json:"sessionHex"`
	Host     string `json:"host"`
	Path     string `json:"path"`
	BodyB64  string `json:"bodyB64"`
	ServerID uint16 `json:"serverId"`
	Port     int    `json:"port"`
}

var cipherSuites = []uint16{
	49196, 49195, 49200, 49199, 49188, 49187, 49192, 49191,
	49162, 49161, 49172, 49171, 157, 156, 61, 60, 53, 47,
}

func helloSpec() *utls.ClientHelloSpec {
	return &utls.ClientHelloSpec{
		CipherSuites:       cipherSuites,
		CompressionMethods: []byte{0},
		Extensions: []utls.TLSExtension{
			&utls.SNIExtension{},
			&utls.StatusRequestExtension{},
			&utls.SupportedCurvesExtension{Curves: []utls.CurveID{utls.X25519, utls.CurveP256, utls.CurveP384}},
			&utls.SupportedPointsExtension{SupportedPoints: []byte{0}},
			&utls.SignatureAlgorithmsExtension{SupportedSignatureAlgorithms: []utls.SignatureScheme{
				utls.ECDSAWithP256AndSHA256, utls.PSSWithSHA256, utls.PKCS1WithSHA256,
				utls.ECDSAWithP384AndSHA384, utls.PSSWithSHA384, utls.PKCS1WithSHA384,
				utls.PSSWithSHA512, utls.PKCS1WithSHA512, utls.PKCS1WithSHA1,
			}},
			&utls.SessionTicketExtension{},
			&utls.ExtendedMasterSecretExtension{},
			&utls.RenegotiationInfoExtension{Renegotiation: utls.RenegotiateOnceAsClient},
		},
	}
}

func frame(cmd uint32, uid uint32, body []byte, prev *int32) []byte {
	total := 17 + len(body)
	out := make([]byte, total)
	binary.BigEndian.PutUint32(out[0:], uint32(total))
	out[4] = 0x31
	binary.BigEndian.PutUint32(out[5:], cmd)
	binary.BigEndian.PutUint32(out[9:], uid)
	if cmd > 1000 {
		var s byte
		for _, b := range body {
			s ^= b
		}
		v := *prev - *prev/3 + 113 + int32(len(body)%17) + int32(cmd%23) + int32(s) + 7
		*prev = v
		binary.BigEndian.PutUint32(out[13:], uint32(v))
	}
	copy(out[17:], body)
	return out
}

// dialGame：gate 返回的 serverId 同时当作端口试一次，失败回退 443
func dialGame(host string, port int, path string) (net.Conn, error) {
	if port != 0 && port != 443 {
		if c, err := dialWS(host, port, path); err == nil {
			fmt.Printf("    [ok] 使用端口 %d\n", port)
			return c, nil
		} else {
			fmt.Printf("    [warn] 端口 %d 失败，回退 443: %v\n", port, err)
		}
	}
	return dialWS(host, 443, path)
}

func dialWS(host string, port int, path string) (net.Conn, error) {
	if port == 0 {
		port = 443
	}
	conn, err := net.Dial("tcp", fmt.Sprintf("%s:%d", host, port))
	if err != nil {
		return nil, err
	}
	u := utls.UClient(conn, &utls.Config{ServerName: host}, utls.HelloCustom)
	if err := u.ApplyPreset(helloSpec()); err != nil {
		return nil, err
	}
	if err := u.Handshake(); err != nil {
		return nil, err
	}
	key := make([]byte, 16)
	rand.Read(key)
	req := fmt.Sprintf("GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\nOrigin: https://h5-seer.61.com\r\nUser-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0\r\n\r\n", path, host, base64.StdEncoding.EncodeToString(key))
	if _, err := io.WriteString(u, req); err != nil {
		return nil, err
	}
	br := bufio.NewReader(u)
	line, err := br.ReadString('\n')
	if err != nil {
		return nil, err
	}
	if indexOf(line, "101") < 0 {
		return nil, fmt.Errorf("handshake rejected: %s", line)
	}
	for {
		l, err := br.ReadString('\n')
		if err != nil {
			return nil, err
		}
		if l == "\r\n" {
			break
		}
	}
	return u, nil
}

func indexOf(s, sub string) int {
	for i := 0; i+len(sub) <= len(s); i++ {
		if s[i:i+len(sub)] == sub {
			return i
		}
	}
	return -1
}

func wsSend(conn net.Conn, payload []byte) error {
	n := len(payload)
	var hdr []byte
	if n < 126 {
		hdr = []byte{0x82, byte(0x80 | n)}
	} else if n < 65536 {
		hdr = []byte{0x82, 0x80 | 126, byte(n >> 8), byte(n)}
	} else {
		hdr = []byte{0x82, 0x80 | 127, 0, 0, 0, 0, byte(n >> 24), byte(n >> 16), byte(n >> 8), byte(n)}
	}
	mask := make([]byte, 4)
	rand.Read(mask)
	hdr = append(hdr, mask...)
	body := make([]byte, n)
	for i := 0; i < n; i++ {
		body[i] = payload[i] ^ mask[i%4]
	}
	_, err := conn.Write(append(hdr, body...))
	return err
}

func wsRead(conn net.Conn) ([]byte, error) {
	h := make([]byte, 2)
	if _, err := io.ReadFull(conn, h); err != nil {
		return nil, err
	}
	n := int(h[1] & 0x7f)
	if n == 126 {
		ext := make([]byte, 2)
		io.ReadFull(conn, ext)
		n = int(binary.BigEndian.Uint16(ext))
	} else if n == 127 {
		ext := make([]byte, 8)
		io.ReadFull(conn, ext)
		n = int(binary.BigEndian.Uint64(ext))
	}
	payload := make([]byte, n)
	if _, err := io.ReadFull(conn, payload); err != nil {
		return nil, err
	}
	return payload, nil
}

func hexDecode(s string) []byte {
	out := make([]byte, len(s)/2)
	for i := 0; i < len(out); i++ {
		fmt.Sscanf(s[i*2:i*2+2], "%02x", &out[i])
	}
	return out
}

// 发送步骤：登录进世界后按 delayMs 依次发送
type sendStep struct {
	Cmd     uint32 `json:"cmd"`
	BodyHex string `json:"bodyHex"`
	DelayMs int    `json:"delayMs"`
}

// cmd 名表：{"NAME": 123, ...} → {123: "NAME"}
func loadCmdNames(path string) map[uint32]string {
	m := map[uint32]string{}
	b, err := os.ReadFile(path)
	if err != nil {
		return m
	}
	var raw map[string]uint32
	if json.Unmarshal(b, &raw) != nil {
		return m
	}
	for k, v := range raw {
		if _, ok := m[v]; !ok {
			m[v] = k
		}
	}
	return m
}

func loadSteps(path string) []sendStep {
	if path == "" {
		return []sendStep{
			{Cmd: 42494, DelayMs: 0},
			{Cmd: 1002, DelayMs: 200},
			{Cmd: 1016, BodyHex: "00000002", DelayMs: 400},
		}
	}
	b, err := os.ReadFile(path)
	if err != nil {
		fmt.Println("read steps:", err)
		return nil
	}
	var st []sendStep
	if err := json.Unmarshal(b, &st); err != nil {
		fmt.Println("parse steps:", err)
		return nil
	}
	return st
}

func main() {
	infoPath := flag.String("info", "login.json", "login info json")
	stepsPath := flag.String("steps", "", "send steps json")
	seconds := flag.Int("seconds", 25, "run seconds")
	hexDump := flag.Bool("hex", false, "print S2C body hex")
	viewAddr := flag.String("view", "", "可视化面板地址，如 127.0.0.1:7800")
	logPath := flag.String("log", "session.jsonl", "事件日志 jsonl")
	serveAddr := flag.String("serve", "", "常驻 JSON 服务地址，如 127.0.0.1:7801")
	sendStr := flag.String("send", "", "命令串（雷小伊语法，分号分隔）如 \"2002;2001,0,3001,725,272;2408,3\"")
	catchIDs := flag.String("catch", "", "要捕捉的野怪 id（逗号分隔），命中 2004 槽位后自动发 2408,slot")
	boot := flag.Bool("boot", false, "收到 S2C 1001 后立刻补发引导帧 1002/1016/42494（不等 2001）")
	enter := flag.String("enter", "", "收到 S2C 1001 后主动进图，格式 地图id,x,y（对齐雷小伊 Send(\"2001,0,map,x,y\")）")
	cmdMap := flag.String("cmdmap", "data/commandid.json", "cmd 名表")
	actionsPath := flag.String("actions", "data/actions.json", "面板可选操作列表")
	login103 := flag.String("account", os.Getenv("SEER_ACCOUNT"), "account for 103 login")
	pass103 := flag.String("password", os.Getenv("SEER_PASSWORD"), "password for 103 login")
	flag.Parse()

	// 单实例锁：避免同 uid 多连接互相顶号
	if lf, err := os.OpenFile(".seerproto.lock", os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0644); err != nil {
		fmt.Println("另一个客户端实例在运行（.seerproto.lock 存在）。如确认已退出，删除该文件重试。")
		os.Exit(1)
	} else {
		fmt.Fprintf(lf, "%d\n", os.Getpid())
		lf.Close()
		defer os.Remove(".seerproto.lock")
	}

	initEvents(loadCmdNames(*cmdMap), *logPath)
	actCh := make(chan actReq, 16)
	loadActions(*actionsPath)
	if *viewAddr != "" {
		startView(*viewAddr, actCh, loadCmdNames(*cmdMap))
	}

	raw, err := os.ReadFile(*infoPath)
	if err != nil {
		fmt.Println("read info:", err)
		os.Exit(1)
	}
	var info loginInfo
	if err := json.Unmarshal(raw, &info); err != nil {
		fmt.Println("parse info:", err)
		os.Exit(1)
	}
	session := hexDecode(info.Session)
	fmt.Printf("uid=%d session=%x host=%s path=%s\n", info.UID, session, info.Host, info.Path)

	// 1) login_gate
	fmt.Println("[1] login_gate 105/111/109")
	gate, err := dialWS("seerh5login.61.com", 443, "/login_gate_webgl")
	if err != nil {
		fmt.Println("gate:", err)
		os.Exit(1)
	}
	prev := int32(0)
	if *login103 != "" && *pass103 != "" {
		fmt.Println("[1b] MAIN_LOGIN_IN(103) 用账号密码登录")
		var b []byte
		u := make([]byte, 16)
		copy(u, []byte(*login103))
		pw := make([]byte, 32)
		copy(pw, []byte(*pass103))
		b = append(b, u...)
		b = append(b, pw...)
		b = append(b, 0, 0, 0, 0) // tmcid
		b = append(b, 0, 0, 0, 2) // GAME_TYPE = 2
		b = append(b, 0, 0, 0, 0)
		b = append(b, make([]byte, 16)...) // IGM_ID
		b = append(b, make([]byte, 6)...)  // IMG_BY
		b = append(b, 0, 0, 0, 0)          // tmcid2
		b = append(b, 0, 0, 0, 0)          // channelId
		ch := make([]byte, 32)
		copy(ch, []byte("h5_web_taomee"))
		b = append(b, ch...)
		fmt.Printf("    103 body len=%d\n", len(b))
		wsSend(gate, frame(103, info.UID, b, &prev))
		gate.SetReadDeadline(time.Now().Add(8 * time.Second))
		for {
			rp, err := wsRead(gate)
			if err != nil {
				fmt.Println("    103 read err:", err)
				break
			}
			if len(rp) < 17 {
				continue
			}
			rc := binary.BigEndian.Uint32(rp[5:])
			fmt.Printf("    S2C cmd=%d len=%d result=%d body=%x\n", rc, len(rp), int32(binary.BigEndian.Uint32(rp[13:])), rp[17:])
			if rc == 103 || rc == 101 {
				if len(rp) >= 33 {
					session = rp[17:33]
					fmt.Printf("    >>> 使用服务端签发的会话: %x\n", session)
				}
				break
			}
		}
	}
	gate105 := append(append([]byte{}, session...), 0, 0, 0, 0)
	for _, gc := range []struct {
		cmd uint32
		bd  []byte
	}{{105, gate105}, {111, nil}, {109, gate105}} {
		f := frame(gc.cmd, info.UID, gc.bd, &prev)
		wsSend(gate, f)
		emitFrame("c2s", f)
	}
	gate.SetReadDeadline(time.Now().Add(2 * time.Second))
	for i := 0; i < 4; i++ {
		if p, err := wsRead(gate); err == nil && len(p) >= 17 {
			fmt.Printf("    gate S2C cmd=%d len=%d\n", binary.BigEndian.Uint32(p[5:]), len(p))
			emitFrame("s2c", p)
		} else {
			break
		}
	}
	gate.Close()
	time.Sleep(1200 * time.Millisecond)

	// 2) 游戏网关 1001
	fmt.Println("[2] game 1001")
	game, err := dialGame(info.Host, info.Port, info.Path)
	if err != nil {
		fmt.Println("game:", err)
		os.Exit(1)
	}
	body := make([]byte, 508)
	if b, e := base64.StdEncoding.DecodeString(info.BodyB64); e == nil && len(b) == 508 {
		copy(body, b)
	}
	copy(body, session)

	prev2 := int32(0)
	f1001 := frame(1001, info.UID, body, &prev2)
	emitFrame("c2s", f1001)
	wsSend(game, f1001)

	// 常驻 JSON 服务模式（agent 用）
	if *serveAddr != "" {
		runServe(game, info.UID, &prev2, *serveAddr, loadCmdNames(*cmdMap), *seconds)
		return
	}

	// 3) 事件循环：维护 result 链 + 首个 ack 之后按 steps 依次发命令
	steps := loadSteps(*stepsPath)
	if s := parseSend(*sendStr); len(s) > 0 {
		steps = append(steps, s...)
		fmt.Printf("    -send: 追加 %d 条命令\n", len(s))
	}
	catchWant := parseIDs(*catchIDs)
	if len(catchWant) > 0 {
		fmt.Printf("    -catch: 目标野怪 %v（监听 2004 自动 2408）\n", catchWant)
	}
	acked := 0
	booted := false
	entered := false
	stepIdx := 0
	var ackAt time.Time
	start := time.Now()
	for time.Since(start) < time.Duration(*seconds)*time.Second {
		// 面板"可选操作"发来的命令（非阻塞）
		select {
		case a := <-actCh:
			fa := frame(a.Cmd, info.UID, a.Body, &prev2)
			emitFrame("c2s", fa)
			wsSend(game, fa)
			fmt.Printf("    >>> 面板 C2S %d\n", a.Cmd)
			continue
		default:
		}
		if acked > 0 && stepIdx < len(steps) && time.Since(ackAt) >= time.Duration(steps[stepIdx].DelayMs)*time.Millisecond {
			st := steps[stepIdx]
			var sb []byte
			if st.BodyHex != "" {
				sb = hexDecode(st.BodyHex)
			}
			fs := frame(st.Cmd, info.UID, sb, &prev2)
			emitFrame("c2s", fs)
			wsSend(game, fs)
			fmt.Printf("    >>> C2S %d body=%s\n", st.Cmd, st.BodyHex)
			stepIdx++
			continue
		}
		game.SetReadDeadline(time.Now().Add(300 * time.Millisecond))
		p, err := wsRead(game)
		if err != nil {
			if ne, ok := err.(net.Error); ok && ne.Timeout() {
				continue
			}
			fmt.Println("    read err:", err)
			break
		}
		if len(p) < 17 {
			continue
		}
		// 官方客户端：result 链取"上行/下行最近一个非 0 result"
		if r := int32(binary.BigEndian.Uint32(p[13:])); r != 0 {
			prev2 = r
		}
		emitFrame("s2c", p)
		cmd := binary.BigEndian.Uint32(p[5:])
		if *hexDump {
			fmt.Printf("    S2C cmd=%d len=%d res=%d body=%x\n", cmd, len(p), int32(binary.BigEndian.Uint32(p[13:])), p[17:])
		} else {
			fmt.Printf("    S2C cmd=%d len=%d res=%d\n", cmd, len(p), int32(binary.BigEndian.Uint32(p[13:])))
		}

		if cmd == 1001 && *enter != "" && !entered {
			entered = true
			parts := strings.Split(*enter, ",")
			if len(parts) >= 1 {
				m, _ := strconv.ParseUint(strings.TrimSpace(parts[0]), 10, 32)
				x, y := uint64(0), uint64(0)
				if len(parts) >= 3 {
					x, _ = strconv.ParseUint(strings.TrimSpace(parts[1]), 10, 32)
					y, _ = strconv.ParseUint(strings.TrimSpace(parts[2]), 10, 32)
				}
				body := make([]byte, 16)
				binary.BigEndian.PutUint32(body[0:], 0)
				binary.BigEndian.PutUint32(body[4:], uint32(m))
				binary.BigEndian.PutUint32(body[8:], uint32(x))
				binary.BigEndian.PutUint32(body[12:], uint32(y))
				fe := frame(2001, info.UID, body, &prev2)
				emitFrame("c2s", fe)
				wsSend(game, fe)
				fmt.Printf("    >>> 主动进图 map=%d x=%d y=%d\n", m, x, y)
			}
		}

		if cmd == 1001 && *boot && !booted {
			booted = true
			for _, bc := range []struct {
				cmd  uint32
				body []byte
			}{{42494, nil}, {1002, nil}, {1016, []byte{0, 0, 0, 2}}} {
				fb := frame(bc.cmd, info.UID, bc.body, &prev2)
				emitFrame("c2s", fb)
				wsSend(game, fb)
				fmt.Printf("    >>> boot %d\n", bc.cmd)
				time.Sleep(200 * time.Millisecond)
			}
		}

		if cmd == 2004 && len(catchWant) > 0 {
			n := (len(p) - 17) / 4
			if n > 9 {
				n = 9
			}
			for i := 0; i < n; i++ {
				id := binary.BigEndian.Uint32(p[17+i*4:])
				if id == 0 || !hasID(catchWant, id) {
					continue
				}
				b := make([]byte, 4)
				binary.BigEndian.PutUint32(b, uint32(i))
				fc := frame(2408, info.UID, b, &prev2)
				emitFrame("c2s", fc)
				wsSend(game, fc)
				fmt.Printf("    >>> 捕捉: 槽位 %d 精灵 %d → 2408\n", i, id)
			}
		}

		if cmd == 2001 {
			acked++
			if acked == 1 {
				ackAt = time.Now()
			}
			token := binary.BigEndian.Uint32(p[21:])
			ab := make([]byte, 12)
			binary.BigEndian.PutUint32(ab[0:], 2)
			binary.BigEndian.PutUint32(ab[4:], 1)
			binary.BigEndian.PutUint32(ab[8:], token)
			fa := frame(45963, info.UID, ab, &prev2)
			emitFrame("c2s", fa)
			wsSend(game, fa)
			fmt.Printf("    >>> ack#%d token=%08x\n", acked, token)
		}
	}
	// 可视化模式下，即使游戏连接已断也把面板留到最后
	if *viewAddr != "" {
		if rest := time.Duration(*seconds)*time.Second - time.Since(start); rest > 0 {
			emitInfo("游戏连接已结束，面板保持到倒计时结束")
			time.Sleep(rest)
		}
	}
	fmt.Println("done")
}


// parseSend：把雷小伊命令串 "2002;2001,0,3001,725,272;2408,3" 转成发送步骤
// 规则与文档一致：cmd 后每个十进制参数就是 1 个 u32（大端）
func parseSend(s string) []sendStep {
	var out []sendStep
	for _, part := range strings.Split(s, ";") {
		part = strings.TrimSpace(part)
		if part == "" {
			continue
		}
		fields := strings.Split(part, ",")
		c, err := strconv.ParseUint(strings.TrimSpace(fields[0]), 10, 32)
		if err != nil {
			fmt.Println("    -send 命令号非法:", part)
			continue
		}
		body := make([]byte, 0, 4*(len(fields)-1))
		bad := false
		for _, a := range fields[1:] {
			v, err := strconv.ParseUint(strings.TrimSpace(a), 10, 32)
			if err != nil {
				fmt.Println("    -send 参数非法:", part)
				bad = true
				break
			}
			var b [4]byte
			binary.BigEndian.PutUint32(b[:], uint32(v))
			body = append(body, b[:]...)
		}
		if bad {
			continue
		}
		out = append(out, sendStep{Cmd: uint32(c), BodyHex: hex.EncodeToString(body), DelayMs: 900})
	}
	return out
}

func parseIDs(s string) []uint32 {
	var out []uint32
	for _, p := range strings.Split(s, ",") {
		p = strings.TrimSpace(p)
		if p == "" {
			continue
		}
		if v, err := strconv.ParseUint(p, 10, 32); err == nil {
			out = append(out, uint32(v))
		}
	}
	return out
}

func hasID(ids []uint32, v uint32) bool {
	for _, x := range ids {
		if x == v {
			return true
		}
	}
	return false
}
