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