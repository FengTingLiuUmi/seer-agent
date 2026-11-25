# 因子关检索与冷启动系统（kb/）

> 单一权威源（SSOT）＝ `kb/docs/<因子>/<难度>.json`，一份文件一个主键 `因子#难度`。
> 其余全是它的**派生投影**：索引 / 统计 / 本体 ABox / 检索结果，只从 docs 幂等重建，禁止手改。

## 数据流

```
scrape/factors-final.json ──split_docs.py──▶ kb/docs/*/*.json (SSOT)
                                                    │
        ┌───────────────────────────┬───────────────┴───────────────┐
        ▼                           ▼                               ▼
  build_index.py               build_stats.py                ingest_factors.py(在 ontology/)
  kb/index/ (Whoosh 单关索引)    kb/stats.json (机制占比)      seer-factors-abox.ttl (本体 ABox)
        │                           │                               │
        └───────────────┬───────────┘                               ▼
                        ▼                                  sync.merge_check() → seer-all.owl
                   plan.py (R1+R2/R3+RRF+硬门)                        （HermiT 一致）
                        │
                        ▼
             ontology/seer_kb_mcp.py  tool_plan / tool_stats / tool_boss / tool_ban …
```

## 每个产物

| 文件 | 作用 |
|---|---|
| `docs/*/*.json` | SSOT。每关：`boss_type/boss_hp/traits(原始)/mech(机制标签)/strategies/pets/why/apex`；档级 `ban/tids` |
| `docs/catalog.json` | doc_id → 路径/关数 清单 |
| `index/` | Whoosh 投影，索引单元=单关，字段 `mech/template/type`，`stage_id` 回指 SSOT |
| `stats.json` | 机制占比：`default_mechs`(df>50%) 自动剥离；`by_position / by_position_difficulty / by_type_position`；`cold_start_hints` 每关 top 非默认机制 |
| `seer-factors-abox.ttl` | 本体 ABox（Factor/FactorStage/Enemy/FactorDifficulty + hasMechanic/isApex/bossTypeCombination/bannedPet/counteredBy） |
| `plan.py` | 检索引擎：R1=因子×难度整块直查；R2=机制 Whoosh；R3=数值模板 Whoosh；RRF 融合；硬门缺口标注；冷启动先验 |
| `mechanisms.py` | trait 文本 → `pve:Mechanic` 标签（27 个），0 漏提取 |

## 契约（与前段讨论对齐）

- **召回粒度**：R1 单元＝`因子×难度`整块；R2/R3 单元＝单关；同因子不同难度是近例（归相似路，且 R1 已含）。
- **本体分工**：术语/身份/一致性走 OWL（`pve:Mechanic`、`pve:isApex`、`pve:bossTypeCombination`、`seer:pet_*`）；实例打分与占比在 docs+索引；三者靠 `mech slug` / `pet id` / `tc iri` 引用联动，不复制定义。
- **机制提取是派生**：`mech` 只用于相似/统计/打标签；原始 `traits` 才权威，抽不到就留空（宁缺毋滥）。

## 重建顺序（幂等，任意可重跑）

```powershell
$env:PYTHONPATH = "C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-factor-kb\.pylibs"
$env:PYTHONUTF8 = "1"
cd seer\seer-factor-kb\scrape; python build_final.py            # 更新 factors-final
cd ..\kb;        python split_docs.py                     # 重建 SSOT
                 python build_index.py                    # 重建 Whoosh
                 python build_stats.py                    # 重建统计
cd ..\ontology;   python ingest_factors.py                # 重建 ABox（追加新因子）
                 python -c "import sync; sync.merge_check()"   # 合并 + HermiT
```

## 校验

```powershell
cd kb;        python -m unittest test_kb          # 检索层 11 项不变量
cd ontology;  python -m unittest test_regression  # 本体 26 项不变量
cd kb;        python eval.py                     # 离线基线（硬门覆盖率@k）
```

## 基线（2026-11-22，1156 个地狱有特性查询）

| 指标 | 值 |
|---|---|
| 全查询硬门覆盖率@8 | **90.6%** |
| 带硬门查询硬门覆盖率@8 | **80.0%** |
| 空召回率 | 5.8% |
| 平均召回条数 | 6.4 |

待办：把属性/血量缺口（困难档、部分地狱关）补上后可进一步提升 R3；硬门“反制校验”（免疫物攻→须特攻手）需给每关阵容补攻击类型标注后再加入过滤。