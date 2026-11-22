# 「为什么这样打」解释契约（why spec）

目标：给每个因子关（优先地狱）的每一关，解释「这个攻略为什么能过」——把 Boss 机制 与 反制手段 对应起来。

## 输入依据
1. 该因子的合并数据（`factors-bili.json` / `factors-extracted.json` 中该因子的 stages：boss_type/boss_hp/traits/strategy/pets）。
2. 规则表 `scrape/counter_rules.md`（机制→反制）。
3. 可用 `mcp__seer__nick` 查精灵机制、`mcp__seer__mult` 查克制（可选）。

## 输出（每关一段，宁缺毋滥）
写入 JSON，结构 `{ "factor":..., "difficulty":"地狱", "whys": [ {"stage":1, "why":"..."}, ... ] }`
- `why` 用一句到三句中文，讲清：①这关 Boss 的致命机制是什么；②为什么用这套精灵/技能能反制（对应 counter_rules 里的哪条）；③有没有更稳/更便宜的替代点（若帖子里给了多方案，点一句差异）。
- 没有 traits 的关，`why` 写「缺少 Boss 特性，无法给出机制解释」，不要硬编。
- 不为命中维度乱下结论：Boss 高闪避→必暴即可，不写「必须必中」；只有明确命中弱化才提必中。

## 批量方式
每个因子一个 agent：读 counter_rules.md + 该因子数据 → write 到 `scrape/whys/factor-<i>.json`，最后回复一行 `{"factor","stages","explained"}` 汇总。