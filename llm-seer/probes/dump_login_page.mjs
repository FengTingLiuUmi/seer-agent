import fs from 'node:fs';
import crypto from 'node:crypto';
import { authenticate, UA, cookieString } from '../../seer-auto/src/login.js';
import { duid } from '../../seer-auto/src/auth.js';
const a=await authenticate('ACCOUNT',process.env.SEER_PASSWORD);
const d=duid();
const redir='https%3A%2F%2Faccount-co.61.com%2Fv3%2F%3Fr%3Dauthorization%2Fsuccess';
const url='https://account-co.61.com/v3/?r=AccountManager/history&duid='+encodeURIComponent(d)+
 '&appid=20210906002&scope=userinfo&state='+crypto.randomBytes(16).toString('hex')+
 '&source=0&register=&bg=0&redirect_url='+redir;
const r=await fetch(url,{headers:{'User-Agent':UA,Referer:'https://h5-seer.61.com/',Cookie:cookieString()}});
const t=await r.text();
fs.writeFileSync('_login_page.html',t);
console.log(t);
