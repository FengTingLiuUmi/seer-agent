// token 存取与自动续期（refresh_token 2 小时一换）
// token 来源：tools/pull_token.mjs 从浏览器 localStorage 读出，存 data/token.json
import fs from 'node:fs';
import path from 'node:path';

const FILE = new URL('../data/token.json', import.meta.url);
const REFRESH_URL = 'https://account-co.61.com/v3/token/refresh';
const APPID = '20210906002';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0';

export function loadToken() {
  try {
    return JSON.parse(fs.readFileSync(FILE, 'utf8'));
  } catch {
    return null;
  }
}

export function saveToken(t) {
  fs.mkdirSync(path.dirname(FILE.pathname.replace(/^\/([A-Za-z]:)/, '$1')), { recursive: true });
  fs.writeFileSync(FILE, JSON.stringify(t, null, 2));
}

/** 剩余有效期（秒） */
export function remaining(t) {
  return Math.round((Number(t?.expireDat ?? 0) - Date.now()) / 1000);
}

async function refresh(t) {
  const body = new URLSearchParams({
    appid: APPID,
    uid: String(t.uid),
    duid: t.duid ?? '',
    refresh_token: String(t.refreshTokenString),
  }).toString();
  const res = await fetch(REFRESH_URL, {
    method: 'POST',
    headers: {
      'User-Agent': UA,
      Referer: 'https://h5-seer.61.com/',
      Accept: 'application/json',
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body,
  });
  const text = await res.text();
  let j = null;
  try { j = JSON.parse(text); } catch { /* html */ }
  if (!j || j.result !== 0 || !j.data?.token) {
    throw new Error('refresh 失败（需重新授权）: ' + text.slice(0, 160));
  }
  const d = j.data;
  return {
    ...t,
    tokenString: d.token,
    refreshTokenString: d.refresh_token ?? t.refreshTokenString,
    expireDat: Date.now() + Number(d.expire ?? 7200) * 1000,
    uid: d.uid ?? t.uid,
    loginType: d.login_type ?? t.loginType,
  };
}

/** 需要时自动续期；失败抛错，提示重新从浏览器取 token */
export async function ensureToken(log = () => {}) {
  const t = loadToken();
  if (!t) throw new Error('没有 token：先运行 node tools/pull_token.mjs（浏览器登录后）');
  const left = remaining(t);
  if (left > 60) return t;
  log('token 剩余 %ds，自动续期…', left);
  const next = await refresh(t);
  saveToken(next);
  log('续期成功，剩余 %ds', remaining(next));
  return next;
}