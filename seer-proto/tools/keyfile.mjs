// 主密钥读取：SEER_KEY 环境变量 > seer-proto/.secrets-key 文件（gitignore）
import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(new URL('..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'));
const KEYFILE = path.join(ROOT, '.secrets-key');

export function loadKey() {
  if (process.env.SEER_KEY) return process.env.SEER_KEY.trim();
  try {
    const k = fs.readFileSync(KEYFILE, 'utf8').trim();
    if (k) return k;
  } catch { /* ignore */ }
  return '';
}

export function saveKey(key) {
  fs.writeFileSync(KEYFILE, key.trim() + '\n', { mode: 0o600 });
}