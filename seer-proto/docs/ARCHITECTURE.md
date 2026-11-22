# seer-proto 代码结构（打包 skill/MCP 用）

> 目标：把"能跑通的协议客户端"做成**可维护、可被其它 agent 调用**的能力。
> 本文分两部分：现状结构（读完能改代码） + 对外接口设计（怎么包成 skill/MCP）。

## 1. 总览

```
┌──────────────┐   HTTP(S)    ┌──────────────────┐
│ tools/*.mjs  │─────────────▶│ account-co.61.com │  密码/凭据 → token → session
└──────┬───────┘              └──────────────────┘
       │ 写 login.json
       ▼
┌───────────────────────────────┐   WSS(TLS, uTLS 指纹)   ┌──────────────┐
│ seerproto.exe                 │────────────────────────▶│ h5gy.61.com  │
│  main.go   会话/帧/命令调度    │◀────────────────────────│ login_gate   │
│  summary.go S2C body 摘要      │                         │ 游戏网关      │
│  view.go   事件环形缓冲+HTTP   │
│  server.go 常驻 JSON 服务      │
└──────┬────────────────────────┘
       │ 事件（每帧一条）
       ▼
  session.jsonl ──tools/report.py──▶ report.html
  http://127.0.0.1:7800 （实时看板）
```

三种运行模式（同一份二进制）：

| 模式 | 启动参数 | 用途 |
|---|---|---|
| 批处理 | `-steps steps.json -seconds N` | 跑固定命令序列，出日志/报告 |
| 常驻服务 | `-serve 127.0.0.1:7801` | 给别的程序（agent）实时下发命令 |
| 可视化 | `-view 127.0.0.1:7800` | 人看的实时看板（可与上面两种共存） |

## 2. Go 源码（4 个文件，约 835 行）

> 目录自 2026-11-13 起**自包含**：登录库与数据已 vendor 进本仓库
> （`lib/` 6 个 js、`data/` 的 `commandid.json` + `login_template.bin`），不再依赖 `seer-auto`。
> 逆向素材在姊妹项目 `../llm-seer`（SWF/反编译/探针）。

### `main.go`（420 行）— 会话与调度

| 函数 | 职责 |
|---|---|
| `helloSpec()` | uTLS ClientHello 复刻（TLS1.2、老套件、无 ALPN）；**别改**，改了会被 RST |
| `frame(cmd, uid, body, prev)` | 17B 头打包：`len u32 / ver u8(0x31) / cmd u32 / uid u32 / result i32 / body`；`cmd>1000` 时算跨帧校验并更新 `prev` |
| `dialWS(host, path)` | 手写 WebSocket 握手（101 Upgrade），复用上面的 uTLS 连接 |
| `wsSend/wsRead` | 单帧收发（客户端帧加掩码；服务端帧解析） |
| `hexDecode` | hex → []byte |
| `loadCmdNames` | 读 `../seer-auto/commandid.json`（`{"NAME":id}`）→ `{id:NAME}` |
| `loadSteps` | 读 `-steps` JSON → `[]sendStep{Cmd,BodyHex,DelayMs}` |
| `main()` | 单实例锁 → 初始化事件/看板 → `prep` 产物 → gate(105/111/109) → 游戏 1001 → 事件循环（维护 result 链、回 45963、按 delay 发 steps） |

关键约束（踩过的坑，别改回去）：
- `result` 链的种子：**上行/下行最近一个非 0 result**（S2C 也要算进去）
- 45963 确认包 body 恒为 12B：`00000002 00000001 <2001.body[4:8]>`
- 进世界后要按官方顺序引导：`45963 → 42494 → 1002 → 1016(00000002)`，否则会话不推进/被踢
- **不要**往 1001 body 的 `0x4c` 写东西（官方该处为 0，写了就收不到 2001）

### `server.go`（158 行）— 常驻 JSON 服务

