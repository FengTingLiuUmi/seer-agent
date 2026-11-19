---
name: seer-rebuild
description: 用 seer-rebuild 反向重建的赛尔号客户端执行登录、Unity 真机登录、只读探测、背包/仓库/装备、精英仓库移入背包、精灵因子、本地战斗模拟、SeerAPI 查询、日志/抓包解析。当用户要求操作赛尔号账号（登录/看背包/看精英仓库/把精灵加入背包/跑因子/本地战斗）、复现雷小伊脱机日常 2.0.9 的功能、或需要把 ID 反查成精灵/技能/道具名时使用。
---

# seer-rebuild 工具包

对 `F:\seer\雷小伊脱机日常 2.0.9.exe` 逆向重建的可执行代码，入口是 CLI：

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
| `battle-window --player --enemy [-plan]` | 本地战斗模拟窗口 | 本地 |
| `simulate --player --enemy [--plan] [--boss-effect]` | 本地战斗模拟（文本战报） | 本地 |
| `battle-window --replay <出招记录.txt>` | 回放真实出招记录 | 本地 |
| `parse-cjc <文件.cjc>` | 解析对战方案 | 本地 |
| `seer-query <resource> <id> [--name]` | 用 seerapi 查数据 | 只读 |
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
7. **本地战斗**：`simulate --player 3022 --enemy 4649 --plan <王哈1.cjc> --boss-effect "id:args:文本;..."`。
8. **查 ID 名称**：`seer-query item 1300670 --fields id,name` 或 `seer-query pet --name "王之哈莫"`。

## 精灵因子（打因子）

「精灵因子」与「图鉴」是两套东西：`45543` 返回**图鉴/精灵收集进度**（`[id][ts][flag][progress 0-100]`），**不是**因子关卡表。

数据模型（seerapi `factor` / `factor_design` + 本地 `Fragments.ini` 对齐）：

```
目标精灵 → factor(factor_id) → factor_design(design_id)
  ├─ 5 关 BOSS = difficulties[].tasks[].boss_pet.id（easy/normal/hard 同序）
  └─ 读状态用 46046 forever 键：time_value / progress_value / fail_times
```

已知因子：

| 因子 | factor_id | design_id | 5 关 BOSS |
|---|---|---|---|
| 谜之英雄（当前） | 2400532 | 225 | 4539文森特 / 4330审判之魂 / 4137坚盾·瓦尔德 / 4845白图泰 / 4848谜之英雄 |
| 灵巢之主·索杰德尔 | 2400338 | 141 | 4569 / 4568 / 4594 / 4597 / 4599 |
| 沙罗摩奥 | 2400612 | 267 | 3296暗烬朱雀 / 4531极恶妖兽 / 4938塞壬斯 / 4625伏尔格安 / 4965沙罗摩奥 |
| 戟决先锋 | 2400545 | 228 | 3618埃拉辛姆 / 3595泰拉图斯 / 3599卡杉德拉 / 3978克利奥 / 4857戟决先锋 |
| 伊娜 | 2400611 | 266 | 4092诶西欧 / 4370僧行 / 4813夏莉莉(单精灵) / 4960塔尼瓦 / 4964伊娜 |

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

- `42396 [关卡id][1][1]` 是雷小伊 **7 月旧链路**（关卡 id=0x6f=111 属沙罗摩奥），官方端不用。
- 雷小伊当前「打因子」的战斗走 **Flash 加密通道（端口 1247）未解密**；选关/换阵容/查进度仍走 Unity 明文。
- 出招循环代码：`factor.battle_loop_steps(skills, switches)`（skills 比 switches 多 1）。
- 代码：`seer_rebuild/factor.py`（`FactorSpec`/`KNOWN_FACTORS`/`CURRENT_FACTOR`/`factor_enter_steps`）、`seer_rebuild/factor_runner.py`（`FactorStagePlan` + `build_factor_stage_steps` + `read_state` + `run`）。

运行：

```powershell
python -m seer_rebuild.cli factor --list --account <号> --password <pw> --resolve  # 只读
python -m seer_rebuild.cli factor --stage 1 --design-id 225 --account <号> --password <pw>  # dry-run 看步骤
python -m seer_rebuild.cli factor --stage 1 --design-id 225 --account <号> --password <pw> --send --write  # 真发
```

## 因子战斗实战要点（已真机验证）

### 多精灵关战斗节奏

