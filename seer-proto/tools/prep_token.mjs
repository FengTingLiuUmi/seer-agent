// 用 data/token.json（可自动续期）生成 fresh login.json，不需要密码/浏览器
import fs from 'node:fs';
import { ensureToken } from '../lib/tokenStore.js';
import { wsAuthenticate, onlineGate, convertToken } from '../lib/auth.js';

const t = await ensureToken((...a) => console.log('token:', ...a));
const uid = Number(t.uid);
await wsAuthenticate(uid, t.tokenString);
const gate = await onlineGate(uid, t.tokenString);
const session = await convertToken(uid, t.tokenString);
const g = /^([^/:]+)(\/[^:]*):(\d+)$/.exec(String(gate.text).trim());
const body = Buffer.from(fs.readFileSync(new URL('../data/login_template.bin', import.meta.url)));
session.copy(body, 0);
// 不写 0x4c：官方 1001 body 该处为 0，模板自带的 3002 在 0x52
const out = {
  uid,
  sessionHex: session.toString('hex'),
  host: g?.[1] ?? 'h5gy.61.com',
  path: g?.[2] ?? '/wss_online_01/',
  serverId: Number(g?.[3] ?? 3002),
  bodyB64: body.toString('base64'),
};
fs.writeFileSync('login.json', JSON.stringify(out, null, 2));
console.log('ok uid=%d session=%s gate=%s%s', uid, out.sessionHex, out.host, out.path);
process.exit(0);