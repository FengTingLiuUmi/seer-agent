# seer-proto

赛尔号客户端（Unity/WebGL 协议）的**可编程实现**：密码登录 → 进世界 → 下发任意命令 → 读回包，
并自带**实时看板**与会话报告，便于 agent 驱动、也便于人观察。

- 协议：17 字节帧头 + 跨帧 `result` 校验 + 45963 确认包 + S2C 引导序列
- 传输：WSS + uTLS 自定义 ClientHello（复刻官方 JA3）
- 登录：纯 HTTP 五步（无浏览器）；凭据可加密存储

## 快速开始

```powershell
# 0) 只需一次：准备加密凭据（需要明文密码）
$env:SEER_PASSWORD = '<密码>'
node tools\gencred.mjs ACCOUNT      # 生成 secrets/cred.enc.json + .secrets-key

# 1) 编译（Go 在 PATH 即可；缓存写到 ../llm-seer/cache）
#    本仓库已带编好的 seerproto.exe；改了 .go 才需要重编
.\build.bat

# 2) 新登录界面（推荐）：常驻服务 + 浏览器控制台 + 给 MCP 复用
.\run-login.bat                      # http://127.0.0.1:7820
#    或双击 .\open-login.bat 自动起服务并打开

# 3) 旧的批处理/看板模式（一次性跑命令序列）
.\run-live.bat
```

> 新登录界面 + MCP 的完整用法见 [docs/LOGIN_AND_MCP.md](docs/LOGIN_AND_MCP.md)。
> 同一个账号只能有一条连接：登录界面、MCP、其它 agent 都共用 `seer-service`。

手工分步：

```powershell
node tools\prep_pwd.mjs                                  # → login.json（session 一次性）
.\seerproto.exe -info login.json -steps steps_run.json -seconds 120 -view 127.0.0.1:7800
python tools\report.py session.jsonl report.html         # 事后报告
```

## 三种运行模式

| 模式 | 参数 | 用途 |
|---|---|---|
| 批处理 | `-steps f.json -seconds N` | 固定命令序列，出日志/报告 |
| 常驻服务 | `-serve 127.0.0.1:7801` | 给程序/agent 实时收发 JSON 行 |
| 可视化 | `-view 127.0.0.1:7800` | 人看的实时看板（可与上面共存） |

其它参数：`-info`（login.json）、`-hex`（打印 S2C body）、`-log`（jsonl 路径）、`-cmdmap`（命令名表）。

## 目录

```
main.go server.go view.go summary.go   # 客户端
lib/    login.js auth.js tokenStore.js loginBody.js ws.js protocol.js   # 登录/鉴权/WS/协议
data/   commandid.json login_template.bin        # 命令名表、1001 模板
tools/  seer_service.py retry_login.py probe_serve.py                 # 常驻代理 / 实测工具
        prep_pwd.mjs gencred.mjs loadcred.mjs keyfile.mjs report.py ...
mcp/    seer_server.py                 # MCP（stdio）：登录/精灵/战斗/命令
ui/     index.html                     # 新登录界面（由 seer_service 托管）
docs/   LOGIN_AND_MCP.md（界面+MCP） HANDOFF.md ARCHITECTURE.md CREDENTIALS.md
steps_run.json steps_safe.json          # 命令序列样例
build.bat run-login.bat open-login.bat run-live.bat smoke.bat
```

## 安全

- 密码**明文永不落盘**：`SEER_PASSWORD` → scrypt+AES-256-GCM → `secrets/cred.enc.json`（可入库）
- 主密钥 `SEER_KEY` 或 `.secrets-key`（**切勿入库**）
- 日志/报告不含密码与 token 全文
- 单实例锁 `.seerproto.lock`；**session 一次性**，相邻登录请间隔 ≥20s
- 只读命令可自由调用；移动/战斗/交易类请显式授权后再用

详细协议与坑位见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) 与 [docs/HANDOFF.md](docs/HANDOFF.md)。

## 姊妹项目

- `../llm-seer`：逆向素材（SWF、反编译 AS、探针、Go 构建缓存）
- `../re`：Ghidra 工程与雷小伊（第三方客户端）分析