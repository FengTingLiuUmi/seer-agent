---
name: seer-rebuild
description: 用 seer-rebuild 反向重建的赛尔号客户端执行登录、Unity 真机登录、只读探测、背包/仓库/装备、精英仓库移入背包、精灵因子、SeerAPI 查询、日志/抓包解析。当用户要求操作赛尔号账号（登录/看背包/看精英仓库/把精灵加入背包/跑因子）、或需要把 ID 反查成精灵/技能/道具名时使用。
---

# seer-rebuild 工具包

## 项目结构（统一 `seer/` 仓库：本体 / 召回 / 执行三层）

```
seer/                          ← 单一项目根（git）
├─ seer-rebuild/           执行层：逆向后端 CLI（本文件主体）
├─ seer-factor-kb/         本体 + KB + 召回层
│   ├─ ontology/seer_kb_mcp.py     MCP stdio server（本体 OWL 按 mtime 热载）
│   ├─ ontology/seer-all.owl       合并本体（seer: / pve: 命名空间）
│   ├─ kb/docs/<因子>/<难度>.json    关卡 SSOT（Boss 硬门/血量/策略/counteredBy）
│   └─ player/                     召回应用层（match_factor/generalize/loadouts.json）
└─ seer-kb-mcp/            把 seer_kb_mcp.py 注册成 MCP `seer` server 的 bundle（cordis.patch.yml）
```

**本体/召回层 7 个 MCP 工具（`mcp__seer__*`；查「打什么 / 克不克 / 怎么过」优先用它们，别拍脑袋）**：

| 工具 | 作用 |
|---|---|
| `nick <简称>` | 昵称消歧 → 规范精灵（id+属性+定位+机制）|
| `boss <因子> <难度>` | 逐关 Boss 硬门 + counteredBy + 禁用表 |
| `role <定位>` | 按 PVE 定位列精灵池（attacker/support/tank/reflect/firstStrike）|
| `mult <技能属性> <boss属性>` | 属性克制倍率（含本系 STAB ×1.5 规则）|
| `ban <因子> <难度>` | 禁用精灵表 |
| `plan <因子> <难度> <关>` | 打法检索（R1 精确 + 相似关召回 + RRF 融合 + 硬门缺口标注）|
| `stats` | 机制占比统计（冷启动先验）|

**难度受控词表**：`简单=easy / 困难=normal / 地狱=hard`；客户端 int = `1/2/3`（对应 46046 进度低16位 `0x100/0x200/0x400`）。

对 ，入口是 CLI：

```
python -m seer_rebuild.cli <子命令> ...
```

## 前置

```powershell
# 解释器二选一（优先当前 PATH 上的 python，也可用显式路径）
$python = "python"
# 或：$python = "F:\python\py310\python.exe"
# 沙箱内：$python = "C:\Users\kmdbn\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"

$env:PYTHONPATH = "C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild"
$env:PYTHONIOENCODING = "utf-8"     # 避免 GBK 控制台中文乱码
chcp 65001                          # 控制台输出中文

# 凭据：从 dsh-credential-vault 凭证库读取（Agent CLI：vaultctl）。不要写死、不要依赖 env（shell 会清洗凭据）。
# 使用「赛尔号测试账号」=大号 / 「赛尔号验证用小号」=小号（用户在线大号时，测试一律用小号）。
$vault = "$env:DSH_PROFILE_DIR\node_modules\dsh-credential-vault\vaultctl.mjs"
$obj = (node $vault show "赛尔号验证用小号") | ConvertFrom-Json    # .username=账号，.secret=密码（不要 echo .secret）
python -m seer_rebuild.cli <子命令> --account $obj.username --password $obj.secret ...
```

## 命令速查

| 子命令 | 作用 | 是否写操作 |
|---|---|---|
| `login --account <号> --password <pw>` | 账号鉴权（uid/session/网关） | 只读 |
| `login ... --connect --mode unity --version 0x31` | Unity 真机登录并收 1001 帧 | 登录 |
| `probe --account --password` | 登录后发只读命令收集 S2C | 只读 |
| `bag --account --password` | 在线读背包（正式/待命，纯文本） | 只读 |
| `warehouse list\|add --account --password` | 读精英仓库(2361) / 把精灵加入背包(2304，默认 dry-run) | 写可选 |
| `team move\|starter\|demote\|equip\|title --account --password [--send]` | 统一阵容/装备调整（移入移出/换首发/降待命/换装备/换称号，默认 dry-run） | 写可选 |
| `factor --list / --stage N [--design-id 225]` | 打精灵因子（默认 dry-run） | 写可选 + 登录 |
| `feature --seq equip\|factor --account --password` | 装备/因子命令序列（默认 dry-run） | 写可选 |
| `inventory --frames <jsonl>` / `--live` | 背包/装备展示（`--frames` 离线，`--live` 实时） | 只读/登录 |
| `parse-cjc <文件.cjc>` | 解析对战方案 | 本地 |
| `seer-query <resource> <id> [--name]` | 按资源查询：`pet` 走本体(名/ID 消歧，精确匹配)，item/equip/skill 等走 seerapi | 只读 |
| `app-log --path/--battle` | 解析日常日志/出招记录 | 本地 |
| `capture-summary <抓包>` | 分析抓包 | 本地 |
| `inspect-app --root F:\seer` | 读本地战斗库/配置 | 本地 |
| `mcp` | 以 MCP stdio 服务器方式暴露工具 | 见 mcp 说明 |

