# 2.0.9 逆向对照（2026-11-14）

对比对象：`雷小伊脱机日常 2.0.9.exe`（21.1MB，UPX 变体壳）dump = `memdump_lx209/`（953 文件 / 364MB）

## 结论：2.0.9 不再是「Flash 宿主」，而是**原生协议客户端**

| 关键字符串 | 2.0.21（登录器） | 2.0.9（脱机日常） |
|---|---|---|
| `play.shtml` / `common_micro` | ✅ 有 | ❌ 无 |
| `get_sid` / `ExternalInterface` / `Shell.Explorer` / `Flash.ocx` | ✅ 有 | ❌ 无 |
| `wss://` + `h5_web_taomee` | ❌ | ✅ 有 |
| `WebSocket` / `WebSocketClient` / `HtmlViewer` | ❌ | ✅ 有 |
| `https://seerh5login.61.com/online_gate?is_ssl=1` | ✅（登录器也走） | ✅ |
| `https://account-co.61.com/...`（authenticate / AccountManager/history / token/trans） | ✅ | ✅ |
| `https://seer-login-ip.61.com/unity-ip.txt` | ❌ | ✅（Unity 版服务器列表） |
| `Unity / Flash / H5` 客户端模式串 | ❌ | ✅ 有（三选一） |
| `onFightEvent` / `SendAndRecv` / `FightToWin`（JS 脚本 API） | ✅（文档） | ✅ 仍保留 |

⇒ **2.0.9 通过 WSS 直连游戏服（channel `h5_web_taomee`），并支持 Unity / Flash / H5 三种客户端**；它不再依赖 IE/Flash 宿主。
这也解释了为什么我们的“Flash 可视化”越走越窄，而**协议路线（seer-proto）才是与它同构的做法**。

## 我们对齐情况

| 环节 | 我们 | 2.0.9 |
|---|---|---|
| 账号鉴权 | `account-co.61.com`（`lib/login.js` 已经是这个域） | 同上 |
| 服务器入口 | `seerh5login.61.com/online_gate?is_ssl=1` | 同上 |
| 传输 | uTLS + WSS `h5gy.61.com/wss_online_0X/` | 同族（`wss://` + `h5_web_taomee`） |
| 17B 帧 / result 链 / 45963 ack | 已实现并跑通过 | 内部同样实现 |

## 当前唯一未解：登录后收不到 `2001`

实测（2026-11-14 00:5x，多次）：

```
C2S 1001(525B) → S2C 8002/3452/45827 广播 → S2C 1001(2931B) → ……（无 2001）
- 试过 -boot（1001 后立即补发 1002 / 1016(00000002) / 42494）：仍无 2001
- socket 未断（跑到 seconds 到点才结束），说明不是被踢
```

对照官方 H5 抓包 `seer-auto/relogin4.jsonl`（1603 条）：

```
C2S 1001(525) → 广播 → S2C 1001(2931) → [客户端拉 WebGL 资源] → S2C 2001(355) → C2S 42494
```

即：官方在收到 1001 回包后约 0.5s 就等到 2001，中间客户端只做了**资源加载**（HTTP），没有额外协议帧。
⇒ 我们缺的**不是某个协议帧**，更可能是服务端状态/会话问题（例如上一次会话未正常断开、占位未释放）。

## 下一步验证清单

1. 用官方 H5/客户端在同一账号上登录一次，确认能正常进图（排除账号被服务端挂起）
2. 我们在 1001 后**主动断开并重连一次**（模拟官方重连），看第二次是否收到 2001
3. 解码 S2C 1001(2931B) 的字段，找是否有 `mapId / state / error` 之类的“为什么没推 2001”的提示
4. 若确认是占位未释放：客户端退出时补发 `2002 LEAVE_MAP` / 正确关闭（避免下次登录处于半在线）