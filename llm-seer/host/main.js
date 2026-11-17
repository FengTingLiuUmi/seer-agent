// seer Flash 可视化宿主（Electron 11 32-bit + Pepper Flash 15）
//
// 结构：
//   Electron 窗口（渲染 Flash） + 本机控制桥 :7830
//     GET  /                 新登录界面（launcher）
//     GET  /state            页面/窗口/Flash 状态
//     GET  /shot.png         当前画面（capturePage，含 Flash 内容）
//     POST /login            {account,password,mode} → 载入游戏（可选盲输入）
//     POST /load             {url}
//     POST /click            {x,y,clicks?}
//     POST /key              {key:"Tab"|"Enter"|"A"|"ArrowLeft"|...}
//     POST /type             {text}       逐字符输入（含中文：走 insertText 回退）
//     POST /eval             {code}       页面内执行 JS
//     POST /resize           {w,h}
//
// 运行：electron.exe . --ppapi-flash-path=<dll> --ppapi-flash-version=15.0.0.152
// 环境：SEER_GAME_URL（默认本地站 index.html）、SEER_LAUNCHER=0 可跳过登录页
const { app, BrowserWindow } = require('electron');
const path = require('path');
const fs = require('fs');
const http = require('http');

const FLASH_DLL = process.env.SEER_FLASH_DLL ||
  'F:\\SeerLauncher\\resources\\app.asar.unpacked\\plugins\\pepflashplayer32_15_0_0_152.dll';
const FLASH_VER = process.env.SEER_FLASH_VER || '15.0.0.152';
const BRIDGE_PORT = Number(process.env.SEER_BRIDGE_PORT || 7830);
const GAME_URL = process.env.SEER_GAME_URL || 'http://127.0.0.1:8001/index.html';
const SHOW_LAUNCHER = process.env.SEER_LAUNCHER !== '0';
const LOGF = path.join(__dirname, 'host-electron.log');

function hlog() {
  try {
    fs.appendFileSync(LOGF, new Date().toISOString() + ' ' +
      Array.prototype.slice.call(arguments).join(' ') + '\n');
  } catch (e) { }
}

app.commandLine.appendSwitch('ppapi-flash-path', FLASH_DLL);
app.commandLine.appendSwitch('ppapi-flash-version', FLASH_VER);
app.commandLine.appendSwitch('enable-plugins');
app.commandLine.appendSwitch('allow-outdated-plugins');
app.commandLine.appendSwitch('disable-http-cache');
app.commandLine.appendSwitch('disable-features', 'FlashDeprecationWarning,ForceFlashLimits');
if (process.env.SEER_NO_SANDBOX !== '0') app.commandLine.appendSwitch('no-sandbox');

let win = null;

function createWindow() {
  win = new BrowserWindow({
    width: 1010,
    height: 720,
    backgroundColor: '#070c14',
    title: '赛尔号 · 登录器',
    show: true,
    webPreferences: {
      plugins: true,
      nodeIntegration: false,
      contextIsolation: false,
      backgroundThrottling: false,
      enableRemoteModule: false,
    },
  });
  win.setMenuBarVisibility(false);
  if (SHOW_LAUNCHER) {
    win.loadURL('http://127.0.0.1:' + BRIDGE_PORT + '/');
  } else {
    win.loadURL(GAME_URL);
  }
  win.webContents.on('did-finish-load', () => {
    hlog('[host] loaded', win.webContents.getURL());
  });
  win.webContents.on('console-message', (e, level, msg) => {
    if (level >= 2) hlog('[page]', String(msg).slice(0, 240));
  });
}

// ---------------------------------------------------------------- 画面/输入

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function shot() {
  const img = await win.webContents.capturePage();
  const size = img.getSize();
  return { png: img.toPNG(), width: size.width, height: size.height };
}

function focusWin() {
  try { win.show(); win.focus(); win.webContents.focus(); } catch (e) { }
}

async function click(x, y, clicks) {
  focusWin();
  const n = Math.max(1, Math.min(3, clicks || 1));
  const ev = (type, clickCount) => ({
    type, x: Math.round(x), y: Math.round(y), button: 'left', clickCount,
  });
  for (let i = 1; i <= n; i++) {
    win.webContents.sendInputEvent(ev('mouseDown', i));
    await sleep(30);
    win.webContents.sendInputEvent(ev('mouseUp', i));
    await sleep(60);
  }
  return { ok: true, x, y, clicks: n };
}

const KEYCODES = {
  tab: 'Tab', enter: 'Return', return: 'Return', esc: 'Escape', escape: 'Escape',
  space: 'Space', backspace: 'Backspace', delete: 'Delete', up: 'Up', down: 'Down',
  left: 'Left', right: 'Right', home: 'Home', end: 'End', pageup: 'Prior', pagedown: 'Next',
};

function normKey(k) {
  const s = String(k || '').replace(/^\{|\}$/g, '');
  const low = s.toLowerCase();
  if (KEYCODES[low]) return KEYCODES[low];
  if (/^(f([1-9]|1[0-2]))$/i.test(s)) return s.toUpperCase();
  if (s.length === 1) return s.toUpperCase();
  return s;
}

