// jsdom 打开账号页 → 点账号条目 → 抓页面自己的登录请求/结果
import crypto from 'node:crypto';
import jsdomPkg from 'jsdom';
const { JSDOM, CookieJar, VirtualConsole } = jsdomPkg;
import { authenticate, UA, cookieString } from '../../seer-auto/src/login.js';
import { duid } from '../../seer-auto/src/auth.js';

await authenticate('ACCOUNT', process.env.SEER_PASSWORD);
const d = duid();
const jar = new CookieJar();
for (const part of cookieString().split(';')) {
  const i = part.indexOf('=');
  if (i <= 0) continue;
  try { jar.setCookieSync(`${part.slice(0, i).trim()}=${part.slice(i + 1).trim()}; Domain=.61.com; Path=/`, 'https://account-co.61.com/'); } catch {}
}

const redir = 'https%3A%2F%2Faccount-co.61.com%2Fv3%2F%3Fr%3Dauthorization%2Fsuccess';
const hist = 'https://account-co.61.com/v3/?r=AccountManager/history&duid=' + encodeURIComponent(d) +
  '&appid=20210906002&scope=userinfo&state=' + crypto.randomBytes(16).toString('hex') +
  '&source=0&register=&bg=0&redirect_url=' + redir;

const html = await (await fetch(hist, { headers: { 'User-Agent': UA, Referer: 'https://h5-seer.61.com/', Cookie: cookieString() } })).text();
const log = [];
const vc = new VirtualConsole();
vc.on('jsdomError', (e) => log.push(['jsdomError', String(e.message || '').slice(0, 160)]));

const dom = new JSDOM(html, {
  url: hist, runScripts: 'dangerously', resources: 'usable', cookieJar: jar,
  pretendToBeVisual: true, virtualConsole: vc,
  beforeParse(w) {
    w.open = (u) => { log.push(['window.open', String(u)]); return null; };
    w.HTMLFormElement.prototype.submit = function () { log.push(['form.submit', this.action]); };

    const OX = w.XMLHttpRequest;
    w.XMLHttpRequest = class extends OX {
      open(m, u, ...r) { this.__u = String(u); log.push(['xhr', m, this.__u]); return super.open(m, u, ...r); }
      send(b) {
        this.addEventListener('load', () => {
          const t = String(this.responseText || '');
          log.push(['xhr.done', this.__u, t.slice(0, 160)]);
          const m = t.match(/[?&]code=([0-9a-zA-Z]{8,})/);
          if (m) log.push(['CODE', m[1]]);
        });
        return super.send(b);
      }
    };
  },
});

await new Promise((r) => setTimeout(r, 5000));
const doc = dom.window.document;
const items = [...doc.querySelectorAll('[class*=item],[class*=account]')].slice(0, 8).map((e) => e.className + ':' + (e.textContent || '').trim().slice(0, 20));
console.log('dom items:', JSON.stringify(items).slice(0, 300));

const target = [...doc.querySelectorAll('*')].find((e) => e.children.length === 0 && (e.textContent || '').trim() === 'ACCOUNT');
console.log('target found:', !!target, target && target.className);
if (target) {
  const clickable = target.closest('[class]') || target;
  clickable.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }));
  console.log('clicked', clickable.className);
  await new Promise((r) => setTimeout(r, 7000));
}
console.log('url now:', dom.window.location.href.slice(0, 120));
console.log('--- log ---');
for (const l of log) console.log(' ', l.join(' | ').slice(0, 200));
const cfg = dom.window.TAOMEE_LOGIN_CONFIGURE;
console.log('cfg type/data/code:', cfg?.type, cfg?.data, cfg?.code);