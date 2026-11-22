# 赛尔号战斗记录（Seer battle records）

在 DSH Web 会话内实时展示 `seer-rebuild` 的赛尔号战斗。

## 数据来源

读取工作区 `battle-records/` 目录（由 `scripts/factor_fight.py --record` 产出）：

- `latest.timeline.jsonl`：**实时进行中**的战斗事件流（逐回合追加 C2S/S2C 帧，开战前由 `reset_live()` 清空）。插件轮询该文件做实时逐回合展示。
- `latest.json`：最近一场**完整**战报（含阵容/逐回合血量/胜负，结束时覆盖）。
- `index.json`：历史索引（列表）。
- 技能名表：`seer-rebuild/seer_rebuild/domain_knowledge/skills.json`（懒加载，把技能 id 反查成名称）。

## 使用

会话里点「⚔️ 战斗记录」展开面板，面板保持展开时每秒自动刷新：

- **精灵面板**：我方/敌方标识 + 敌方体力条（红条 `当前/满血`）。
- **战斗日志**：实时 `-----回合 N -----`、我方出招、敌方体力、换宠、`---战斗结束[胜负]---`，并自动滚到底部。
- **完整战报**：战斗结束后（timeline 清空 / `latest.json` 有胜负）回退为阵容 + 逐回合表。
- **历史记录**：折叠列表。

## 说明

- 实时展示是**尽力而为**的：敌方满血按 `[当前][满血]` 成对、取较大满血值（Boss 通常最高）发现；技能号通过 `skills.json` 反查，查不到时显示 `技能#id`。
- 文件读取依赖 Session 工作区与 `remote.workspaceFiles`；本插件只读、不修改、不发起任何战斗操作。