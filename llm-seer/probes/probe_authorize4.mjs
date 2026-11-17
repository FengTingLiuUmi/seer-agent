import { authenticate, UA, cookieString } from '../../seer-auto/src/login.js';
import { duid } from '../../seer-auto/src/auth.js';
const a=await authenticate('ACCOUNT',process.env.SEER_PASSWORD);
const d=duid(), ck=cookieString();
const H={'User-Agent':UA,Referer:'https://account-co.61.com/',Origin:'https://account-co.61.com',Cookie:ck};
const redir='https%3A%2F%2Faccount-co.61.com%2Fv3%2F%3Fr%3Dauthorization%2Fsuccess';
const st=Buffer.from(String(a.session)).toString('base64').replace(/=+$/,'');
const variants=[
 ['tad=unknown+st32', `&source=0&register=&bg=0&redirect_url=${redir}&tad=unknown&appid=20210906002&duid=${d}&scope=userinfo&state=${st}`],
 ['tad=none',         `&source=0&register=&bg=0&redirect_url=${redir}&tad=none&appid=20210906002&duid=${d}&scope=userinfo&state=${st}`],
 ['no duid tad',      `&source=0&register=&bg=0&redirect_url=${redir}&tad=unknown&appid=20210906002&scope=userinfo&state=${a.session}`],
];
for(const [n,t] of variants){
  const r=await fetch('https://account-co.61.com/v3/?r=authorization/authorize'+t,{headers:H,redirect:'manual'});
  const b=await r.text();
  const msg=(b.match(/data:\s*"([^"]{0,40})"/)||[])[1]||'';
  console.log('%-16s %s loc=%s msg=%s', n, r.status, (r.headers.get('location')||'').slice(0,60), msg);
}
process.exit(0);
