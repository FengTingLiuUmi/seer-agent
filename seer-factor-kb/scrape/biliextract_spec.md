# B站补特性抽取契约（bilibili extract spec）

目的：论坛正文里缺 Boss 特性时，用 web_search 查 B站攻略补「逐关 Boss 特性 + 攻略方式」。

输出 schema 与 `extract_spec.md` 完全一致（items[].stages[] 的 boss_type/boss_hp/traits/strategy/pets/config），并增加 `source`（来源 URL 或搜索词）。

## 每个因子一个 agent 的流程
1. `web_search` 组合查（命中优先）：`赛尔号因子精灵 <name> 地狱难度 攻略`、`<name> 地狱 因子 特性`、`<name> 地狱因子 打法`。
2. 必要时 `web_fetch` 打开最像的结果页（B站 video 简介、dvg.cn/aisee.tv 镜像、贴吧等）。
3. 从结果文本抽逐关数据，宁缺毋滥不编造。
4. `write` JSON 到 `scrape/biliextract/<slug>.json`；查不到写 `stages:[]` + note。
5. 回复一行 `{"factor","stages","found"}` 汇总。

## traits 关键词（同 extract_spec）
必先/封属/N固伤/免疫物攻/免疫特攻/只吃暴击/消强/吸强(偷强)/两命/多命/免死/裸伤上限/面板免疫/护盾/盾罩/清PP/断回合/命中弱化/闪避/随机弱化/全属性+1/吸血/回血/月亮/暴食/必暴/必中/减伤X%/具体异常名。

## 难度优先级
地狱 > 困难 > 简单；先尽量地狱，标题里同时有困难可一并补 note。

## 进化形态
精确到「前缀·名」：无限·欧根尼克≠欧根尼克、裂岩·艾克特希≠艾克特希、曜焰万象·文森特≠文森特、枫落殇·西叶≠西叶 等。