async function key(k) {
  focusWin();
  const code = normKey(k);
  win.webContents.sendInputEvent({ type: 'keyDown', keyCode: code });
  await sleep(20);
  win.webContents.sendInputEvent({ type: 'char', keyCode: code });
  await sleep(20);
  win.webContents.sendInputEvent({ type: 'keyUp', keyCode: code });
  await sleep(40);
  return { ok: true, key: code };
}

async function type(text) {
  focusWin();
  const s = String(text == null ? '' : text);
  for (const ch of s) {
    if (ch === '\n' || ch === '\r') { await key('Enter'); continue; }
    if (ch === '\t') { await key('Tab'); continue; }
    if (/^[\x20-\x7e]$/.test(ch)) {
      win.webContents.sendInputEvent({ type: 'keyDown', keyCode: ch });
      win.webContents.sendInputEvent({ type: 'char', keyCode: ch });
      win.webContents.sendInputEvent({ type: 'keyUp', keyCode: ch });
      await sleep(35);
    } else {
      // 非 ASCII：insertText（Flash 文本框通常也能收到）
      try { win.webContents.insertText(ch); } catch (e) { }
      await sleep(35);
    }
  }
  return { ok: true, typed: s.length };
}

async function loadURL(url) {
  win.loadURL(url);
  await new Promise((resolve) => {
    const done = () => resolve();
    win.webContents.once('did-finish-load', done);
    setTimeout(done, 15000);
  });
  return { ok: true, url: win.webContents.getURL() };
}

async function pageState() {
  try {
    return await win.webContents.executeJavaScript(`(function(){
      var o = document.querySelector('embed,object');
      var cb = false, props = [];
      try {
        cb = !!(o && o.startWebSessionLogin);
        var names = ['PercentLoaded','IsPlaying','TotalFrames','CurrentFrame','startWebSessionLogin','getAd','get_uid"];
        for (var i=0;i<names.length;i++){ var t='-';
          try { var v=o[names[i]]; t=(typeof v==='function')?'fn':(v===undefined?'undef':typeof v); } catch(e){ t='err'; }
          props.push(names[i]+':'+t);
        }
      } catch (e) { }
      var d = document.getElementById('dbg');
      return JSON.stringify({
        url: location.href, title: document.title,
        docW: document.documentElement.clientWidth, docH: document.documentElement.clientHeight,
        flash: o ? { tag: o.tagName, id: o.id || '', cb: cb, props: props } : null,
        mime: !!(navigator.mimeTypes && navigator.mimeTypes['application/x-shockwave-flash']),
        hits: (window.__hits || []).slice(-10),
        dbg: d ? d.textContent : ''
      });
    })()`, true);
  } catch (e) {
    return JSON.stringify({ error: e.message, url: win.webContents.getURL() });
  }
}

// ---------------------------------------------------------------- 登录页

