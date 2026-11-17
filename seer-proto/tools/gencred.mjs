// 生成加密凭据：secrets/cred.enc.json（可入库，主密钥 SEER_KEY 不入库）
//   node tools/gencred.mjs               # 交互式：从环境变量/account.ini 取值
//   SEER_KEY=xxx SEER_PASSWORD=yyy node tools/gencred.mjs ACCOUNT
import fs from 'node:fs';
import crypto from 'node:crypto';
import path from 'node:path';
import { loadKey } from './keyfile.mjs';

const ROOT = path.resolve(new URL('..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'));
const account = process.argv[2] ?? 'ACCOUNT';
const key = loadKey();
if (!key) {
  console.log('需要主密钥：SEER_KEY 或 seer-proto/.secrets-key');
  process.exit(1);
}

let pwd = process.env.SEER_PASSWORD;
if (!pwd) {
  const ini = 'F:/seer/account.ini';
  if (fs.existsSync(ini)) {
    const m = new RegExp('\\[' + account + '\\]\\s*\\n\\s*pass\\s*=\\s*(\\S+)').exec(fs.readFileSync(ini, 'utf8'));
    if (m) pwd = m[1];
  }
}
if (!pwd) { console.log('没有密码：设置 SEER_PASSWORD'); process.exit(1); }

const N = 32768, r = 8, p = 1;
const salt = crypto.randomBytes(16);
const iv = crypto.randomBytes(12);
const dk = crypto.scryptSync(key, salt, 32, { N, r, p, maxmem: 64 * 1024 * 1024 });
const cipher = crypto.createCipheriv('aes-256-gcm', dk, iv);
const data = JSON.stringify({ account, password: pwd, [account]: pwd });
const enc = Buffer.concat([cipher.update(data, 'utf8'), cipher.final()]);
const out = {
  v: 1, kdf: 'scrypt', N, r, p,
  salt: salt.toString('base64'),
  cipher: 'aes-256-gcm',
  iv: iv.toString('base64'),
  tag: cipher.getAuthTag().toString('base64'),
  data: enc.toString('base64'),
};
fs.mkdirSync(path.join(ROOT, 'secrets'), { recursive: true });
fs.writeFileSync(path.join(ROOT, 'secrets', 'cred.enc.json'), JSON.stringify(out, null, 2));
console.log('已生成 secrets/cred.enc.json（%d 字节密文）；记得 .gitignore 里只放行它、排除 SEER_KEY', enc.length);