# 雷小伊脱机日常 2.0.9 复刻（seer-rebuild）

本仓库是从 `F:\seer\雷小伊脱机日常 2.0.9.exe` 的内存镜像与本地数据出发，重建的
**登录 / 协议 / 对战脚本 / 日常处理 / 进度与战斗观测** 参考实现。

> 目标不是分发原程序，也不是绕过授权；而是把“它怎么工作”写成可读、可测试、
> 可替换的代码。默认 `dry-run`，不会自动登录或写账号。

## 1. 已确认的事实（证据见 `docs/逆向分析.md`）

| 能力 | 2.0.9 的实现 | 本仓库 |
|---|---|---|
| 账号密码登录 | `http://account-co.61.com/index.php?r=userIdentity/authenticate...`，解析 `data.uid` / `data.session` | `login.authenticate()` |
| Unity OAuth | `https://account-co.61.com/v3/?r=...` → 回调 `code` → `token/trans` | `login.oauth_authorize_url()` / `exchange_code()` |
| 网关 | `https://seerh5login.61.com/online_gate?is_ssl=1` → `host:port` | `login.get_gateway()` / `parse_gateway()` |
| H5/Unity 连接 | `wss://host:port/`，子协议 `taomee` / `h5_web_taomee` | `ws.WebSocket` |
| H5 登录包 | cmd `1001` + 508B 模板（session/区号/端口/平台/UA） | `login.build_h5_login_body()` |
| Flash 登录包 | cmd `1001` + 44B body（`0x8ca151` 的 hex 常量） | `login.build_flash_login()` |
| 对战方案 | `seer_cfg/script/method/**/*.cjc` 明文 GBK INI | `cjc.BattlePlan` |
| 本地战斗 | `seer_cfg/json/{monsters_pro,moves,skill_effect,BossEffect,typesRelation}.ini` | `battle_data.BattleData` / `battle.Battle` |
| 出招记录 | `seer_cfg/DLL/config/日常记录/出招记录/*.txt` | `BattleResult.write_log()` |
| 一键日常 | `seer_cfg/DLL/config/一键日常配置/一键日常<uid>.ini` | `daily.load_app_daily_config()` |
| 进度 | `日常日志`、`启动进度<uid>.ini`、`日常记录<uid>.ini` | `progress.ProgressTracker` |

## 2. 快速开始

详细登录函数对照见 [docs/登录实现.md](docs/登录实现.md)，完整证据见
[docs/逆向分析.md](docs/逆向分析.md)。

要求 Python 3.11+，无第三方依赖（WebSocket 自实现）。

```powershell
cd seer-rebuild
$env:PYTHONPATH = (Get-Location).Path

# 读取 2.0.9 本地配置与战斗库规模
python -m seer_rebuild.cli inspect-app --root F:\seer

# 读取真实日常日志 / 出招记录，生成进度与战斗摘要
python -m seer_rebuild.cli app-log `
  --path "F:\seer\seer_cfg\DLL\config\日常日志\20260607-ACCOUNT.ini" `
  --battle "F:\seer\seer_cfg\DLL\config\日常记录\出招记录\ACCOUNT.txt"

# 分析官方 H5 抓包，校准 1001 body / cmd 表
python -m seer_rebuild.cli capture-summary <官方cmdlog.jsonl>

# 用 seerapi 查询在线数据（可选；失败时无副作用）
python -m seer_rebuild.cli seer-query pet 3022 --fields id,name,base_stats
python -m seer_rebuild.cli seer-query item 300697 --fields id,name
python -m seer_rebuild.cli seer-query pet --name "王之哈莫" --limit 3

# 解析一个对战方案
python -m seer_rebuild.cli parse-cjc "F:\seer\seer_cfg\script\method\_5.29量子回廊静态基准v1.3_秋殇_1764157759723\王哈1.cjc"

# 本地模拟：王之哈莫 vs 星光·魔焰猩猩，带 BOSS 特性
python -m seer_rebuild.cli simulate --player 3022 --enemy 4649 `
  --plan "F:\seer\seer_cfg\script\method\_5.29量子回廊静态基准v1.3_秋殇_1764157759723\王哈1.cjc" `
  --boss-effect "1261:185 139 235:神话：免疫异常状态；42:3 0:迅捷：先制+3；77:150 0:锋锐：每回合附加150点固定伤害" `
  --max-turns 20 --out battle.txt

# 战斗窗口（逐回合，像雷小伊一样；模拟模式）
python -m seer_rebuild.cli battle-window --player 3437 --enemy 4649 --max-turns 20
# 回放真实 2.0.9 出招记录
python -m seer_rebuild.cli battle-window --replay "F:\seer\seer_cfg\DLL\config\日常记录\出招记录\ACCOUNT.txt"

# 背包/装备展示窗口（回放抓包 + SeerAPI 反查名称）
python -m seer_rebuild.cli inventory --frames .\seer-rebuild\feature1_frames.jsonl --resolve
# 实时登录采集（先跑一次生成 jsonl，再打开窗口）
python -m seer_rebuild.cli inventory --live .\seer-rebuild\inventory_raw.jsonl --account ACCOUNT --password <密码> --resolve

