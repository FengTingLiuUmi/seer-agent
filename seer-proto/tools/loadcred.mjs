// 凭据加载：SEER_PASSWORD > secrets/cred.enc.json（SEER_KEY 解密）> F:\seer\account.ini
// 明文只在内存里存在，不落盘、不打印。
import fs from 'node:fs';
import crypto from 'node:crypto';
import path from 'node:path';
import { loadKey } from './keyfile.mjs';

const ROOT = path.resolve(new URL('..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'));
const CRED = path.join(ROOT, 'secrets', 'cred.enc.json');

export async function loadCredential(account) {
  if (process.env.SEER_PASSWORD) {
    return { password: process.env.SEER_PASSWORD, source: 'env' };
  }
  if (fs.existsSync(CRED)) {
    const key = loadKey();
    if (!key) throw new Error('存在 cred.enc.json 但缺少主密钥（SEER_KEY 或 .secrets-key）');
    const j = JSON.parse(fs.readFileSync(CRED, 'utf8'));
    const dk = crypto.scryptSync(key, Buffer.from(j.salt, 'base64'), 32, { N: j.N, r: j.r, p: j.p, maxmem: 64 * 1024 * 1024 });
    const dec = crypto.createDecipheriv('aes-256-gcm', dk, Buffer.from(j.iv, 'base64'));
    dec.setAuthTag(Buffer.from(j.tag, 'base64'));
    const plain = Buffer.concat([dec.update(Buffer.from(j.data, 'base64')), dec.final()]).toString('utf8');
    const obj = JSON.parse(plain);
    const pwd = obj[account] ?? obj.password;
    if (!pwd) throw new Error('cred.enc.json 中没有该账号');
    return { password: pwd, source: 'cred.enc.json' };
  }
  // 本地开发兜底：仓库外的启动器配置
  const ini = 'F:/seer/account.ini';
  if (fs.existsSync(ini)) {
    const t = fs.readFileSync(ini, 'utf8');
    const m = new RegExp('\\[' + account + '\\]\\s*\\n\\s*pass\\s*=\\s*(\\S+)').exec(t);
    if (m) return { password: m[1], source: 'account.ini' };
  }
  return { password: '', source: 'none' };
}