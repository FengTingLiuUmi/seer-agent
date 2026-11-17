import { authenticate, UA, cookieString } from '../../seer-auto/src/login.js';
import { duid } from '../../seer-auto/src/auth.js';
const a = await authenticate('ACCOUNT', process.env.SEER_PASSWORD);
const uid=String(a.uid), rt=String(a.session), d=duid();
const url='https://account-co.61.com/v3/token/refresh';
const body=new URLSearchParams({appid:'20210906002',uid,duid:d,refresh_token:rt}).toString();
const base={ 'User-Agent':UA, Referer:'https://seerh5.61.com/' };
const variants=[
 ['form', {method:'POST', headers:{...base,'Content-Type':'application/x-www-form-urlencoded'}, body}],
 ['form+origin', {method:'POST', headers:{...base,'Content-Type':'application/x-www-form-urlencoded','Origin':'https://seerh5.61.com','X-Requested-With':'XMLHttpRequest'}, body}],
 ['json', {method:'POST', headers:{...base,'Content-Type':'application/json'}, body:JSON.stringify({appid:'20210906002',uid,duid:d,refresh_token:rt})}],
 ['get', {method:'GET', headers:base}],
];
for(const [name,opt] of variants){
  try{
    const r=await fetch(url,opt); const t=await r.text();
    const clean=t.replace(/<script[\s\S]*?<\/script>/g,' ').replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim();
    console.log('%-10s %s | %s', name, r.status, clean.slice(0,160));
  }catch(e){ console.log(name,'ERR',e.message); }
}
process.exit(0);