- **每只精灵一场只能行动一次**：`2405 出招 → S2C 2505 → 2407 换宠 → 2405 出招 → …`（切回已行动精灵报 `10021`）。
- 配队 = N 只精灵各带一个技能，用 `factor --skill <技能序列> --switch <换宠catch序列>`（switch 比 skill 少 1）。
- 正式栏上限 6 只；加人前先 `team move --catch-time <x> --send`（2304 flag=0）移除死重。

### 八四公式（简单多精灵关通用解法，已真机过第2关）

`帝皇之御首发 31505 守御八方(自爆→下两次必先必暴必中) → 换1级六界 19314 剑挥四方(弹伤→BOSS 到 1 血) → 换1级时空界皇 31253 时空跃迁术(必先补刀)`

```powershell
team starter --catch-time 0x602211ae --send                       # 帝皇之御首发
factor --stage 2 --design-id 228 --catch-time 0x62ef6f18 \
  --skill "31505,19314,31253" --switch "0x62ef6f18,0x5ffd1dd6" --send --write
```

### 单精灵关（1v1，第3关）

不能 2407 换宠，只派首发 solo。同为 `2405 → 2505 → 42390(+45827) → 2506`；**有 45827 才是过关**（无 45827 = 战败）。

卡杉德拉(战斗+火) 实机通关解法（账号 ACCOUNT）：

- **精灵**：圣灵谱尼(5000 神灵)首发，魂印「生命(回1/4)+能量(按损失体力50%百分比)」boss 有效。
- **配队 buff**：西游四件套(首发全属性+1) + 启灵元神(神照给首发30%HP护盾) + 银翼套装(攻击+30%) + 漫游者-AH目镜(攻击30/特攻30/体力40) + 属性称号「夏日狂想曲」(id 417，攻击+60/体力+30，用 `team title --title-id 417 --send` 即 3404 切换)。
- ⚠️ 属性称号必须真正发 3404 切换（不是只读回包）；账号有**多个**可戴的属性称号（`team title --title-id <id> --send`）：已实测 417 夏日狂想曲(攻击+60/体力+30)、300 神话(体力+100/双防+25) 能戴；236 齐天小圣 / 272 吉光凤羽 / 268 皇帝的意志 报 1940035（不可切）。seerapi「能力加成」称号共 91 个，账号拥有不少，别只按名字搜 2 个就下结论。
- **连招（关键）**：交替 `25679 光荣之梦 → 31143 神灵救世光`。
  - `25679`：全属性+1（对手非混沌则翻倍=+2）+ 下2回合先制+2 + 回1/2体力；
  - `31143`（第5招，160威力）：靠 25679 的先制+2 **抢在 BOSS 必先前出手**，且「消除对手回合类效果→3回合禁止回血 + 吸取200固定 + 未击败叠百分比伤害」。
  - 例：`--skill "25679,31143,25679,31143,25679,31143"`（交替即可，磨死）。

呆 BOSS 卡杉德拉是「必先+2」且会 26091「免疫<400伤害」+26092「回血1/3」，所以：**必须用先制招抢在必先前出手**，且**必须用带「消除回合/禁回血」的招**（31143 正是）。

### 伊娜因子（design 266）已真机通关要点

- 5 关 BOSS 见上文「已知因子」表；第 3 关夏莉莉(4813)是单精灵关。
- 第 1-4 关：圣灵谱尼 solo（25679→31143 交替）或八四公式都能过；第 4 关塔尼瓦(地面+龙，先制+3/消强/弱化/固定伤害)谱尼 solo 会死，用八四过。
- **第 5 关伊娜本体(地面+超能，先制+3 + 每回合回血 + 减伤 + 固定伤害)真实通关解法**：
  - 套装换 **漆黑天使套(448)**：全属性+50 / 攻击伤害+40% / 首发300护盾 / 首发首攻必暴（仅限 BOSS），**保留漫游者-AH 目镜**；
  - 首发圣灵谱尼 + 西游四件套 + 启灵元神 + 称号「夏日狂想曲」(417)；
  - **出招：连续打 `31143 神灵救世光`，不要再插 `25679 光荣之梦`**。31143 的「消除回合类效果→3回合禁回血」正好锁死伊娜每回合回血，+「吸200固定 + 未击败叠百分比」越打越疼；25679 的先制+2 对先制+3 是浪费回合。8 回合谱尼几乎满血过。
  - 换装命令：`team equip --ids "1301043,1301040,1301045,1301044,1301046" --send`（漆黑头 / 漫游者目镜 / 漆黑腰 / 漆黑手 / 漆黑足）。

