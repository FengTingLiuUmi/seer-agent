// 下载 32 位 Electron 11（Chromium 87，最后一个还带 Flash PPAPI 的版本）
import fs from 'node:fs';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';

const MIRRORS = [
  'https://npmmirror.com/mirrors/electron/11.5.0/electron-v11.5.0-win32-ia32.zip',
  'https://registry.npmmirror.com/-/binary/electron/11.5.0/electron-v11.5.0-win32-ia32.zip',
  'https://github.com/electron/electron/releases/download/v11.5.0/electron-v11.5.0-win32-ia32.zip',
];
const OUT = 'electron11-32.zip';

for (const u of MIRRORS) {
  try {
    const r = await fetch(u);
    if (!r.ok) { console.log('skip', u.slice(0, 60), r.status); continue; }
    const total = Number(r.headers.get('content-length') || 0);
    console.log('downloading', u, (total / 1048576).toFixed(1), 'MB');
    let done = 0, last = 0;
    const src = Readable.fromWeb(r.body);
    src.on('data', (c) => {
      done += c.length;
      if (done - last > 20 * 1048576) { last = done; console.log('  ', (done / 1048576).toFixed(0), 'MB'); }
    });
    await pipeline(src, fs.createWriteStream(OUT));
    console.log('done', fs.statSync(OUT).size, 'bytes');
    process.exit(0);
  } catch (e) {
    console.log('fail', u.slice(0, 60), e.message);
  }
}
process.exit(1);