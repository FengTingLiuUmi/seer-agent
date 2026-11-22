---
name: 赛尔号 PVE 知识库（llmwiki）
tags: index,知识库
---

# 赛尔号 PVE 知识库（llmwiki）

面向父 agent 的「阅读理解/决策型」领域知识层：**一页一主题 + frontmatter 元信息 + `[[backlink]]` 关联**。
精确查询（精灵/技能反查、按类型克制 + 定位标签选打手）仍走上层 `BattleData` / `SqliteKB` / `roster_cache`，这里不做 JOIN。

## 目录结构

| 目录 | 内容 |
|---|---|
| `bosses/` | boss如何攻克 |
| `mechanics/` | 机制页：伤害公式、弹伤、多命、因子规则、必先/先制、封属/断回合 |
| `tactics/` | 战术页：常见攻克方式、八四公式、站场、强攻手选型、战斗火焰 |
| `runbooks/` | 实战复盘：哪一关、什么阵容出招、结果如何 |
| 上层 `docs/pve-theory/` | 原始 Wiki 快照（`04-codes` 技能代码、`06-levels` 关卡合规仍以它为准） |

## 检索入口

父 agent 组队时用 CLI 而不是读全库：

```bash
python -m seer_rebuild.cli wiki list              # 列出全部页面（含 tags）
python -m seer_rebuild.cli wiki boss 4092         # 按 species 读某个 BOSS 页
python -m seer_rebuild.cli wiki find --tag boss --type 光  # 按 frontmatter 过滤
python -m seer_rebuild.cli wiki search 弹伤        # 关键词全文检索
python -m seer_rebuild.cli wiki backlink 八四公式   # 谁引用了某一页
```

- **先查 BOSS 页**：拿大概信息；
- **再沿 backlink 跳机制/战术页**：补伤害/弹伤/站位依据；
- **最后用 DB 层选角**：`roster_cache` 按标签+克制挑出账号里实际能上场的打手。

## 页面规范

每个 `.md` 首部是 YAML frontmatter；正文里用 `[[页面标题]]` 做 backlink（标题与 `name` 一致）。
新增一页时照抄 [`_template.md`](_template.md)：

- `name`：页面标题（backlink 目标）
- `tags`：逗号分隔，分类（boss/mechanic/tactic/runbook）+ 属性/机制关键词
- `type`（仅 BOSS）：属性列表
- `species`（仅 BOSS）：精灵 ID
- `multi_life`（仅 BOSS）：0/1/2，表示多命（0=单命，1=2命）

