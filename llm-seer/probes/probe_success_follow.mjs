import { authenticate, UA, cookieString } from '../../seer-auto/src/login.js';
import { duid } from '../../seer-auto/src/auth.js';
const a=await authenticate('ACCOUNT',process.env.SEER_PASSWORD);
const s=String(a.session), d=duid();
const h={'User-Agent':UA,Referer:'https://seerh5.61.com/','X-Requested-With':'XMLHttpRequest',Cookie:cookieString()};
for (const [n,u] of [
  ['success+code(session)', `https://account-co.61.com/v3?r=authorization/success&code=${s}&appid=20210906002&duid=${d}`],
  ['success+sid(session)', `https://account-co.61.com/v3/authorization/success?sid=${s}&appid=20210906002&duid=${d}`],
]) {
  const r=await fetch(u,{headers:h,redirect:'follow'});
  const t=await r.text();
  const cfg=(t.match(/TAOMEE_LOGIN_CONFIGURE\s*=\s*(\{[\s\S]{0,300}?\});/)||[])[1]||'';
  console.log('%-22s %s final=%s cfg=%s', n, r.status, r.url.slice(0,90), cfg.slice(0,120));
}
process.exit(0);