第二列含 `--account/--password` 的子命令需要账号密码作为参数显式传入。

## 硬性规则

1. **写操作默认 dry-run**：`warehouse add` / `team` / `feature` 只有显式 `--send`（配合 `--write`）才真正发包；其余命令为只读。
2. **账号密码不落盘**：密码只作为命令行参数，用完不写进任何文件；会话日志里脱敏（`session[:6]+'...'+session[-4:]`）。
3. **不用主号**：涉及写/登录的操作提示用户用小号。不要与官方客户端/雷小伊同时在线（会顶号）。
4. **Unity 连接**：`get_unity_gateway()` 从 `unity-ip.txt` 随机取 IP + 随机端口 `1202..1230`（2.0.9 `FUN_0044b723` 反编译），不是固定 1203，也不是 `online_gate` 的 300x。
5. **编码**：读 2.0.9 的 INI/TXT 一律 GBK；写文件用 UTF-8；控制台中文乱码时先 `chcp 65001`。
6. **失败降级**：SeerAPI 反查失败返回 `None`/16 进制，不中断流程。

## 精灵存储三层（与「装备/装扮/称号」是不同维度，不要混）

赛尔号把**精灵**放在三处独立存储，统一用 **catch_time 作为个体唯一标识**（同一 species 可有多只，靠 catch_time 区分；species 只是物种）：

| 存储 | 命令 | S2C 结构 | 说明 |
|---|---|---|---|
| 背包 | `43706 GET_PET_INFO_BY_ONCE`（C2S 空） | `[正式count] + 每只[species+148B+catch_time]`，正式后接待命 | 出战阵容（正式=主队，待命=替补） |
| 精英仓库 | `2361 GET_LOVE_PET_LIST`（C2S 空） | `[count] + N×[species,flag,catch_time]`（12B/项） | 精英收藏；flag=1 表示已出战 |
| 普通仓库 | `2303 GET_PET_LIST`（分页 `[offset][count]`） | 每项 16B `[species,flag,catch,level]` | 大仓库，分页；账号 400+ 只 |

> ⚠️ **找精灵必须三处都读**（43706 + 2361 + 2303），只读精英收藏会漏。实测：西游套的沙悟净(3519)、天河神将(2735) 只在普通仓库(2303)，精英收藏(2361)里没有；三藏(3409)、蒙奇多克(2727) 在精英收藏。

**西游四件套羁绊（首发全属性+1，boss 有效）**：三藏 3409 + 蒙奇多克 2727 + 沙悟净 3519 + 天河神将 2735 同时放正式 → 首发精灵全属性+1。绿火（GUI 借/领）= 全属性+1，可叠成 **全属性+2**（攻防速命中翻倍）。

**移动 = `2304 PET_RELEASE`**，body `[catch_time][flag]`：

| flag | 含义 |
|---|---|
| 0 | 正式放回仓库 |
| 1 | 加入**正式**（主队） |
| 2 | 加入**待命** |
| 3 | 待命放回仓库 |
| 4 | 正式降待命 |

- 换首发 / 待命升正式：`2308 PET_DEFAULT`，body `[catch_time]`。
- 单精灵详情：`2301 GET_PET_INFO`，C2S body `[catch_time]`，S2C 布局：
  `0x00 species` `0x24 level` `0x34 体力(满)` `0x38 体力(当前)` `0x3c 物攻` `0x40 物防` `0x44 特攻` `0x48 特防` `0x4c 速度` `0x6c+8i 技能id(i=0..4)`。
- 代码：`seer_rebuild/warehouse.py`（`read_elite_warehouse` / `add_to_bag` / `plan_add`）、`seer_rebuild/pets.py`（`read_bag` / `parse_pet_list` / `parse_bag_43706` / `move_pet`）、`seer_rebuild/pet_details.py`（`parse_2301`）。

