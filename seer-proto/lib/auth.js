// 完整登录链（依据 2026-11-12 抓包）：
//   HTTP authenticate → token/refresh → account ws 认证
//   → online_gate(seeronlinegw) → token/convert → login_gate(105/109/111) → 游戏网关(1001)
import crypto from 'node:crypto';
import fs from 'node:fs';
import { RawWebSocket } from './ws.js';
import { authenticate, cookieString, UA, APPID, clearCookies } from './login.js';
import { Encoder } from './protocol.js';

const DUID_FILE = new URL('../data/duid.txt', import.meta.url);
const UA_STR = UA;

export function duid() {
  try {
    return fs.readFileSync(DUID_FILE, 'utf8').trim();
  } catch {
    const d = crypto.randomBytes(16).toString('hex');
    fs.mkdirSync(new URL('../data/', import.meta.url), { recursive: true });
    fs.writeFileSync(DUID_FILE, d);
    return d;
  }
}

function headers(extra = {}) {
  const h = { 'User-Agent': UA_STR, Referer: 'https://h5-seer.61.com/', ...extra };
  const c = cookieString();
  if (c) h.Cookie = c;
  return h;
}

async function postForm(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: headers({ 'Content-Type': 'application/x-www-form-urlencoded' }),
    body: new URLSearchParams(body).toString(),
  });
  const text = await res.text();
  let j = null;
  try { j = JSON.parse(text); } catch { /* ignore */ }
  return { status: res.status, text, json: j };
}

/** 1) 账号鉴权 → 拿 refresh_token（实测 authenticate 返回的 session 即 refresh_token） */
export async function authAccount(account, password) {
  clearCookies();
  const a = await authenticate(account, password);
  if (!a.uid) throw new Error('authenticate 失败: ' + a.raw.slice(0, 200));
  return { uid: Number(a.uid), refreshToken: String(a.session) };
}

/** 2) refresh_token → token */
export async function refreshToken(uid, refresh) {
  const r = await postForm('https://account-co.61.com/v3/token/refresh',
    { appid: APPID, uid: String(uid), duid: duid(), refresh_token: refresh });
  const data = r.json?.data;
  if (!data?.token) throw new Error('token/refresh 失败: ' + r.text.slice(0, 200));
  return data; // { uid, token, expire, refresh_token, time }
}

/** 3) account ws 认证 */
export async function wsAuthenticate(uid, token) {
  const ws = new RawWebSocket();
  const result = await new Promise((resolve, reject) => {
    ws.on('open', () => {
      ws.sendText(JSON.stringify({
        r: 'common/authentication', appid: APPID, duid: duid(), uid: String(uid), token, tad: '#https://seerh5.61.com/',
      }));
    });
    ws.on('message', (buf) => {
      try {
        const j = JSON.parse(Buffer.from(buf).toString('utf8'));
        if (j.r === 'common/authentication') resolve(j);
      } catch { /* ignore */ }
    });
    ws.on('error', reject);
    setTimeout(() => reject(new Error('账号认证超时')), 8000);
    ws.connect('wss://account-co.61.com/v3/ws/', headers({ Origin: 'https://h5-seer.61.com' })).catch(reject);
  });
  ws.close();
  if (result.result !== 0) throw new Error('账号 ws 认证失败: ' + JSON.stringify(result).slice(0, 200));
  return result;
}

/** 4) 取网关（seeronlinegw） */
export async function onlineGate(uid, token) {
  const t = Math.floor(Date.now() / 1000);
  const res = await fetch(`https://seeronlinegw.61.com/online_gate/?is_ssl=1&t=${t}`, { headers: headers() });
  const text = (await res.text()).trim();
  return { text, json: (() => { try { return JSON.parse(text); } catch { return null; } })() };
}

/** 5) token → 游戏会话（32 hex） */
export async function convertToken(uid, token) {
  const r = await postForm(`https://account-co.61.com/v3/token/convert?t=${Math.floor(Date.now() / 1000)}`,
    { appid: APPID, uid: String(uid), duid: duid(), token });
  const hex = typeof r.json?.data === 'string' ? r.json.data : null;
  if (!hex) throw new Error('token/convert 失败: ' + r.text.slice(0, 200));
  return Buffer.from(hex, 'hex');
}

