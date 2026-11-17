// 赛尔号 H5 协议帧编解码
//
// 帧: [u32 totalLen][u8 version='1'][u32 cmdID][u32 userID][i32 result][body]
//   totalLen = 17 + body.length
//   result  : cmdID<=1000 时为 0；cmdID>1000 时为一个**有状态**校验值（非加密），
//             必须用上一帧的 result 递推，因此帧要按顺序发送。
//
// 来源: 官方客户端 resource/app/socket/socket_*.js（见 docs/reference/socket.deob.js）
export const HEAD_LEN = 17;
export const VERSION = 0x31; // '1'
export const PACKAGE_MAX = 0x800000;

/** 参数序列化：数组递归；字符串 UTF-8；Buffer 原样；整数 u32；null/undefined 跳过 */
export function serializeArgs(args) {
  const parts = [];
  for (const a of args ?? []) {
    if (Array.isArray(a)) parts.push(serializeArgs(a));
    else if (typeof a === 'string') parts.push(Buffer.from(a, 'utf8'));
    else if (Buffer.isBuffer(a)) parts.push(a);
    else if (a === undefined || a === null) continue;
    else if (Number.isInteger(a)) {
      const b = Buffer.alloc(4);
      b.writeUInt32BE(a >>> 0);
      parts.push(b);
    } else {
      throw new TypeError('unsupported arg type: ' + typeof a);
    }
  }
  return Buffer.concat(parts);
}

export class Encoder {
  constructor(userID = 0) {
    this.userID = userID >>> 0;
    this.result = 0;
  }

  /** 打包一帧，并推进内部 result 状态 */
  pack(cmdID, args = []) {
    const body = serializeArgs(args);
    if (cmdID > 1000) {
      let s = 0;
      for (let i = 0; i < body.length; i++) s ^= body[i] & 0xff;
      this.result = (this.result - Math.floor(this.result / 3) + 113 + (body.length % 17) + (cmdID % 23) + s + 7) | 0;
    }
    const head = Buffer.alloc(HEAD_LEN);
    head.writeUInt32BE(HEAD_LEN + body.length, 0);
    head.writeUInt8(VERSION, 4);
    head.writeUInt32BE(cmdID >>> 0, 5);
    head.writeUInt32BE(this.userID, 9);
    head.writeInt32BE(cmdID > 1000 ? this.result : 0, 13);
    return Buffer.concat([head, body]);
  }
}

export function parse(buf) {
  if (buf.length < HEAD_LEN) throw new Error('short frame');
  const total = buf.readUInt32BE(0);
  if (total < HEAD_LEN || total > PACKAGE_MAX) throw new Error('bad frame length ' + total);
  if (buf.length < total) throw new Error('incomplete frame');
  return {
    total,
    version: buf.readUInt8(4),
    cmdID: buf.readUInt32BE(5),
    userID: buf.readUInt32BE(9),
    result: buf.readInt32BE(13),
    body: buf.subarray(HEAD_LEN, total),
    raw: buf.subarray(0, total),
  };
}

/** 处理 WS/TCP 粘包、半包 */
export class FrameSplitter {
  constructor() {
    this.buf = Buffer.alloc(0);
  }

  push(chunk) {
    this.buf = Buffer.concat([this.buf, chunk]);
    const out = [];
    for (;;) {
      if (this.buf.length < 4) break;
      const total = this.buf.readUInt32BE(0);
      if (total < HEAD_LEN || total > PACKAGE_MAX) throw new Error('bad frame length ' + total);
      if (this.buf.length < total) break;
      out.push(parse(this.buf.subarray(0, total)));
      this.buf = this.buf.subarray(total);
    }
    return out;
  }
}