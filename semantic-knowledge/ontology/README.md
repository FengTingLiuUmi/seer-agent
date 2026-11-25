# 赛尔号本体（因子 PVE）—— 建模与使用说明

## v1（重构）核心原则
- **骨干是“赛尔号游戏本体”**，权威来源与主键对齐 SeerAPI（`seer:seerapiId`）。
- **“打法/机制”是上层应用**，不在地基里。地基 `seer-game.ttl` 只描述游戏实体与关系；
  上层 `seer-pve.ttl` 描述方案/步骤/定位/推荐/Ban/替代与规则。
- 设计依据与映射表见 [DESIGN.md](DESIGN.md)。

## 文件结构
| 文件 | 层 | 状态 |
|---|---|---|
| `seer-game.ttl` | 游戏本体（骨干 TBox） | ✅ 当前 |
| `seer-pve.ttl` | PVE 打法层（TBox + 定位个体） | ✅ 当前 |
| `DESIGN.md` | 分层设计与 SeerAPI 资源→类 映射 | ✅ 当前 |
| `seer-rules.swrl` | 推理规则（机制/克制/被Ban→推荐） | ✅ 当前（待按新命名空间重写） |
| `seer-onto.ttl` / `.owl` / `-inferred.ttl` | v0.1「打法本位」旧模型 | ⚠️ 已废弃，仅存档对照 |
| `run.py` / `check_onto.py` / `export_owl.py` | 工具脚本 | 前两个仍指向旧模型，会在 ingest 阶段重写 |

## 怎么打开（Protégé）
1. `File → Open` 选 **`seer-game.ttl`**（Protégé 能直接读 Turtle）。
2. 再 `File → Open` 选 **`seer-pve.ttl`**（它 `owl:imports` 了 seer-game）。
3. 视图：Classes（类层级）/ Object properties（关系）/ Individuals（个体，暂由 ingest 生成）。
4. 想看中文名：`File → Preferences → Renderer` → 用 `rdfs:label` 渲染。

## ABox 从哪来
本层 TBox 不手写实体。下一步 `ingest.py` 用 **seerapi** 拉取并生成：
- `pet / skill / soulmark / element_type_combination / factor / buff / equip / item / nature / mintmark`
- **`title`（称号）与 `suit`（套装）**
- pet 的基础面板（`base_*`）、技能威力/先制、完整克制表、效果类型

已锁定的主键样例（帝皇之御=3512、潘多拉=3396/2965、六界帝神=3329、时空界皇=3463、
艾欧=3437、鲁斯王=306、魔焰=309、蒂朵=4377；魂印 821/709/2170/653/776/752/1209/1601）。

## 本地脚本（旧模型，供参考）
```powershell
python export_owl.py   # ttl -> owl（已切换为导出 seer-game/seer-pve）
python check_onto.py   # 旧模型体检，跑通流程可复用思路
python run.py          # 旧模型的查询+前向推理演示
```
> rdflib 依赖：`python -m pip install --user rdflib`；owlready2 推理需 Java 在 PATH。

---

## 当前实际模块清单（2026-11-24，合并进 `seer-all.owl`）

