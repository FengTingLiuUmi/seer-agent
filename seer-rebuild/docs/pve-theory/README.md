# 赛尔号 PVE 概论（本地知识库）

整理自 [赛尔号PVE概论（BiliGame Wiki）](https://wiki.biligame.com/seer/%E8%B5%9B%E5%B0%94%E5%8F%B7PVE%E6%A6%82%E8%AE%BA)，抓取并清理于 2026-11-18。原文持续更新，以 wiki 为准；本地自用，勿对外分发（BiliGame Wiki 通常为 CC BY-NC-SA）。

## 目录

- [01-basics.md](01-basics.md) —— 基础规则、关卡分类、BOSS 血量/能力面板、出战顺序、战斗道具
- [02-damage-and-logic.md](02-damage-and-logic.md) —— 红伤公式、克制/随机、BOSS 出招逻辑、增伤减伤
- [03-tactics-and-build.md](03-tactics-and-build.md) —— 战术体系（强攻/站场/弹伤）、外设火焰、特性/刷法/刻印/宝石
- [04-codes.md](04-codes.md) —— 技能「代码 → 效果」速查表大全
- [05-boss-traits.md](05-boss-traits.md) —— BOSS 特性词典
- [06-levels-and-compliance.md](06-levels-and-compliance.md) —— 关卡类型（排行榜/加速特权/共用次数）与合规边界

## 用途

在 seer-rebuild 里做 PVE 组队 / 打因子前参考。配合 `seer_rebuild/domain_knowledge/` 使用：

- `strategies.json` —— 结构化「BOSS 特性 → 反制 / 打法模板」精确匹配；
- `sqlite_kb.py` + `knowledge.db` —— 精灵 / 技能 / 标签的查表。

## 颜色标记约定（wiki 原文沿用）

- 〔红〕红色强调：多数表内表示「BOSS 无效」或「有恢复 / 需额外警惕」，以各表句首说明为准。
- 〔绿〕一般为免疫 / 抵挡（攻击伤害免疫类）。
- 〔蓝〕一般为护盾 / 护罩类。