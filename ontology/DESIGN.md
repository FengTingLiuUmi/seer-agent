# 赛尔号本体 · 建模设计（修正版）

## 为什么重构
之前 `seer-onto.ttl` 把「机制/打法/角色」当成了本体骨干 —— 这些其实是**派生/应用层**。
正确做法：**骨干 = 赛尔号游戏本身的实体**，来源与主键对齐 SeerAPI；「打法」只是引用游戏实体的计划/推理层。

## 分层
```
pve 层（seer-pve.ttl，owl:imports seer-game）
  BattlePlan / Step / Role / 推荐与被Ban关系 / 规则
  ─────────── 引用下面的游戏实体 ───────────
game 层（seer-game.ttl，权威 TBox，ABox 由 ingest.py 从 SeerAPI 生成）
  Pet / Skill / Soulmark / ElementType / TypeCombination /
  Factor / FactorStage / Buff / Item / Equip / Nature / Mintmark /
  Title / Suit  ...  以及各种 effect_type
```

## SeerAPI 资源 → 本体类（PVE 子集 + 称号/套装）
| SeerAPI 资源 | 本体类 | 备注 |
|---|---|---|
| pet | seer:Pet | 含 enemy_resource_id 的实例即 Boss |
| pet_class / pet_advance / pet_effect | seer:PetClass / PetAdvance / PetEffect | 分类、进化、特性 |
| skill / skill_effect_type / skill_effect_param / skill_hide_effect | seer:Skill / SkillEffectType | 技能与“先制/固伤/回血/反弹/增伤…”效果类型（**替代我手造的 Buff 分类**） |
| soulmark / soulmark_tag | seer:Soulmark / SoulmarkTag | 魂印 |
| element_type / element_type_combination | seer:ElementType / TypeCombination | 属性与克制 |
| factor / factor_design | seer:Factor / FactorStage | 因子与关卡 |
| buff / buff_type | seer:Buff / BuffType | 状态 |
| battle_effect / field_effect / eid_effect (+ _type) | seer:BattleEffect / FieldEffect | 战斗/场地效果（“机制”的正身） |
| item / item_category | seer:Item | 道具 |
| equip / gem / energy_bead | seer:Equip / Gem / EnergyBead | 装备/宝石/能量珠 |
| nature | seer:Nature | 性格（→ 面板 → 卡阈值） |
| mintmark（ability/universal/gem） | seer:Mintmark | 刻印 |
| **title** | **seer:Title** | **称号（已纳入）** |
| **suit / suit_bonus** | **seer:Suit / SuitBonus** | **套装（已纳入）** |

## 关系 anchor（已从 SeerAPI 观测到的跨引用）
- pet ↔ skill（`skill[]`）、pet ↔ soulmark（`soulmark[]`）、pet ↔ type（`type`→element_type_combination）、pet ↔ factor（`factor[]`）、pet ↔ pet_class
- soulmark ↔ effect/tag；skill ↔ skill_effect_type；pet 有 base_stats（hp/atk/def/sp_atk/sp_def/spd/total）

## 已确认过的主键对齐
- pet id：3512(帝皇之御)、3396/2965(潘多拉)、3329(六界帝神)、3463(时空界皇)、3437(艾欧)、306(鲁斯王)、309(魔焰)、4377(蒂朵)
- soulmark id：821、709、2170、653、776、752、1209、1601

## 下一步
`ingest.py`：用 `seerapi` 拉全量 pet/skill/soulmark/element_type_combination/factor/buff/equip/title/suit/...，
由 rdflib 自动生成 game 层 ABox（含完整克制表、字段级效果类型）。pve 层实例（伊塔五关方案等）作为独立种子文件挂载。