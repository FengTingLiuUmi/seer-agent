package main

import (
	"bufio"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net"
	"os"
	"time"
)

type cmdReq struct {
	ID      int    `json:"id"`
	Cmd     uint32 `json:"cmd"`
	BodyHex string `json:"bodyHex"`
}

type srvMsg struct {
	Type    string `json:"type"`
	ID      int    `json:"id,omitempty"`
	Cmd     uint32 `json:"cmd,omitempty"`
	Name    string `json:"name,omitempty"`
	Len     int    `json:"len,omitempty"`
	Res     int32  `json:"res,omitempty"`
	BodyHex string `json:"bodyHex,omitempty"`
	Error   string `json:"error,omitempty"`
}

func cmdName(names map[uint32]string, cmd uint32) string {
	if names == nil {
		return ""
	}
	return names[cmd]
}

// runServe: 常驻模式，127.0.0.1:<port> 上接受 JSON 行命令，回传所有 S2C 帧。
//
// 进世界引导（对齐官方抓包 relogin4.jsonl）：
//
//	S2C 2001 → C2S 42494 → S2C 42494 → C2S 1002 → S2C 1002
//	          → C2S 1016(00000002) → S2C 1016 → ready
//
// 注意：登录进世界这一步没有 45963 ack（45963 只用于「地图切换」确认，
// 在地图切换时服务端会下发 2001 with 12B body = 00000002 00000001 <token>）。
// 旧实现 2001 后先发 45963 再发 42494，会污染 result 链 → 服务端立刻 EOF。
func runServe(game net.Conn, uid uint32, prev *int32, addr string, names map[uint32]string, secs int) {
	ln, err := net.Listen("tcp", addr)
	if err != nil {
		fmt.Fprintln(os.Stderr, "listen:", err)
		return
	}
	fmt.Fprintf(os.Stderr, "serve on %s（等客户端连接）\n", addr)
	c, err := ln.Accept()
	if err != nil {
		fmt.Fprintln(os.Stderr, "accept:", err)
		return
	}
	defer c.Close()
	fmt.Fprintln(os.Stderr, "client connected")

	out := json.NewEncoder(c)
	flush := func(m srvMsg) {
		_ = out.Encode(m)
		if b, e := json.Marshal(m); e == nil {
			fmt.Println(string(b))
		}
	}

	inCh := make(chan cmdReq, 64)
	go func() {
		dec := json.NewDecoder(bufio.NewReader(c))
		for {
			var r cmdReq
			if err := dec.Decode(&r); err != nil {
				close(inCh)
				return
			}
			inCh <- r
		}
	}()

	ready := false
	sent42494 := false
	sent1002 := false
	sent1016 := false
	bootAck := os.Getenv("SEER_BOOT_ACK") == "1" // 1 = 先回 45963 并等它回包，再发 42494
	acked := false
	lastID := 0
	var pending []cmdReq
	deadline := time.Now().Add(time.Duration(secs) * time.Second)

	sendCmd := func(cmd uint32, body []byte) {
		f := frame(cmd, uid, body, prev)
		game.Write(f)
	}

	for time.Now().Before(deadline) {
		// 待发命令：ready 前排队，ready 后立即下发
		for {
			select {
			case r, ok := <-inCh:
				if !ok {
					return
				}
				if !ready {
					pending = append(pending, r)
					continue
				}
				var body []byte
				if r.BodyHex != "" {
					body, _ = hex.DecodeString(r.BodyHex)
				}
				f := frame(r.Cmd, uid, body, prev)
				if _, err := game.Write(f); err != nil {
					flush(srvMsg{Type: "error", ID: r.ID, Error: err.Error()})
					return
				}
				lastID = r.ID
				flush(srvMsg{Type: "c2s", ID: r.ID, Cmd: r.Cmd, Name: cmdName(names, r.Cmd), Len: len(f),
					Res: int32(uint32(f[13])<<24 | uint32(f[14])<<16 | uint32(f[15])<<8 | uint32(f[16]))})
			default:
				goto read
			}
		}
	read:
		game.SetReadDeadline(time.Now().Add(200 * time.Millisecond))
		p, err := wsRead(game)
		if err != nil {
			if ne, ok := err.(net.Error); ok && ne.Timeout() {
				continue
			}
			flush(srvMsg{Type: "error", Error: "read: " + err.Error()})
			return
		}
		if len(p) < 17 {
			continue
		}
		res := int32(uint32(p[13])<<24 | uint32(p[14])<<16 | uint32(p[15])<<8 | uint32(p[16]))
		if res != 0 {
			*prev = res
		}
		cmd := uint32(p[5])<<24 | uint32(p[6])<<16 | uint32(p[7])<<8 | uint32(p[8])
		flush(srvMsg{Type: "s2c", ID: lastID, Cmd: cmd, Name: cmdName(names, cmd), Len: len(p), Res: res,
			BodyHex: hex.EncodeToString(p[17:])})

		switch {
		case !sent42494 && cmd == 2001:
			if bootAck && !acked {
				// 变体 B：先 45963 ack（body 12B），等 S2C 45963 再发 42494
				token := uint32(p[21])<<24 | uint32(p[22])<<16 | uint32(p[23])<<8 | uint32(p[24])
				ab := make([]byte, 12)
				ab[3] = 2
				ab[7] = 1
				ab[8] = byte(token >> 24)
				ab[9] = byte(token >> 16)
				ab[10] = byte(token >> 8)
				ab[11] = byte(token)
				sendCmd(45963, ab)
				acked = true
				break
			}
			sendCmd(42494, nil)
			sent42494 = true
		case bootAck && acked && !sent42494 && cmd == 45963:
			sendCmd(42494, nil)
			sent42494 = true
		case sent42494 && !sent1002 && cmd == 42494:
			sendCmd(1002, nil)
			sent1002 = true
		case sent1002 && !sent1016 && cmd == 1002:
			sendCmd(1016, []byte{0, 0, 0, 2})
			sent1016 = true
		case sent1016 && !ready && cmd == 1016:
			ready = true
			flush(srvMsg{Type: "ready"})
			for _, r := range pending {
				inCh <- r
			}
			pending = nil
		case ready && cmd == 2001 && len(p) == 29:
			// 地图切换确认：2001 body 12B = 00000002 00000001 <token>
			token := uint32(p[21])<<24 | uint32(p[22])<<16 | uint32(p[23])<<8 | uint32(p[24])
			ab := make([]byte, 12)
			ab[3] = 2
			ab[7] = 1
			ab[8] = byte(token >> 24)
			ab[9] = byte(token >> 16)
			ab[10] = byte(token >> 8)
			ab[11] = byte(token)
			sendCmd(45963, ab)
		}
	}
	flush(srvMsg{Type: "bye"})
}