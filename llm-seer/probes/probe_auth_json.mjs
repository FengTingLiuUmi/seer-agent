import { authenticate } from '../../seer-auto/src/login.js';
const a = await authenticate('ACCOUNT', process.env.SEER_PASSWORD);
const j = JSON.parse(a.raw.match(/\{[\s\S]*\}/)[0]);
console.log('keys:', Object.keys(j), '| data keys:', j.data && Object.keys(j.data));
const d = j.data || {};
for (const k of Object.keys(d)) {
  const v = String(d[k]);
  console.log('  %-16s %s', k, v.length > 40 ? v.slice(0, 40) + '…(' + v.length + ')' : v);
}
console.log('cookies:', (await import('../../seer-auto/src/login.js')).cookieString().slice(0, 120));
process.exit(0);
