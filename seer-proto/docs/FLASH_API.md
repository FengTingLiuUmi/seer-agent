# Flash 宿主接口（给大模型 / agent 用）

## 已跑通（实测）

```
宿主:  llm-seer/host/host_play.ps1      (32 位 PowerShell + IE 控件 + Flash)
接口:  seer-proto/tools/flash_api.py    (127.0.0.1:7801，REST)
IPC:   llm-seer/ipc/{cmd,resp,state}.json  (宿主轮询，250ms 一条)
```

实测返回：

```
GET  /state -> {"title":"赛尔号…","url":"https://seer.61.com/play.shtml?micro=1&uid=ACCOUNT",
                "flash":{"id":"Client","tag":"OBJECT","pct":-1},
                "forAs":["getHostname","getAd","getUrlParams","addFav","getSessionID","getSign",
                          "noticeRotate","openInnerFrame","closeInnerFrame","confirmInitLocal",
                          "callActionScriptFunc","loginWithThird","sendShortcutToDesktop","showWeDownloadList"],
                "sid":"undefined","frames":["/0"]}
POST /eval   -> {"t":"赛尔号…","n":14,"client":"object","sess":"fn"}
```

## 接口

| 方法与路径 | 参数 | 说明 |
|---|---|---|
| `GET /state` | — | 页面标题/URL、Flash 对象、forAs 列表、session、frames |
| `POST /eval` | `{"code":"<js>"}` | 在页面执行任意 JS，返回字符串结果（万能入口） |
| `POST /key` | `{"keys":"{TAB}abc{ENTER}"}` | SendKeys 盲操作（不读像素） |
| `POST /click` | `{"x":512,"y":330}` | 按客户区坐标点击 |
| `POST /nav` | `{"url":"https://…"}` | 跳转 |
| `POST /login` | — | 盲注键盘登录（账号→Tab→密码→Enter） |
| `GET /health` | — | 宿主是否在线 |

## 为什么 `eval` 是核心

页面里有两条可编程通道，`eval` 都能直达：

1. **官方 JS API**：`gamePublic.forAs.*`（`getSessionID / getSign / callActionScriptFunc / loginWithThird / openInnerFrame …`）
2. **Flash 对象**：`window.Client`（`Client.swf` 用 `ExternalInterface.addCallback` 注册的 `getSession()`、`kickOffFun()`；`Login.swf` 在 `tmcid==76` 时会注册 `startWebSessionLogin`）

`callActionScriptFunc(fn)` 的实现（dump 原文）就是 `window['Client'][fn]()`，所以能直接调回调。

## 登录的两条路

| 方式 | 状态 | 说明 |
|---|---|---|
| A. session 注入 `startWebSessionLogin` | 需 `tmcid==76`，当前页面未注册 | 可在我们自己的宿主页加 flashvars 触发；或在页面里 `eval` 调 `window.Client.startWebSessionLogin(hex)`（若已注册） |
| B. 盲注键盘填登录面板 | 已实现（`/login`） | 不需要像素；焦点顺序不确定，可用 `/eval`+TCP 表自动验证并搜索序列 |

## 建议的 LLM 接口形态

1. **保留 HTTP REST**（已实现）——任何 agent/语言都能调
2. **上 MCP 工具**（下一步）：`flash_state` / `flash_eval` / `flash_login` / `flash_key` / `flash_click` / `flash_net`
3. **高层语义工具**（在 `/eval` 之上封装）：`open_pet_panel`、`list_pets`、`start_pet_level`、`capture_pet`
4. **事件流**（可选）：把 `/state` 变化 + TCP 表变化推成 SSE，方便 agent 等待“进入游戏”

## 自动登录搜索（待实现）

思路：`/login` 尝试若干焦点序列 → 用 `GetExtendedTcpTable` 检查是否出现 `:1864` 连接 → 命中即停。全程无像素。