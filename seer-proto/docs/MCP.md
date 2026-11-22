# MCP 工具（大模型直接操作 Flash 端）

## 组成

```
host_play.ps1   (32 位 PS + IE 控件 + Flash)          ← 已能到"登录开始界面"
flash_api.py    (REST :7801)                          ← 把命令转给宿主（文件 IPC）
flashctl.py     (CLI/库：state/eval/key/click/net)     ← agent 与 MCP 共用
mcp/flash_server.py (MCP stdio)                        ← 暴露 6 个工具
```

## 工具

| 工具 | 参数 | 作用 |
|---|---|---|
| `flash_state` | — | 页面标题/URL、Flash 对象、forAs API 列表、sid、frames |
| `flash_eval` | `code` | 在页面执行任意 JS（可调 `gamePublic.forAs.*`、`window.Client.*`） |
| `flash_key` | `keys` | SendKeys（`{TAB}`/`{ENTER}`） |
| `flash_click` | `x`,`y` | 客户区坐标点击（盲点） |
| `flash_login` | — | 盲注键盘登录（账号→Tab→密码→Enter） |
| `flash_net` | `wait_seconds` | 查 1863/1864 连接；可等待出现 `:1864`（=已进游戏） |

## 启动顺序

```powershell
cd "C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\llm-seer\host"
.\run-flash.bat          # 1) 宿主  2) REST :7801
```

自检：

```powershell
python ..\..\seer-proto\tools\flashctl.py state
python ..\..\seer-proto\tools\flashctl.py eval "document.title"
python ..\..\seer-proto\tools\flashctl.py net
```

## MCP 注册

任何 MCP 客户端（stdio）：

```json
{
  "mcpServers": {
    "seer-flash": {
      "command": "python",
      "args": ["C:/Users/kmdbn/Documents/deepseek-harness/default-workspace/seer/seer-proto/mcp/flash_server.py"]
    }
  }
}
```

协议实现：`initialize` / `tools/list` / `tools/call` / `ping`，JSON-RPC 逐行（UTF-8）。

## 已验证

```
initialize  -> {"name":"seer-flash","version":"0.1.0"}
tools/list  -> flash_state, flash_eval, flash_key, flash_click, flash_login, flash_net
tools/call  -> flash_state 返回真实页面状态（title/forAs[14]/flash{id:Client}）
```

实测链路：`MCP client → flash_server.py → HTTP :7801 → 文件 IPC → host_play.ps1 → IE 页面 JS → Flash`

## 下一步

1. **高层工具**（基于 `flash_eval`）：
   - `list_pets` / `open_pet_panel` / `start_pet_level` / `capture_pet`
2. **自动登录**：`flash_login` 试多种焦点序列，用 `flash_net(wait_seconds)` 判定成功
3. **事件流**：把 `/state` 与 TCP 变化推 SSE，agent 可等“进入游戏”