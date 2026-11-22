"""战斗记录登记：把每场战报统一写入一个目录，供前端(DSH 插件/网页)做实时+历史展示。

目录契约（默认 `<项目根>/battle-records`）：
  index.json   历史索引  {"battles":[{id, ts, factor_name, design_id, stage, winner, title}]}
  latest.json  最近一场完整报告（每场结束后覆盖；前端据此刷新"最近一场"）
  <id>.json    每场完整报告

"实时进行中的战斗"：由 `factor_fight.py` 在战斗过程中持续写 `latest.timeline.jsonl`
（每回合追加一条 C2S/S2C 事件），前端可轮询该文件做逐回合实时展示；战斗结束产出
`latest.json` 完整战报（含阵容/装备/称号/逐回合血量/胜负）。

用法：
  from seer_rebuild.battle_records import record_battle
  record_battle(report_dict)                      # 写入默认目录
  record_battle(report_dict, records_dir=...)     # 自定义目录
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

DEFAULT_RECORDS_DIR = Path(
    r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\battle-records"
)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_id(report: dict) -> str:
    """用战斗时间戳做 id；report 里没有则用当前时间。"""
    ts = report.get("started_at") or report.get("time") or int(time.time())
    return f"battle-{ts}"


def _summary(report: dict) -> dict:
    result = report.get("result") or {}
    factor = report.get("factor_name", "") or ""
    stage = report.get("stage_index")

    # winner 抽成纯字符串。历史脏数据会整包塞 result 对象、以及“战败也标胜利”的旧值，
    # 所以以 result.passed / result.over 为准推导；只有极老格式（顶层 winner 字符串且无 result）才直接采用。
    top = report.get("winner")
    if isinstance(top, str) and not result:
        winner = top
    else:
        passed = bool(result.get("passed"))
        over = bool(result.get("over"))
        # 旧 bug 会把 42390 误判成 passed=true（敌血还是满的也没死），
        # 过关必须敌方结算后 0 血；这里做一次兜底纠偏。
        enemy_hp = result.get("enemy_hp")
        if passed and enemy_hp is not None and enemy_hp != 0:
            passed = False
        winner = "胜利" if passed else ("未结束" if not over else "未过关")

    # 标题：优先因子名（前端另外会显示「第N关」，这里不再重复塞关卡号）
    head = factor or report.get("title") or "战斗"

    return {
        "id": _make_id(report),
        "ts": report.get("started_at") or report.get("time") or int(time.time()),
        "factor_name": factor,
        "design_id": report.get("design_id"),
        "stage": stage,
        "winner": winner,
        "title": head,
    }


def record_battle(report: dict, records_dir: str | Path | None = None) -> dict:
    """把一场完整战报写入记录目录：<id>.json + 更新 index.json + 覆盖 latest.json。"""
    root = Path(records_dir) if records_dir else DEFAULT_RECORDS_DIR
    root.mkdir(parents=True, exist_ok=True)

    battle_id = _make_id(report)
    _write_json(root / f"{battle_id}.json", report)

    index = _load_json(root / "index.json") or {"battles": []}
    battles = index.get("battles", [])
    summary = _summary(report)
    battles = [b for b in battles if b.get("id") != battle_id]
    battles.insert(0, summary)
    # 最多保留最近 200 场历史
    _write_json(root / "index.json", {"battles": battles[:200]})

    _write_json(root / "latest.json", report)
    return summary


def append_timeline(event: dict, records_dir: str | Path | None = None) -> None:
    """战斗进行中追加一条 C2S/S2C 事件到 latest.timeline.jsonl（实时逐回合数据源）。"""
    root = Path(records_dir) if records_dir else DEFAULT_RECORDS_DIR
    root.mkdir(parents=True, exist_ok=True)
    with (root / "latest.timeline.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def reset_live(records_dir: str | Path | None = None) -> None:
    """开战前清空 latest.timeline.jsonl（旧场次不残留）。"""
    root = Path(records_dir) if records_dir else DEFAULT_RECORDS_DIR
    root.mkdir(parents=True, exist_ok=True)
    (root / "latest.timeline.jsonl").write_text("", encoding="utf-8")