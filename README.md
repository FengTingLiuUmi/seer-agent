# seer · 赛尔号 Agent 能力底座（本体 / 召回 / 执行三层）

把赛尔号账号操作沉淀为可脚本化、可被 LLM/Agent 调用的能力，分三层解耦：

- **本体 + 召回**（`seer-factor-kb`）：OWL 本体（精灵/技能/克制/关卡机制）+ `kb/docs` 关卡 SSOT + MCP 召回（`seer_kb_mcp` 7 工具）。
- **执行**（`seer-rebuild`）：登录 / 读背包仓库 / 调阵容装备 / 打精灵因子 / 本地战斗模拟 / 战斗战报。
- **编排**（`dsh-seer-agent`）：DSH 父子 Agent 预设（父规划、子执行）。

---

## 1. 速览

| 项 | 值 |
|---|---|
| 执行入口 | `python -m seer_rebuild.cli <子命令>` |
| 控制台脚本 | `seer-rebuild`（见 `seer-rebuild/pyproject.toml`） |
| 召回 MCP | `seer-factor-kb/ontology/seer_kb_mcp.py`（server `seer`，7 工具：`nick/boss/role/mult/ban/plan/stats`）|
| 执行 MCP | `seer_rebuild.mcp_server`（stdio，10 个工具）|
| Python | 执行包纯标准库（`dependencies = []`）；本体层用 `rdflib` + `whoosh`（见 §4）|
| 外部数据 | `F:\seer\seer_cfg\json\*.ini`（战斗库，GBK）+ seerapi（可选反查）|
| 净网协议 | 赛尔号 Unity 网关（TCP 1202–1230）/ 61.com 登录接口 |

---

## 2. 项目结构

```
seer/
├── seer-factor-kb/        ★ 本体 + 知识库 + 召回层
│   ├── ontology/            OWL 本体（seer-all.owl + seer-pve-*.ttl）+ MCP server seer_kb_mcp.py
│   ├── kb/docs/             关卡 SSOT（<因子>/<难度>.json）
│   ├── kb/index/            Whoosh 索引（派生，不入库）
│   └── player/              召回应用层（match_factor/generalize/loadouts）
├── seer-kb-mcp/           ★ 把 seer_kb_mcp.py 注册成 MCP `seer` server 的 bundle（cordis.patch.yml）
├── seer-rebuild/          ★ 执行主包（Python：CLI + 战斗，核心交付物）
├── seer-proto/            ★ Go 代理（WSS 代理 + MCP + Web API :7801）
├── llm-seer/              ★ Flash 宿主（Node + 32位PS + IE + Flash32 OCX）
├── dsh-seer-agent/        ★ DSH 父子 Agent 预设（seer-lead / seer-stage）
├── logs/                  本地战报/诊断输出（不入库）
└── README.md              本文
```

> 逆向/研究资料与历史抓包证据均已 `.gitignore`，不在仓库内。

---

## 3. 执行层核心包（`seer-rebuild/seer_rebuild/`，30 模块）

