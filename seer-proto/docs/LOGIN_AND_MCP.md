# 新登录界面 + MCP —— 使用与接口

这一层把「登录 → 进世界 → 操作精灵」封装成人和 AI 都能用的接口，底座仍是
`seerproto.exe`（uTLS 指纹 + 17B 帧 + result 链），不再依赖 Flash 宿主或大漠插件。

```
浏览器（新登录界面）
        │ HTTP
        ▼
seer-service :7820  ──HTTP──▶ MCP server（stdio）──▶ 任意 MCP 客户端 / agent
        │ 子进程 + serve JSON 行
        ▼
seerproto.exe -serve :7811 ──WSS(uTLS)──▶ h5gy.61.com 游戏网关
```

**一个账号只允许一条连接**：界面和 MCP 共用同一个 seer-service，所以不会互相顶号。

---

## 1. 启动

```powershell
cd seer-proto

# 只起服务（登录界面 + REST）
python tools\seer_service.py                 # http://127.0.0.1:7820

# 起服务并立即登录
python tools\seer_service.py --autologin
```

打开 <http://127.0.0.1:7820> 就是新的登录界面：填米米号（密码留空 = 用加密凭据），
点登录；右侧实时显示玩家/地图/收发帧，下方可以直接发命令（`2303`、`GET_PET_LIST`、`精灵列表`）。

> 端口可改：`--port 7820 --serve-port 7811 --view-port 7812`。
> `--view-port` 是 seerproto 自带的协议看板（可关：`--no-view`）。

---

## 2. REST 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/status` | 会话状态（ready / 玩家 / 地图 / 精灵 / 冷却 / 事件序号） |
| GET | `/api/state` | 游戏快照（map / players / pets / achievements） |
| GET | `/api/events?since=N&limit=M` | 帧事件增量（c2s/s2c，带 bodyHex） |
| GET | `/api/pets` | 最近一次精灵列表解码结果 |
| POST | `/api/login` | `{"account":"ACCOUNT","force":true}` → 鉴权→token→session→进世界 |
| POST | `/api/logout` | 断开并释放单实例锁 |
| POST | `/api/send` | `{"cmd":2303}` / `{"cmd":"GET_PET_LIST"}` / `{"cmd":"精灵列表","bodyHex":"","waitMs":5000}` |
| POST | `/api/pets` | 发 2303 并解码，落盘 `bodies/2303.bin` |
| POST | `/api/petinfo` | `{"bodyHex":"0000008f"}` → 2301 详情 |

`/api/send` 的 `cmd` 支持三种写法：数字 id、`commandid.json` 里的名字、中文别名（见 MCP 的 `ALIASES`）。

---

## 3. MCP 服务器

文件：`mcp/seer_server.py`（纯 stdlib，stdio JSON-RPC，开箱即用）。

手工自检：

```powershell
# initialize / tools/list / 调用 seer_status
'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | python mcp\seer_server.py
```

`seer-service` 不在线时 MCP 会自动拉起它（detached），所以客户端不需要先启动服务。

### 工具

| 工具 | 作用 |
|---|---|
| `seer_login` | 登录并进世界（用本机加密凭据，不需明文密码） |
| `seer_status` | 会话/玩家/地图/精灵概览 |
| `seer_pets` | 拉精灵列表（2303） |
| `seer_pet_info` | 单个精灵详情（2301，需 bodyHex） |
| `seer_capture` | 捕捉当前野生精灵（2409，实验） |
| `seer_fight` | 战斗动作：`use_skill`(2405) / `escape`(2410) / `catch`(2409) |
| `seer_send` | 万能命令入口 |
| `seer_events` | 最近收发帧（看游戏对操作的反应） |
| `seer_logout` | 断开会话 |

### 注册到 DSH（一条命令，自动备份）

```powershell
pwsh -File seer-proto\mcp\register-mcp.ps1          # 追加注册（已有则跳过）
pwsh -File seer-proto\mcp\register-mcp.ps1 -Remove  # 移除
```

脚本会备份 `cordis.patch.yml`，然后追加下面这段（写入的是**顶层数组**的一项；
`serverName` 决定工具前缀 `mcp__seer__*`）。**重启 DSH 后生效**：

```yaml
- id: mcp-seer
  name: "@deepseek-ai/dsh-mcp-client"
  config:
    serverName: seer
    transport: stdio
    command: python
    args:
      - "C:/Users/kmdbn/Documents/deepseek-harness/default-workspace/seer/seer-proto/mcp/seer_server.py"
    cwd: "C:/Users/kmdbn/Documents/deepseek-harness/default-workspace/seer/seer-proto"
    toolCallTimeoutMs: 300000
```

其它 MCP 客户端（Claude/Codex 等）：

```json
{"mcpServers":{"seer":{"command":"python",
 "args":["C:/Users/kmdbn/Documents/deepseek-harness/default-workspace/seer/seer-proto/mcp/seer_server.py"]}}}
```

> 登录会占住账号：同一时间只保留一个 seer-service。想给别的 agent 用，直接调同一个 HTTP 地址即可。

---

## 4. 登录链（为什么不用 Flash）