const LAUNCHER_HTML = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>赛尔号 · 登录器</title>
<style>
*{box-sizing:border-box}html,body{height:100%;margin:0}
body{font:14px/1.6 "Microsoft YaHei UI",system-ui,sans-serif;color:#dbe7f5;display:flex;align-items:center;justify-content:center;
  background:radial-gradient(900px 500px at 20% -10%,#123049,transparent 60%),radial-gradient(700px 400px at 110% 120%,#1a2740,transparent 55%),#070c14}
.card{width:360px;padding:26px;border-radius:16px;border:1px solid #1e3348;background:linear-gradient(180deg,#111d2f,#0d1624);
  box-shadow:0 24px 60px rgba(0,0,0,.6)}
.brand{display:flex;gap:12px;align-items:center;margin-bottom:18px}
.logo{width:42px;height:42px;border-radius:12px;background:conic-gradient(from 210deg,#2b6c8f,#f5c86b,#2b6c8f);display:grid;place-items:center}
h1{font-size:18px;margin:0;letter-spacing:.5px}p.sub{margin:2px 0 0;color:#7d93ad;font-size:12px}
label{display:block;font-size:12px;color:#7d93ad;margin:14px 0 6px}
input{width:100%;padding:11px 12px;border-radius:10px;border:1px solid #1e3348;background:#0a1421;color:#dbe7f5;outline:0;font-size:15px}
input:focus{border-color:#2f7d97;box-shadow:0 0 0 3px rgba(79,209,224,.12)}
button{width:100%;margin-top:18px;padding:12px;border:0;border-radius:10px;cursor:pointer;font:600 15px/1 "Microsoft YaHei UI";
  color:#1a1206;background:linear-gradient(180deg,#ffd98a,#e9ae4b);letter-spacing:2px}
button:disabled{filter:grayscale(.7) brightness(.7);cursor:not-allowed}
button.ghost{margin-top:8px;background:transparent;border:1px solid #1e3348;color:#dbe7f5;font-weight:500;letter-spacing:1px}
.hint{margin-top:12px;font-size:12px;color:#7d93ad;min-height:18px}.err{color:#ff6b6b}
</style></head><body>
<div class="card">
  <div class="brand"><div class="logo">◈</div><div><h1>赛尔号 · 登录器</h1><p class="sub">Flash 可视化宿主 · Pepper Flash 15</p></div></div>
  <label>米米号</label><input id="u" value="ACCOUNT" spellcheck="false">
  <label>密码（可选，仅自动输入到 Flash 登录框）</label><input id="p" type="password" placeholder="留空则手动在 Flash 里登录">
  <button id="go">打开游戏</button>
  <button id="manual" class="ghost">只打开，不自动输入</button>
  <div class="hint" id="h">打开后可用 MCP 的 flash_shot / flash_click / flash_type 操作</div>
</div>
<script>
async function post(path, body){
  const r = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body||{})});
  return await r.json();
}
async function openGame(autoType){
  const btn = document.getElementById('go'); btn.disabled = true;
  document.getElementById('h').textContent = '正在载入 Flash 客户端…';
  try{
    const r = await post('/login', {account: document.getElementById('u').value.trim(),
      password: autoType ? document.getElementById('p').value : '', autoType: autoType});
    if (!r.ok) throw new Error(r.error || 'failed');
    document.getElementById('h').textContent = '已载入：' + (r.url || '');
  }catch(e){
    document.getElementById('h').textContent = '失败：' + e.message;
    document.getElementById('h').className = 'hint err';
    btn.disabled = false;
  }
}
document.getElementById('go').onclick = () => openGame(true);
document.getElementById('manual').onclick = () => openGame(false);
</script></body></html>`;

// ---------------------------------------------------------------- HTTP 桥

function readBody(req) {
  return new Promise((resolve) => {
    let b = '';
    req.on('data', (c) => { b += c; if (b.length > 8e6) req.destroy(); });
    req.on('end', () => {
      try { resolve(b ? JSON.parse(b) : {}); } catch (e) { resolve({}); }
    });
  });
}

function send(res, obj, code) {
  const body = Buffer.isBuffer(obj) ? obj : Buffer.from(JSON.stringify(obj), 'utf8');
  res.writeHead(code || 200, {
    'Content-Type': Buffer.isBuffer(obj) ? 'application/json' : 'application/json; charset=utf-8',
    'Content-Length': body.length,
    'Access-Control-Allow-Origin': '*',
    'Cache-Control': 'no-store',
  });
  res.end(body);
}

function startBridge() {
  http.createServer(async (req, res) => {
    const u = new URL(req.url, 'http://127.0.0.1');
    const p = u.pathname;
    try {
      if (req.method === 'GET' && (p === '/' || p === '/launcher')) {
        const b = Buffer.from(LAUNCHER_HTML, 'utf8');
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Content-Length': b.length });
        return res.end(b);
      }
      if (req.method === 'GET' && p === '/state') {
        const st = JSON.parse(await pageState());
        st.window = win.getContentSize();
        st.url = win.webContents.getURL();
        return send(res, { ok: true, state: st });
      }
      if (req.method === 'GET' && p === '/shot.png') {
        const s = await shot();
        res.writeHead(200, { 'Content-Type': 'image/png', 'Content-Length': s.png.length, 'Cache-Control': 'no-store' });
        return res.end(s.png);
      }
      if (req.method === 'POST') {
        const b = await readBody(req);
        if (p === '/login') {
          const url = b.url || GAME_URL;
          await loadURL(url);
          if (b.autoType && b.account) {
            await sleep(1500);
            await key('Tab');
            await type(b.account);
            await key('Tab');
            if (b.password) await type(b.password);
            await key('Enter');
          }
          return send(res, { ok: true, url: win.webContents.getURL() });
        }
        if (p === '/load') return send(res, await loadURL(b.url));
        if (p === '/click') return send(res, await click(Number(b.x) || 0, Number(b.y) || 0, Number(b.clicks) || 1));
        if (p === '/key') return send(res, await key(b.key || b.keys));
        if (p === '/type') return send(res, await type(b.text));
        if (p === '/eval') {
          const r = await win.webContents.executeJavaScript(String(b.code || ''), true);
          return send(res, { ok: true, result: r });
        }
        if (p === '/resize') {
          win.setContentSize(Number(b.w) || 996, Number(b.h) || 700);
          return send(res, { ok: true, size: win.getContentSize() });
        }
      }
      send(res, { ok: false, error: 'not found' }, 404);
    } catch (e) {
      send(res, { ok: false, error: e.message }, 500);
    }
  }).listen(BRIDGE_PORT, '127.0.0.1', () => {
    hlog('[bridge] http://127.0.0.1:' + BRIDGE_PORT);
  });
}

app.on('ready', () => {
  startBridge();
  createWindow();
});
app.on('window-all-closed', () => app.quit());
process.on('uncaughtException', (e) => hlog('[fatal]', e.message));