实测证据（账号 ACCOUNT）：精英仓库有两只 3512 帝皇之御（catch=`0x62d8b735` 在仓库、`0x602211ae` 在背包），用 2304 flag=2 把仓库那只加入待命，43706 块数 6→7→8。

## 赛尔号三套「外观/加成」系统（务必区分，不要混）

1. **装备** = 角色身上的「头盔 / 护甲 / 武器 / 目镜」栏，提供属性加成。
   - 单件加成：`seerapi get equip <id>` 的 `bonus.attribute`（如「漫游者-AH」是目镜装备）
   - 套装加成：`seerapi get suit <id>` 的 `bonus.desc`
2. **装扮** = 时装 / 套装外观，只看外形、改皮肤。
3. **称号** = 独立称号栏（如「夏日狂想曲」），提供称号加成：
   - `seerapi get title <id>` 的 `attr_bonus` / `ability_desc`

反查规则：

- 头盔/护甲/武器（装备）→ `seerapi get equip <id>`，看 `bonus`
- 时装/套装外观（装扮）→ `seerapi get suit <id>`，看 `equips` + `bonus`
- 称号 → `seerapi get title <id>`，看 `ability_desc`

部位（equip_type）：0 头部 / 1 目镜 / 2 腰部 / 3 手部 / 4 足部 / 5 背景 / 6 坐骑

## 典型流程

1. **登录并确认**：`login --account X --password P --connect --mode unity --version 0x31 --keep 20`，看到 `[recv] cmd=1001 result=…` 即成功。
2. **看背包（正式/待命）**：`bag --account X --password P`（纯文本，内部 `read_bag`）。
3. **看精英仓库 + 把精灵加入背包**：
   - `warehouse list --account X --password P`（读 2361 精英收藏清单，带名称反查）
   - `warehouse add --account X --password P --species-id 3512`（按物种找个体，默认 dry-run 打印要发的 2304）
   - `warehouse add --account X --password P --catch-time 0x62d8b735 --slot reserve --send`（真发：加入待命）
   - `--slot formal`=加入正式(flag=1) / `--slot reserve`=加入待命(flag=2)
4. **调整阵容/装备（先 dry-run 再真发）**：
   - `team move --account X --password P --catch-time <个体id> --to-bag`（加入背包；去掉 `--to-bag` 即放回仓库）
   - `team starter --account X --password P --catch-time <个体id>`（换首发 / 待命升正式）
   - `team demote --account X --password P --catch-time <个体id>`（正式降待命）
   - `team equip --account X --password P --ids <装备id,逗号分隔>`
   - `team title --account X --password P --title-id <称号id>`
   - 确认无误后加 `--send` 真发。
5. **看背包装备**：`inventory --live <out.jsonl> --account X --password P --resolve`（或离线 `--frames feature1_frames.jsonl --resolve`）。
6. **跑因子/装备序列（先只读）**：`feature --seq factor --account X --password P --resolve`，确认清单后再 `--send --write`。
7. **查 ID 名称**：精灵名/ID 消歧走本体——`seer-query pet "王之哈莫"` 或 `seer-query pet 4816`（精确匹配）；装备/道具/技能走 `seer-query item 1300670 --fields id,name`。

## 精灵因子（打因子）

「精灵因子」与「图鉴」是两套东西：`45543` 返回**图鉴/精灵收集进度**（`[id][ts][flag][progress 0-100]`），**不是**因子关卡表。

数据模型（seerapi `factor` / `factor_design` + 本地 `Fragments.ini` 对齐）：

```
目标精灵 → factor(factor_id) → factor_design(design_id)
  ├─ 5 关 BOSS = difficulties[].tasks[].boss_pet.id（easy/normal/hard 同序）
  └─ 读状态用 46046 forever 键：time_value / progress_value / fail_times
```


**进战斗（官方 Unity 端实证，unity_yz_battle / unity_mzyx）**：

```
46046 [forever 键]          读状态
41284 [design_id][难度]      进入因子关
41282 [design_id][难度]      开始因子战斗
2441 [加载%] → 2404 准备 → 出招循环：
  2405 [技能id]             出招
  2407 [catch_time]         切换精灵（换到下一只再出招）
  2405 [技能id] …
2506 S2C 战斗结束
```

- 出招循环代码：`factor.battle_loop_steps(skills, switches)`（skills 比 switches 多 1）。
- 代码：`seer_rebuild/factor.py`（`FactorSpec`/`load_factor_spec`/`forever_keys`/`factor_enter_steps`）、`seer_rebuild/factor_runner.py`（`FactorStagePlan` + `build_pre_battle_steps` + `read_state` + `run`）。

运行：

