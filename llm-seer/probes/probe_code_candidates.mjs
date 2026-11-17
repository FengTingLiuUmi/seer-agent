import { authenticate, UA, cookieString } from '../../seer-auto/src/login.js';
import { duid } from '../../seer-auto/src/auth.js';
const a=await authenticate('ACCOUNT',process.env.SEER_PASSWORD);
const s=String(a.session), uid=String(a.uid), d=duid();
const b64=(x)=>Buffer.from(x).toString('base64').replace(/=+$/,'');
const codes=[['raw',s],['b64(session)',b64(s)],['b64(uid:session)',b64(uid+':'+s)],['b64(uid|session)',b64(uid+'|'+s)]];
const h={'User-Agent':UA,Referer:'https://seerh5.61.com/','Origin':'https://seerh5.61.com','X-Requested-With':'XMLHttpRequest',Cookie:cookieString()};
for(const [name,code] of codes){
  const u='https://account-co.61.com/v3?r=authorization/success&code='+encodeURIComponent(code)+'&appid=20210906002&duid='+encodeURIComponent(d);
  const r=await fetch(u,{headers:h,redirect:'manual'});
  const t=await r.text();
  console.log('%-16s %s | %s', name, r.status, t.replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim().slice(0,110));
}
process.exit(0);
