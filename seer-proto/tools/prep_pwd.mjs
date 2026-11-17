// 纯密码登录（复刻雷小伊）：authenticate → history(state) → AccountManager/login(code) → token/trans
//   密码来源：SEER_PASSWORD > secrets/cred.enc.json > F:\seer\account.ini（见 docs/CREDENTIALS.md）
import fs from 'node:fs';
import crypto from 'node:crypto';
import { authenticate, UA, cookieString } from '../lib/login.js';
import { duid, wsAuthenticate, onlineGate, convertToken } from '../lib/auth.js';
import { loadCredential } from './loadcred.mjs';

const acct = process.argv[2] ?? 'ACCOUNT';
const cred = await loadCredential(acct);
if (!cred.password) {
  console.log('没有密码：SEER_PASSWORD / secrets/cred.enc.json / account.ini 都没有');
  process.exit(1);
}

const H = () => ({
  'User-Agent': UA, Referer: 'https://h5-seer.61.com/',
  Cookie: cookieString(), 'X-Requested-With': 'XMLHttpRequest',
});

// 1) 账号密码 → session cookie
const a = await authenticate(acct, cred.password);
if (!a.uid) { console.log('authenticate 失败:', String(a.raw).slice(0, 120)); process.exit(1); }
const uid = Number(a.uid);
const d = duid();

// 2) history 页 → state
const redir = 'https%3A%2F%2Faccount-co.61.com%2Fv3%2F%3Fr%3Dauthorization%2Fsuccess';
const hist = 'https://account-co.61.com/v3/?r=AccountManager/history&duid=' + encodeURIComponent(d) +
  '&appid=20210906002&scope=userinfo&state=' + crypto.randomBytes(16).toString('hex') +
  '&source=0&register=&bg=0&redirect_url=' + redir;
const page = await (await fetch(hist, { headers: H() })).text();
const state = (page.match(/AccountManager\/login&state=([0-9a-f]+)/) || [])[1];
if (!state) { console.log('history 页里没找到 state'); process.exit(1); }

// 3) login AJAX → code
const loginUrl = 'https://account-co.61.com/v3?r=AccountManager/login&state=' + state +
  '&duid=' + encodeURIComponent(d) + '&uid=' + uid + '&type=taomee';
const lj = await (await fetch(loginUrl, { headers: H() })).json();
if (lj.result !== 0) { console.log('login 失败:', JSON.stringify(lj).slice(0, 160)); process.exit(1); }
const code = (String(lj.data).match(/[?&]code=([^&]+)/) || [])[1];
if (!code) { console.log('login 返回里没有 code'); process.exit(1); }

// 4) code → token
const tr = await fetch('https://account-co.61.com/v3/?r=token/trans', {
  method: 'POST',
  headers: { ...H(), 'Content-Type': 'application/x-www-form-urlencoded', Origin: 'https://h5-seer.61.com' },
  body: `appid=20210906002&duid=${encodeURIComponent(d)}&code=${encodeURIComponent(code)}`,
});
const tj = await tr.json();
if (tj.result !== 0 || !tj.data?.token) { console.log('token/trans 失败:', JSON.stringify(tj).slice(0, 160)); process.exit(1); }
const token = tj.data.token;

// 5) 存 token（供 tokenStore 续期）+ 后续会话链
fs.writeFileSync(new URL('../data/token.json', import.meta.url), JSON.stringify({
  key: 'TAOMEESDK_TOKEN_20210906002',
  tokenString: token,
  expireDat: Date.now() + Number(tj.data.expire ?? 7200) * 1000,
  refreshTokenString: tj.data.refresh_token ?? '',
  uid, loginType: 'taomee', duid: d,
}, null, 2));

await wsAuthenticate(uid, token);
const gate = await onlineGate(uid, token);
const session = await convertToken(uid, token);
const g = /^([^/:]+)(\/[^:]*):(\d+)$/.exec(String(gate.text).trim());
const body = Buffer.from(fs.readFileSync(new URL('../data/login_template.bin', import.meta.url)));
session.copy(body, 0);
// 不写 0x4c：官方 1001 body 该处为 0，模板自带的 3002 在 0x52
const out = {
  uid,
  sessionHex: session.toString('hex'),
  host: g?.[1] ?? 'h5gy.61.com',
  port: 443,
  path: g?.[2] ?? '/wss_online_01/',
  serverId: Number(g?.[3] ?? 3002),
  bodyB64: body.toString('base64'),
};
fs.writeFileSync('login.json', JSON.stringify(out, null, 2));
console.log('ok uid=%d session=%s gate=%s%s (密码来源: %s)', uid, out.sessionHex, out.host, out.path, cred.source);
process.exit(0);