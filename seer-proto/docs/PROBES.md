# 捕获 / 关卡 命令探测记录

方法：一条命令 = 一次全新登录（`tools/probe_cmds.py`），空 body 发送，观察回包或断线。
断线（`read err: EOF`）说明该命令**需要 body 参数**，不是禁用。

## 结果

| cmd | 名称 | 空 body 结果 | 备注 |
|---|---|---|---|
| 2169 | `GET_CATCH_GAME_RESULT` | ✅ **有回包**（29 B） | 可直接用，回包待解析 |
| 2189 | `SHOW_CATCH_GUIDE` | ❌ 断线 | 需参数 |
| 1021 | `FIGHT_READY_INFO` | ❌ 断线 | 需参数（地图/战斗上下文） |
| 2021 | `MAP_BOSS` | ❌ 断线 | 需参数 |
| 2383 | `PET_ROOM_FIGHT_INFO` | ❌ 断线 | 需参数 |
| 2409 | `CATCH_MONSTER` | 未测（预计需参数） | 核心捕获命令 |
| 2261 | `ASK_BALL_INFO` | 未测 | 精灵球信息 |
| 2262 | `GET_BALL` | 未测 | 取球 |
| 2301 | `GET_PET_INFO` | 未测 | 需 pet id |
| 2303 | `GET_PET_LIST` | 已知断线 | 需参数 |

## AS3 反编译结果（四个模块全部导出）

| 模块（解密后） | 导出目录 | 文件数 |
|---|---|---|
| `RobotCoreDLL.dec.swf` (33.7MB) | `llm-seer/patch/core_dec_as` | 1824 |
| `RobotAppDLL.dec.swf` (6.2MB) | `llm-seer/patch/app_as` | 1278 |
| `RobotApp_2DLL.dec.swf` (2.9MB，新下载并解密) | `llm-seer/patch/app2_as` | 1143 |
| `Login.swf` | `llm-seer/patch/login_as` | 271 |

**命令体格式（关键发现）**：`SocketConnection.send(CommandID.X, a, b, ...)` = **若干个 u32 大端**。实例：

| 命令 | AS3 调用 | 含义 |
|---|---|---|
| `FIGHT_READY_INFO` (1021) | `send(CommandID.FIGHT_READY_INFO, rand & 0xFFFFFFF0 \| slot)` | 4 字节，slot=0..3（`KillPluginPanel.as:120-126`） |
| `ITEM_LIST` | `send(CommandID.ITEM_LIST, 1200073, 1200073, 2)` | 3×u32（`BattleToolBar.as`） |
| `GET_DAILY_VALUE` (2707) | `send(CommandID.GET_DAILY_VALUE, 11059)` | 单 u32 |
| `ITEM_BUY` | `send(CommandID.ITEM_BUY, id, count)` | 2×u32 |
| `GET_NINJA_SKILL` | `send(CommandID.GET_NINJA_SKILL, catchTime, 0)` | 2×u32 |

**捕获相关定位**：

- `CATCH_MONSTER` (2409) 只有一个 **监听器**：`app2_as/.../MapProcess_1303.as:683 addCmdListener(CommandID.CATCH_MONSTER, onCatchMonster)`
  → 说明 2409 是**服务器推送的捕获结果**，不是客户端发起的捕获动作
- `MAP_BOSS` (2021) 同样是监听器（`app_as/.../ogre/BossCmdListener.as:21`）
- 其他捕获相关 id：`CATCH_RARE_PET=9756`、`CATCH_GAME_*`(2167-2172)、`SHOW_CATCH_GUIDE=2189`
- ⇒ 真正的“丢球捕获”动作还在战斗模块里，下一步按 `send(CommandID.FIGHT_*` / `*ITEM*` 检索

**注意**：1021 带 `00000000` body 依然断线 —— 因为它要求**处于战斗中**（上下文不对，不是参数错）。

## 验证成功：`2303 GET_PET_LIST`（查表 → 组 body → 发帧 闭环打通）

- 发送：`cmd=2303`，`body = 00000001 00000014`（起始 id 1、结束 id 20）
- 回复：`S2C 2303 len=292`（原 309 含 17B 头）
- 解析：`u32 count=18` + 18 × 16B 记录，每条 = `{u32 a, u32 b, u32 c, u32 catchTime}`

```
count = 0x12 = 18
rec[0] = a=0x12(18)  b=0x0c(12)  c=0     catchTime=0x4b0e7657 (1259238999)
rec[1] = a=0x36(54)  b=0x26(38)  c=0     catchTime=0x4b121d27 (1259478311)
rec[2] = a=0x08(8)   b=0x2e(46)  c=0     catchTime=0x4b34a78f (1261741967)
rec[3] = a=0x12(18)  b=0x24(36)  c=0     catchTime=0x4b38a5cd (1262003661)
rec[4] = a=0x1c(28)  b=0x21(33)  c=0     catchTime=0x4b38a75a (1262004058)
```

`catchTime` 明确是宠物捕获时间戳；`a/b/c` 语义待定（疑似 等级 / 精灵id / 标志），
下一步用 `1..5` 之类小范围再探一次即可交叉确认。

**方法学结论（可复用）**：`AS3 里的 send(CommandID.X, args…)` + `body = args 依次 u32 大端`
= 90% 的命令都能一次发对，不再靠盲试。

## 结论与下一步

- **盲发空 body 的性价比很低**：每失败一次就要重新登录（一次性 session + 冷却风险）
- 正确做法：**从客户端 AS3 里读命令体的构造**（`RobotCoreDLL.swf` / `RobotAppDLL.swf` 反编译），
  找 `CommandID.X` 的调用点，照抄字段顺序，再用真实 body 发一次验证

已开始导出：`llm-seer/patch/core_as`（RobotCoreDLL）→ 之后 grep `CATCH_MONSTER` / `FIGHT_READY_INFO` / `MAP_BOSS`

## 规律（供后续判断）

- `GET_*` / `SHOW_*` 不一定是无参的（2189 就断线）
- 与“当前地图/当前战斗”相关的命令（1021/2021/2383）几乎都要参数
- 已验证安全的空 body 命令：3401、3454、2003、47334、4178、45824、40006、2169