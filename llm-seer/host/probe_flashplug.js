// 用假 electron 跑官方 launcher 的 flash-plugin.js，捕获它实际设置的开关/窗口参数
const Module = require('module');
const path = require('path');

const switches = [];
const windows = [];
const calls = [];

class FakeBrowserWindow {
  constructor(opts) { windows.push(opts); calls.push(['new BrowserWindow', opts]); }
  loadURL(u) { calls.push(['loadURL', String(u)]); }
  loadFile(f) { calls.push(['loadFile', String(f)]); }
  webContents = {
    on() {}, once() {}, setWindowOpenHandler() {}, session: { setPermissionRequestHandler: (h) => calls.push(['permHandler']) },
    executeJavaScript: async () => null, send() {}, openDevTools() {}, setDevToolsWebContents() {},
  };
  on() {} once() {} show() {} hide() {} setMenu() {} removeMenu() {} setTitle() {} loadURL2() {}
  static getAllWindows() { return []; }
  static fromWebContents() { return null; }
}

const fakeElectron = {
  app: {
    commandLine: {
      appendSwitch: (k, v) => { switches.push([k, v]); },
      appendArgument: (v) => { switches.push(['ARG', v]); },
      hasSwitch: () => false,
      getSwitchValue: () => '',
    },
    whenReady: () => Promise.resolve(),
    on: () => {},
    getPath: () => process.cwd(),
    getAppPath: () => process.cwd(),
    isPackaged: false,
    quit: () => {},
    setName: () => {},
    setAppUserModelId: () => {},
  },
  BrowserWindow: FakeBrowserWindow,
  BrowserView: class { constructor(o) { windows.push(o); } setBounds() {} setAutoResize() {} },
  ipcMain: { on: () => {}, handle: () => {}, removeHandler: () => {} },
  ipcRenderer: { on: () => {}, send: () => {}, invoke: async () => null },
  session: { defaultSession: { setPermissionRequestHandler: (h) => calls.push(['permReqHandler']), setPermissionCheckHandler: (h) => calls.push(['permCheckHandler']), webRequest: { onBeforeRequest: () => {}, onHeadersReceived: () => {} } } },
  shell: { openExternal: () => {}, openPath: () => {} },
  dialog: { showMessageBox: async () => ({ response: 0 }), showOpenDialog: async () => ({ canceled: true }) },
  Menu: { setApplicationMenu: () => {}, buildFromTemplate: () => ({}) },
  nativeImage: { createFromPath: () => ({}) },
  screen: { getPrimaryDisplay: () => ({ bounds: { width: 1920, height: 1080 } }) },
};

const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === 'electron') return fakeElectron;
  return origLoad.apply(this, arguments);
};

const target = process.argv[2];
try {
  const mod = require(path.resolve(target));
  calls.push(['required-ok', typeof mod, Object.keys(mod || {}).slice(0, 8)]);
  if (typeof mod === 'function') { try { const r = mod(fakeElectron.app, fakeElectron); calls.push(['called', typeof r]); } catch (e) { calls.push(['call-err', e.message]); } }
  else if (mod && typeof mod.init === 'function') { try { mod.init(); calls.push(['init ok']); } catch (e) { calls.push(['init-err', e.message]); } }
  else if (mod && typeof mod.default === 'function') { try { mod.default(); calls.push(['default ok']); } catch (e) { calls.push(['default-err', e.message]); } }
} catch (e) {
  calls.push(['require-err', e.message]);
}

setTimeout(() => {
  console.log('=== appendSwitch ===');
  for (const s of switches) console.log(' ', JSON.stringify(s));
  console.log('=== calls ===');
  for (const c of calls) console.log(' ', JSON.stringify(c).slice(0, 400));
  console.log('=== BrowserWindow opts ===');
  for (const w of windows) console.log(' ', JSON.stringify(w).slice(0, 500));
}, 300);