// 登录链路（HTTP）：账号鉴权 → token 转换 → 取游戏网关
// 依据：官方客户端 login*.js 的请求写法 + 实测响应（见 docs/protocol.md）。
import crypto from 'node:crypto';

export const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0';
export const REFERER = 'https://seerh5.61.com/';
export const APPID = '20210906002';

export const md5 = (s) => crypto.createHash('md5').update(s, 'utf8').digest('hex');

// 极简 cookie jar：account-co 会在鉴权后下发 Set-Cookie，后续步骤要用
const jar = new Map();

function cookieHeader() {
  return [...jar.entries()].map(([k, v]) => `${k}=${v}`).join('; ');
}

function headers(extra = {}) {
  const h = { 'User-Agent': UA, Referer: REFERER, ...extra };
  const c = cookieHeader();
  if (c) h.Cookie = c;
  return h;
}

function absorbCookies(res) {
  const list = typeof res.headers.getSetCookie === 'function'
    ? res.headers.getSetCookie()
    : (res.headers.get('set-cookie') ? [res.headers.get('set-cookie')] : []);
  for (const raw of list) {
    const [pair] = raw.split(';');
    const i = pair.indexOf('=');
    if (i > 0) jar.set(pair.slice(0, i).trim(), pair.slice(i + 1).trim());
  }
}

export function clearCookies() {
  jar.clear();
}

export function cookieString() {
  return cookieHeader();
}

/** 1) 米米号 + 密码(MD5) 鉴权 → { uid, session } */
export async function authenticate(account, password) {
  const url = 'http://account-co.61.com/index.php?r=userIdentity/authenticate' +
    `&account=${encodeURIComponent(account)}&rememberAcc=false&passwd=${md5(password)}` +
    '&rememberPwd=true&vericode=&game=02&tad=none';
  const res = await fetch(url, { headers: headers() });
  absorbCookies(res);
  const text = await res.text();
  let data = {};
  try {
    const m = text.match(/\{[\s\S]*\}/);
    data = m ? JSON.parse(m[0]) : {};
  } catch {
    data = {};
  }
  return {
    uid: data?.data?.uid ?? data?.uid,
    session: data?.data?.session ?? data?.session,
    raw: text,
    status: res.status,
  };
}

/** 2) session → token（appid 来自客户端常量 20210906002） */
export async function exchangeToken({ account, session }) {
  const url = `https://account-co.61.com/v3/?r=token/trans&appid=${APPID}&duid=${encodeURIComponent(account)}`;
  const res = await fetch(url, {
    method: 'POST',
    headers: headers({ 'Content-Type': 'application/x-www-form-urlencoded' }),
    body: session ? `session=${encodeURIComponent(session)}` : '',
  });
  absorbCookies(res);
  const text = await res.text();
  return { token: text.trim(), raw: text, status: res.status };
}

/** 3) 取网关 IP:port（客户端 POST 空 body） */
export async function getGateway() {
  const url = 'https://seerh5login.61.com/online_gate?is_ssl=1';
  const res = await fetch(url, {
    method: 'POST',
    headers: headers({ 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' }),
    body: '',
  });
  absorbCookies(res);
  const text = (await res.text()).trim();
  // 实测返回形如 "h5gy.61.com/ws/:3001"（host + path + :port）
  let host, port, path = '/';
  const m3 = text.match(/^([^/:]+)(\/[^:]*)?:(\d{2,5})$/);
  if (m3) {
    host = m3[1];
    path = m3[2] || '/';
    port = m3[3];
  } else {
    const m2 = text.match(/(\d{1,3}(?:\.\d{1,3}){3}):(\d{2,5})/);
    host = m2?.[1];
    port = m2?.[2];
  }
  return { host, port, path, raw: text, status: res.status };
}

/** 完整流程；任一步失败都保留原始响应便于排查 */
export async function loginFlow(account, password, { onStep = () => {} } = {}) {
  clearCookies();
  const auth = await authenticate(account, password);
  onStep('authenticate', auth);
  if (!auth.uid) throw new Error('authenticate failed: ' + auth.raw.slice(0, 200));

  const tok = await exchangeToken({ account, session: auth.session });
  onStep('token', tok);

  const gate = await getGateway();
  onStep('gateway', gate);
  if (!gate.host) throw new Error('gateway parse failed: ' + gate.raw.slice(0, 200));

  return { uid: Number(auth.uid), session: auth.session, token: tok.token, ...gate };
}

