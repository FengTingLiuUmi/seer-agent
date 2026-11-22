# 赛尔号本体查询（seer KB MCP）

本地 stdio MCP，只读查询 `seer-factor-kb/ontology/seer-all.owl`（赛尔号 PVE 知识图谱）。

## 工具

| 工具 | 作用 | 示例参数 |
|---|---|---|
| `mcp__seer__nick` | 昵称消歧：把「潘/王哈/艾欧/冰潘/村长」等简称解析成规范精灵 id+属性+定位 | `{"name":"潘"}` |
| `mcp__seer__boss` | 查因子某难度的逐关 Boss 硬门 + 反制精灵 + 禁用表 | `{"factor":"佩洛瑟斯","difficulty":"地狱"}` |
| `mcp__seer__role` | 按 PVE 定位列精灵池 | `{"role":"attacker"}` |
| `mcp__seer__mult` | 技能属性 vs Boss属性 克制倍率 + 本系 STAB | `{"skill_type":"机械","boss_type":"机械战斗"}` |
| `mcp__seer__ban` | 查因子×难度的禁用精灵 | `{"factor":"伊塔回溯型","difficulty":"地狱"}` |
| `mcp__seer__plan` | 因子关打法检索（R1 精确整块 + R2/R3 相似关召回 + R4 克制面 + R_hard 硬门 + RRF 融合 + 硬门缺口） | `{"factor":"飞鱼骑士","difficulty":"地狱","stage":5}` |
| `mcp__seer__stats` | 机制占比统计（默认机制 + 冷启动先验 + 各机制 df） | `{}` |

难度取值：`简单/困难/地狱` 或 `easy/normal/hard`。定位取值：`attacker/support/tank/reflect/firstStrike`（或中文）。

## 说明

- 服务由 `F:\python\py310\python.exe` 启动 `ontology/seer_kb_mcp.py`，依赖 `ontology/.pylibs/rdflib`（通过 `PYTHONPATH` 注入）。
- 唯一知识来源 = `seer-factor-kb/ontology/seer-all.owl`：名字(`rdfs:label`/`skos:altLabel`)、属性(`hasTypeCombination`)、克制(`type_multiplier`)、定位(`pve:hasRole`)、硬门(`PVE.*`)。
- `nick` 精确匹配，不做子串（避免「伊芙→伊芙莉莎」误配）。
- 只读，不修改任何文件；本体重建后按 mtime 自动热加载，无需重启进程。