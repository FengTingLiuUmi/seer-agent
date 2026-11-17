import { authenticate, UA, cookieString } from '../../seer-auto/src/login.js';
import { duid } from '../../seer-auto/src/auth.js';
const a=await authenticate('ACCOUNT',process.env.SEER_PASSWORD);
const ck=cookieString(), d=duid();
const H={'User-Agent':UA,Referer:'https://seerh5.61.com/',Cookie:ck};
const redir='https%3A%2F%2Faccount-co.61.com%2Fv3%2F%3Fr%3Dauthorization%2Fsuccess';
const tails=[
 ['state=rand', `&source=0&register=&bg=0&redirect_url=${redir}&tad=unknown&appid=20210906002&scope=userinfo&state=rnd123`],
 ['state empty', `&source=0&register=&bg=0&redirect_url=${redir}&tad=unknown&appid=20210906002&scope=userinfo&state=`],
];
for (const [n,t] of tails) {
  for (const pre of ['https://account-co.61.com/v3/?r=authorization/authorize', 'https://account-co.61.com/v3/?r=authorization/authorize&duid='+encodeURIComponent(d)]) {
    const r=await fetch(pre+t,{headers:H,redirect:'manual'});
    const body=await r.text();
    const clean=body.replace(/<script[\s\S]*?<\/script>/g,' ').replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim();
    console.log('%-12s %s loc=%s | %s', n, r.status, (r.headers.get('location')||'').slice(0,70), clean.slice(0,90));
  }
}
process.exit(0);