```powershell
python -m seer_rebuild.cli factor --list --design-id 225 --account <号> --password <pw> --resolve  # 只读
python -m seer_rebuild.cli factor --stage 1 --design-id 225 --account <号> --password <pw>  # dry-run 看步骤
python -m seer_rebuild.cli factor --stage 1 --design-id 225 --account <号> --password <pw> --send --write  # 真发
```

## 因子战斗实战要点（已真机验证）

### 多精灵关战斗节奏

- 正式栏上限 6 只；加人前先 `team move --catch-time <x> --send`（2304 flag=0）移除死重。

### 八四公式（简单下多精灵单命关通用解法 ）

### 单精灵关（1v1，第3关）

不能 2407 换宠，只派首发 solo。同为 `2405 → 2505 → 42390(+45827) → 2506`；**有 45827 才是过关**（无 45827 = 战败）。

### 出招节奏 / 装备读取 修正

- 「每只精灵一场只能行动一次」只在 **normal/hard 的「不可重复上阵」规则**下成立；**easy 无此规则，同一只精灵可连续行动多次**（伊娜全 5 关实测：圣灵谱尼一场连打 8 回合）。

### 因子难度推进 / 每日限制（实测）

- 因子关：三难度各自 5 关，兑目标精灵消耗 `pet_consume` 碎片（伊娜=400）；简单每关 12 片、普通 18、困难 36。
- 每个难度只能同时进行一个：`46046` 三键 `[progress,time,fail]`，`time` 1→2 表示已推进到普通；`progress` 低 16 位是难度标记（0x100 简单 / 0x200 普通 / 0x400 困难），高 16 位是本难度已过关数。
- `41413` 领取/结算 action=(1,0) 实测报 **103208**（未到结算条件时）。

## PVE 理论知识（组队 / 打因子前先读）

已整理好的 PVE 理论速查在 `seer/seer-rebuild/docs/pve-theory/`（本地快照，来源 BiliGame Wiki《赛尔号PVE概论》，2026-11-18 清理；原文持续更新以 wiki 为准）：

| 主题 | 文件 |
|---|---|
| 基础规则 / 关卡分类 / BOSS 血量 / 能力面板 / 出战顺序 / 道具 | `seer/seer-rebuild/docs/pve-theory/01-basics.md` |
| 红伤公式 / 克制 / 随机 / 出招逻辑 / 增伤减伤 | `seer/seer-rebuild/docs/pve-theory/02-damage-and-logic.md` |
| 战术（强攻/站场/弹伤）/ 外设火焰 / 特性刷法刻印宝石 | `seer/seer-rebuild/docs/pve-theory/03-tactics-and-build.md` |
| 技能「代码 → 效果」速查表大全 | `seer/seer-rebuild/docs/pve-theory/04-codes.md` |
| BOSS 特性词典 | `seer/seer-rebuild/docs/pve-theory/05-boss-traits.md` |
| 关卡类型（排行榜/加速特权/共用次数）与合规边界 | `seer/seer-rebuild/docs/pve-theory/06-levels-and-compliance.md` |

**打因子一关的标准流程（SOP，务必照走，别省）一定要按照这个步骤执行**：
见 `seer\seer-rebuild\seer_rebuild\llmwiki\bosses\一般关卡攻略思路.md`



## 数据路径

| 数据 | 路径 |
|---|---|
| 战斗库（精灵/技能/效果/BOSS/克制） | `F:\seer\seer_cfg\json\` |
| 对战方案（.cjc/.cjpt） | `F:\seer\seer_cfg\script\method\**\` |
| 一键日常配置 | `F:\seer\seer_cfg\DLL\config\一键日常配置\` |
| 出招记录（战报） | `F:\seer\seer_cfg\DLL\config\日常记录\出招记录\` |
| 日常日志 | `F:\seer\seer_cfg\DLL\config\日常日志\` |

## 抓包解析备忘

- 游戏连接是 **binary TCP**（端口段 1202..1230），帧头 17B：`[u32 totalLen][u8 version][u32 cmd][u32 uid][i32 result]` + body。
- 用 `tshark -z follow,tcp,raw,<stream>` 重组流；参考 `seer-rebuild/scripts/dig_*.py` / `analyze_*.py` 系列脚本导出 frames jsonl。
- `capture-summary` 只认 `SEERWS`/JSONL 文本日志，不认 pcapng。
- 战报 2505 的「敌方技能/敌血」要按稳定 **enemy_eid** 锚定（`battle_report._enemy_action_by_eid`），别用「非我方 catch」猜测定位——否则敌血显示成 0/39、单回合伤害算出 ~9993 这类离谱值。


详细命令与证据见 `seer-rebuild/README.md`、`docs/逆向分析.md`、`docs/登录实现.md`。