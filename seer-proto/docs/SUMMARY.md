# 赛尔号自动化 — 阶段总结（2026-11-12）

## 一、目标

做一个能让 agent 自主操作赛尔号、完成**图鉴补充**与**日常关卡**的载体。

结论：
- **让官方客户端执行** → 最稳（读帧 + UI 操作，无需 OCR）；
- **自建客户端** → 已进世界，但服务端暂不接受主动包（差最后一步）；
- **注入官方客户端** → 不可行（破坏跨帧校验链，必断）。

## 二、协议（已完全掌握）

帧结构（17 字节头）：

```
[u32 totalLen][u8 ver][u32 cmdID][u32 uid][i32 result][body]
```

- `cmdID > 1000` 时，`result` 是**跨帧累积校验**：
  `r = r - ⌊r/3⌋ + 113 + len%17 + cmdID%23 + xor(body) + 7`（已用官方帧验证：算出 250，完全一致）
- body 序列化：数组递归 / 字符串 UTF-8 无长度前缀 / 整数 u32 / Buffer 原样
- cmdID 表：**3034 条**（来自官方 `core` 模块的 `CommandID`）
  - `LOGIN_IN=1001`、`SYSTEM_TIME=1002`、`RANGE_ONLINE=106`、`MAIN_LOGIN_IN=103`
- 登录链：
  ```
  HTTP authenticate(MD5 密码) → token/refresh|convert
  → account ws 认证 → online_gate → login_gate(105/109/111)
  → 游戏 ws → 1001 → S2C 1001/2001
  ```

## 三、实验结果汇总

| 实验 | 结果 |
|---|---|
| CDP 抓官方客户端帧 | ✅ 实时解码 2001/2101/2002/45963 |
| Node 自建客户端 | ✅ 拿到 S2C 1001 (2931B)；❌ 发任何包即断 |
| 注入官方客户端 socket | ❌ 破坏校验链，断线重连 |
| TLS 降级（1.2 + 老套件） | ❌ 仍断 |
| **Go + uTLS（复刻 JA3）+ login_gate + WebGL body** | ✅ **收到 S2C 2001（进世界成功）** |
| 进世界后发 42494/1002（含强制官方 result=171） | ❌ 仍然 EOF |

**当前唯一卡点**：进世界成功后，服务端不接受我们主动发的包。

**首要假设**：官方进世界后第一个主动包是 **45963 确认包**（回应 2101/2001），我们没发 → 会话被视为“未确认”，随后任何主动包都被断。

## 四、雷小伊的实现（逆向结论）

```
脚本层（.cjcy / Lua-like VM，SEND / SLEEP）
  ↓
协议层（C++ 自实现，17B 帧 + 跨帧校验 + 会话）
  ↓
传输层（websocketpp + OpenSSL 1.0.2，JA3 = 258a5a1e95b8a911872bae9081526644）
```

- `42494` 在它里面只是脚本的 `SEND` 指令，全程序仅 `FUN_0068e9ef` 引用；
- `FUN_0044bd96` 完整写出了 1001 的 508 字节布局：
  `session16 | "taomee"x64 | serverid | 1 | "PC"x16 | 10000,1,1,2 | "unity_app_taomee"x32 | "com.taomee.seer.mobile"x32 | … | u32 0`
- 内嵌 QuickJS，但跑的是它自己的调度脚本（不是官方客户端 JS）；同时有 MiniBlink/WebView2 + 识图做兜底。
- 它不被踢的根本原因：**它拥有完整客户端身份**（自己的 TLS 栈 + 完整状态机），不是靠某个隐藏字段。

## 五、产出物

| 路径 | 内容 |
|---|---|
| `seer-auto/` | Node 协议库 + 登录链 + cmd 表 + 任务框架 |
| `seer-agent/` | CDP 数据驱动载体（读帧已通；注入不可行，保留作参考） |
| **`seer-proto/`** | **Go + uTLS 客户端（当前主线，能进世界）** |
| `seer-proto/main.go` | uTLS ClientHello 复刻 + login_gate + 1001 + 42494 |
| `seer-proto/tools/prep.mjs` | token → 认证 → convert → 生成 `login.json` |
| `re/tools/ghproj/seerbot` | Ghidra 工程（已分析）+ 4 个脚本（DumpProtoRefs/DumpProtoCore/DumpFuncs/Dump42494） |
| `re/tools/ja3.py` | JA3 解析器；`bot.pcap` / `node.pcap` 对比结论 |
| `re/memdump/` | 572MB 提权内存 dump（已解壳） |
| `re/tools/image.bin` | 由 dump 重建的 16MB 镜像（Ghidra 输入） |
| `seer-auto/docs/` | `protocol.md` / `architecture.md` |

## 六、复现命令

```powershell
# 1) 取 token（需要浏览器开着调试端口 9335 并已登录）
cd seer-auto
node tools\pull_token.mjs

# 2) 准备登录信息（token → 认证 → convert → login.json）
cd ..\seer-proto
$env:SEER_BODY='webgl'      # WebGL 身份 body（App 身份收不到 2001）
node tools\prep.mjs

# 3) 跑客户端
.\seerproto.exe -info login.json
```

Go 构建（JDK 环境不需要；需要 Go）：

