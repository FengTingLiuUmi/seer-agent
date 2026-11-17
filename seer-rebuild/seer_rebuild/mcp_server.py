"""MCP（Model Context Protocol）服务器：把 seer-rebuild 的能力暴露为工具。

零依赖：用标准库实现 MCP 的 stdio 传输（每行一个 JSON-RPC 2.0 消息，
与官方 SDK 的 stdio 传输一致）。

支持的工具（名字、参数、说明见 TOOLS）：

  seer_login            账号鉴权（返回 uid/session/网关，不连接游戏）
  seer_unity_login      Unity 真机登录并发 1001，返回登录结果
  seer_probe             登录后发送只读命令并收集响应
  seer_feature           精灵背包/装备 或 精灵因子 的已抓包命令序列（默认 dry-run）
  seer_inventory         实时读取当前装备/背包
  seer_battle_simulate   本地战斗模拟（返回逐回合战报，无 GUI）
  seer_query             用 seerapi 查询 pet/skill/item/… 数据
  seer_applog            解析 2.0.9 日常日志 / 出招记录
  seer_capture_summary   分析官方 H5 抓包

写操作默认 dry-run；只有显式 write=true 才真正的 send。
"""
from __future__ import annotations

import asyncio
import json
import sys
import traceback
from typing import Any, Callable

from .applog import parse_battle_record, parse_daily_log, summarize
from .battle import simulate
from .captures import summarize as summarize_capture
from .features import CAPTURE_EQUIP, CAPTURE_FACTOR, readable_steps
from .inventory import snapshot_from_live
from .login import authenticate, get_gateway, get_unity_gateway, parse_gateway
from .probe import probe_credentials
from .provider import SeerApiProvider

SERVER_NAME = "seer-rebuild-mcp"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"


# ---------------------------------------------------------------------------
# 工具注册表
def _schema(required: list[str], **props: dict[str, Any]) -> dict:
    props.setdefault("type", "object")
    props.setdefault("properties", {})
    return {"type": "object", "properties": props.get("properties", {}), "required": required}