- `runServe(game, uid, prev, addr, names, secs)`
- 监听 `addr`，接受一个客户端，读 JSON 行：`{"id":1,"cmd":3401,"bodyHex":""}`
- 回 JSON 行：`{"type":"c2s|s2c|ready|error|bye","cmd":..,"name":..,"len":..,"res":..,"bodyHex":".."}`
- 状态机：`stage 0..4`（0 未 ack → 1 等 42494 → 2 等 1002 → 3 等 1016 → 4 ready），
  `stage<4` 时收到的命令先排队，ready 后按序发出
- 适合被 MCP server 内部复用（见第 5 节）

### `view.go`（147 行）— 事件与看板

| 函数 | 职责 |
|---|---|
| `ev` 结构 | `{t, dir, cmd, name, len, res, body(hex), msg}` |
| `initEvents(names, logPath)` | 载入命令名表、打开 `session.jsonl` |
| `emit(e)` | 追加到内存环形（4000 条）+ 落 jsonl + `Sync()` |
| `emitFrame(dir, raw)` | 拆帧 → 填 cmd/res/body，`s2c` 时调用 `summarize()` 生成中文摘要 |
| `startView(addr)` | 起 HTTP：`/`（内嵌 HTML，700ms 轮询）和 `/events?since=N` |

### `summary.go`（110 行）— S2C 摘要

- `summarize(cmd, body)`：按 cmd 生成一行人类可读文本
  - `2001` 昵称 + 文本片段；`2003` 玩家数 + 昵称列表；`3401` 成就条数；
    `3454` 进度字节；`1016` 会话密钥
- 辅助：`utf8Runs`（抽 CJK/ASCII 片段）、`cstr`（定长 NUL 字段）、`be32`
- **新增一种 cmd 的可视化 → 只改这里**（不改协议层）

## 3. 协议要点（改代码前必读）

```
帧： len(u32) ver(u8) cmd(u32) uid(u32) result(i32) body
C2S ver=0x31，S2C ver=0x3E（S2C 的 ver 我们不校验）

result 链（cmd>1000）：
  r = r_prev - r_prev/3 + 113 + len%17 + cmd%23 + xor(body) + 7
  r_prev = 上行/下行最近一个非 0 result（全局一个累加器）

进世界：1001(body 508B，前 16B 是 session) → S2C 1001 → S2C 2001(ENTER_MAP)
        → C2S 45963(body={2,1,2001.body[4:8]}) → 服务端回 S2C 45963
错误信号：S2C 1001 res=10001（session 无效）→ 紧跟 EOF；
         某个 C2S 发出后 20~30ms 内 EOF ⇒ 该命令参数不对（不是封号）
```

## 4. 登录链路（`tools/prep_pwd.mjs`，纯 HTTP，无浏览器）

```
1) index.php?r=userIdentity/authenticate&passwd=md5(pwd)&account=..   → set-cookie
2) GET /v3/?r=AccountManager/history&duid&appid&scope&state&...        → 页面里取 state
3) GET /v3?r=AccountManager/login&state&uid&type=taomee                → data 里带 code
4) POST /v3/?r=token/trans (appid,duid,code)                           → token+refresh_token
5) wsAuthenticate → onlineGate(host/path/serverId) → convertToken(16B session)
   → 写 login.json {uid, sessionHex, host, path, serverId, bodyB64}
```
必备细节：`X-Requested-With: XMLHttpRequest`（否则回反爬 HTML）、第 3 步必须带 `uid/type`（否则 30000）。

凭据（`docs/CREDENTIALS.md`）：
`SEER_PASSWORD` > `secrets/cred.enc.json`（scrypt+AES-256-GCM）> `F:\seer\account.ini`；
主密钥 `SEER_KEY` 或 `seer-proto/.secrets-key`（均已 gitignore）。

## 5. 打包成 skill / MCP 的建议

### 5.1 推荐形态

