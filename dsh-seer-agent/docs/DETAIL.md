# 赛尔号父子 agent（Seer parent-child agent）

把赛尔号自动化从「单 agent + skill 文本协作」改造成 DSH 原生父子 agent。

## 预设

| id | 名称 | 角色 |
|---|---|---|
| `seer-lead` | 赛尔号 | 父 agent：读现状、组队、派子 agent、汇总 |
| `seer-stage` | 赛尔号·单关 | 子 agent：单关模拟 + 真机打 + 回传胜负 |

## 数据来源

- 技能：`~/.agents/skills/seer-rebuild`、`~/.agents/skills/seerapi-cli`（由 `skill-filesystem` 默认根扫描，父/子都可 `skill` 加载）。
- CLI：`python -m seer_rebuild.cli ...`（通过 `tool-pwsh` 在 Windows 上执行）。
- 战斗记录 UI：另见 `@local/dsh-seer-battle`（本 bundle 不重复提供）。

## 父子协作链路

1. 用户在新建会话选「赛尔号」（`seer-lead`）。
2. 父 agent 登录 + 读 `bag` / 普通仓库 `2303` / 精英仓库 `2361` / 因子进度 `46046`。
3. 父 agent 对每关读 `factor_design` + seerapi + `docs/pve-theory`，决定精简阵容与出招。
4. 父 agent 调用 `subagent`（`agentPreset: seer-stage`），下发自包含 context；一次可并行多关。
5. 子 agent 先 `simulate`，再 `factor --send --write --report-dir` 真打，观察 `2506`/`45827`；最终回复 = 纯 JSON「战报回执」（stage/design_id/cleared/winner/report/error）。
6. 父 agent 收到完成通知后 `JSON.parse` 回执；需要逐回合数据时读回执 `report` 指向的 `seer/battle-records/latest.json`，据此汇总、推进下一关。

## 数据契约

- **战报回执**（子 agent 最终回复，父 agent 直接 `JSON.parse`）：
  ```json
  {"stage":2,"design_id":228,"difficulty":1,"boss_species":3595,"cleared":true,"winner":"胜利","report":"seer/battle-records/latest.json","error":null}
  ```
- **权威战报**：`seer/battle-records/latest.json`（`lineup` / `turns[].enemy_hp` / `damage` / `winner`），由 `battle_records.record_battle()` 写入，与 `dsh-seer-battle` UI 同一数据源。
- 判定：`45827` = 过关（`cleared=true`）；仅 `2506` 无 `45827` = 未过关。

## 安全规则（父/子 persona 已内置）

写操作先 dry-run；账号密码走凭证库不落盘；优先小号、不顶号；不动主号除非用户明示。