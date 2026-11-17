// 准备 Go 探针需要的登录信息：token → 认证 → 网关 → 会话 → 1001 body
import fs from 'node:fs';
import { ensureToken } from '../lib/tokenStore.js';
import { wsAuthenticate, onlineGate, convertToken } from '../lib/auth.js';
import { buildLoginBody } from '../lib/loginBody.js';
import fsx from 'node:fs';

const t = await ensureToken((...a) => console.log('token:', ...a));
const uid = Number(t.uid);
console.log('uid', uid, 'token', String(t.tokenString).slice(0, 8) + '…');

await wsAuthenticate(uid, t.tokenString);
const gate = await onlineGate(uid, t.tokenString);
console.log('gate', gate.text);

const session = await convertToken(uid, t.tokenString);
const m = /^([^/:]+)(\/[^:]*):(\d+)$/.exec(String(gate.text).trim());
const host = m?.[1] ?? 'h5gy.61.com';
const path = m?.[2] ?? '/wss_online_02/';
const serverId = Number(process.env.SEER_SERVER_ID ?? m?.[3] ?? 3002);

let body;
if (process.env.SEER_BODY === 'webgl') {
  body = Buffer.from(fsx.readFileSync(new URL('../data/login_template.bin', import.meta.url)));
  session.copy(body, 0);
  console.log('using webgl template body');
} else {
  body = buildLoginBody({ session, serverId, device: process.env.SEER_DEVICE ?? '' });
}
const out = {
  uid,
  sessionHex: session.toString('hex'),
  host,
  path,
  serverId,
  bodyB64: body.toString('base64'),
};
fs.writeFileSync('login.json', JSON.stringify(out, null, 2));
console.log('login.json written', { uid, host, path, serverId, session: out.sessionHex });
process.exit(0);


