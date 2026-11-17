import { authenticate, UA, cookieString } from '../../seer-auto/src/login.js';
import { duid } from '../../seer-auto/src/auth.js';
const a = await authenticate('ACCOUNT', process.env.SEER_PASSWORD);
const uid=String(a.uid), s=String(a.session), d=duid();
const url='https://account-co.61.com/v3/?r=token/trans&appid=20210906002&duid='+encodeURIComponent(d);
const h={'User-Agent':UA, Referer:'https://seerh5.61.com/','Content-Type':'application/x-www-form-urlencoded',
         'Origin':'https://seerh5.61.com','X-Requested-With':'XMLHttpRequest'};
for (const [name, opt] of [
  ['trans session', {method:'POST', headers:h, body:`session=${encodeURIComponent(s)}`}],
  ['trans token',   {method:'POST', headers:h, body:`session=${encodeURIComponent(s)}&uid=${uid}`}],
  ['trans plain',   {method:'POST', headers:h}],
]) {
  const r=await fetch(url,opt); const t=await r.text();
  const clean=t.replace(/<script[\s\S]*?<\/script>/g,' ').replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim();
  console.log('%-14s %s | %s', name, r.status, clean.slice(0,120));
}
process.exit(0);
