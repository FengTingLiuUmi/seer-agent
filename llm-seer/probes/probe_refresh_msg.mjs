import { authenticate } from '../../seer-auto/src/login.js';
import { refreshToken } from '../../seer-auto/src/auth.js';
const a = await authenticate('ACCOUNT', process.env.SEER_PASSWORD);
try { const t = await refreshToken(Number(a.uid), String(a.session)); console.log('OK', JSON.stringify(t).slice(0,120)); }
catch (e) {
  const t = String(e.message);
  const txt = t.replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim();
  console.log('HTML MESSAGE:', txt.slice(0,300));
}
process.exit(0);