/** 6) 登录网关：105 / 111 / 109 */
export async function loginGate(uid, sessionBytes) {
  const ws = new RawWebSocket();
  const enc = new Encoder(uid);
  const replies = [];
  ws.on('open', () => {
    ws.send(enc.pack(105, [sessionBytes, 0]));
    setTimeout(() => { try { ws.send(enc.pack(111, [])); ws.send(enc.pack(109, [sessionBytes, 0])); } catch { /* ignore */ } }, 300);
  });
  await new Promise((resolve, reject) => {
    ws.on('message', (buf) => {
      const f = Buffer.from(buf);
      if (f.length >= 17) replies.push({ cmd: f.readUInt32BE(5), len: f.readUInt32BE(0) });
    });
    ws.on('error', reject);
    ws.connect('wss://seerh5login.61.com/login_gate_webgl', headers({ Origin: 'https://h5-seer.61.com' })).catch(reject);
    setTimeout(resolve, 2500);
  });
  return { ws, replies };
}

/** 7) 游戏网关：1001 */
export async function enterGame(uid, sessionBytes, gate) {
  const tpl = Buffer.from(fs.readFileSync(new URL('../data/login_template.bin', import.meta.url)));
  sessionBytes.copy(tpl, 0);
  if (gate) tpl.writeUInt16BE(Number(gate) & 0xffff, 0x4c);
  const ws = new RawWebSocket();
  const enc = new Encoder(uid);
  const frames = [];
  // 从 online_gate 的文本（如 h5gy.61.com/wss_online_02/:3002）推 URL 与 gate 号
  const m = /^([^/:]+)(\/[^:]*):(\d+)$/.exec(String(gate?.text ?? '').trim());
  const host = m?.[1] ?? 'h5gy.61.com';
  const pathPart = m?.[2] ?? '/wss_online_02/';
  const gateId = m?.[3];
  if (gateId) tpl.writeUInt16BE(Number(gateId) & 0xffff, 0x4c);
  console.log('[game] url=wss://%s%s gate=%s', host, pathPart, gateId);
  ws.on('open', () => ws.send(enc.pack(1001, [tpl])));
  await new Promise((resolve, reject) => {
    ws.on('message', (buf) => {
      const f = Buffer.from(buf);
      if (f.length >= 17) frames.push({ cmd: f.readUInt32BE(5), len: f.readUInt32BE(0), body: f.subarray(17, 17 + 48).toString('hex') });
      if (f.readUInt32BE(5) === 1001) { console.log('[game] got 1001'); resolve(); }
    });
    ws.on('error', reject);
    ws.connect(`wss://${host}${pathPart}`, headers({ Origin: 'https://h5-seer.61.com' })).catch(reject);
    setTimeout(resolve, 15000);
  });
  ws.close();
  return frames;
}

/** 一把梭 */
export async function fullLogin(account, password, log = console.log) {
  const a = await authAccount(account, password);
  log('1) authenticate uid=%s refresh=%s…', a.uid, a.refreshToken.slice(0, 8));

  const tok = await refreshToken(a.uid, a.refreshToken);
  log('2) token=%s… expire=%ds', tok.token.slice(0, 8), tok.expire);

  const au = await wsAuthenticate(a.uid, tok.token);
  log('3) account ws 认证 result=%s', au.result);

  const gate = await onlineGate(a.uid, tok.token);
  log('4) online_gate → %s', String(gate.text).slice(0, 80));

  const session = await convertToken(a.uid, tok.token);
  log('5) token/convert → session %s', session.toString('hex'));

  const g1 = await loginGate(a.uid, session);
  log('6) login_gate replies %j', g1);

  const g2 = await enterGame(a.uid, session);
  log('7) game frames %j', g2);
  return { uid: a.uid, token: tok.token, session };
}



