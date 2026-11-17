// 按反编译出的 App 客户端布局生成 LOGIN_IN(1001) 的 508 字节 body
// 布局（FUN_0044bd96）：session16 | "taomee"x64 | u32 serverid | u3241 | "PC"x16
//   | u32 10000,1,1,2 | "unity_app_taomee"x32 | "com.taomee.seer.mobile"x32
//   | 空x64 *3 | 字符串x64 | 空x64 | u32 0
export const BODY_LEN = 508;

function pad(buf, off, str, len) {
  buf.write(str, off, len, 'utf8'); // 后面自动为 0
}

export function buildLoginBody({ session, serverId = 3002, device = '' }) {
  const b = Buffer.alloc(BODY_LEN);
  session.copy(b, 0);

  pad(b, 0x10, 'taomee', 64);
  b.writeUInt32BE(serverId >>> 0, 0x50);
  b.writeUInt32BE(1, 0x54);
  pad(b, 0x58, 'PC', 16);
  b.writeUInt32BE(10000, 0x68);
  b.writeUInt32BE(1, 0x6c);
  b.writeUInt32BE(1, 0x70);
  b.writeUInt32BE(2, 0x74);
  pad(b, 0x78, 'unity_app_taomee', 32);
  pad(b, 0x98, 'com.taomee.seer.mobile', 32);
  pad(b, 0x178, device, 64);
  // 0xb8/0xf8/0x138 三段空 64 字节，0x178 一段字符串，0x1b8 空 64
  b.writeUInt32BE(0, 0x1f8);
  return b;
}
