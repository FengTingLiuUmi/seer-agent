# 不用识图：观察与操作的三种通道

> 结论：**Flash 端完全可以不靠模板匹配**。识图只作为"人看"的辅助，判断与操作都可以走下面三条通道。

## 通道 A —— 网络包（已实现：`tools/tcp_proxy.py`）

Flash 客户端走的是**明文 TCP**（1863/1864），没有 TLS，天生适合中间人观察。

```
Flash 客户端 ──► 本地代理(127.0.0.1:18630) ──► 真实服务器
                     │
                     ├─ 应答 <policy-file-request/>（否则 Flash 直接拒绝连接）
                     ├─ 按 17B 帧解析双向流量 → proxy-18630.jsonl
                     └─ 可主动插入/改写帧（= 不用像素就能"操作"）
```

**已验证**（本机）：

```
policy via proxy: <?xml ... allow-access-from domain="*" to-ports="*" ...>  217 B
S2C cmd=101 len=21 res=0 body=00000000
日志：{"dir":"C2S","cmd":101,...} {"dir":"S2C","cmd":101,"len":21,...}
```

**能观察**：官方客户端每一帧——session、`1001`、`2001`（地图/昵称）、`2003`（同图玩家）、
`2101`（移动广播）……全部是结构化数据，比截图可靠。
**能操作**：代理是双向的，可以注入 `2101` 走路、`3401` 查询，甚至改写客户端发出的帧。
**前置**：让客户端连到代理。三种做法：
1. 自托管 SWF（见通道 C）时，直接把 Socket 目标改成 `127.0.0.1`；
2. 改写 SWF 里的服务器常量（我们有 FFDec + JDK，可批量改）；
3. 系统级重定向（hosts + 端口映射，需要管理员/网络配置）。

## 通道 B —— 内存（已实现：`tools/mem_read.py`）

AVM2 堆里，昵称/地图名是 UTF-16 字符串，坐标/ID 是紧邻的整数，可以定点读。

```
python tools\mem_read.py procs <过滤>
python tools\mem_read.py find <pid|名称> <文本> [--utf16]
```

**已验证**（拿 Edge 进程当靶）：

```
hits: 20
0x00000215883ef690  b'...C\x00h\x00r\x00o\x00m\x00e\x00 \x00L\x00e\x00g\x00a\x00c\x00y\x00...'
0x0000021586107973  b'rosoft\\Edge\\Application\\msedge.exe" --type=gpu-process'
```

**能观察**：当前地图名、角色昵称、坐标、面板文本——不需要截图。
**能操作**：内存只读最安全；写内存风险高（AVM2 对象布局脆弱）。操作建议仍走帧注入或 AS3 调用。

## 通道 C —— AS3 桥（最强，前面已找到入口）

`Login.swf` 暴露了 `ExternalInterface` 回调，其中：

```as
addCallback("startWebSessionLogin", ...)   // 参数是 hex: <uid 4B BE><session 16B>
   → LoginManager.MODE = SESSION_MODE      // 跳过账号密码框，直接进游戏
```

配合我们已有的 session（`prep_pwd.mjs` → `convertToken`），可以**零点击进世界**；
再往 SWF 注入一个通用 `eval` 桥（FFDec），所有后续操作都变成 AS3 函数调用。

## 推荐组合

| 目的 | 用什么 |
|---|---|
| 观察（状态/坐标/玩家/面板数据） | **A 网络包**（首选，结构化）；B 内存（兜底） |
| 操作（走路/接任务/开关面板） | **A 帧注入**（服务端视角一致）或 **C AS3 调用** |
| 人机共用/调试 | 截图 + `visual_driver.py`（唯一保留的"看图"用途） |

**识图只保留一个用途：给人看。** agent 的决策与执行不再依赖像素。

## 立即可做的下一步

1. 用通道 A 抓**官方 Flash 客户端**到 per-server 端口的首帧——这正好能解开之前卡住的
   "per-server 首帧需加密"（`SocketEncryptImpl`）：代理看得见它到底发了什么、加密边界在哪。
2. 拿到后，`seerproto` 的 Flash TCP 模式就能直接复用该格式（我们已有 17B 帧/校验实现）。

需要路由（前置条件）时，优先走"自托管 SWF + 改 Socket 目标"，因为它不需要管理员权限，也便于反复实验。