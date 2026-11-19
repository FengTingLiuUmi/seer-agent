"""赛尔号协议命令号 = 帧头里那个``cmd``字段（u32），全协议通用。

每条帧（C2S/S2C）都是 ``[u32 totalLen][u8 version][u32 cmd][u32 uid][i32 result] + body``，
``cmd``在偏移 5..8。这里用 :class:`Cmd`（IntEnum）统一维护，别再把命令号散落成各模块的
int 常量 / 裸数字。

用法：
    from .commands import Cmd
    await c.send(Cmd.GET_PET_INFO_BY_ONCE, [])      # 等价于 43706
    if f.cmd == Cmd.FIGHT_OVER: ...                 # 等价于 2506
"""
from __future__ import annotations

from enum import IntEnum


class Cmd(IntEnum):
    # —— 会话 / 心跳 ——
    LOGIN = 1001                # 登录（双向）
    HEARTBEAT = 1002            # 心跳（双向；S2C 回 4B token）
    GET_SESSION_KEY = 1016      # 会话密钥，body = u32(2)
    BOOTSTRAP = 42494           # 登录引导帧（connect 时先发）

    # —— 地图 / 角色 / 会话 ——
    ENTER_MAP = 2001            # 进入地图
    SESSION_TOKEN = 2002        # S2C 下发 4B 动态 session token

    # —— 精灵 ——
    GET_PET_INFO = 2301         # 单精灵详情，body=[catch_time]
    GET_PET_LIST = 2303         # 普通仓库（分页），body=[offset][count]
    PET_RELEASE = 2304          # 仓库↔背包移动，body=[catch][flag]
    PET_DEFAULT = 2308          # 换首发/升正式，body=[catch]
    GET_LOVE_PET_LIST = 2361    # 精英收藏，S2C=[count]+12B/项
    GET_PET_INFO_BY_ONCE = 43706  # 一次性读背包，S2C=[count]+变长详情
    TOKEN_ECHO = 45963          # 回传 token（C2S）/ 单只背包推送（S2C）

    # —— 战斗 ——
    READY_TO_FIGHT = 2404       # 准备战斗（C2S 空 / S2C 回 seed）
    USE_SKILL = 2405            # 出招，body=[技能 id]
    SWITCH_PET = 2407           # 战斗内换宠，body=[catch_time]
    FIGHT_NPC_MONSTER = 2408    # 发起野怪战
    END_BATTLE = 2410           # 结束/逃跑（yaxue 观察）
    NOTE_START_FIGHT = 2504     # S2C 开战
    NOTE_USE_SKILL = 2505       # S2C 技能结算
    FIGHT_OVER = 2506           # S2C 战斗结束
    BATTLE_EVENT = 2595         # S2C 战斗事件

    # —— 装备 / 外观 / 称号 ——
    CHANGE_CLOTH = 2604         # 换装备/装扮，body=[count][ids...]
    SETTITLE = 3404             # 换称号，body=[title_id]

    # —— 因子（官方 Unity 端） ——
    FACTOR_ENTER_STAGE = 41284  # 进入因子关，body=[design_id][difficulty]
    FACTOR_START_BATTLE = 41282  # 开始因子战斗，body=[design_id][difficulty]
    FACTOR_ACTION = 41413       # 因子领取/结算，body=[factor_id][action0][action1]
    FIGHT_H5_PVE_BOSS = 42396   # 发起 BOSS 战（雷小伊旧链路），body=[关卡id][1][1]
    MULTI_ITEM_LIST = 42399     # 道具背包查询，body=[count][ids...]
    STAGE_LIST = 45543          # 图鉴/收集进度（分页），body=[start][end]
    GET_MULTI_FOREVER = 46046   # 读 forever 键，body=[count][ids...]
    PET_CURE_FREE = 47136       # 免费治疗（空 body）

    # —— 压血 / 自动恢复（yaxue 实证） ——
    AUTO_RECOVER_SWITCH = 41228  # 自动恢复开关，body=[0x6afe0b13 关 / 0x6afe0b1e 开]
    BAIHU_TRIAL = 41129          # 发起白虎战（圣尊啸傲·白虎试炼），body=[8684]