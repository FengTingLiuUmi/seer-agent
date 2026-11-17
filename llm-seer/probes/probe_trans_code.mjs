import { authenticate, UA } from '../../seer-auto/src/login.js';
import { duid } from '../../seer-auto/src/auth.js';
const a = await authenticate('ACCOUNT', process.env.SEER_PASSWORD);
const s=String(a.session), d=duid();
const H={'User-Agent':UA, Referer:'https://seerh5.61.com/','Origin':'https://seerh5.61.com','X-Requested-With':'XMLHttpRequest','Content-Type':'application/x-www-form-urlencoded'};
const base='https://account-co.61.com/v3/?r=token/trans&appid=20210906002&duid='+encodeURIComponent(d);
for(const [name,body] of [
 ['code=',`code=${encodeURIComponent(s)}`],
 ['code=&session',`code=${encodeURIComponent(s)}&session=${encodeURIComponent(s)}`],
 ['code=&uid',`code=${encodeURIComponent(s)}&uid=${a.uid}`],
]){
  const r=await fetch(base,{method:'POST',headers:H,body}); const t=await r.text();
  const clean=t.replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim();
  console.log('%-16s %s | %s', name, r.status, clean.slice(0,120));
}
process.exit(0);
