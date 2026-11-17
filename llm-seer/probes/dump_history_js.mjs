import fs from 'node:fs';
const u='https://support-res.61.com/account.61.com/api/js/history/history.118078ca.js';
const t=await (await fetch(u)).text();
fs.writeFileSync('_history.js',t);
console.log('len',t.length);
for (const pat of ['select__item','AccountManager/login','location.href','location.replace','window.open','code=']) {
  const i=t.indexOf(pat);
  console.log('==',pat,i);
  if(i>0) console.log('   ', t.slice(Math.max(0,i-200), i+220).replace(/\s+/g,' ').slice(0,400));
}