不要把一个"长期跑着的 wss 客户端"直接暴露给 LLM；建议：

```
MCP server (node 或 python，薄壳)
   ├─ 内部管理 seerproto.exe（单实例、自动重启、冷却）
   └─ 复用 -serve 的 JSON 行协议
```

**MCP tools（建议 5 个，越小越好）**

| tool | 入参 | 说明 |
|---|---|---|
| `seer_status` | — | 返回 `{connected, ready, uid, last_2001, events_tail}` |
| `seer_send` | `{cmd:int, body_hex?:string, wait_ms?:int}` | 发一条命令，返回该 cmd 的 S2C 回包（或超时） |
| `seer_query` | `{name:"ACHIEVELIST"}` | 按命令名查若干条（内部查 commandid.json） |
| `seer_events` | `{since?:int, limit?:int}` | 拉事件（含 summary 文本），给 agent 读 |
| `seer_report` | `{out?:string}` | 生成 report.html 并返回路径 |

**资源（MCP resources）**
- `seer://session/events` → `session.jsonl`
- `seer://catalog/commands` → `commandid.json`（3034 条）
- `seer://state/current` → 最新地图/坐标/玩家（由 2001+2003 维护）

**Skill 形态（无 MCP 时）**：一个 `SKILL.md` + 三个脚本：
`login.sh`（prep_pwd）、`send.sh`（-steps 单条）、`watch.sh`（-view + 打开浏览器）。

### 5.2 安全与稳定性边界（写进 tool 描述里）

- **单实例**：文件锁 `.seerproto.lock`，并发调用要排队
- **不要连续重登**：session 一次性；相邻两次登录间隔 ≥ 20s，否则可能长时间收不到 2001
- **未知参数会断线**：`seer_send` 内部把"20~30ms 内 EOF"映射成 `E_BAD_ARGS`（可重登重试一次）
- **写操作白名单**：只放行读类命令（4401/2003/3401/47334…），移动/战斗/交易类需要显式授权
- **日志脱敏**：不落 `password` / `token` 全文；session 只留前 8 位

### 5.3 目录整理建议（打包前）

```
seer-proto/
├── main.go server.go view.go summary.go      # 客户端（保留）
├── lib/   login.js auth.js tokenStore.js loginBody.js ws.js protocol.js   # 已 vendor
├── data/  commandid.json login_template.bin (token.json/duid.txt 生成物, gitignore)
├── docs/  HANDOFF.md ARCHITECTURE.md CREDENTIALS.md
├── tools/
│   ├── prep_pwd.mjs gencred.mjs loadcred.mjs keyfile.mjs   # 登录/凭据
│   ├── prep_token.mjs prep.mjs                              # token 路线（备用）
│   └── report.py save_bodies.py mkbat.py agent_client.py     # 观测/测试
├── steps_run.json steps_safe.json            # 命令序列样例
├── build.bat run-live.bat                    # 编译 / 一键演示
└── ../llm-seer/                              # 逆向素材（SWF/反编译/探针/Go 缓存）
```
> 历史探针已迁至 `../llm-seer/probes/`，SWF/反编译在 `../llm-seer/{swf,dec,ref,tools}/`。

## 6. 维护约定

1. **新增一个可读命令**：先在 `steps_*.json` 里试 → 通了再在 `summary.go` 加一行解码 → 补进 `docs/COMMANDS.md`（建议新建，记录 cmd/body 格式/示例回包）
2. **改协议层前**先跑 `docs/HANDOFF.md` 的"验证清单"（1001→2001→45963），任何一步变了立刻能发现
3. **事件日志是唯一真相**：排查问题时先看 `session.jsonl`，再看 `report.html`
4. **凭据轮换**：`gencred` 重跑即可；`cred.enc.json` 可提交，`.secrets-key` 必须自己保管
5. **不要提交**：`login.json`、`session.jsonl`、`report.html`、`data/token.json`、`bodies/`