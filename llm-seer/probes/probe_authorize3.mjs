import { authenticate, UA, cookieString } from '../../seer-auto/src/login.js';
const a=await authenticate('ACCOUNT',process.env.SEER_PASSWORD);
const redir='https%3A%2F%2Faccount-co.61.com%2Fv3%2F%3Fr%3Dauthorization%2Fsuccess';
const u='https://account-co.61.com/v3/?r=authorization/authorize'+`&source=0&register=&bg=0&redirect_url=${redir}&tad=unknown&appid=20210906002&scope=userinfo&state=rnd`;
const r=await fetch(u,{headers:{'User-Agent':UA,Referer:'https://seerh5.61.com/',Cookie:cookieString()}});
const t=await r.text();
console.log('status',r.status,'len',t.length);
console.log(t.slice(0,700).replace(/\s+/g,' '));
process.exit(0);
