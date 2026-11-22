"""命令行入口：登录、日常、观测。"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from .applog import parse_battle_record, parse_daily_log, summarize
from .captures import summarize as summarize_capture
from .features import CAPTURE_EQUIP, CAPTURE_FACTOR, FeatureStep, format_steps, readable_steps
from .provider import SeerApiProvider
from .probe import probe_credentials
from .battle_data import BattleData
from .cjc import BattlePlan
from .client import GameClient
from .daily import (
    DailyRunner,
    TaskContext,
    builtin_tasks,
    load_app_daily_config,
    load_task_spec,
    tasks_from_app_config,
)
from .login import (
    HttpClient,
    LoginSession,
    authenticate,
    build_h5_login_body,
    exchange_code,
    extract_code,
    get_gateway,
    get_unity_gateway,
    oauth_authorize_url,
    parse_gateway,
)
from .progress import Observer, ProgressTracker


def _print(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def cmd_oauth_url(args: argparse.Namespace) -> None:
    print(oauth_authorize_url(args.duid, args.state))


def cmd_oauth_exchange(args: argparse.Namespace) -> None:
    token = exchange_code(args.code, duid=args.duid)
    _print({"token": token[:8] + "...", "length": len(token)})


def cmd_login(args: argparse.Namespace) -> None:
    client = HttpClient(proxy=args.proxy) if args.proxy else None
    sess = authenticate(args.account, args.password, client=client)
    gateway = get_gateway(client=client)
    host, port, path = parse_gateway(gateway)
    sess.gateway, sess.host, sess.port, sess.path = gateway, host, port, path
    sess.mode = args.mode
    _print(sess.masked())

    if args.connect:
        asyncio.run(_connect_and_report(sess, args))


async def _connect_and_report(sess: LoginSession, args: argparse.Namespace) -> None:
    c = GameClient(sess, mode=args.mode, area_id=args.area, version=args.version, proxy=getattr(args, "proxy", None), logger=print)
    try:
        first = await c.connect(timeout=args.timeout)
        if first:
            _print({"cmd": first.cmd, "result": first.result, "body": first.body.hex()})
        loop = asyncio.get_running_loop()
        end = loop.time() + args.keep
        while not c.frames.empty() or loop.time() < end:
            try:
                f = await asyncio.wait_for(c.next_frame(), timeout=min(1.0, max(0.1, end - loop.time())))
            except asyncio.TimeoutError:
                continue
            _print({"cmd": f.cmd, "result": f.result, "len": len(f.body), "body": f.body[:64].hex()})
    finally:
        await c.close()


def cmd_parse_cjc(args: argparse.Namespace) -> None:
    plan = BattlePlan.load(args.path)
    _print(
        {
            "path": str(plan.path),
            "plans": [
                {"pet_id": p.pet_id, "warehouse": p.warehouse_index, "cycle": p.cycle_skills, "use": p.use_skill}
                for p in plan.plans
            ],
            "refs": list(plan.refs),
        }
    )


def cmd_daily(args: argparse.Namespace) -> None:
    cfg = load_app_daily_config(args.config) if args.config else None
    if args.spec:
        tasks = load_task_spec(args.spec)
    elif cfg:
        tasks = tasks_from_app_config(cfg, include_write=args.write)
    else:
        tasks = builtin_tasks(include_write=args.write)
    progress = ProgressTracker(log_path=args.log)
    runner = DailyRunner(tasks, progress=progress, dry_run=not args.write, retries=args.retries)
    observer = Observer()
    observer.subscribe(lambda kind, payload: progress._log(f"[事件] {kind}: {str(payload)[:200]}"))

    async def run() -> None:
        if not args.session:
            print("未提供 --session；只展示任务列表，不连接游戏。")
            _print({"tasks": [t.name for t in tasks], "dry_run": not args.write})
            return
        sess = LoginSession(**json.loads(Path(args.session).read_text(encoding="utf-8")))
        c = GameClient(sess, mode=args.mode, version=getattr(args, "version", 0x31), proxy=getattr(args, "proxy", None), logger=print)
        await c.connect(timeout=args.timeout)
        ctx = TaskContext(c, sess, progress, observer, cfg, dry_run=not args.write)
        await runner.run(ctx)
        await c.close()

    asyncio.run(run())
    progress.write_markdown(args.out or "daily_progress.md")
    progress.write_json("daily_progress.json")


def cmd_observe(args: argparse.Namespace) -> None:
    async def run() -> None:
        sess = LoginSession(**json.loads(Path(args.session).read_text(encoding="utf-8")))
        c = GameClient(sess, mode=args.mode, version=getattr(args, "version", 0x31), proxy=getattr(args, "proxy", None), logger=print)
        await c.connect(timeout=args.timeout)
        end = asyncio.get_running_loop().time() + args.seconds
        while asyncio.get_running_loop().time() < end:
            try:
                f = await asyncio.wait_for(c.next_frame(), timeout=min(1.0, end - asyncio.get_running_loop().time()))
            except asyncio.TimeoutError:
                continue
            print(f"cmd={f.cmd} result={f.result} len={len(f.body)} body={f.body[:64].hex()}")
        await c.close()

    asyncio.run(run())


def cmd_inspect_app(args: argparse.Namespace) -> None:
    root = Path(args.root)
    cfg_path = root / "seer_cfg" / "DLL" / "config" / "一键日常配置" / "一键日常ACCOUNT.ini"
    out = {"root": str(root), "exists": root.exists()}
    if cfg_path.exists():
        cfg = load_app_daily_config(cfg_path)
        out["daily_config"] = cfg.values
    data_root = root / "seer_cfg" / "json"
    if data_root.exists():
        data = BattleData(data_root)
        out["species"] = len(data.species)
        out["moves"] = len(data.moves)
        out["effects"] = len(data.effects)
        out["boss_effects"] = len(data.boss_effects)
    _print(out)


def cmd_app_log(args: argparse.Namespace) -> None:
    out: dict = {}
    if args.path:
        events = parse_daily_log(args.path)
        out["daily"] = summarize(events).as_dict()
    if args.battle:
        out["battle"] = parse_battle_record(args.battle).as_dict()
    _print(out)


def cmd_capture_summary(args: argparse.Namespace) -> None:
    _print(summarize_capture(args.path).as_dict())


def cmd_seer_query(args: argparse.Namespace) -> None:
    fields = [x for x in (args.fields or "").split(",") if x]

    # pet 名/ID 消歧 → 本体（seer-all.owl），不再走 seerapi / BattleData 名反查。
    if args.resource in ("pet", "精灵"):
        from .ontology import pet_lookup
        q = args.name or args.id_or_name
        if q is None:
            raise SystemExit("pet 查询需要给 id 或 --name <名称>")
        r = pet_lookup(str(q))
        if r is not None:
            if r["matches"]:
                _print(r)
                return
            # 本体无精确匹配：数字 id 降级 seerapi 查未建模精灵；名称不做子串（避免误配）
            if str(q).strip().isdigit():
                p = SeerApiProvider(scheme=args.scheme, hostname=args.hostname)
                _print(p.get("pet", int(str(q).strip()), fields=fields or None))
            else:
                r["note"] = "本体无精确匹配（不做子串，避免『伊芙→伊芙莉莎』这类误配）；请换精确名。"
                _print(r)
            return
        # 本体不可用 → 降级 seerapi（并标注）

    p = SeerApiProvider(scheme=args.scheme, hostname=args.hostname)
    if args.name:
        if args.id_or_name is not None:
            raise SystemExit("--name 与按 id 查询不能同时用；name 参数直接给子串")
        _print(p.find(args.resource, args.name, limit=args.limit))
    else:
        _print(p.get(args.resource, args.id_or_name, fields=fields or None))


def cmd_inventory(args: argparse.Namespace) -> None:
    from .inventory import parse_frames_jsonl, resolve
    from .inventory_window import InventoryWindow

    if args.live:
        from .inventory import snapshot_from_live
        snap = snapshot_from_live(args.account, args.password, args.live)
    elif args.frames:
        snap = parse_frames_jsonl(args.frames)
    else:
        raise SystemExit("需要 --frames <jsonl> 或 --live <out.jsonl>（含 --account/--password）")

    provider = SeerApiProvider() if args.resolve else None
    if provider:
        snap = resolve(snap, provider)
    InventoryWindow(snap).run()


def cmd_probe(args: argparse.Namespace) -> None:
    out = probe_credentials(args.account, args.password)
    _print(out)


def cmd_feature(args: argparse.Namespace) -> None:
    steps = CAPTURE_EQUIP if args.seq == "equip" else CAPTURE_FACTOR
    if args.resolve:
        provider = SeerApiProvider()
        print("\n".join(readable_steps(steps, provider=provider, dry_run=not args.write)))
    else:
        print(format_steps(steps, dry_run=not args.write))
    if not args.send:
        return

    async def run() -> None:
        sess = authenticate(args.account, args.password)
        host, port = get_unity_gateway()
        sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
        c = GameClient(sess, mode="unity")
        await c.connect(timeout=20.0)
        for s in steps:
            if s.write and not args.write:
                print(f"[dry-run] skip write {s.name} cmd={s.cmd}")
                continue
            try:
                await c.send(s.cmd, [s.body])
            except (ConnectionError, asyncio.IncompleteReadError) as e:
                print(f"[send-failed] {s.name} cmd={s.cmd}: {e}")
                break
            end = asyncio.get_running_loop().time() + 1.5
            while asyncio.get_running_loop().time() < end:
                try:
                    f = await asyncio.wait_for(c.next_frame(), timeout=0.8)
                except asyncio.TimeoutError:
                    break
                print(f"[recv] cmd={f.cmd} result={f.result} len={len(f.body)} body={f.body[:48].hex()}")
        await c.close()

    asyncio.run(run())


def cmd_mcp(args: argparse.Namespace) -> None:
    from .mcp_server import main as mcp_main
    mcp_main()


def cmd_bag(args: argparse.Namespace) -> None:
    from .pets import read_bag, format_bag_text

    bag = read_bag(args.account, args.password, resolve_names=not args.no_resolve)
    print(format_bag_text(bag))


def cmd_warehouse(args: argparse.Namespace) -> None:
    from .warehouse import add_to_bag, read_elite_warehouse

    if args.action == "list":
        _print(read_elite_warehouse(args.account, args.password, resolve_names=not args.no_resolve))
        return

    # add
    result = add_to_bag(
        args.account,
        args.password,
        catch_time=args.catch_time,
        species_id=args.species_id,
        slot=args.slot,
        send=args.send,
        resolve_names=not args.no_resolve,
    )
    _print(result)


def cmd_roster_dump(args: argparse.Namespace) -> None:
    from .roster import read_roster

    rows = read_roster(args.account, args.password)
    lines = [
        json.dumps(
            {"uid": str(args.account), "kind": "pet",
             "species_id": r["species_id"], "catch_time": r["catch_time"],
             "location": r["location"], "level": r.get("level")},
            ensure_ascii=False, separators=(",", ":"),
        )
        for r in rows
    ]
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"[roster-dump] {len(rows)} 只 -> {args.out}")
    else:
        print("\n".join(lines))


def cmd_flame(args: argparse.Namespace) -> None:
    from .flame import claim_flame, read_flame_state

    if args.action == "status":
        _print(read_flame_state(args.account, args.password))
    elif args.action == "claim":
        if not args.send:
            print(f"[dry-run] 领火 47348 via={args.via} flame={args.flame}（加 --send 才真正发包）")
            return
        _print(claim_flame(args.account, args.password, args.flame, args.via))


def _parse_ids(text: str) -> list[int]:
    return [int(x, 0) for x in text.split(",") if x.strip()]


def cmd_pet_level(args: argparse.Namespace) -> None:
    from .roster import read_levels

    _print({"levels": read_levels(args.account, args.password, _parse_ids(args.catch_time))})


def cmd_team(args: argparse.Namespace) -> None:
    from .team import demote_step, equip_step, execute, move_step, starter_step, title_step

    if args.action == "move":
        steps = [move_step(args.catch_time, args.to_bag)]
    elif args.action == "equip":
        steps = [equip_step(_parse_ids(args.ids))]
    elif args.action == "title":
        steps = [title_step(args.title_id)]
    elif args.action == "starter":
        steps = [starter_step(args.catch_time)]
    elif args.action == "demote":
        steps = [demote_step(args.catch_time)]
    else:
        raise SystemExit("未知 action")
    for line in execute(args.account, args.password, steps, send=args.send):
        print(line)


def cmd_factor(args: argparse.Namespace) -> None:
    from .factor_runner import FactorStagePlan, read_state, run

    if args.list:
        if args.design_id is None and args.factor_id is None:
            raise SystemExit("--list 需要 --design-id 或 --factor-id（不再有默认当前因子）")
        _print(read_state(args.account, args.password, resolve=args.resolve,
                          factor_id=args.factor_id, design_id=args.design_id))
        return

    if args.design_id is None:
        raise SystemExit("需要 --design-id（官方端 41284/41282 进入因子关；不再有默认当前因子）")

    if args.stage is None and not args.all:
        raise SystemExit("需要 --stage N 或 --all；先用 --list --design-id <id> 看当前进度")

    def _plan(idx: int) -> FactorStagePlan:
        return FactorStagePlan(
            stage_index=idx,
            boss_species=args.boss_species,
            boss_name="",
            lineup=_parse_ids(args.lineup) if args.lineup else [],
            reserve=_parse_ids(args.reserve) if args.reserve else [],
            skills={},
            battle_skills=_parse_ids(args.skill) if args.skill else [],
            battle_switches=_parse_ids(args.switch) if args.switch else [],
            lineup_catch=_parse_ids(args.catch_time) if args.catch_time else [],
            reserve_catch=_parse_ids(args.reserve_catch) if args.reserve_catch else [],
            boss_id=args.boss_id,
            factor_id=args.factor_id,
            design_id=args.design_id,
            difficulty=getattr(args, "difficulty", 1),
            collect_action=tuple(_parse_ids(args.collect_action)) if args.collect_action else (1, 0),
            equip_ids=_parse_ids(args.equip) if args.equip else None,
            title_id=args.title_id,
            clear_reserve=_parse_ids(args.clear_reserve) if args.clear_reserve else [],
        )

    # 每个因子固定 5 关；官方端第几关由服务端按账号进度自动推进。
    indices = [args.stage] if args.stage else list(range(1, 6))
    plans = [_plan(i) for i in indices]
    for line in run(
        args.account,
        args.password,
        plans,
        send=args.send,
        write=args.write,
        turn_wait=args.turn_wait,
        resolve=args.resolve,
        report_dir=args.report_dir,
        records_dir=args.records_dir,
    ):
        print(line)


def cmd_wiki(args: argparse.Namespace) -> None:
    from . import wiki
    import json

    def _show(page: dict | None) -> None:
        if not page:
            print("(未找到)")
            return
        print(f"== {page['path']} ==")
        meta = page.get("meta") or {}
        fm = {k: meta[k] for k in ("name", "species", "type", "weak", "multi_life", "factors", "tags", "aliases") if k in meta}
        print(f"[meta] {json.dumps(fm, ensure_ascii=False)}")
        print()
        print(page["body"])
        print()
        print("相关：", " ".join(wiki.backlinks_of_page(page["path"])) or "—")

    if args.action == "list":
        for p in wiki.list_pages(category=args.category):
            tags = ",".join(map(str, p["tags"] or []))
            print(f"{p['path']}\tname={p['name']}\tspecies={p['species']}\ttags={tags}")
        return

    if args.action == "boss":
        _show(wiki.boss(int(args.value, 0)))
        return

    if args.action == "read":
        _show(wiki.read_page(args.value))
        return

    if args.action == "find":
        for p in wiki.find(tag=args.tag, type_=args.type_, species=args.species, name=args.name, keyword=args.keyword, category=args.category):
            print(f"{p['path']}\tname={p['meta'].get('name')}\tspecies={p['meta'].get('species')}")
        return

    if args.action == "search":
        for h in wiki.search(args.value):
            print(f"{h['path']}\tname={h['name']}\n    …{h['snippet']}…")
        return

    if args.action == "backlink":
        for rel in wiki.backlinks(args.value):
            print(rel)
        return


def cmd_yaxue(args: argparse.Namespace) -> None:
    from .yaxue import Target, resolve_from_species, restore, run

    if args.restore:
        if not args.account or not args.password:
            raise SystemExit("--restore 需要 --account / --password（或 SEER_ACCOUNT/SEER_PASSWORD 环境变量）")
        if args.send:
            print("⚠️ 真机会顶掉在线账号，不要与官方客户端/雷小伊同时在线；测试请用验证用小号。")
        for line in restore(args.account, args.password, send=args.send):
            print(line)
        return

    catch_times = _parse_ids(args.catch_time) if args.catch_time else []
    species_ids = _parse_ids(args.species) if args.species else []
    targets = [Target(catch_time=ct) for ct in catch_times]

    if not catch_times and not species_ids:
        raise SystemExit("需要 --catch-time 或 --species（至少一种）")
    needs_creds = bool(args.send) or bool(species_ids)
    if needs_creds and (not args.account or not args.password):
        raise SystemExit("--send 或 --species 需要 --account / --password（或 SEER_ACCOUNT/SEER_PASSWORD 环境变量）")

    if species_ids:
        # 读背包把 species -> 个体（只读登录；同名多只全列出）
        resolved, warnings = resolve_from_species(
            args.account, args.password, species_ids, resolve_names=not args.no_resolve
        )
        for w in warnings:
            print(f"[警告] {w}")
        targets += [t for t in resolved if t.catch_time]

    if not targets:
        raise SystemExit("没有解析到可压血的目标（species 不在背包 / catch_time 为空）")

    if args.skill:
        skills = _parse_ids(args.skill)
        if len(skills) != len(targets):
            raise SystemExit(f"--skill 数量({len(skills)}) 与目标数量({len(targets)}) 不一致")
        for t, sk in zip(targets, skills):
            t.skill = sk

    if args.send:
        print("⚠️ 真机会顶掉在线账号，不要与官方客户端/雷小伊同时在线；测试请用验证用小号。")
    for line in run(
        args.account,
        args.password,
        targets,
        close_auto=not args.keep_auto,
        recover=args.recover,
        send=args.send,
        resolve_names=not args.no_resolve,
    ):
        print(line)


def cmd_battle_report(args):
    import json
    from pathlib import Path
    from .battle_report import build_report_from_timeline, report_to_text

    timeline = [json.loads(l) for l in Path(args.timeline).read_text(encoding="utf-8").splitlines() if l.strip()]
    bag = json.loads(Path(args.bag).read_text(encoding="utf-8")) if args.bag else None
    snap = json.loads(Path(args.snap).read_text(encoding="utf-8")) if args.snap else None
    rep = build_report_from_timeline(
        timeline, bag=bag, snap=snap,
        data_root=r"F:\seer\seer_cfg\json",
        factor_name=args.factor_name or "", design_id=args.design_id,
        stage_index=args.stage, enemy_max_hp=args.enemy_max_hp,
    )
    text = report_to_text(rep)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out + ".txt").write_text(text + "\n", encoding="utf-8")
        Path(args.out + ".json").write_text(json.dumps(rep.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[已写] {args.out}.txt / {args.out}.json")


def cmd_session(args: argparse.Namespace) -> None:
    from .session import GameSession

    sess = GameSession(args.account, args.password)
    if args.sub == "login":
        info = sess.login(keep=args.keep)
        _print({
            "uid": info.uid,
            "host": info.host,
            "port": info.port,
            "1001_result": info.result,
            "login_body_len": len(info.body_hex) // 2,
            "session_masked": info.masked_session,
        })
    else:  # snapshot
        snap = sess.snapshot(resolve_names=args.resolve)
        _print(snap.as_dict())
    sess.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="seer-rebuild")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("oauth-url", help="打印 Unity OAuth 登录页")
    p.add_argument("--duid", default=None)
    p.add_argument("--state", default=None)
    p.set_defaults(func=cmd_oauth_url)

    p = sub.add_parser("oauth-exchange", help="OAuth code → token")
    p.add_argument("--code", required=True)
    p.add_argument("--duid", default="")
    p.set_defaults(func=cmd_oauth_exchange)

    p = sub.add_parser("login", help="账号密码登录（Flash 链路）")
    p.add_argument("--account", default=None)
    p.add_argument("--password", default=None)
    p.add_argument("--connect", action="store_true")
    p.add_argument("--mode", choices=["unity", "flash", "h5"], default="unity")
    p.add_argument("--area", type=int, default=None)
    p.add_argument("--timeout", type=float, default=15.0)
    p.add_argument("--version", type=lambda x: int(x, 0), default=0x31)
    p.add_argument("--proxy", default=None, help="HTTP CONNECT 代理，如 127.0.0.1:7897")
    p.add_argument("--keep", type=float, default=3.0)
    p.set_defaults(func=cmd_login)

    p = sub.add_parser("parse-cjc", help="解析 .cjc 对战方案")
    p.add_argument("path")
    p.set_defaults(func=cmd_parse_cjc)

    p = sub.add_parser("daily", help="日常任务")
    p.add_argument("--config", default=None, help="2.0.9 一键日常 INI")
    p.add_argument("--spec", default=None, help="自定义 JSON 任务表")
    p.add_argument("--session", default=None, help="登录后的 session JSON")
    p.add_argument("--mode", choices=["unity", "flash", "h5"], default="unity")
    p.add_argument("--write", action="store_true", help="允许发送写操作（默认 dry-run）")
    p.add_argument("--proxy", default=None, help="HTTP CONNECT 代理，如 127.0.0.1:7897")
    p.add_argument("--retries", type=int, default=1)
    p.add_argument("--timeout", type=float, default=15.0)
    p.add_argument("--log", default="daily.log")
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_daily)

    p = sub.add_parser("observe", help="只读观测帧")
    p.add_argument("--session", required=True)
    p.add_argument("--mode", choices=["unity", "flash", "h5"], default="unity")
    p.add_argument("--seconds", type=float, default=30.0)
    p.add_argument("--proxy", default=None, help="HTTP CONNECT 代理，如 127.0.0.1:7897")
    p.add_argument("--timeout", type=float, default=15.0)
    p.set_defaults(func=cmd_observe)

    p = sub.add_parser("capture-summary", help="分析官方 H5 抓包（cmdlog/frames）")
    p.add_argument("path")
    p.set_defaults(func=cmd_capture_summary)

    p = sub.add_parser("app-log", help="读取 2.0.9 日常日志 / 出招记录")
    p.add_argument("--path", default=None, help="日常日志 INI")
    p.add_argument("--battle", default=None, help="出招记录 TXT")
    p.set_defaults(func=cmd_app_log)

    p = sub.add_parser("seer-query", help="按资源查询：pet 走本体(名/ID 消歧)，item/equip/skill 等走 seerapi")
    p.add_argument("resource")
    p.add_argument("id_or_name", nargs="?", default=None)
    p.add_argument("--name", default=None, help="按名称子串搜索列表")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--fields", default="")
    p.add_argument("--scheme", default=None)
    p.add_argument("--hostname", default=None)
    p.set_defaults(func=cmd_seer_query)

    p = sub.add_parser("mcp", help="以 MCP stdio 服务器方式暴露工具")
    p.set_defaults(func=cmd_mcp)

    p = sub.add_parser("session", help="登录会话（基础）：login 或 snapshot")
    p.add_argument("sub", choices=["login", "snapshot"])
    p.add_argument("--account", default=None)
    p.add_argument("--password", default=None)
    p.add_argument("--keep", type=float, default=5.0)
    p.add_argument("--resolve", action="store_true")
    p.set_defaults(func=cmd_session)

    p = sub.add_parser("inventory", help="背包/装备展示窗口")
    p.add_argument("--frames", default=None, help="scan_frames 产物 jsonl（回放抓包）")
    p.add_argument("--live", default=None, help="实时登录并把 S2C 落地到该 jsonl")
    p.add_argument("--account", default=None)
    p.add_argument("--password", default=None)
    p.add_argument("--resolve", action="store_true", help="用 SeerAPI 反查名称")
    p.set_defaults(func=cmd_inventory)

    p = sub.add_parser("feature", help="精灵背包/装备 或 精灵因子 的已抓包命令序列")
    p.add_argument("--seq", choices=["equip", "factor"], required=True)
    p.add_argument("--account", default=None)
    p.add_argument("--password", default=None)
    p.add_argument("--send", action="store_true", help="实际登录并发送")
    p.add_argument("--write", action="store_true", help="允许发送写操作（默认 dry-run）")
    p.add_argument("--resolve", action="store_true", help="用 SeerAPI 反查 ID 为中文名（只读展示）")
    p.set_defaults(func=cmd_feature)

    p = sub.add_parser("probe", help="Unity 登录后发送只读命令并记录响应")
    p.add_argument("--account", default=None)
    p.add_argument("--password", default=None)
    p.set_defaults(func=cmd_probe)

    p = sub.add_parser("bag", help="在线读背包（正式/待命）")
    p.add_argument("--account", default=None)
    p.add_argument("--password", default=None)
    p.add_argument("--no-resolve", action="store_true", help="不反查精灵名")
    p.set_defaults(func=cmd_bag)

    p = sub.add_parser("warehouse", help="精英仓库（2361）：列出 / 把精灵加入背包")
    p.add_argument("action", choices=["list", "add"])
    p.add_argument("--account", default=None)
    p.add_argument("--password", default=None)
    p.add_argument("--catch-time", type=lambda x: int(x, 0), default=None, help="add：精灵个体 catch_time")
    p.add_argument("--species-id", type=lambda x: int(x, 0), default=None, help="add：按 species 在精英仓库里找个体")
    p.add_argument("--slot", choices=["formal", "reserve"], default="formal", help="add：加入正式(flag=1) 或 待命(flag=2)")
    p.add_argument("--send", action="store_true", help="add：实际发包（写操作；默认 dry-run）")
    p.add_argument("--no-resolve", action="store_true", help="list/add：不反查精灵名")
    p.set_defaults(func=cmd_warehouse)

    p = sub.add_parser("roster-dump", help="只读导出玩家全部精灵个体（43706+2361+2303，统一 JSONL 契约）")
    p.add_argument("--account", default=None)
    p.add_argument("--password", default=None)
    p.add_argument("--out", default=None, help="输出 UTF-8 JSONL 文件路径（否则打印到 stdout）")
    p.set_defaults(func=cmd_roster_dump)

    p = sub.add_parser("flame", help="战斗火焰：读状态 / 领火（绿火6 蓝火7）")
    p.add_argument("action", choices=["status", "claim"])
    p.add_argument("--account", default=None)
    p.add_argument("--password", default=None)
    p.add_argument("--flame", type=lambda x: int(x, 0), default=6, help="火焰 id：6=绿火 7=蓝火")
    p.add_argument("--via", type=int, default=2, help="领取方式：1=VIP每日免费 2=友谊之星")
    p.add_argument("--send", action="store_true", help="claim：实际发包领火（默认 dry-run）")
    p.set_defaults(func=cmd_flame)

    p = sub.add_parser("pet-level", help="只读：按 catch_time 读个体等级(2301)，组队前选满级用")
    p.add_argument("--account", default=None)
    p.add_argument("--password", default=None)
    p.add_argument("--catch-time", required=True, help="个体 catch_time，逗号分隔")
    p.set_defaults(func=cmd_pet_level)

    p = sub.add_parser("team", help="统一阵容/装备调整（默认 dry-run）")
    p.add_argument("action", choices=["move", "equip", "title", "starter", "demote"])
    p.add_argument("--account", default=None)
    p.add_argument("--password", default=None)
    p.add_argument("--catch-time", type=lambda x: int(x, 0), default=None, help="move/starter/demote：精灵个体 catch_time")
    p.add_argument("--to-bag", action="store_true", help="move：加入背包（否则放回仓库）")
    p.add_argument("--ids", default=None, help="equip：装备/装扮 ID，逗号分隔")
    p.add_argument("--title-id", type=lambda x: int(x, 0), default=None, help="title：称号 ID")
    p.add_argument("--send", action="store_true", help="实际登录并发送写命令（默认只打印 dry-run）")
    p.set_defaults(func=cmd_team)

    p = sub.add_parser("factor", help="打精灵因子关卡（默认 dry-run 只列步骤）")
    p.add_argument("--account", default=None)
    p.add_argument("--password", default=None)
    p.add_argument("--list", action="store_true", help="只读：登录后读因子进度 + 关卡列表")
    p.add_argument("--stage", type=int, default=None, help="目标第 N 关（1 基）")
    p.add_argument("--all", action="store_true", help="打全部 5 关")
    p.add_argument("--boss-id", type=lambda x: int(x, 0), default=None, help="42396 的关卡 id（发起 BOSS 战）")
    p.add_argument("--boss-species", type=lambda x: int(x, 0), default=None, help="本关 BOSS species（展示/技能映射；官方端由服务端按进度自动推进）")
    p.add_argument("--skill", default=None, help="出招技能 id 序列，逗号分隔（由主 agent 提供，按回合顺序）")
    p.add_argument("--switch", default=None, help="出招间切换精灵的 catch_time 序列，逗号分隔（2407，比 --skill 少一个）")
    p.add_argument("--lineup", default=None, help="正式精灵 species，逗号分隔（技能映射/展示）")
    p.add_argument("--catch-time", default=None, help="正式精灵 catch_time，逗号分隔（2304 加正式）")
    p.add_argument("--reserve", default=None, help="待命精灵 species，逗号分隔")
    p.add_argument("--reserve-catch", default=None, help="待命精灵 catch_time，逗号分隔（2304 加待命）")
    p.add_argument("--clear-reserve", default=None, help="要清除的待命 catch_time，逗号分隔")
    p.add_argument("--factor-id", type=lambda x: int(x, 0), default=None, help="41413 领取的 factor id")
    p.add_argument("--design-id", type=lambda x: int(x, 0), default=None, help="官方端进入因子的 design_id（41284/41282；必填）")
    p.add_argument("--difficulty", type=str, default="1", help="41284/41282 难度：1/简单/easy 2/困难/normal 3/地狱/hard")
    p.add_argument("--collect-action", default=None, help="41413 的 action0,action1")
    p.add_argument("--equip", default=None, help="更换装备/装扮 id，逗号分隔")
    p.add_argument("--title-id", type=lambda x: int(x, 0), default=None, help="更换称号 id")
    p.add_argument("--turn-wait", type=float, default=2.0, help="出招后等待战斗结束的秒数")
    p.add_argument("--report-dir", default=None, help="落盘目录：写入 timeline.jsonl + turns.jsonl（完整帧，供 battle-report 用）")
    p.add_argument("--records-dir", default=None, help="实时写 latest.timeline.jsonl 到该目录（供 dsh-seer-battle 插件战斗记录实时更新，如 seer/battle-records）")
    p.add_argument("--send", action="store_true", help="实际登录并发包")
    p.add_argument("--write", action="store_true", help="允许发送写命令（默认 dry-run）")
    p.add_argument("--resolve", action="store_true", help="反查 ID 名称（--list 时用）")
    p.set_defaults(func=cmd_factor)

    p = sub.add_parser("wiki", help="llmwiki 知识库检索：list / boss / find / search / backlink / read")
    p.add_argument("action", choices=["list", "boss", "find", "search", "backlink", "read"])
    p.add_argument("value", nargs="?", default=None, help="boss:species / read:相对路径 / search:关键词 / backlink:页名")
    p.add_argument("--category", default=None, help="只列/过滤一级目录，如 bosses、tactics、mechanics、runbooks")
    p.add_argument("--tag", default=None, help="find：按 tag 过滤")
    p.add_argument("--type", dest="type_", default=None, help="find：按属性过滤")
    p.add_argument("--species", type=lambda x: int(x, 0), default=None, help="find：按 species 过滤")
    p.add_argument("--name", default=None, help="find：按页名过滤")
    p.add_argument("--keyword", default=None, help="find：正文/名/别名含关键词")
    p.set_defaults(func=cmd_wiki)

    p = sub.add_parser("yaxue", help="压血：把打手送进白虎试炼打到残血并关自动恢复（默认 dry-run）")
    p.add_argument("--account", default=None)
    p.add_argument("--password", default=None)
    p.add_argument("--catch-time", default=None, help="要压血的个体 catch_time，逗号分隔（0x 前缀十六进制亦可）")
    p.add_argument("--species", default=None, help="要压血的物种 species_id，逗号分隔（从背包反查个体）")
    p.add_argument("--skill", default=None, help="每只的 2405 出招技能 id，逗号分隔（与目标数一致；缺省读 2301 首个装备技）")
    p.add_argument("--recover", action="store_true", help="压血前先 42036 全体回复")
    p.add_argument("--keep-auto", action="store_true", help="不发送 41228 关自动恢复（默认会关）")
    p.add_argument("--send", action="store_true", help="实际登录并发包（写操作；默认 dry-run）")
    p.add_argument("--restore", action="store_true", help="恢复模式：打开自动恢复 + 全体回复（压血后的还原）")
    p.add_argument("--no-resolve", action="store_true", help="不反查精灵名")
    p.set_defaults(func=cmd_yaxue)

    p = sub.add_parser("battle-report", help="从战斗时间线(jsonl)生成战报")
    p.add_argument("--timeline", required=True, help="时间线 jsonl（每行 dir/cmd/body/result）")
    p.add_argument("--bag", default=None, help="read_bag 输出 json（阵容）")
    p.add_argument("--snap", default=None, help="session snapshot 输出 json（装备/称号）")
    p.add_argument("--factor-name", default="", help="因子名")
    p.add_argument("--design-id", type=lambda x: int(x, 0) if x else None, default=None)
    p.add_argument("--stage", type=int, default=None)
    p.add_argument("--enemy-max-hp", type=int, default=None)
    p.add_argument("--out", default=None, help="输出前缀（生成 <out>.txt / <out>.json）")
    p.set_defaults(func=cmd_battle_report)

    p = sub.add_parser("inspect-app", help="读取 2.0.9 本地配置/战斗数据")
    p.add_argument("--root", default=r"F:\seer")
    p.set_defaults(func=cmd_inspect_app)

    args = ap.parse_args(argv)
    # 凭据从环境变量读取（DSH 凭据库注入的 SEER_ACCOUNT / SEER_PASSWORD），
    # 未显式传 --account/--password 时回落。
    for _field, _env in (("account", "SEER_ACCOUNT"), ("password", "SEER_PASSWORD")):
        if hasattr(args, _field) and getattr(args, _field) in (None, ""):
            _v = os.environ.get(_env)
            if _v is not None:
                setattr(args, _field, _v)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())