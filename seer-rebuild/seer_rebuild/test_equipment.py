"""读取装备测试 main：直接走 inventory.snapshot_from_live + resolve。

位置：seer_rebuild/test_equipment.py（与 inventory.py 同级）
运行：
    chcp 65001
    $env:PYTHONIOENCODING = "utf-8"
    $env:PYTHONPATH = "C:\\Users\\kmdbn\\Documents\\deepseek-harness\\default-workspace\\seer\\seer-rebuild"
    python test_equipment.py --account <账号> --password <密码>

说明（对应 inventory.py 的注释）：
    赛尔号把「外观」拆成两套：
      equipment = 装备段：真正提供属性加成（bonus/suit_bonus 有值）
      clothes   = 装扮段：纯外观时装
    两者都从登录 1001 快照的 _worn_sections 解析，再用 SeerAPI 的 equip 资源补 name/部位/bonus/套装。
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)                      # seer-rebuild 根目录（含 seer_rebuild 包）
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from seer_rebuild.inventory import snapshot_from_live, resolve
from seer_rebuild.provider import SeerApiProvider


def read_equipment(account: str, password: str, resolve_names: bool = True) -> dict:
    """读当前装备 / 装扮 / 称号（走 inventory 的实时 1001 快照解析）。"""
    snap = snapshot_from_live(account, password, None)
    if resolve_names:
        snap = resolve(snap, SeerApiProvider())
    return snap.as_dict()


def main() -> None:
    ap = argparse.ArgumentParser(description="读取装备测试（inventory 路径）")
    ap.add_argument("--account", default=os.environ.get("SEER_ACCOUNT"), help="账号")
    ap.add_argument("--password", default=os.environ.get("SEER_PASSWORD"), help="密码")
    ap.add_argument("--no-resolve", action="store_true", help="不反查名称，只显示 id（跳过 SeerAPI）")
    args = ap.parse_args()

    if not args.account or not args.password:
        ap.error("需要 --account / --password（或环境变量 SEER_ACCOUNT / SEER_PASSWORD）")

    data = read_equipment(args.account, args.password, resolve_names=not args.no_resolve)

    def _fmt(e: dict) -> str:
        return (f"[{e.get('slot') or '?'}] {e.get('name')}(id={e.get('id')}) "
                f"bonus={e.get('bonus') or '-'} suit={e.get('suit') or '-'} suit_bonus={e.get('suit_bonus') or '-'}")

    print("=== 装备段（equipment，提供属性加成）===")
    equip_list = data.get("equipment") or []
    if not equip_list:
        print("  (空 —— 没穿任何有加成的装备)")
    for e in equip_list:
        print(f"  {_fmt(e)}")

    print("\n=== 装扮段（clothes，纯外观）===")
    clothes_list = data.get("clothes") or []
    if not clothes_list:
        print("  (空)")
    for c in clothes_list:
        print(f"  {_fmt(c)}")

    print("\n=== 称号（titles）===")
    titles = data.get("titles") or []
    if not titles:
        print("  (空 —— 没戴称号)")
    for t in titles:
        print(f"  {t.get('name')}(id={t.get('id')}) bonus={t.get('bonus') or '-'} desc={t.get('desc') or '-'}")

    print("\n=== 完整 JSON ===")
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()