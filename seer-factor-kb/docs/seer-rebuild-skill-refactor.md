# seer-rebuild skill 重构蓝图

> 目标：把 seer-rebuild 钉死在「传感 + 执行」两件事；一切「名字/属性/克制/定位/思路」都从 `seer-factor-kb` 本体（SSOT）取，不再自己维护知识。
> 本文件是**要替换 `~/.agents/skills/seer-rebuild` 的蓝图**（那份在工作区外，先落这里审）。

## 0. 边界（谁管什么）

| 层 | 职责 | 产出 |
|---|---|---|
| seer-factor-kb（知识/规划，不动执行） | 本体、克制、定位、攻略召回、适配(prompt)、玩家缓存 | 改后阵容（species 名 + 思路） |
| seer-rebuild（传感 + 执行） | 登录、只读 dump、把改后阵容映射到个体并发包、日志 | 统一 JSONL + 可发包步骤 |

## 1. 数据契约（核心）

**物种 = `seerapiId`（int，对齐本体 `seer:seerapiId` + IRI `seer:pet_<id>`）**
**个体 = `catch_time`（int，同物种可多只，唯一标识）**
**位置 = `bag`(43706 背包) / `elite`(2361 精英仓库) / `normal`(2303 普通仓库)**

新增命令 `roster-dump` 只吐原始 id，不内嵌 name/type/role：

```
# JSONL，每行一条个体
{"uid":"753949294","kind":"pet","species_id":3512,"catch_time":1612845486,"location":"bag"}
{"uid":"753949294","kind":"pet","species_id":3512,"catch_time":1656067893,"location":"elite"}
```

消费侧（`player/load_dump.py`）按 `(species_id, catch_time)` 去重，并拿 `scrape/pets-index.json`（SeerAPI 全量表）补 clean_name。

## 2. 知识 SSOT（消名字/克制/定位三源冲突）

| 知识 | 唯一来源 | seer-rebuild 该做什么 |
|---|---|---|
| 精灵名 | 本体 `rdfs:label`；clean 名 = `pets-index.json`(SeerAPI) | **放弃** `BattleData.local_names` |
| 属性 | 本体 `hasTypeCombination` | 不自己算 |
| 克制 | 本体 `type_multiplier.combine2`（seer-typechart.ttl） | **放弃** `docs/pve-theory` 克制引用 |
| 定位 | 本体 `pve:hasRole`(强攻/辅助/站场/弹伤/必先) | 不自己标 |

- `seer-query` 降级：只用于查本体**没建模**的资源（item/equip/skill 等）；名字/克制/定位一律走知识侧 MCP：`nick / boss / role / mult`。
- `scripts/read_main_full.py` 的 `local_names()`（BattleData）删除或不再使用。

## 3. 命令面

**保留**：`login / bag / warehouse / team / factor / inventory / parse-cjc / app-log / capture-summary / inspect-app / probe / session / yaxue / battle-report / wiki`

**新增（已做）**：
- `roster-dump [--account --password] [--out file.jsonl]` —— 三处只读、统一 JSONL。✅ 已实现（`seer_rebuild/roster.py` + `cli.py`）。

**新增（待做，需小号验证）**：
- `factor-plan` —— 输入「改后阵容（species 名列表）+ 思路」，输出 `FactorStagePlan`（把 species → 玩家实际 `catch_time` 个体 → 出招 2405 / 换宠 2407 序列）。
  - 不再做「dry-run 预览」两段；直接产出可发包步骤，真发包仍走现有 `--send --write` 显式开关保护。

**废止**：
- `feature --seq factor` 里的手写 steps 路径，合并进 `factor-plan`。

## 4. 执行桥（`factor-plan`）输入/输出

```json
// 输入（适配层产出）
{"design_id":225, "difficulty":3, "stages":[
  {"stage":1, "lineup":["帝皇之御","月照星魂","深渊狱神·哈迪斯"], "思路":"表姐自爆必暴+克制强攻"}
]}

// 输出（seer-rebuild）
{"stage":1, "individuals":[
  {"species_id":3512,"catch_time":1612845486,"role":"首发/自爆","skill":31505},
  {"species_id":3866,"catch_time":<该玩家月照的catch>,"role":"强攻","skill":<技能id>}
], "moves":[2405..2407..2405], "send_guard":"--send --write"}
```

## 5. 已做 / 待做

**已做（本次，全本地不登录）**
- `seer_rebuild/roster.py` + `cli.py` 的 `roster-dump`（统一契约）。
- `roster.jsonl` 已导出（大号当天状态，1138 条原始）。
- `player/load_dump.py` 改吃 roster.jsonl，name 走 SeerAPI 全量表。

**待做**
- 用**小号**登录验证 `factor-plan`（写一个能跑的雏形）。
- 把本蓝图内容写进真正 `~/.agents/skills/seer-rebuild/SKILL.md`（需工作区外写权限）。
- ✅ 删 `read_main_full.py` 的 BattleData 名反查（`local_names` + 名称反查循环已移除，输出只留原始 id）。`docs/pve-theory` 克制引用改为"参考，本体为准"（待做）。
- ✅ `seer-query` 指向本体：新增 `seer_rebuild/ontology.py`，`seer-query pet`/`mcp_server.seer_query` 的精灵名/ID 消歧走 `seer-all.owl`（精确匹配），item/equip/skill 等未建模资源仍走 seerapi。
- MCP 合并：知识侧 `seer_kb_mcp`(nick/boss/role/mult/ban/**plan/stats**) 已单入口指向 `ontology/seer-all.owl`；执行侧(reroster/factor-plan)合并与重启见 DSH 侧 bundle（`@local/seer-kb-mcp`）。