### 出招节奏 / 装备读取 修正

- 「每只精灵一场只能行动一次」只在 **normal/hard 的「不可重复上阵」规则**下成立；**easy 无此规则，同一只精灵可连续行动多次**（伊娜全 5 关实测：圣灵谱尼一场连打 8 回合）。
- ⚠️ `42399 MULTI_ITEM_LIST` 是**道具背包**查询，**不是装备拥有探测**（用它查套装会误报「没有」）；判断套装拥有要换思路：直接换装试/或读本地 `suit.ini` Arry 再核对。
- 战报能力：`seer-rebuild/battle_report.py` + CLI `battle-report --timeline ... --bag ... --snap ...`；`scripts/factor_fight.py` 加 `--report-dir <dir>` 落 timeline/bag/snap/report。实时装备/称号读取修好了（之前把 `connect()` 返回的 1001 登录快照丢了）。

### 因子难度推进 / 每日限制（实测）

- 因子是「碎片农场」：三难度各自 5 关，兑目标精灵消耗 `pet_consume` 碎片（伊娜=400）；简单每关 12 片、普通 18、困难 36。
- **每个难度每日只能刷一轮**：简单 5/5 打完后再 `41284 进关(diff=1)` 报 **1905004**（战斗不初始化）；推进到普通后简单不能再回刷。
- 简单→普通→困难依次推进：`46046` 三键 `[progress,time,fail]`，`time` 1→2 表示已推进到普通；`progress` 低 16 位是难度标记（0x100 简单 / 0x200 普通 / 0x400 困难），高 16 位是本难度已过关数。
- `41413` 领取/结算 action=(1,0) 实测报 **103208**（未到结算条件时）。
- **普通难度规则**：每场战斗 **6 回合内必须击败** + **不可重复上阵**；BOSS 普遍带「减伤 + 每回合回血」，谱尼 31143 暴击被削到 ~685、八四六界弹伤被削到 ~45%，easy 那套伤害不够、暂未破（需要 无视减伤/固定/百分比穿透 的打手）。

### 克制速查（戟决先锋 5 关）

| 关 | BOSS | 类型 | 最优克制 |
|---|---|---|---|
| 1 | 埃拉辛姆 | 神秘+战斗 | 超能 / 虚空 4× |
| 2 | 泰拉图斯 | 草+战斗 | 飞行 4× |
| 3 | 卡杉德拉 | 战斗+火 | 水+超能 4×（卫岳）；超能/虚空/飞行 2× |
| 4 | 克利奥 | 虫 | 火 / 飞行 2× |
| 5 | 戟决先锋 | 冰+暗影 | 战斗 / 火 / 虫 2× |

### 关键坑

- `2405` 必须用精灵**当前装备**的技能：先 `43706→2301` 读装备技能槽（`pet_details.parse_2301`）；seerapi learnset 里的招不一定装着。
- 单精灵关的 S2C 2503/2504 体积明显更小（约 924B/442B），可据此识别是否已推进到单精灵关。
- 双属性招对「有一个克制、另一个被抵抗」的 BOSS 会被稀释；尽量用纯属性招或双克制招（如 水+超能 打 战斗+火）。

## 因子关自动化（父子 agent 协作）

> 这是「调度模板 + 工具」，**不是内置关卡预设**。具体某一关用什么阵容/出招，由**父 agent 现场读 BOSS 后动态生成**，作为 context 下发给子 agent。

### 父 agent（lead）职责

1. 登录 + 读背包/仓库：`bag`、普通仓库 `2303`、精英收藏 `2361`（`warehouse list`）。
2. **读因子进度**（判断从第几关开始）：`46046` 查 `[0x4a0c6, 0x4a0c7, 0x4a0c4, 0x1ece9]`，响应第 2 位（`0x4a0c7`）= 当前打到的关数（第 1 关=0、第 3 关=3）。
3. 对当前关 BOSS（species/属性/特性），现场组队 + 定出招（用 `seer-query` / `BattleData` 反查）。
4. 逐个调度子 agent，循环打完、汇总结果。

### 子 agent（专注单关）输入/职责

父下发这样的 context（JSON）：

```json
{"boss_species": 3296, "lineup": [3512, 3045, 3463], "moves": {"3512": 31505, "3045": 19314, "3463": 31252}}
```

