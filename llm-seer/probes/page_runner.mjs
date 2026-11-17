// 用 jsdom 跑「淘米登录」页面的 JS（雷小伊 的做法就是内嵌 JS 引擎跑这些页面脚本）
import crypto from 'node:crypto';
import jsdomPkg from 'jsdom';
const { JSDOM, CookieJar } = jsdomPkg;
import { authenticate, UA, cookieString } from '../../seer-auto/src/login.js';
import { duid } from '../../seer-auto/src/auth.js';

const pwd = process.env.SEER_PASSWORD;
const a = await authenticate('ACCOUNT', pwd);
const d = duid();
const jar = new CookieJar();
for (const part of cookieString().split(';')) {
  const i = part.indexOf('=');
  if (i < 0) continue;
  try { jar.setCookieSync(`${part.slice(0, i).trim()}=${part.slice(i + 1).trim()}; Domain=.61.com; Path=/`, 'https://account-co.61.com/'); } catch { /* ignore */ }
}

const redir = 'https%3A%2F%2Faccount-co.61.com%2Fv3%2F%3Fr%3Dauthorization%2Fsuccess';
const hist = 'https://account-co.61.com/v3/?r=AccountManager/history&duid=' + encodeURIComponent(d) +
  '&appid=20210906002&scope=userinfo&state=' + crypto.randomBytes(16).toString('hex') +
  '&source=0&register=&bg=0&redirect_url=' + redir;

const log = [];
const html = await (await fetch(hist, {
  headers: { 'User-Agent': UA, Referer: 'https://h5-seer.61.com/', Cookie: cookieString() },
})).text();
console.log('history page len', html.length, '| has login url:', /AccountManager\/login/.test(html));

const dom = new JSDOM(html, {
  url: hist,
  runScripts: 'dangerously',
  resources: 'usable',
  cookieJar: jar,
  pretendToBeVisual: true,
  virtualConsole: new jsdomPkg.VirtualConsole().on('jsdomError', (e) => {
    const m = String(e.message || '');
    if (!/Not implemented/.test(m)) log.push(['jsdomError', m.slice(0, 120)]);
  }).on('error', (m) => log.push(['console.error', String(m).slice(0, 120)])),
  beforeParse(w) {
    const OX = w.XMLHttpRequest;
    w.XMLHttpRequest = class extends OX {
      open(m, u, ...rest) {
        this.__u = String(u);
        log.push(['xhr.open', m, this.__u]);
        return super.open(m, u, ...rest);
      }
      send(body) {
        if (body) log.push(['xhr.body', this.__u, String(body).slice(0, 160)]);
        this.addEventListener('load', () => {
          log.push(['xhr.done', this.__u, String(this.responseText || '').slice(0, 200)]);
        });
        return super.send(body);
      }
    };
  },
});

await new Promise((r) => setTimeout(r, 8000));
console.log('--- log ---');
for (const l of log) console.log(' ', l.join(' | ').slice(0, 220));
const cfg = dom.window.TAOMEE_LOGIN_CONFIGURE;
console.log('login url:', cfg?.url?.login);
console.log('cfg data/code/type:', cfg?.data, cfg?.code, cfg?.type);