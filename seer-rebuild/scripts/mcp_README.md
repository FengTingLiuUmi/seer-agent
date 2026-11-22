# MCP 服务器

`seer_rebuild.mcp_server` 把重建能力暴露为 MCP 工具（stdio 传输，零依赖，标准库 JSON-RPC 2.0）。

## 启动

```powershell
$env:PYTHONPATH = "C:/Users/kmdbn/Documents/deepseek-harness/default-workspace/seer/seer-rebuild"
python -m seer_rebuild.mcp_server
# 等价于：
python -m seer_rebuild.cli mcp
```

配置要接到你用的 agent/client 时，把 `mcp_config.example.json` 按对应客户端格式（Claude Desktop / Cursor / DSH / VS Code …）填进 `mcpServers`。

## 工具一览

| 工具 | 作用 | 是否写操作 |
|---|---|---|
| `seer_login` | 账号鉴权（uid/session/网关），不连接游戏 | 只读 |
| `seer_unity_login` | Unity 真机登录并收 1001 关键帧 | 登录 |
| `seer_probe` | 登录后发只读命令并收集 S2C | 只读 |
| `seer_feature` | 背包/装备 或 精灵因子 的已抓包序列 | 默认 dry-run |
| `seer_inventory` | 实时当前装备/背包 | 只读 |
| `seer_query` | seerapi 查 pet/skill/item/factor | 只读 |
| `seer_applog` | 解析日常日志/出招记录 | 纯本地 |
| `seer_capture_summary` | 分析抓包 | 纯本地 |

- 写操作只在 `seer_feature` 且显式 `write=true` 时才真正发送。
- 登录类工具需要账号密码作为参数显式传入，服务器不落盘任何凭据。

## 自测

```powershell
python -m unittest tests.test_mcp
```

或手工喂一个 `tools/list`：

```powershell
'{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python -m seer_rebuild.mcp_server
```