| 环节 | 做法 | 位置 |
|---|---|---|
| 鉴权 | `userIdentity/authenticate`（md5 密码） | `tools/prep_pwd.mjs` |
| code | `AccountManager/history` → `AccountManager/login` | 同上 |
| token | `token/trans` | 同上 |
| 会话 | `wsAuthenticate → onlineGate → convertToken` → `login.json` | `lib/auth.js` |
| 进世界 | gate 105/111/109 → 1001(508B) → S2C 2001 → **42494 → 1002 → 1016** | `main.go` / `server.go` |

关键坑（已写进代码注释）：
- `result` 链 = 「上行/下行最近一个非 0 result」代入 `r - r/3 + 113 + len%17 + cmd%23 + xor(body) + 7`
- **登录进世界没有 45963 ack**；45963 只用于地图切换确认（2001 body 12B）
- session 一次性：相邻登录至少间隔 20–45s，过快会被服务端 EOF

---

## 5. 精灵捕捉（能力边界，务必读）

**已就绪**：会话、命令通道、事件观察、精灵列表拉取（2303）、任意命令下发。
**未标定**：捕捉的战斗时序（进入野生战斗 → 2409 → 战斗结束），因为需要真实的野生战斗样本。

已确认可用的命令（`data/commandid.json`）：

| cmd | 名称 | 用途 |
|---|---|---|
| 2303 | GET_PET_LIST | 精灵仓库/背包 |
| 2301 | GET_PET_INFO | 单体详情（body `0000008f` 形如 petId） |
| 2313 | IS_COLLECT | 采集状态 |
| 2405 | USE_SKILL | 战斗用技能 |
| 2409 | CATCH_MONSTER | 捕捉 |
| 2410 | ESCAPE_FIGHT | 逃跑 |
| 2506 | FIGHT_OVER | 战斗结束 |

`seer_capture` 的行为：发 2409（可带 `bodyHex`），收集随后 8 秒内的帧，返回 `got_cmds`。
判断成功看是否出现 `2506` / `2002` / `2001`（战斗结束/切图）或 2409 回包携带精灵数据。
**body 格式尚未用真实野生战斗标定**——拿到样本后只需要改 `decode_2303` 和这里的常量。

---

## 6. 实测记录（2026-11-13）

客户端侧的两个真实 bug 已修掉（`server.go`）：

1. **`-serve` 引导时序**：旧实现在 `2001` 后同时发 `45963` + `42494`。按官方抓包
   （`seer-auto/relogin4.jsonl`）登录进世界应为 `2001 → 42494 → 1002 → 1016`，
   `45963` 只用于**地图切换**（2001 body 12B）。已改成逐条等回包。
2. **回包匹配**：S2C 帧原先不带请求 id，代理按 id 等会假超时；改为按 `cmd + 序号` 匹配，
   服务端同时把最近请求 id 附在 S2C 上。

登录实测（多次，含 18 分钟/25 分钟冷却窗口）：

| 时间 | 结果 |
|---|---|
| 17:08（旧二进制，`-steps`） | 进世界并跑完 `steps_gather` |
| 17:35 起 | 鉴权/token/1001 全部成功，**收到 `2001` 后约 20ms 被服务端 EOF** |
| 18:26（无 ack 变体） | 同上 |
| 18:37（先 ack 再 42494 变体） | 同上（还多收到 2604/3404 外观帧） |

结论：**登录链本身是通的**（能进世界、能拿到玩家/地图数据），
关闭发生在进世界后的第一个瞬间，且两种时序一致 ⇒ 不是发包顺序问题，更像：

- 同一账号短时间反复登录触发的**服务端冷却/风控**（官方抓包里首次进世界没有 ack）；
- 或 `data/login_template.bin` 里的客户端版本/服务器字段过期（1001 body 模板来自更早的抓包）。

**下一步（拿到干净窗口后）**：等 ≥45 分钟无任何登录 → 用 `-steps steps_gather.json`
单跑一次（这是 17:08 成功过的那条路）；若仍 EOF，则重新抓一份官方 1001 body 更新
`login_template.bin`（`seer-auto/tools/relogin_capture.mjs`）。

在此之前，**精灵捕捉无法实测**，`seer_capture` 的工具形态已就绪，等世界会话稳定即可标定 body。

## 7. 已知问题 / 排障

| 现象 | 原因 | 处理 |
|---|---|---|
| 登录 `read: EOF`，但已收到 2001 | 账号短时间反复登录，服务端冷却；或进世界时序错 | 停 10–20 分钟再试；确认没有第二个客户端（官方登录器/H5）在线 |
| `S2C 1001 res=10001` | session 失效/被顶 | 重新 `/api/login`（间隔 ≥20s） |
| 发某命令后 20–30ms EOF | 该命令参数不对 | 换 bodyHex；重登一次 |
| `seer-service 不可达` | 没启动或端口被占 | `python tools\seer_service.py`；看 `service-proto.err` |
| MCP 工具不出现 | profile patch 未生效 | 重启 DSH；或用 HTTP 接口直接调 |

日志：`service-proto.out` / `service-proto.err`（seerproto 原始输出）、`session.jsonl`（帧流水）、
`bodies/*.bin`（回包原始字节）。