| 层 | 模块 | 职责 |
|---|---|---|
| 传输/协议 | `protocol.py` `ws.py` `client.py` | 帧编解码（17B 帧头）、手写 RFC6455 WS、`GameClient` 三通道（unity TCP / h5 WSS / flash TCP）|
| 登录 | `login.py` `session.py` `progress.py` | 61.com 鉴权、OAuth、Unity 网关选址、三端登录体构造、会话/进度 |
| 领域能力 | `pets.py` `warehouse.py` `team.py` `inventory.py` `pet_details.py` `features.py` `probe.py` | 背包(43706/2303/2361)、仓库移动(2304)、阵容/装备/称号(2308/2604/3404)、1001 快照读穿戴、2301 详情、命令序列、只读探测 |
| 因子 | `factor.py` `factor_runner.py` | `FactorSpec`/`load_factor_spec`（显式 design_id/factor_id）、41284/41282 进关、2404/2405/2407 出招、进度读取（含难度 `difficulty_int` 锚定）|
| 战斗 | `battle_data.py` `battle.py` `battle_observer.py` `battle_window.py` `battle_report.py` | 本地数据底座/模拟引擎/逐帧观测/tk 窗口/**真实战斗战报** |
| 数据/知识 | `provider.py` `ini_util.py` `domain_knowledge.py` `sqlite_kb.py` + `domain_knowledge/` | seerapi 子进程反查、GBK INI、本地战斗库 |
| 入口 | `cli.py` `mcp_server.py` | argparse 子命令分发；MCP stdio 工具暴露 |

内部依赖主链：`cli / mcp → client → {login, protocol, ws}`；领域模块依赖 `client + battle_data + ini_util + features + provider`。

### 本体与召回层（`seer-factor-kb`，与执行层同仓）

| 层 | 位置 | 职责 |
|---|---|---|
| 本体 | `ontology/*.ttl → seer-all.owl` | OWL 建模（`seer:`/`pve:` 命名空间，IRI + seerapiId 桥接）；难度受控词表 `简单=easy / 困难=normal / 地狱=hard` |
| SSOT | `kb/docs/<因子>/<难度>.json` | 每「因子×难度」一份关卡权威档（Boss 硬门/血量/策略/counteredBy），派生数据不复制 |
| 检索 | `kb/index/`（Whoosh）+ `kb/plan.py` | R1 精确 + 机制/数值模板/克制面/硬门四路相似召回 + 加权 RRF + 硬门缺口标注 |
| MCP | `ontology/seer_kb_mcp.py`（server `seer`）| 7 工具：`nick/boss/role/mult/ban/plan/stats`；OWL 按 mtime 热载 |

MCP 注册：`seer-kb-mcp/cordis.patch.yml` → serverName=`seer`，command=python，args 指向 `seer_kb_mcp.py`。

---

## 4. 依赖

### Python（执行核心包零第三方依赖）
纯 stdlib：`asyncio struct urllib http.cookiejar hashlib tkinter sqlite3 argparse json dataclasses subprocess`。

### Python（本体/召回层）
`rdflib`（OWL 解析）+ `whoosh`（检索索引），位于 `seer-factor-kb/.pylibs`（不入库；重装依赖或补 requirements）。

### 外部 CLI / 服务（按需，非强依赖）
- `seerapi` — 数据反查（`provider.py` 子进程调用，`api.seerapi.com`）
- `tshark` — pcapng 抓包解析（仅本地分析用）

### 外部数据 / 服务
- `F:\seer\seer_cfg\json\*.ini` — 战斗库（精灵/技能/套装/因子/BOSS/称号，GBK）
- 赛尔号 Unity 网关（`unity-ip.txt` 随机 IP + 端口 1202–1230）
- `seer-rebuild/data/login_template.bin` — Flash 登录模板

---

## 5. 快速开始

```powershell
$env:PYTHONPATH = "C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild"
$env:PYTHONIOENCODING = "utf-8"; chcp 65001

# 只读：读因子进度
python -m seer_rebuild.cli factor --list --factor-id 2400611 --account <号> --password <pw>
# 读背包 / 精英仓库
python -m seer_rebuild.cli bag --account <号> --password <pw>
python -m seer_rebuild.cli warehouse list --account <号> --password <pw>
# 打因子（默认 dry-run，--send 真发）
python -m seer_rebuild.cli factor --stage 1 --design-id 266 --account <号> --password <pw>
# 本地战斗模拟
python -m seer_rebuild.cli simulate --player 5000 --enemy 4964
# 数据反查（精灵名走 seer-factor-kb 本体）
python -m seer_rebuild.cli seer-query pet --name "伊娜"
# 战报（从时间线 jsonl 生成）
python -m seer_rebuild.cli battle-report --timeline timeline.jsonl --bag bag.json --snap snap.json --out report
```

召回 MCP：`seer_kb_mcp.py`（server `seer`），7 工具 `nick/boss/role/mult/ban/plan/stats`。

---

## 6. 已实测能力 / 关键沉淀

- **精灵存储三层**：背包(43706)=正式+待命，精英仓库(2361)，普通仓库(2303 分页)；`catch_time` 为个体唯一标识。
- **外观/加成三套**：装备(属性) / 装扮(时装) / 称号(加成)，别混。
- **精灵因子**：官方 Unity 明文链路 `41284 进关 → 41282 开战 → 2404/2405/2407`；`46046` 读进度。
- **难度受控词表**：`简单=easy / 困难=normal / 地狱=hard`；客户端 int `1/2/3`，对应 46046 进度低16位 `0x100/0x200/0x400`。当前已有进度时切换难度被拒（实测 41284 报 `1905004`）；过关锁阵容后，下一关重复上阵已被锁个体报 `1905010`。
- **伊娜因子(design 266) 简单 5/5 已真机全通**：漆黑天使套(448) + 圣灵谱尼首发 + 连续 `31143 神灵救世光`。八四公式(帝皇31505→六界19314→时空31253)用于多精灵关。
- **飞鱼骑士(design 130) 困难第1关已真机通过**：表姐「守御八方」(31505) 自爆给必先+必暴，接两个堕落炮魂「邪眸暗耀光」(35093) 强攻（光/暗影对暗影·邪灵双克制）。
- **战报**：`battle_report.py` 从真实 C2S/S2C 时间线产出 阵容/装备/称号/逐回合出招与敌方血量/胜负。

---

## 7. 子项目说明

| 项目 | 语言 | 定位 |
|---|---|---|
| `seer-factor-kb` | Python(rdflib/whoosh) | **本体 + 知识库 + 召回层**：OWL SSOT + 关卡文档 + MCP 7 工具 |
| `seer-kb-mcp` | YAML | 把 `seer_kb_mcp.py` 注册成 DSH MCP `seer` server 的 bundle |
| `seer-rebuild` | Python | **执行主包**：登录/因子/战斗/战报，CLI+MCP |
| `seer-proto` | Go | WSS 代理 + MCP + Web API（`main.go`，`tools/flash_api.py:7801`）|
| `llm-seer` | Node+PS | Flash 宿主：IE 控件 + `Flash32_34_0_0_155.ocx` 跑官方 Flash 端 |
| `dsh-seer-agent` | YAML | DSH 父子 Agent 预设（seer-lead / seer-stage）|

---

## 8. 目标架构 / 下一步设计点（未动，供评审）

1. **入口收敛**：`cli.py` 巨型子命令分发器 + `mcp_server.py` 手写注册 → 统一 command/tool registry。
2. **会话样板去重**：各域函数重复 `authenticate → get_unity_gateway → GameClient → asyncio.run → close` → 抽 `session_scope()`。
3. **provider 直连**：seerapi 子进程 → HTTP 直连 + 持久缓存。
4. **主包瘦身**：`seer-rebuild/` 内的历史抓包证据与约 150 个分析脚本迁出主包，只保留 `seer_rebuild/` 代码 + 少量运营脚本。
5. **版本声明统一**：`requires-python>=3.11` 与实际 py3.10 不一致。
6. **知识层边界**：OWL 本体（seer-factor-kb）、`strategies.json`、`sqlite_kb` 三者并存，明确其各自边界与派生关系，避免重复事实源。