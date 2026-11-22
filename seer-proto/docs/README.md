# 文档索引

| 文档 | 内容 | 读者 |
|---|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 代码结构、协议要点、**打包成 skill/MCP 的设计**、维护约定 | 改代码 / 打包的人 |
| [HANDOFF.md](HANDOFF.md) | 全部实验结论的时间线（含 Flash TCP 服务器行为矩阵、SWF 解密、登录链逆向） | 接续研究的人 |
| [CREDENTIALS.md](CREDENTIALS.md) | 凭据存储方案（scrypt+AES-256-GCM）、主密钥管理、轮换步骤 | 部署 / 运维 |
| [SUMMARY.md](SUMMARY.md) | 早期阶段总结（协议/雷小伊 逆向结论） | 想了解背景的人 |

## 读的顺序（新人）

1. 根目录 `README.md` —— 能跑起来
2. `ARCHITECTURE.md` 的「协议要点」—— 为什么这些常量不能乱改
3. `HANDOFF.md` 搜关键词（如 `45963`、`1001`、`103`）—— 想看某个结论的来龙去脉

## 待补

- `COMMANDS.md`：逐个命令的 `cmd / body 格式 / 示例回包`（目前散在 `HANDOFF.md` 与 `steps_*.json`）
- `MCP.md`：MCP server 的 tool 契约（草稿已在 `ARCHITECTURE.md` 第 5 节）