_TOOL_SPECS: list[dict] = [
    {
        "name": "seer_login",
        "description": "账号密码鉴权：userIdentity/authenticate → uid/session + online_gate。只做 HTTP，不连接游戏，返回脱敏信息。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "米米号"},
                "password": {"type": "string", "description": "密码"},
            },
            "required": ["account", "password"],
        },
    },
    {
        "name": "seer_unity_login",
        "description": "Unity 真机登录：鉴权 + 连接 unity-ip 网关 + 发 1001，返回登录结果与收到的关键帧。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "account": {"type": "string"},
                "password": {"type": "string"},
                "keep": {"type": "number", "default": 6, "description": "登录后收帧等待秒数"},
            },
            "required": ["account", "password"],
        },
    },
    {
        "name": "seer_probe",
        "description": "登录 Unity 后依次发送只读命令（2707/8016/8015/3452/…）并收集 S2C 响应。",
        "inputSchema": {
            "type": "object",
            "properties": {"account": {"type": "string"}, "password": {"type": "string"}},
            "required": ["account", "password"],
        },
    },
    {
        "name": "seer_feature",
        "description": "精灵背包/装备 或 精灵因子 的已抓包命令序列。默认 dry-run 只返回可读清单；write=true 才真正发送。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "seq": {"type": "string", "enum": ["equip", "factor"], "description": "equip=背包/装备，factor=精灵因子"},
                "account": {"type": "string"},
                "password": {"type": "string"},
                "write": {"type": "boolean", "default": False, "description": "是否真正发送写操作"},
                "resolve": {"type": "boolean", "default": True, "description": "是否用 SeerAPI 反查 ID 名称"},
            },
            "required": ["seq", "account", "password"],
        },
    },
    {
        "name": "seer_inventory",
        "description": "实时读取当前装备/背包，返回结构化清单（可反查名称）。",
        "inputSchema": {
            "type": "object",
            "properties": {"account": {"type": "string"}, "password": {"type": "string"}},
            "required": ["account", "password"],
        },
    },
    {
        "name": "seer_factor",
        "description": "打精灵因子关卡。list=true 只读进度+关卡列表；否则按 stage/boss_id/skill/lineup 构造并默认 dry-run 返回步骤，write=true 才真正发送。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "account": {"type": "string"},
                "password": {"type": "string"},
                "list": {"type": "boolean", "default": False, "description": "true=只读进度+关卡列表"},
                "stage": {"type": "integer", "description": "目标第 N 关（1 基）"},
                "all": {"type": "boolean", "default": False},
                "boss_id": {"type": "integer", "description": "42396 关卡 id"},
                "skills": {"type": "string", "description": "出招技能 id 逗号分隔（由主 agent 按回合顺序提供）"},
                "switches": {"type": "string", "description": "出招间切换的 catch_time 逗号分隔（2407，比 skills 少一个）"},
                "lineup": {"type": "string", "description": "正式精灵 species 逗号分隔"},
                "catch_time": {"type": "string", "description": "正式精灵 catch_time 逗号分隔（2304 加正式）"},
                "reserve": {"type": "string", "description": "待命 species 逗号分隔"},
                "reserve_catch": {"type": "string", "description": "待命 catch_time 逗号分隔（2304 加待命）"},
                "clear_reserve": {"type": "string", "description": "清除待命 catch_time 逗号分隔"},
                "factor_id": {"type": "integer", "description": "41413 领取 id"},
                "design_id": {"type": "integer", "description": "官方端进入因子 design_id（默认当前因子 225）"},
                "write": {"type": "boolean", "default": False, "description": "是否真正发送（默认 dry-run）"},
            },
            "required": ["account", "password"],
        },
    },
    {
        "name": "seer_battle_simulate",
        "description": "本地战斗模拟：给定双方精灵与 BOSS 特性，返回逐回合战报（文本，无 GUI）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "player_ids": {"type": "string", "description": "我方精灵 ID，逗号分隔"},
                "enemy_ids": {"type": "string", "description": "对方精灵 ID，逗号分隔"},
                "plan_path": {"type": "string", "description": ".cjc 方案路径（可选）"},
                "boss_effects": {"type": "string", "description": "id:args:text;...（可选）"},
                "max_turns": {"type": "integer", "default": 50},
                "data_root": {"type": "string", "default": r"F:\seer\seer_cfg\json"},
            },
            "required": ["player_ids", "enemy_ids"],
        },
    },
    {
        "name": "seer_query",
        "description": "用 seerapi 查询在线数据：按 id 或名称子串查 pet/skill/item/factor 等。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource": {"type": "string", "description": "如 pet/skill/item/factor/equip"},
                "id_or_name": {"type": "string", "description": "数字 id 或名称子串"},
                "by_name": {"type": "boolean", "default": False, "description": "true=按名称子串 list"},
            },
            "required": ["resource", "id_or_name"],
        },
    },
    {
        "name": "seer_applog",
        "description": "解析 2.0.9 的日常日志（INI）与出招记录（TXT），返回进度/战斗摘要。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "daily_path": {"type": "string"},
                "battle_path": {"type": "string"},
            },
        },
    },
    {
        "name": "seer_capture_summary",
        "description": "分析官方 H5 抓包（cmdlog*.jsonl / frames.jsonl），统计命令、提取 1001 登录体。",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
]

