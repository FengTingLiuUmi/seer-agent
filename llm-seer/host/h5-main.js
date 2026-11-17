// H5/Unity(WebGL) 宿主：加载 https://seerh5.61.com/?sid=<会话> 并注入 JS 驱动
// 用法: electron11-32\electron.exe h5-main.js   （需先跑 seer-proto/tools/prep_pwd.mjs 生成 login.json）
const { app, BrowserWindow } = require('electron');
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const ROOT = 'C:\\Users\\kmdbn\\Documents\\deepseek-harness\\default-workspace';
const SEER = path.join(ROOT, 'seer-proto');
const IPC = path.join(ROOT, 'llm-seer', 'ipc');
const LOGF = path.join(ROOT, 'llm-seer', 'host', 'host-h5-log.txt');

function hlog() {
  const line = Array.prototype.slice.call(arguments).join(' ');
  try { fs.appendFileSync(LOGF, line + '\n'); } catch (e) { }
  console.log(line);
}

function prepSid() {
  try {
    execFileSync('node', ['tools/prep_pwd.mjs'], { cwd: SEER, stdio: 'pipe' });
  } catch (e) {
    hlog('[prep] fail', e.message);
  }
  const j = JSON.parse(fs.readFileSync(path.join(SEER, 'login.json'), 'utf8'));
  return { uid: j.uid, sid: String(j.uid) + j.sessionHex };
}

app.commandLine.appendSwitch('disable-http-cache');
app.commandLine.appendSwitch('no-sandbox');

let win = null;
const STARTED = Date.now();

function createWindow(info) {
  const url = 'https://seerh5.61.com/?sid=' + info.sid;
  hlog('[h5] url=' + url);
  win = new BrowserWindow({
    width: 1200, height: 800,
    backgroundColor: '#000',
    title: 'seer h5 host',
    webPreferences: { nodeIntegration: false, contextIsolation: false, backgroundThrottling: false, plugins: false },
  });
  win.loadURL(url);
  win.webContents.on('did-finish-load', () => hlog('[h5] page loaded'));
}

function ev(code) {
  return win.webContents.executeJavaScript(code).catch((e) => 'ERR: ' + e.message);
}

const PROBE = `(function(){
  var out={url:location.href.slice(0,120),title:document.title,
    egret: (typeof egret!=='undefined'),
    login: (typeof LoginManager2!=='undefined'),
    socket: (typeof SocketConnection!=='undefined'),
    user: (typeof LoginManager!=='undefined'&&LoginManager.userID)||null,
    keys: Object.keys(window).filter(function(k){return /^(gamePublic|LoginManager|SocketConnection|CommandID|MainManager|PetManager)/.test(k);})};
  return JSON.stringify(out);
})()`;

app.on('ready', () => {
  const info = prepSid();
  hlog('[h5] sid=' + info.sid);
  createWindow(info);
  setInterval(async () => {
    const st = await ev(PROBE);
    hlog('[state] ' + st);
    // IPC：读 cmd.json 执行，写 resp.json（与 Flash 宿主同一套）
    const cf = path.join(IPC, 'cmd.json');
    const rf = path.join(IPC, 'resp.json');
    if (fs.existsSync(cf)) {
      let req = null;
      try { req = JSON.parse(fs.readFileSync(cf, 'utf8')); fs.unlinkSync(cf); } catch (e) { }
      if (req) {
        let result;
        if (req.op === 'eval') { result = await ev(req.code); }
        else if (req.op === 'state') { result = await ev(PROBE); }
        else if (req.op === 'nav') { win.loadURL(req.url); result = 'ok'; }
        else { result = 'unknown op'; }
        try { fs.writeFileSync(rf, JSON.stringify({ id: req.id, op: req.op, ok: true, result: result })); } catch (e) { }
        hlog('[ipc] ' + req.op + ' -> ' + String(result).slice(0, 120));
      }
    }
  }, 2000);
});

app.on('window-all-closed', () => app.quit());