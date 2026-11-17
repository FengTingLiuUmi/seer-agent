# 脚本目录

2.0.9 的 `.ysc` / `.cjcy` 由 VMProtect / 自定义加密保护，本仓库不直接执行它们。
这里提供两种可读替代：

1. **日常 JSON**（`daily_basic.json`）：`DailyRunner` 逐条发命令，默认只读。
2. **对战方案**：直接读取 `F:\seer\seer_cfg\script\method\**\*.cjc`，无需转格式。

运行：

```powershell
$env:PYTHONPATH = (Resolve-Path ..).Path
python -m seer_rebuild.cli daily --spec daily_basic.json --session session.json --mode unity
```

`session.json` 至少包含：

```json
{"uid": ACCOUNT, "session": "<32 hex>", "mode": "unity", "host": "h5gy.61.com", "port": 3002, "path": "/wss_online_02/"}
```

写操作（领奖/兑换）默认 dry-run，必须显式 `--write`，并先用 `observe` 校准 body。