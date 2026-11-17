// 离线自检（不联网、不登录）：数据完整性 / 凭据可解密 / 步骤文件合法 / 忽略规则
import fs from 'node:fs';
import path from 'node:path';
import { loadCredential } from './loadcred.mjs';

const ROOT = path.resolve(new URL('..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'));
const results = [];
const ok = (name, extra = '') => results.push([true, name, extra]);
const bad = (name, extra = '') => results.push([false, name, extra]);

function readJson(p) {
  return JSON.parse(fs.readFileSync(path.join(ROOT, p), 'utf8'));
}

// 1) 命令名表
try {
  const m = readJson('data/commandid.json');
  const n = Object.keys(m).length;
  n >= 3000 ? ok('data/commandid.json', `${n} 条`) : bad('data/commandid.json', `只有 ${n} 条`);
} catch (e) {
  bad('data/commandid.json', e.message);
}

// 2) 1001 模板
try {
  const b = fs.readFileSync(path.join(ROOT, 'data/login_template.bin'));
  b.length === 508 ? ok('data/login_template.bin', '508 字节') : bad('data/login_template.bin', `${b.length} 字节`);
} catch (e) {
  bad('data/login_template.bin', e.message);
}

// 3) 步骤文件
for (const f of fs.readdirSync(ROOT).filter((x) => x.startsWith('steps_') && x.endsWith('.json'))) {
  try {
    const steps = readJson(f);
    const good = Array.isArray(steps) && steps.every((s) => Number.isInteger(s.cmd));
    good ? ok(f, `${steps.length} 步`) : bad(f, '格式应为 [{cmd,bodyHex,delayMs}]');
  } catch (e) {
    bad(f, e.message);
  }
}

// 4) 凭据可解密（本地）
try {
  const c = await loadCredential('ACCOUNT');
  c.password ? ok('凭据解密', `来源 ${c.source}`) : bad('凭据解密', '没有可用密码');
} catch (e) {
  bad('凭据解密', e.message);
}

// 5) 忽略规则
try {
  const gi = fs.readFileSync(path.join(ROOT, '.gitignore'), 'utf8');
  const need = ['.secrets-key', 'secrets/', 'login.json', 'session.jsonl', 'seerproto.exe'];
  const miss = need.filter((x) => !gi.includes(x));
  miss.length ? bad('.gitignore', '缺少 ' + miss.join(',')) : ok('.gitignore', `${need.length} 项关键忽略`);
} catch (e) {
  bad('.gitignore', e.message);
}

// 6) 源码存在
const srcs = ['main.go', 'server.go', 'view.go', 'summary.go', 'go.mod'];
const miss = srcs.filter((f) => !fs.existsSync(path.join(ROOT, f)));
miss.length ? bad('Go 源码', '缺少 ' + miss.join(',')) : ok('Go 源码', `${srcs.length} 个文件`);

// 7) lib 自包含
const libs = ['login.js', 'auth.js', 'ws.js', 'protocol.js', 'tokenStore.js', 'loginBody.js'];
const missLib = libs.filter((f) => !fs.existsSync(path.join(ROOT, 'lib', f)));
missLib.length ? bad('lib/ 自包含', '缺少 ' + missLib.join(',')) : ok('lib/ 自包含', `${libs.length} 个模块`);

// 输出
for (const [pass, name, extra] of results) {
  console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${extra ? '  — ' + extra : ''}`);
}
const failed = results.filter((r) => !r[0]).length;
console.log(`\n${results.length - failed}/${results.length} 通过`);
process.exit(failed ? 1 : 0);