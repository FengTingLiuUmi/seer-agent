# 捕捉 / 关卡：命令行用法（对齐雷小伊语法）

## `-send`：直接兼容雷小伊的 `Send()` 命令串

```powershell
# 去目标地图（2002 离开当前图 → 2001 进入）
.\seerproto.exe -info login.json -steps steps_empty.json -send "2002;2001,0,3001,725,272" -seconds 30
```

规则（与 `雷小伊js脚本开发文档` 一致）：

| 写法 | 含义 |
|---|---|
| `2002` | 命令 2002，无参数（body 空） |
| `2001,0,3001,725,272` | 命令 2001，参数 0/3001/725/272 → body = 4×u32 大端 |
| `2303,1,20` | `GET_PET_LIST` 取 id 1..20 的精灵（已验证有回包） |
| 分号 `;` | 一条串里依次发送，每条间隔 900ms（首包需等 2001 ack） |

## `-catch`：命中野怪自动开战

```powershell
.\seerproto.exe -info login.json -steps steps_empty.json -catch "164" -send "2002;2001,0,3001,725,272" -seconds 120
```

逻辑：

```
收到 S2C 2004 (MAP_OGRE_LIST) → body 拆 9 个 u32 槽位
   槽位 i 的精灵 id ∈ -catch 列表  →  发 2408, i   (FIGHT_NPC_MONSTER)
```

日志会打印：

```
    >>> 捕捉: 槽位 3 精灵 164 → 2408
```

## 相关命令号（来自 commandid.json + AS3）

| cmd | 名称 | 参数 |
|---|---|---|
| 2001 | ENTER_MAP | type, mapID, x, y |
| 2002 | LEAVE_MAP | — |
| 2004 | MAP_OGRE_LIST | 服务器推送，9×u32 精灵 id |
| 2408 | FIGHT_NPC_MONSTER | 槽位下标 |
| 2409 | CATCH_MONSTER | 服务器推送（捕获结果） |
| 2407 | CHANGE_PET | 换精灵 |
| 2410 | ESCAPE_FIGHT | 逃跑 |
| 2415 / 2416 | START_FIGHT_LEVEL / LEAVE_FIGHT_LEVEL | —（关卡） |

## 注意

- 本机实测：连续登录多次后，服务端会只给 `S2C 1001` 而**不推 2001**（等于进了门没进世界），此状态下不会发送 steps/-send
  → 等 5–10 分钟，或在官网手动登录一次释放
- 目标地图 id / 坐标需要从game里取（`2001,type,mapID,x,y` 中的 mapID 可先用当前地图 id 试；x/y 用 0,0 也可）