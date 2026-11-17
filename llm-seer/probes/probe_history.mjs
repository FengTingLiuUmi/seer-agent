// 按雷小伊反编译出来的 URL 结构，试 AccountManager/history 拿 code
import crypto from 'node:crypto';
import { authenticate, UA, cookieString } from '../../seer-auto/src/login.js';
import { duid } from '../../seer-auto/src/auth.js';

const acct = 'ACCOUNT';
const pwd = process.env.SEER_PASSWORD;
const a = await authenticate(acct, pwd);
const rand = () => crypto.randomBytes(0x20).toString('hex').slice(0, 32);
const d = duid();
const redir = 'https%3A%2F%2Faccount-co.61.com%2Fv3%2F%3Fr%3Dauthorization%2Fsuccess';

const url = 'https://account-co.61.com/v3/?r=AccountManager/history&duid=' + encodeURIComponent(d) +
  '&appid=20210906002&scope=userinfo&state=' + rand() +
  '&source=0&register=&bg=0&redirect_url=' + redir;

console.log('session uid=%s', a.uid);
const r = await fetch(url, {
  headers: {
    'User-Agent': UA, Referer: 'https://h5-seer.61.com/',
    Cookie: cookieString(),
  },
  redirect: 'manual',
});
console.log('status', r.status, 'loc', (r.headers.get('location') || '').slice(0, 160));
const t = await r.text();
const msg = (t.match(/data:\s*"([^"]{0,60})"/) || [])[1] || '';
console.log('len', t.length, 'msg', msg);
console.log(t.slice(0, 400).replace(/\s+/g, ' '));
const code = (url && t.match(/code=([0-9a-f]{8,})/)) ? t.match(/code=([0-9a-f]{8,})/)[1] : '';
console.log('code in html:', code);