TOOLS = [{"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]} for t in _TOOL_SPECS]


# ---------------------------------------------------------------------------
# 工具实现
def _as_text(obj: Any) -> str:
    if isinstance(obj, str):
        return obj
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def tool_login(args: dict) -> dict:
    sess = authenticate(args["account"], args["password"])
    gateway = get_gateway()
    host, port, path = parse_gateway(gateway)
    return {
        "uid": sess.uid,
        "gateway": gateway,
        "host": host,
        "port": port,
        "path": path,
        "session_masked": (sess.session[:6] + "..." + sess.session[-4:]) if sess.session else "",
    }


def tool_unity_login(args: dict) -> dict:
    from .client import GameClient
    from .login import LoginSession

    sess = authenticate(args["account"], args["password"])
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"

    async def _run() -> dict:
        c = GameClient(sess, mode="unity")
        await c.connect(timeout=20.0)
        out: dict = {"uid": sess.uid, "host": host, "port": port, "frames": []}
        end = asyncio.get_running_loop().time() + float(args.get("keep", 6))
        while asyncio.get_running_loop().time() < end:
            try:
                f = await asyncio.wait_for(c.next_frame(), timeout=min(1.0, end - asyncio.get_running_loop().time()))
            except asyncio.TimeoutError:
                continue
            out["frames"].append({"cmd": f.cmd, "result": f.result, "len": len(f.body), "body": f.body[:64].hex()})
        await c.close()
        return out

    return asyncio.run(_run())


def tool_probe(args: dict) -> dict:
    return probe_credentials(args["account"], args["password"])


def tool_feature(args: dict) -> dict:
    steps = CAPTURE_EQUIP if args.get("seq") == "equip" else CAPTURE_FACTOR
    dry_run = not bool(args.get("write"))
    if args.get("resolve", True):
        provider = SeerApiProvider()
        lines = readable_steps(steps, provider=provider, dry_run=dry_run)
        return {"seq": args["seq"], "dry_run": dry_run, "steps": lines}
    return {
        "seq": args["seq"],
        "dry_run": dry_run,
        "steps": [
            {
                "name": s.name,
                "cmd": s.cmd,
                "write": s.write,
                "body_hex": s.body.hex(),
            }
            for s in steps
        ],
    }


def tool_inventory(args: dict) -> dict:
    from .inventory import resolve

    prov = SeerApiProvider()
    snap = snapshot_from_live(args["account"], args["password"], None)
    resolve(snap, prov)
    return snap.as_dict()


def _parse_id_list(text: str) -> list[int]:
    return [int(x, 0) for x in text.split(",") if x.strip()]


def tool_factor(args: dict) -> dict:
    from .factor import CURRENT_FACTOR, FACTOR_STAGES, DEFAULT_LINEUP
    from .factor_runner import FactorStagePlan, read_state, run

    if args.get("list"):
        return {"list": True, **read_state(args["account"], args["password"], resolve=True)}

    stage = args.get("stage")
    if stage is None and not args.get("all"):
        return {"error": "需要 stage 或 all=true；先用 list=true 看当前进度"}

    def _plan(idx: int) -> FactorStagePlan:
        st = FACTOR_STAGES[idx - 1]
        species = st["boss_species"]
        lineup = _parse_id_list(args["lineup"]) if args.get("lineup") else list(DEFAULT_LINEUP.get(species, ([], {}))[0])
        return FactorStagePlan(
            stage_index=idx,
            boss_species=species,
            boss_name=st["boss_name"],
            lineup=lineup,
            reserve=_parse_id_list(args["reserve"]) if args.get("reserve") else [],
            skills={},
            battle_skills=_parse_id_list(args["skills"]) if args.get("skills") else [],
            battle_switches=_parse_id_list(args["switches"]) if args.get("switches") else [],
            lineup_catch=_parse_id_list(args["catch_time"]) if args.get("catch_time") else [],
            reserve_catch=_parse_id_list(args["reserve_catch"]) if args.get("reserve_catch") else [],
            boss_id=args.get("boss_id"),
            factor_id=args.get("factor_id"),
            design_id=args.get("design_id") or CURRENT_FACTOR.design_id,
            collect_action=(1, 0),
            clear_reserve=_parse_id_list(args["clear_reserve"]) if args.get("clear_reserve") else [],
        )

    indices = [stage] if stage else list(range(1, len(FACTOR_STAGES) + 1))
    lines = run(
        args["account"],
        args["password"],
        [_plan(i) for i in indices],
        send=bool(args.get("write")),
        write=bool(args.get("write")),
    )
    return {"dry_run": not bool(args.get("write")), "steps": lines}


def tool_battle_simulate(args: dict) -> dict:
    from .battle_data import BattleData, BossTrait
    from .cjc import BattlePlan

    data_root = args.get("data_root", r"F:\seer\seer_cfg\json")
    data = BattleData(data_root)
    plan = BattlePlan.load(args["plan_path"]) if args.get("plan_path") else None
    players = [data.make_pet(int(x), side="player") for x in args["player_ids"].split(",")]
    enemies = [data.make_pet(int(x), side="enemy") for x in args["enemy_ids"].split(",")]
    traits: list[BossTrait] = []
    if args.get("boss_effects"):
        for item in args["boss_effects"].split(";"):
            if not item.strip():
                continue
            parts = item.split(":")
            bid = int(parts[0])
            targs = [int(x) for x in parts[1].split()] if len(parts) > 1 and parts[1].strip() else []
            desc = parts[2] if len(parts) > 2 else ""
            traits.append(BossTrait(bid, targs, desc))
    result = simulate(
        data_root, player_ids=[p.species.id for p in players], enemy_ids=[e.species.id for e in enemies],
        plan_path=args.get("plan_path"), boss_traits=traits, max_turns=int(args.get("max_turns", 50)),
    )
    return {
        "winner": result.winner,
        "turns": result.turns,
        "snapshot_count": len(result.snapshots),
        "log": "\n".join(result.log_lines),
    }


def tool_query(args: dict) -> dict:
    prov = SeerApiProvider()
    resource = args["resource"]
    key = args["id_or_name"]
    if args.get("by_name"):
        return {"resource": resource, "name": key, "items": prov.find(resource, key, limit=10)}
    if key.isdigit():
        return {"resource": resource, "id": int(key), "item": prov.get(resource, int(key))}
    try:
        return {"resource": resource, "id": int(key), "item": prov.get(resource, int(key))}
    except ValueError:
        return {"resource": resource, "name": key, "items": prov.find(resource, key, limit=10)}


def tool_applog(args: dict) -> dict:
    out = {}
    if args.get("daily_path"):
        out["daily"] = summarize(parse_daily_log(args["daily_path"])).as_dict()
    if args.get("battle_path"):
        out["battle"] = parse_battle_record(args["battle_path"]).as_dict()
    return out


def tool_capture_summary(args: dict) -> dict:
    return summarize_capture(args["path"]).as_dict()


_DISPATCH: dict[str, Callable[[dict], Any]] = {
    "seer_login": tool_login,
    "seer_unity_login": tool_unity_login,
    "seer_probe": tool_probe,
    "seer_feature": tool_feature,
    "seer_inventory": tool_inventory,
    "seer_factor": tool_factor,
    "seer_battle_simulate": tool_battle_simulate,
    "seer_query": tool_query,
    "seer_applog": tool_applog,
    "seer_capture_summary": tool_capture_summary,
}


# ---------------------------------------------------------------------------
# MCP 协议处理
def handle_method(method: str, params: dict) -> dict:
    if method == "initialize":
        return {
            "protocolVersion": params.get("protocolVersion", PROTOCOL_VERSION),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name not in _DISPATCH:
            return {
                "content": [{"type": "text", "text": f"unknown tool: {name}"}],
                "isError": True,
            }
        result = _DISPATCH[name](arguments)
        return {"content": [{"type": "text", "text": _as_text(result)}], "isError": False}
    raise RuntimeError(f"method not supported: {method}")


def _reply(msg: dict, result: dict) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": msg.get("id"), "result": result}, ensure_ascii=False)


def _error(msg: dict, err: Exception) -> str:
    return json.dumps(
        {"jsonrpc": "2.0", "id": msg.get("id"), "error": {"code": -32000, "message": str(err)}},
        ensure_ascii=False,
    )


def serve(stream_in: Any = sys.stdin, stream_out: Any = sys.stdout) -> None:
    """stdio 传输：每行一个 JSON-RPC 消息。"""
    for line in stream_in:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(msg, dict) or "method" not in msg:
            continue
        if "id" not in msg and msg.get("method", "").startswith("notifications/"):
            continue  # 通知不回复
        try:
            result = handle_method(msg["method"], msg.get("params") or {})
            stream_out.write(_reply(msg, result) + "\n")
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc(file=sys.stderr)
            stream_out.write(_error(msg, exc) + "\n")
        stream_out.flush()


def main() -> None:
    serve()


if __name__ == "__main__":
    main()