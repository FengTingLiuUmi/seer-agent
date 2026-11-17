import { authenticate, exchangeToken } from '../../seer-auto/src/login.js';
import { wsAuthenticate, convertToken, onlineGate } from '../../seer-auto/src/auth.js';
const acct='ACCOUNT', pwd=process.env.SEER_PASSWORD;
const a = await authenticate(acct, pwd);
console.log('auth uid=%s session=%s...', a.uid, String(a.session).slice(0,8));
const t = await exchangeToken({account: acct, session: String(a.session)});
console.log('token/trans ->', String(t.token).slice(0,10)+'...', 'status', t.status);
try { const r = await wsAuthenticate(Number(a.uid), t.token); console.log('wsAuth ok', JSON.stringify(r).slice(0,80)); } catch(e){ console.log('wsAuth fail', e.message.slice(0,80)); }
try { const s = await convertToken(Number(a.uid), t.token); console.log('convert ok session=%s', s.toString('hex')); } catch(e){ console.log('convert fail', e.message.slice(0,80)); }
try { const g = await onlineGate(Number(a.uid), t.token); console.log('gate', g.text.trim().slice(0,40)); } catch(e){ console.log('gate fail', e.message.slice(0,60)); }
process.exit(0);
