# 凭据存储（待优化为加密存储）

## 现状（临时，禁止入库）

- 密码**不写入任何会提交的文件**：运行时通过环境变量 `SEER_PASSWORD` 传入，
  或由 `prep_pwd.mjs` 在本地读 `F:\seer\account.ini`（该文件在仓库之外）。
- 生成物（`login.json` / `session.jsonl` / `data/token.json` / `duid.txt`）**全部 gitignore**。
- 日志与看板：只输出 `uid`、`session` 前 8 位、命令名、长度、result、body-hex；
  **不打印密码、token 全文**。

## 目标（要上传 GitHub 时）

需要一个“可提交”的加密凭据文件，例如 `secrets/cred.enc.json`：

```json
{
  "v": 1,
  "kdf": "scrypt",
  "N": 32768, "r": 8, "p": 1,
  "salt": "<base64>",
  "cipher": "aes-256-gcm",
  "iv": "<base64>",
  "tag": "<base64>",
  "data": "<base64(明文 JSON: {account, password, duid})>"
}
```

- 主密钥来自 `SEER_KEY` 环境变量（或系统密钥环 / CI Secret），**不入库**
- 解密只在进程内进行，用完即弃；任何日志都不出现明文
- 备选平台方案：
  - Windows：DPAPI（`ConvertFrom-SecureString`，绑定当前用户）
  - GitHub Actions：Repository Secret `SEER_KEY`
- 轮换：换密码时只需重新生成 `cred.enc.json`，无需改代码

## 实现清单

- [x] `tools/gencred.mjs`：明文 → scrypt(N=32768,r=8,p=1,maxmem=64MB) + AES-256-GCM → `secrets/cred.enc.json`
- [x] `tools/loadcred.mjs`：主密钥 + `cred.enc.json` → 内存凭据（失败给出明确报错）
- [x] `tools/keyfile.mjs`：主密钥来源 `SEER_KEY` 环境变量 > `seer-proto/.secrets-key`（gitignore）
- [x] `prep_pwd.mjs` 三条来源：`SEER_PASSWORD` > `cred.enc.json` > `account.ini`
- [x] 自测：`secrets/cred.enc.json` 293B（密文 62B），换 shell 后仍能解密并完成登录
      `ok uid=ACCOUNT session=… gate=… (密码来源: cred.enc.json)`
- [ ] CI：`SEER_KEY` 走 secret，`cred.enc.json` 正常入库
- [ ] 仓库 go-live 前跑一次 `git ls-files | grep -Ei 'token|login\\.json|session|duid'` 复核

## 本地密钥文件

`seer-proto/.secrets-key`（48 hex，权限 600，**已 gitignore**）。
这是唯一能解开 `secrets/cred.enc.json` 的东西，务必自己备份（密码管理器 / GitHub Secret）。
丢了就重新跑一次 `gencred`（需要明文密码）。