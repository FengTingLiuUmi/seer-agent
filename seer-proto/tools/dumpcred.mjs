// 取出密码写到临时文件（供宿主盲注键盘用），调用方读完即删
import fs from 'node:fs';
import { loadCredential } from './loadcred.mjs';

const out = process.argv[2];
const account = process.argv[3] || 'ACCOUNT';
const { password } = await loadCredential(account);
if (!password) {
  console.error('no password');
  process.exit(1);
}
fs.writeFileSync(out, password, { mode: 0o600 });
console.log('ok');