// 复刻 history 页的登录 AJAX：AccountManager/login + duid/uid/type → 返回带 code 的 URL
import crypto from 'node:crypto';
import { authenticate, UA, cookieString } from '../../seer-auto/src/login.js';
import { duid } from '../../seer-auto/src/auth.js';

await authenticate('ACCOUNT', process.env.SEER_PASSWORD);
const d = duid();
const H = { 'User-Agent': UA, Referer: 'https://h5-seer.61.com/', Cookie: cookieString(), 'X-Requested-With': 'XMLHttpRequest' };

const redir = 'https%3A%2F%2Faccount-co.61.com%2Fv3%2F%3Fr%3Dauthorization%2Fsuccess';
const hist = 'https://account-co.61.com/v3/?r=AccountManager/history&duid=' + encodeURIComponent(d) +
  '&appid=20210906002&scope=userinfo&state=' + crypto.randomBytes(16).toString('hex') +
  '&source=0&register=&bg=0&redirect_url=' + redir;
const page = await (await fetch(hist, { headers: H })).text();
const state = (page.match(/AccountManager\/login&state=([0-9a-f]+)/) || [])[1];
console.log('state', state);

const loginUrl = 'https://account-co.61.com/v3?r=AccountManager/login&state=' + state +
  '&duid=' + encodeURIComponent(d) + '&uid=ACCOUNT&type=taomee';
const r = await fetch(loginUrl, { headers: H });
const t = await r.text();
console.log('login ajax ->', r.status, t.slice(0, 300));

let data = '';
try { data = JSON.parse(t).data || ''; } catch { /* ignore */ }
console.log('data url:', data.slice(0, 200));
const code = (data.match(/[?&]code=([^&]+)/) || [])[1];
console.log('code:', code);
if (!code) process.exit(1);

// token/trans
const body = `appid=20210906002&duid=${encodeURIComponent(d)}&code=${encodeURIComponent(code)}`;
const tr = await fetch('https://account-co.61.com/v3/?r=token/trans', {
  method: 'POST',
  headers: { ...H, 'Content-Type': 'application/x-www-form-urlencoded', Origin: 'https://h5-seer.61.com' },
  body,
});
const tt = await tr.text();
console.log('token/trans ->', tr.status, tt.slice(0, 300));