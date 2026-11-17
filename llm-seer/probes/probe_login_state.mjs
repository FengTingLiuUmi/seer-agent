// 完整复刻雷小伊：history 页 → AccountManager/login&state= → 取 code → token/trans → token
import crypto from 'node:crypto';
import { authenticate, UA, cookieString } from '../../seer-auto/src/login.js';
import { duid } from '../../seer-auto/src/auth.js';

const pwd = process.env.SEER_PASSWORD;
const a = await authenticate('ACCOUNT', pwd);
const d = duid();
const H = () => ({ 'User-Agent': UA, Referer: 'https://h5-seer.61.com/', Cookie: cookieString() });

const redir = 'https%3A%2F%2Faccount-co.61.com%2Fv3%2F%3Fr%3Dauthorization%2Fsuccess';
const hist = 'https://account-co.61.com/v3/?r=AccountManager/history&duid=' + encodeURIComponent(d) +
  '&appid=20210906002&scope=userinfo&state=' + crypto.randomBytes(16).toString('hex') +
  '&source=0&register=&bg=0&redirect_url=' + redir;

const page = await (await fetch(hist, { headers: H() })).text();
const state = (page.match(/AccountManager\/login&state=([0-9a-f]+)/) || [])[1];
console.log('state:', state);
if (!state) { console.log('no state in page'); process.exit(1); }

const loginUrl = 'https://account-co.61.com/v3?r=AccountManager/login&state=' + state;
const r2 = await fetch(loginUrl, { headers: H(), redirect: 'manual' });
console.log('login ->', r2.status, 'loc:', (r2.headers.get('location') || '').slice(0, 200));
let loc = r2.headers.get('location') || '';
let code = (loc.match(/[?&]code=([^&]+)/) || [])[1];
if (!code) {
  const body = await r2.text();
  code = (body.match(/[?&]code=([0-9a-f]{16,})/) || [])[1] || '';
  console.log('body len', body.length, 'code from body:', code);
}
console.log('code:', code);
if (!code) process.exit(1);

const body = `appid=20210906002&duid=${encodeURIComponent(d)}&code=${encodeURIComponent(code)}`;
const r3 = await fetch('https://account-co.61.com/v3/?r=token/trans', {
  method: 'POST',
  headers: { ...H(), 'Content-Type': 'application/x-www-form-urlencoded', Origin: 'https://h5-seer.61.com' },
  body,
});
const t3 = await r3.text();
console.log('token/trans ->', r3.status, t3.slice(0, 300));