| 文件 | 内容 | 个体数 | 生成脚本 |
|---|---|---|---|
| `seer-game.ttl` | 骨干 TBox + 精灵/技能/属性/克制 | — | 手写 + `ingest.py` |
| `seer-onto.ttl` | PVE 层 TBox（Boss/关卡/机制/策略/配置/BossTrait/关卡规则） | — | 手写 |
| `seer-status.ttl` + `seer-status-abox.ttl` | 异常状态子本体 | 43 状态 / 16 数据属性 | `ingest_status.py` |
| `seer-pve.ttl` / `-abox` / `-supp` / `-alias` / `-roles` | 因子打法 SSOT、精灵补全、别名与定位 | 详见各自文件 | `ingest.py --pve`、`build_supp.py`、`add_roles.py` |
| `seer-typechart.ttl` | 克制表全量 | 676 关系 / 139 组合 | `ingest_typechart.py` |
| `seer-gear-abox.ttl` | 套装 / 部件 / 称号 / 性格 / 场合 | 481 套装 / 2132 部件 / 597 称号 / 25 性格 | `ingest_gear.py` |
| `seer-boss-abox.ttl` + `seer-factors-abox.ttl` | Boss 硬门与因子关卡 | — | `ingest_factors.py` 等 |
| **`seer-effects-abox.ttl`** | **战斗效果层（buff / 战斗效果 / 场地 / 魂印 / 特性 / 宝石 / 能量珠 / 进阶 / 刻印 / 道具分类）** | buff 3555、战斗效果 43、场地 3、魂印 2167、魂印标签 20、特性 300、特性组 50、宝石 245、能量珠 48、进阶 28、刻印 3843、刻印分类 98、道具分类 21；外加 1906 只“魂印引用到的精灵”占位个体 | `ingest_effects.py` |

`seer-effects-abox.ttl` 的几点约定（改数据前先读 `ingest_effects.py` 顶部注释）：

1. **个体 IRI = `seer:{资源名}_{id}`**，嵌套引用按 url 里的资源名派生，天然接得上
   （`seer:pet_2419`、`seer:soulmark_tag_4`、`seer:mintmark_class_12`）。
2. 引用字段用专用对象属性（`buffType` / `soulmarkTag` / `affectsPet` / `mintmarkType` /
   `containsMintmark` …），避免和同名数值属性抢词；`test_regression.py::TestEffects`
   有一条不变量专门守“同一属性不得对象/字面量混用”。
3. `seer:effect` 已被异常状态模块占用，本层一律写 `{资源}Effect`（`gemEffect` /
   `mintmarkEffect` / `soulmarkEffect`），否则会触发 domain 违规。
4. 魂印表覆盖全服 2579 只精灵，而本体只精模 PVE 池（~673 只）：`--no-stub` 之外的默认
   行为会用 `scrape/pets-index.json` 给缺的精灵补 `rdfs:label + seerapiId` 占位（不写六维/
   属性组合，避免冒充精模数据）。

重跑方式（增量、可断点续跑，详情缓存 `.cache/effects/{res}/{id}.json`）：

```powershell
$env:PYTHONPATH="<ws>\seer-factor-kb\.pylibs"; $env:PYTHONUTF8="1"
python ingest_effects.py                     # core 集（约 10k 次取数）
python ingest_effects.py --only mintmark     # 单资源补数
python ingest_effects.py --only gem --purge gem   # 改了字段映射后重建该资源
python sync.py --merge-only                  # 并入 seer-all.owl
python test_regression.py                    # 42 项回归（含 TestEffects 8 项）
python status_selftest.py --baseline _mcp_baseline.json   # 重建后重采基线
python status_selftest.py --check  _mcp_baseline.json     # 三个维度全绿才算过关
```

MCP 侧随之新增两个查询工具（`seer_kb_mcp.py`）：`soulmark`（按精灵/标签查魂印，
`pve_only` 过滤）与 `effect`（按关键词查 buff/战斗效果/场地，含高频 buff 标签概览）。
**新增工具要重启 MCP 进程才会出现在 `tools/list` 里**（图本身按 mtime 自动重载）。

## 尚未接入（已知缺口）
- `item` 全量 12802 条未灌（多数是素材/装饰；建议按“战斗消耗品”分类定向灌）。
- `eid_effect` / `skill_effect_type` / `pet_class` 未灌（前者已由技能层部分覆盖）。
- 没装 `owlready2`（无 Java 环境），`sync.py` 的 HermiT 一致性推理一直跳过；
  `check_onto.py` 因此跑不了，结构验收改由 `status_selftest.py` 的 rdflib 断言兜底。