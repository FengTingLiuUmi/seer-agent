# 赛尔号父子 agent（dsh-seer-agent）

把「赛尔号」从单 agent skill 改造为 DSH 原生 **父子 agent** 预设。安装后会出现两个 Agent 预设：

| 预设 id | 显示名 | 角色 | 谁用它 |
|---|---|---|---|
| `seer-lead` | 赛尔号 | **父 agent（lead）** | 用户在新建会话时选择 |
| `seer-stage` | 赛尔号·单关 | **子 agent（打手）** | 由 `seer-lead` 的 `subagent` 工具通过 `agentPreset: seer-stage` 自动下发，**不要手动选择** |

## 分工

- **父 `seer-lead`**：登录 + 读背包/仓库/因子进度 → 现场读 BOSS 组队 → 用 `subagent` 逐关派 `seer-stage` 子 agent（一次可并行多个）→ 解析子 agent 回传的结构化战报回执 → 汇总。
- **子 `seer-stage`**：只做一关三件事——本地 `simulate` 出招模拟 → 真机 `factor --send --write`（先 dry-run，`--report-dir` 落战报）→ 最终回复返回一段纯 JSON「战报回执」给父 agent 解析。

两者开工都先 `skill` 加载 `seer-rebuild`（CLI/协议/SOP 的唯一权威），`seerapi-cli` 按需加载。

## 数据契约（父解析子回传）

子 agent 的**最终回复就是一个纯 JSON 对象**（父 agent 收到完成通知后直接 `JSON.parse`，不做自由文本解析）：

```json
{
  "stage": 2,
  "design_id": 228,
  "difficulty": 1,
  "boss_species": 3595,
  "cleared": true,
  "winner": "胜利",
  "report": "seer/battle-records/latest.json",
  "error": null
}
```

- `cleared` / `winner`：S2C `45827` = 过关（`cleared=true`、`winner="胜利"`）；只有 `2506` 没 `45827` = 未过关。
- `report`：指向权威战报 `seer/battle-records/latest.json`。父 agent 需要逐回合血量/伤害/被锁 catch_time 时，直接读这个文件（字段 `lineup` / `turns[].enemy_hp` / `damage` / `winner`），与 `dsh-seer-battle` UI 共用同一数据源。
- 可选进阶：父 agent 也能用 `workflow` 工具的 `agent(prompt, { schema })` 一次性并行派多个子 agent 并拿到 **schema 校验过的结构化返回**，适合整轮 5 关 fan-out。

## 安装

在 DSH 里用 `plugin_manager`（或 Web「插件」页）安装本 bundle 的**绝对目录**：

```text
C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\dsh-seer-agent
```

安装会改动 profile（需授权）；**新会话**才生效，已有会话保持启动时的预设。安装后新建会话，在预设选择器里选「赛尔号」即可。

## 为什么是这套设计

- DSH 的父子 agent 机制 = 父 agent 持有 `subagent` 工具派生子 agent；`tool-subagent` 的 `agentPreset` 字段（仅 in-process `spawn` 支持）能指定子 agent 用独立预设，于是父/子各有各的 persona 与工具集——这正是「真正的父子 agent」，而不是单 agent 在 SKILL 里写一段协作文字。
- `seer-stage` 不挂 `subagent`/`web`/`ask-user`/`goal`：打手不该再往下派活，也不该直接问用户；阻塞时把结果回传给父 agent，由父 agent 决策/问用户。
- 账号密码、dry-run 先行、不顶号、优先小号等硬规则写在两个 persona 里，并延续 `seer-rebuild`/`seerapi-cli` skill 的原始规范。