子 agent 只做三件事：
- 本地模拟出战报：`simulate --player 3512,3045,3463 --enemy 3296 --moves ...`
- 真机打一关：官方 Unity 链路 `factor_enter_steps()` = 41284 进关 → 41282 开始战斗 → `battle_loop_steps()` 2404/2405/2407 出招（默认 dry-run，`--send --write` 真发）；换阵容用 `team` 的 2304（flag 0/1/2/3/4）
- 回传胜负（观测 2506 FIGHT_OVER）

### 为什么预设不写进 skill

- skill 只沉淀「怎么登录/读/调阵容/模拟/真机只写/反查」这些**稳定能力**；
- 关卡阵容是「攻略知识」，会随关卡/版本变化，应由父 agent 每次现场组队，保持灵活性。

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

**打因子一关的标准流程（SOP，务必照走，别省）**：

1. 读 BOSS：`factor_design`（`seerapi get factor_design <design_id>`）拿当前关的**规则**（6回合/不可重复上阵/封属/断回合）与**特性 desc**；再读 `04-codes.md` / `05-boss-traits.md` 查对应机制。
2. 读追踪键：`46046` 读 rule id=1 的 `user_info`（伊娜=303248..303271），确认哪些 catch_time 已被锁、本轮不可用。
3. 选打手：用 `python -m seer_rebuild.roster_cache` 或 `seer_rebuild/roster_cache.py` 的 `station_tanks()` / `attackers(stype=...)` 从 `.roster_cache` 选（静态类型/种族值 + 动态等级/技能 + SqliteKB 标签三层 JOIN）。
4. **精简阵容 + 换装/称号**：只放本关确实要用的（过关会锁阵容所有 catch_time）；按战术换套装/称号（强攻=银翼+星光铸就者(591)，站场=漆黑+神话(300)）。
5. 出招序列定好后，`factor --stage N --design-id <id> --difficulty 1/2/3 --skill ... --switch ... --send --write --report-dir ...` 真打，逐回合看 2505 血量；**有 45827 才是过关**。

## 实战教训（伊娜普通第1关真机复盘，2026-11-18，用户实测）

## 实战教训（伊娜普通第1关真机复盘，2026-11-18，用户实测）

真机打通伊娜(design 266) 普通第1关（诶西欧，神秘·超能→**虚空4×**/2命）。我此前 4 处全错，务必记住：

1. **出战背包要精确清到本关所需阵容**：不可重复上阵(rule id=1)下，多余精灵会被派出/占位，后面无精灵可用。打前用 `team move --catch-time <ct> --send`（不带 `--to-bag`=放回仓库）清干净，只留确要用几只。
2. **装备/称号按战斗类型换（不换=白送）**：
   - 多精灵**强攻** → 银翼骑士套(365，先手加法增伤60%) + 称号「星光铸就者」(591)；
   - 单精灵**站场** → 漆黑天使(448) + 称号「神话」(300)。
   - 用 `team equip --ids ... --send` / `team title --title-id ... --send` 真发切换。
3. **BOSS 可能多命**：诶西欧 2 命。多命要「多强攻手连发」或「弹伤(六界剑挥四方→1血)+收割」；这关实证 **六界 + 希瓦** 过。判断多命别只依赖 factor_design desc（它没写），以实战/2506/复苏为准。
4. **强攻手核心 = 必先出手 ＋ 打出最大伤害（不看先制、不看初始威力）**：
   - PVE 中 BOSS 必先 + 血极厚：**先制+N 快不过「必先」，所以先制不重要**；出手保障只看「**必先（必定先手）**」——自身魂印/技能自带，或表姐(帝皇之御 31505 自爆→必先必暴必中)提供，或能扛住 BOSS 一下（草王/护盾类辅助给盾）。
   - 强攻手核心技能 = **能打出最大有效伤害的那招**（翻倍/增伤后最高），而非面板威力 / 必中 / 先制。
   - **希瓦(3865)＝虚空单属性物攻强攻手**，核心＝**湮灭幽袭(33301，130威力，「当前HP低于对手则威力翻倍」→ 低血×2 = 260 有效威力)**，纯虚空 4× 打神秘·超能类，压血后伤害最大。必先由表姐自爆(31505)提供。
   - 神罗(4169)＝虚空·混沌（打神秘·超能仅 2.75×），同样有低血翻倍技、需压血；不压血即白板。
   - 常见增伤强攻手：**月照星魂(3866)、魔钰(3567)**；弹伤：六界神王(3045，剑挥四方19314→1血)。
   - 4倍克制优先选**单属性**克制技；高闪避用**必中**。
