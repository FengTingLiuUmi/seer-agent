// 最小 WebSocket 客户端（TLS + 握手 + 帧），因为 Node 内置 WebSocket 不能自定义
// 握手头（游戏网关要求 Origin / Cookie）。
import tls from 'node:tls';
import crypto from 'node:crypto';
import { EventEmitter } from 'node:events';

const GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11';

export class RawWebSocket extends EventEmitter {
  constructor() {
    super();
    this.socket = null;
    this.buf = Buffer.alloc(0);
    this.open = false;
    this.closed = false;
    this.readyState = 0;
  }

  connect(urlStr, headers = {}, { timeoutMs = 10000, tlsOptions = null } = {}) {
    const url = new URL(urlStr);
    const host = url.hostname;
    const port = Number(url.port || 443);
    const path = (url.pathname || '/') + (url.search || '');
    const key = crypto.randomBytes(16).toString('base64');

    return new Promise((resolve, reject) => {
      const tlsCfg = Object.assign({ host, port, servername: host, ALPNProtocols: ['http/1.1'] }, tlsOptions || {});
      const socket = tls.connect(tlsCfg, () => {
        const lines = [
          `GET ${path} HTTP/1.1`,
          `Host: ${host}${port === 443 ? '' : ':' + port}`,
          'Upgrade: websocket',
          'Connection: Upgrade',
          `Sec-WebSocket-Key: ${key}`,
          'Sec-WebSocket-Version: 13',
          ...Object.entries(headers).map(([k, v]) => `${k}: ${v}`),
          '',
          '',
        ];
        socket.write(lines.join('\r\n'));
      });
      const timer = setTimeout(() => { socket.destroy(); reject(new Error('ws handshake timeout')); }, timeoutMs);
      let handshakeBuf = Buffer.alloc(0);
      let handshook = false;
      socket.on('data', (chunk) => {
        if (handshook) return this.#onData(chunk);
        handshakeBuf = Buffer.concat([handshakeBuf, chunk]);
        const sep = handshakeBuf.indexOf('\r\n\r\n');
        if (sep < 0) return;
        clearTimeout(timer);
        const head = handshakeBuf.subarray(0, sep).toString('latin1');
        const status = head.split('\r\n')[0];
        if (!/ 101 /.test(status)) {
          socket.destroy();
          return reject(new Error('handshake rejected: ' + status));
        }
        handshook = true;
        this.socket = socket;
        this.tlsInfo = { protocol: socket.getProtocol(), cipher: socket.getCipher() && socket.getCipher().name };
        this.open = true;
        this.readyState = 1;
        this.emit('open');
        resolve(this);
        const rest = handshakeBuf.subarray(sep + 4);
        if (rest.length) this.#onData(rest);
      });
      socket.on('error', (e) => { this.emit('error', e); reject(e); });
      socket.on('close', () => { this.closed = true; this.open = false; this.readyState = 3; this.emit('close', 1006, ''); });
    });
  }

  #onData(chunk) {
    this.buf = Buffer.concat([this.buf, chunk]);
    for (;;) {
      if (this.buf.length < 2) return;
      const b0 = this.buf[0];
      const fin = (b0 & 0x80) !== 0;
      const opcode = b0 & 0x0f;
      const masked = (this.buf[1] & 0x80) !== 0;
      let len = this.buf[1] & 0x7f;
      let off = 2;
      if (len === 126) {
        if (this.buf.length < 4) return;
        len = this.buf.readUInt16BE(2);
        off = 4;
      } else if (len === 127) {
        if (this.buf.length < 10) return;
        len = Number(this.buf.readBigUInt64BE(2));
        off = 10;
      }
      if (masked) {
        if (this.buf.length < off + 4 + len) return;
        const mask = this.buf.subarray(off, off + 4);
        off += 4;
        if (this.buf.length < off + len) return;
        const payload = Buffer.from(this.buf.subarray(off, off + len));
        for (let i = 0; i < payload.length; i++) payload[i] ^= mask[i % 4];
        this.buf = this.buf.subarray(off + len);
        this.#dispatch(opcode, payload, fin);
      } else {
        if (this.buf.length < off + len) return;
        const payload = Buffer.from(this.buf.subarray(off, off + len));
        this.buf = this.buf.subarray(off + len);
        this.#dispatch(opcode, payload, fin);
      }
    }
  }

  #dispatch(opcode, payload, fin) {
    if (opcode === 0x9) return this.#frame(0xa, payload); // ping → pong
    if (opcode === 0xa) { this.emit('pong'); return; }
    if (opcode === 0x8) {
      const code = payload.length >= 2 ? payload.readUInt16BE(0) : 1005;
      const reason = payload.length > 2 ? payload.subarray(2).toString('utf8') : '';
      this.emit('close', code, reason);
      try { this.socket.end(); } catch {}
      this.open = false; this.readyState = 3;
      return;
    }
    this.emit('message', payload);
  }

  #frame(opcode, payload) {
    const mask = crypto.randomBytes(4);
    const len = payload.length;
    let header;
    if (len < 126) {
      header = Buffer.from([0x80 | opcode, 0x80 | len]);
    } else if (len < 65536) {
      header = Buffer.alloc(4);
      header[0] = 0x80 | opcode; header[1] = 0x80 | 126;
      header.writeUInt16BE(len, 2);
    } else {
      header = Buffer.alloc(10);
      header[0] = 0x80 | opcode; header[1] = 0x80 | 127;
      header.writeBigUInt64BE(BigInt(len), 2);
    }
    const body = Buffer.from(payload);
    for (let i = 0; i < body.length; i++) body[i] ^= mask[i % 4];
    return Buffer.concat([header, mask, body]);
  }

  addEventListener(type, fn, opts) {
    const handler = type === 'message' ? (p) => fn({ data: p }) : fn;
    if (opts && opts.once) this.once(type, handler);
    else this.on(type, handler);
  }

  removeEventListener() {}

  send(data) {
    if (!this.open) throw new Error('ws not open');
    const buf = Buffer.isBuffer(data) ? data : Buffer.from(data);
    this.socket.write(this.#frame(0x2, buf));
  }

  sendText(str) {
    if (!this.open) throw new Error('ws not open');
    this.socket.write(this.#frame(0x1, Buffer.from(String(str), 'utf8')));
  }

  close() {
    if (!this.open) return;
    try { this.socket.write(this.#frame(0x8, Buffer.alloc(0))); } catch { /* ignore */ }
    this.socket.end();
    this.open = false;
  }
}