# 打精灵因子关卡：先只读看进度/关卡列表
python -m seer_rebuild.cli factor --list --account <号> --password <密码> --resolve
# 打某一关（默认 dry-run 只列步骤，不发包）
python -m seer_rebuild.cli factor --account <号> --password <密码> `
  --stage 3 --boss-id 0x6f --skill 0x798a --lineup 3512,3045,3463 --factor-id 0x24a052
# 真正发包（小号 + 不要与官方客户端同时在线）
python -m seer_rebuild.cli factor --account <号> --password <密码> --stage 3 --boss-id 0x6f --send --write

# 以 MCP 服务器方式暴露工具（stdio）
python -m seer_rebuild.mcp_server
```

登录（会访问网络；`--connect` 才会发 1001）：

```powershell
# Flash/账号密码：只做 HTTP 鉴权 + 网关
python -m seer_rebuild.cli login --account 12345678 --password "..." 

# Unity OAuth：打印登录页；浏览器登录后把回调 URL 或 code 交给 exchange
python -m seer_rebuild.cli oauth-url
python -m seer_rebuild.cli oauth-exchange --code "https://account-co.61.com/v3/?r=authorization/success&code=..."
```

日常（默认 dry-run；没有 `--session` 只列任务）：

```powershell
python -m seer_rebuild.cli daily --config "F:\seer\seer_cfg\DLL\config\一键日常配置\一键日常ACCOUNT.ini"
```

## 3. 包结构

```
seer_rebuild/
  protocol.py     H5 17B / Flash 17B 帧、result 递推、粘包
  ws.py           RFC6455 客户端（wss、子协议、ping/pong、分片）
  login.py        authenticate / OAuth / token / online_gate / 登录体
  client.py       H5 WSS 与 Flash TCP 客户端
  battle_data.py  monsters_pro / moves / skill_effect / BossEffect / 属性
  cjc.py          .cjc / .cjpt 对战方案解析与出招选择
  battle.py       回合制本地模拟、BOSS 特性、战报
  battle_window.py 逐回合战斗窗口（tkinter，模拟/回放）
  inventory.py     背包/装备数据采集与解析
  inventory_window.py 背包/装备展示窗口（tkinter）
  factor.py        因子关数据（BOSS/阵容）+ 战斗步骤构造
  factor_runner.py 打精灵因子关卡执行器（进度/关卡列表解析 + 步骤构造 + live 驱动）
  mcp_server.py    MCP 服务器（登录/探测/特征/战斗/因子/查询/日志 工具）
  daily.py        一键日常配置、任务框架、内置命令任务
  applog.py       日常日志 / 出招记录解析（真实 2.0.9 数据）
  captures.py     官方 H5 抓包解析（1001 body / cmd 统计）
  provider.py     可选 SeerAPI provider（pet/skill/item/error_code 反查）
  progress.py     任务状态 / 事件总线 / Markdown+JSON 进度
  cli.py          命令行
data/
  login_template.bin  官方 H5 508B 登录模板（从官方客户端提取）
```

## 4. 状态矩阵

| 模块 | 状态 | 说明 |
|---|---|---|
| `protocol.py` | ✅ 单测 | H5/Flash 17B 头、长度、result 递推 |
| `ws.py` | ✅ 代码审查 | 无网络环境未做 live 握手；子协议/帧格式按 RFC6455 |
| `login.py` | ⚠️ 部分实测 | URL、字段、OAuth 路径来自 2.0.9 字符串 + 2.0.7 反编译；未用真实账号跑通 |
| `client.py` | ⚠️ 未 live | 1001 模板偏移需用抓包校准；默认 `area_id=None` |
| `battle_data.py` | ✅ 单测 | 5616 精灵、26755 技能、2374 效果、35 BOSS 特性 |
| `cjc.py` | ✅ 单测 | 明文 .cjc/.cjpt；重复 section 保留 |
| `battle.py` | ⚠️ 近似 | 公式/特性为可读近似，不是官方战斗服务器逐字节复刻 |
| `daily.py` | ⚠️ 骨架 | 只读 cmd 可试；写操作默认 dry-run，body 未校准 |
| `factor.py` / `factor_runner.py` | ⚠️ 部分实测 | 选关/切阵容/战斗/领取步骤构造有 lxy_yz_2/3 抓包证据，单测覆盖；实机战斗循环未用真实账号逐回合校准 |
| `.ysc` / `.cjcy` | ❌ 未解密 | `.ysc` 含 VMProtect；`.cjcy` 容器已解析，内部 `dzb.txt` 仍加密 |

## 5. 安全与边界

- 不包含账号密码、cookie、token；示例用占位符。
- `daily` 默认 `dry_run=True`，不会发送写包；必须显式 `--write`。
- 不要与官方客户端同时在线；第三方客户端有封号风险。
- 本项目只使用公开可见的本地文件与用户自己的内存镜像，不绕过任何授权。

## 6. 下一步（需要真实抓包）

1. 用 `client.py` 的 `observe` 抓 1001 后的前 30 帧，校准 `area_id` 与模板偏移。
2. 抓 `2875/2876/2877/8016/2707` 的请求/响应 body，补全 `daily.py` 解析。
3. 用 `出招记录` 的对局校准 `battle.py` 的伤害公式与 BOSS 特性。
4. 若要继续 `.ysc`：先确认 VMProtect 版本与是否允许动态调试；否则只保留格式说明。