```powershell
$env:PATH="C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\re\tools\go\go\bin;$env:PATH"
$env:GOCACHE="$PWD\.gocache"; $env:GOMODCACHE="$PWD\.gomod"; $env:GOPATH="$PWD\.gopath"
$env:GOPROXY='https://goproxy.cn,direct'
go build -o seerproto.exe .
```

## 七、下一步

### A（推荐）补 45963 确认

1. 解出官方 `45963` 帧结构（body 形如 `00000002 00000001 <4B 来自 2001/2101>`，已有多个样本）；
2. Go 客户端在收到 `2101/2001` 时立即回 `45963`；
3. 再试 `42494` / `1002`。

### B（保底）转 UI 操作

- 读帧判断状态 → 固定坐标点击 → 读帧验证；
- 不做运行时 OCR（坐标一次性标定）；
- 适合日常/图鉴这类固定流程。

## 八、注意事项

- `F:\seer\account.ini` 含 ACCOUNT 明文密码，勿外传；
- `seer-auto/data/session.json`、`token.json`、`cmdlog*.jsonl` 含会话数据，勿提交；
- 同账号协议客户端与官方客户端**不能同时在线**（顶号：登录返回空 body 或立刻断线）。
## 九、2026-11-12 晚间补充：自建客户端进展

### 已确认

1. **uTLS 指纹**（TLS1.2 + 老套件 + 无 ALPN）+ `login_gate 105/109/111` + **WebGL 身份 1001 body** → 能收到 `S2C 2001`（进世界）。
2. 身份必须用 **WebGL**（`h5` / `unity_webgl_h5`）；App 身份（`taomee` / `unity_app_taomee`）收不到 2001。
3. **进世界后只读不写时连接稳定**（12s 内持续收到 2001/9019，无断线）。
4. 一旦写入：
   - 发 `45963` ack（8B `[1,0]` 或 12B `[seq,1,token]`）→ EOF；
   - 发 `42494`（含强制 result=171）→ EOF；
   - 发 `1002` → EOF。
5. `45963` 官方的结构（从 relogin4 配对得出）：
   - 首次：`00000001 00000000`（8 字节）
   - 后续：`0000000N 00000001 <4B token>`，token = 最新 `2001` body 的 offset 4..7

### 仍未解释

- 官方发同样的 45963/42494 不断，我们发就断；
- 猜测：服务端校验的不只是 result 链，还包含 1001 里某个动态字段（我们复制的 body 里 session 外的字段可能“过期”或与服务器分配不一致），导致会话被标记为可疑，任何主动包即断开。

### 下一步候选实验

1. 抓一次官方 45963 的**完整帧（含 result）**，用它原样（含 result）替换我们的 ack 再试；
2. 检查 1001 的 result 是否被服务端与“期望值”比对（强制 250 试一次）；
3. 用官方客户端在线时，实时读取其 C2S 帧并**立即**注入同结构帧（同一状态窗口内），验证服务端是否只校验“最近一帧”。

### 2026-11-12 深夜：写入实验结论

| 实验 | 结果 |
|---|---|
| 收到 2001 → 只读（不写） | 稳定 12s，持续收帧 |
| 收到 2001 → 发 45963 ack（8B / 12B 两种） | 连接被中止 |
| 收到 2001 → 发 42494 | 连接被中止 |
| 收到 2001 → 发 42494→1002→1016→41345 官方顺序 | 连接被中止 |
| 不 ack、直接发官方顺序 | 同样被中止 |
| 2001 后发 42494 且 result 强制=171（官方值） | 仍被中止 |

**结论**：自建客户端可以完成 `1001` 登录并进入世界（收到 2001），
但服务端会在**第一个客户端数据帧**上中止连接，与本机/网络无关（错误为
`connection aborted by the software in your host machine`，即服务端 RST）。

**判断**：服务端对“非官方客户端会话”有额外写入门槛（可能是会话级的不可见状态/证明），
仅靠帧级复刻无法通过；雷小伊能写，是因为它整条链路与官方同构。

**建议**：
- 若目标只是“图鉴/日常”，转 **UI 操作 + 帧校验**（`seer-agent`），放弃自建写入；
- 若坚持自建，下一步应逆向 1001 之后服务端的“会话可信度”判定（无头绪，成本高）。

### ack 规则与最后结论

官方 ack（45963）规则（由 relogin4 全量统计）：

- 首个 2001 之后：`seq=1`，**8 字节** `00000001 00000000`，延迟 ~19ms；
- 之后每个 2001 之后：`seq=2`，**12 字节** `00000002 00000001 <token>`，token = 该 2001 body[4:8]，延迟 2~25ms。

按此规则实现后：**发 ack 仍然被 RST**（不是 ack 格式问题）。
只发 `41345`（不发 ack）时连接能继续、还收到新的 2001；其余任何写入（45963 / 42494 / 1002）都被 RST。

**最终结论（截至 2026-11-12 深夜）**：服务端只允许该会话“读 + 少数预授权请求”，
任何主动数据帧都会被断开；帧内容、TLS 指纹、ack 格式都不是根本原因，
更像是会话级的“客户端可信度”判定（雷小伊以完整原生客户端通过）。

**可行落地方向**：不写入协议，改由官方客户端执行动作（`seer-agent`：读帧判断 + 点击 + 帧校验，无需 OCR）。
