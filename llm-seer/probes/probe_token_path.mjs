// 探测：authenticate 拿到的 session 能不能直接当 token 用（跳过 token/refresh）
import { authenticate } from '../../seer-auto/src/login.js';
import { wsAuthenticate, convertToken, onlineGate, refreshToken } from '../../seer-auto/src/auth.js';
import { duid } from '../../seer-auto/src/auth.js';

const acct = process.argv[2] ?? 'ACCOUNT';
const pwd = process.env.SEER_PASSWORD;
if (!pwd) { console.log('need SEER_PASSWORD'); process.exit(1); }

const a = await authenticate(acct, pwd);
console.log('authenticate: uid=%s session=%s… raw=%s', a.uid, String(a.session).slice(0, 8), a.raw.slice(0, 60).replace(/\s+/g, ' '));

// 1) refresh_token 长什么样 / 服务器给什么
try {
  const t = await refreshToken(Number(a.uid), String(a.session));
  console.log('refreshToken OK token=%s… exp=%s', String(t.token).slice(0, 8), t.expire);
  process.exit(0);
} catch (e) {
  console.log('refreshToken FAIL:', String(e.message).slice(0, 120));
}

// 2) 直接用 session 当 token 去 convert
try {
  const s = await convertToken(Number(a.uid), String(a.session));
  console.log('convertToken(session) OK session=%s', s.toString('hex'));
} catch (e) {
  console.log('convertToken(session) FAIL:', String(e.message).slice(0, 120));
}

// 3) 直接用 session 当 token 去 wsAuthenticate
try {
  const r = await wsAuthenticate(Number(a.uid), String(a.session));
  console.log('wsAuthenticate(session) ->', JSON.stringify(r).slice(0, 120));
} catch (e) {
  console.log('wsAuthenticate(session) FAIL:', String(e.message).slice(0, 120));
}
process.exit(0);