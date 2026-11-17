package main

import (
	"fmt"
	"strings"
	"unicode/utf8"
)

// 从 body 里抽取可读 UTF-8 片段（CJK / ASCII 词），用于看板摘要
func utf8Runs(b []byte) []string {
	var out []string
	var cur []rune
	flush := func() {
		if len(cur) >= 2 {
			out = append(out, string(cur))
		}
		cur = nil
	}
	for i := 0; i < len(b); {
		r, size := utf8.DecodeRune(b[i:])
		if r == utf8.RuneError && size == 1 {
			flush()
			i++
			continue
		}
		ok := r >= 0x4e00 && r <= 0x9fff // CJK
		if !ok && r >= 0x20 && r < 0x7f {
			ok = true
		}
		if !ok {
			flush()
			i += size
			continue
		}
		cur = append(cur, r)
		i += size
	}
	flush()
	return out
}

func be32(b []byte, off int) uint32 {
	if off+4 > len(b) {
		return 0
	}
	return uint32(b[off])<<24 | uint32(b[off+1])<<16 | uint32(b[off+2])<<8 | uint32(b[off+3])
}

// NUL 结尾的定长字段
func cstr(b []byte, off, max int) string {
	if off >= len(b) {
		return ""
	}
	end := off + max
	if end > len(b) {
		end = len(b)
	}
	s := b[off:end]
	if i := strings.IndexByte(string(s), 0); i >= 0 {
		s = s[:i]
	}
	return strings.TrimSpace(strings.ToValidUTF8(string(s), ""))
}

// 给看板生成一行人类可读摘要
func summarize(cmd uint32, body []byte) string {
	switch cmd {
	case 2001:
		nick := cstr(body, 8, 16)
		runs := utf8Runs(body)
		return fmt.Sprintf("进入地图 · 昵称=%s · 文本=%s", nick, strings.Join(head(runs, 3), " / "))
	case 2003:
		n := be32(body, 0)
		runs := utf8Runs(body)
		return fmt.Sprintf("地图玩家 %d 人 · %s", n, strings.Join(head(dedupe(runs), 8), ", "))
	case 1001:
		return fmt.Sprintf("登录回包 %d 字节 · 会话=%x", len(body), body[:min(16, len(body))])
	case 3401:
		return fmt.Sprintf("成就列表 %d 条", be32(body, 0))
	case 3454:
		return fmt.Sprintf("成就进度 %d 字节", len(body))
	case 1016:
		return "会话密钥: " + cstr(body, 0, 40)
	}
	return ""
}

func head(s []string, n int) []string {
	if len(s) > n {
		return s[:n]
	}
	return s
}

func dedupe(s []string) []string {
	seen := map[string]bool{}
	out := []string{}
	for _, x := range s {
		if len(x) < 2 || seen[x] {
			continue
		}
		seen[x] = true
		out = append(out, x)
	}
	return out
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}