5. **「不可重复上阵」= 过关才锁本关出战的 catch_time，失败/未过关不锁**：
   - 追踪键 = `factor_design` 里 rule id=1 的 `user_info`（伊娜 design 266 = 303248..303271 共 24 个）；用 `46046` 读，值 = 已锁定的 catch_time（0=空槽）。
   - 实测：第1关过关锁了 帝皇/六界神王/希瓦 3 只；我第2关失败(战败)用的 蒂朵/六界帝神/时空 **仍未被锁**（可复用）。→ **只有过关才锁本关出战精灵**。
   - 报错 `1905010「错误的操作顺序」` 经常是「已出战精灵重复上场」的迷惑文案。
   - 组队前先读追踪键，确保所选精灵本轮未被锁。
6. **弹伤机制（剑挥 19314 类）＝反映一个实际伤害量；「剩 1 血」只在"会结算死亡"的一条命触发**：
   - 弹伤伤害足够弹死当前命。若目标是**最后一条命**（打死即结算死亡），弹伤才把它定格在 **1 血**，需补刀收；若目标**不是最后一条命**（后面还有命）→ **整条命被弹掉**（直接死，不剩 1 血）。
   - 2 命 BOSS（命2 满血）：弹伤把**命1 直接弹掉** → 再用**强攻手伤害 > 命2 HP** 收命2（强攻手多、弹伤手少，故优先这样省弹伤）；或第二发弹伤把命2 打到 1 血再补刀。
   - 锁按 **catch_time**：同名精灵的不同个体可分别上场。
   - **站场手不一定需要克制**：只要能在击败 BOSS 前活着即可（回血/减伤/护盾/免死 + 固定/百分比/真实伤害磨）。选型看「生存 + 稳定输出」，不看克制。
7. **伊娜普通第2关（僧行 2 命）已过关配方（3 只就够，别多带）**：
   ```
   蒂朵(4377) 35914 幻梦芳逝（自爆→下只必先必中）
   → 六界帝神(3329) 19314 剑挥四方（弹伤→命1直接弹掉）
   → 月照星魂(3866) 33309 月下华尔兹（增伤强攻→一击收满血命2）
   ```
   - 月照魂印「登场首回合 100% 必暴（每场2次）+ 致命附加百分比伤害」就是能爆命2 的增伤强攻手；不等补刀、不等双强攻。
   - ⚠️ **过关会把本关**出战阵容**里的精灵全锁（含没出招的后备）**：这次多带的魔钰也被锁了。→ 阵容要精简到「本关确实要用」的几只，别放占位。
8. **伊娜普通第3关（单精灵 夏莉莉）已过关配方（1 只 solo）**：
   ```
   加尔鲁特(4606 草) 37140 叶刃百裂击 × 5 回合
   ```
   - 夏莉莉 = 地面·超能，**先制+6(必先) + 每回合断回合 + 隐藏**。单精灵关不能换宠。
   - **断回合会清「我方回合类效果」**（减伤/护盾/回血/强化都会没了）→ solo 别靠回合类站场（如星光·丽莎布布的减伤就被清、3回合死）。
   - 正确思路 = **给 BOSS 上 debuff**：加尔鲁特魂印「受击后给 BOSS 叠碧叶猛毒」，减伤+增伤+固伤全算在 BOSS 身上，**不被断回合清**；草 1.5× 磨死。
   - 过关配方不需要克制站场，唯一标准是「活着磨死 + debuff 型减伤」。

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

## 未实现（诚实告知用户）

- `.ysc`（VMProtect）/ `.cjcy` 内部 `dzb.txt` 未解密
- `account.ini` 的本地密码解密未定位
- 雷小伊「打因子」的**战斗**走 Flash 加密通道（端口 1247）未解密；官方 Unity 端打因子走明文（`41284/41282`）
- 「进战斗之后的出招循环」（2404/2405 逐回合）尚未真机端到端验证
- 完整“一键日常”写包未抓全；`feature` 的 write 目前是抓包回放（固定 ID）
- 阵容“任意中间槽位互换”（交换第 i / 第 j 个正式位，非第 1 位）未在抓包里看到单独命令；**换首发=2308** 已覆盖“把某只提到第 1 位”

详细命令与证据见 `seer-rebuild/README.md`、`docs/逆向分析.md`、`docs/登录实现.md`。