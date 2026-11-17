import { authenticate, UA, cookieString } from '../../seer-auto/src/login.js';
import { duid } from '../../seer-auto/src/auth.js';
const a = await authenticate('ACCOUNT', process.env.SEER_PASSWORD);
const s=String(a.session), d=duid();
const h={'User-Agent':UA, Referer:'https://seerh5.61.com/','Origin':'https://seerh5.61.com','X-Requested-With':'XMLHttpRequest'};
const tries=[
 ['auth/success GET', `https://account-co.61.com/v3?r=authorization/success&code=${encodeURIComponent(s)}&appid=20210906002&duid=${encodeURIComponent(d)}`],
 ['auth/success POST',`https://account-co.61.com/v3/authorization/success`],
];
for(const [name,url] of tries){
  const r = name.endsWith('POST')
    ? await fetch(url,{method:'POST',headers:{...h,'Content-Type':'application/x-www-form-urlencoded'},body:`code=${encodeURIComponent(s)}&appid=20210906002&duid=${encodeURIComponent(d)}`})
    : await fetch(url,{headers:h});
  const t=await r.text();
  const clean=t.replace(/<script[\s\S]*?<\/script>/g,' ').replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim();
  console.log('%-18s %s | %s', name, r.status, clean.slice(0,140));
}
process.exit(0);
