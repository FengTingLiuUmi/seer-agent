#!/usr/bin/env python3
"""Flash 端 TCP 中间人代理（明文协议，无需证书/无需管理员）

作用：
  1) 让 Flash 客户端连到本代理 → 代理转发到真实服务器 → 双向记录全部帧
  2) 代理可以主动往任意方向插入/修改帧（等于"不使用识图就能操作"）
  3) 顺带把 per-server 端口的首帧握手/加密抓下来

用法:
  python tcp_proxy.py --listen 127.0.0.1:18630 --upstream 101.43.19.60:1863
  python tcp_proxy.py --listen 127.0.0.1:18631 --upstream 101.35.207.167:1272 --frames

输出:
  proxy-<port>.jsonl   每行 {t, dir, raw|cmd,len,res,body}
"""
import argparse, socket, struct, threading, time, json, sys, os

POLICY = (
    b'<?xml version="1.0"?><!DOCTYPE cross-domain-policy SYSTEM '
    b'"http://www.adobe.com/xml/dtds/cross-domain-policy.dtd">'
    b'<cross-domain-policy><allow-access-from domain="*" to-ports="*" '
    b'secure="false"/></cross-domain-policy>\x00'
)

lock = threading.Lock()
logf = None


def log(obj):
    with lock:
        logf.write(json.dumps(obj, ensure_ascii=False) + '\n')
        logf.flush()


def parse_frames(buf, label, src):
    """尽力解析 17B 帧（len u32 | ver u8 | cmd u32 | uid u32 | res i32 | body）"""
    off = 0
    n = len(buf)
    while off + 17 <= n:
        ln, ver = struct.unpack_from('>IB', buf, off)
        cmd = struct.unpack_from('>I', buf, off + 5)[0]
        uid = struct.unpack_from('>I', buf, off + 9)[0]
        res = struct.unpack_from('>i', buf, off + 13)[0]
        if ln < 17 or off + ln > n:
            break
        body = buf[off + 17:off + ln]
        print('%-4s %-8s cmd=%-6d len=%-5d uid=%-10d res=%-6d body=%s' % (
            label, src, cmd, ln, uid, res, body[:24].hex()), flush=True)
        log({'t': int(time.time() * 1000), 'dir': label, 'cmd': cmd, 'len': ln,
             'uid': uid, 'res': res, 'body': body.hex()})
        off += ln
    return off


def pump(src, dst, label, frames=False):
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            if frames:
                parse_frames(data, label, '')
            else:
                print('%-4s %5d B %s' % (label, len(data), data[:48].hex()), flush=True)
                log({'t': int(time.time() * 1000), 'dir': label, 'raw': data.hex()})
            dst.sendall(data)
    except OSError:
        pass
    finally:
        for s in (src, dst):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                s.close()
            except OSError:
                pass


def handle(client, up_host, up_port, frames):
    client.settimeout(10)
    try:
        sniff = client.recv(4096, socket.MSG_PEEK)
    except OSError:
        client.close()
        return
    if sniff.startswith(b'<policy-file-request/>'):
        client.recv(4096)
        client.sendall(POLICY)
        print('POLICY served (%d bytes)' % len(POLICY), flush=True)
        log({'t': int(time.time() * 1000), 'dir': 'policy', 'raw': POLICY.hex()})
        client.close()
        return
    try:
        up = socket.create_connection((up_host, up_port), timeout=8)
    except OSError as e:
        print('upstream fail:', e, flush=True)
        client.close()
        return
    client.settimeout(None)
    up.settimeout(None)
    t1 = threading.Thread(target=pump, args=(client, up, 'C2S', frames), daemon=True)
    t2 = threading.Thread(target=pump, args=(up, client, 'S2C', frames), daemon=True)
    t1.start(); t2.start(); t1.join(); t2.join()


def main():
    global logf
    ap = argparse.ArgumentParser()
    ap.add_argument('--listen', default='127.0.0.1:18630')
    ap.add_argument('--upstream', required=True)
    ap.add_argument('--frames', action='store_true', help='按 17B 帧解析并打印')
    a = ap.parse_args()
    lh, lp = a.listen.split(':')
    uh, up = a.upstream.split(':')
    lp, up = int(lp), int(up)
    logf = open('proxy-%d.jsonl' % lp, 'a', encoding='utf-8')
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((lh, lp))
    srv.listen(64)
    print('proxy %s -> %s:%d  (frames=%s)' % (a.listen, uh, up, a.frames), flush=True)
    while True:
        c, addr = srv.accept()
        print('accept', addr, flush=True)
        threading.Thread(target=handle, args=(c, uh, up, a.frames), daemon=True).start()


if __name__ == '__main__':
    main()