// 试 HTTP 鉴权的三种密码形态（不打印密码本身）
import fs from 'node:fs';
import crypto from 'node:crypto';

const acct = 'ACCOUNT';
const ini = fs.readFileSync('F:/seer/account.ini', 'utf8');
const pwd = new RegExp('\\[' + acct + '\\]\\s*\\n\\s*pass\\s*=\\s*(\\S+)').exec(ini)[1];
const md5 = (s) => crypto.createHash('md5').update(s, 'utf8').digest('hex');
const variants = { plain: pwd, md5: md5(pwd), dmd5: md5(md5(pwd)) };

for (const [name, val] of Object.entries(variants)) {
  const url = 'http://account-co.61.com/index.php?r=userIdentity/authenticate' +
    `&account=${acct}&rememberAcc=false&passwd=${val}&rememberPwd=true&vericode=&game=02&tad=none`;
  try {
    const res = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0', Referer: 'https://seerh5.61.com/' } });
    const t = (await res.text()).replace(/\s+/g, ' ').slice(0, 160);
    console.log('%-6s %s %s', name, res.status, t);
  } catch (e) {
    console.log('%-6s fetch fail %s', name, e.message);
  }
}