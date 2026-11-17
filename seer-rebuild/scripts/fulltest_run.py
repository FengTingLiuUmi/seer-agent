"""动态执行全量测试：先读当前背包，再放回非目标、加入目标、排序。"""
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
sys.path.insert(0, str(ROOT))

from seer_rebuild.team import (
    demote_step, equip_step, execute, move_step, starter_step, title_step,
)

ATU = 0x602886B7           # 阿徒
AIXIA = 0x601F36EB         # 艾夏拉（目标保留，正式第2）
CHONGSHENG = 0x56ED2170    # 重生之翼（目标待命）


def build(formal, reserve):
    steps = [
        equip_step([1300670, 1300838, 1300672, 1300671, 1300673]),
        title_step(300),
    ]
    # 放回当前正式里除艾夏拉外的一切
    for c in formal:
        if c != AIXIA:
            steps.append(move_step(c, to_bag=False))
    # 放回当前待命全部
    for c in reserve:
        steps.append(move_step(c, to_bag=False))
    # 加入目标
    steps.append(move_step(ATU, to_bag=True))
    steps.append(move_step(CHONGSHENG, to_bag=True))
    # 排序：阿徒第1、艾夏拉第2
    steps.append(starter_step(ATU))
    steps.append(starter_step(AIXIA))
    steps.append(starter_step(ATU))
    # 重生之翼降待命
    steps.append(demote_step(CHONGSHENG))
    return steps


def main():
    from seer_rebuild.pets import read_bag
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--account", default="ACCOUNT")
    ap.add_argument("--password", default="PASSWORD")
    a = ap.parse_args()

    if a.send:
        bag = read_bag(a.account, a.password, resolve_names=False)
        formal = [p["catch_time"] for p in bag["正式"]]
        reserve = [p["catch_time"] for p in bag["待命"]]
        steps = build(formal, reserve)
        print(f"当前正式 {len(formal)} 只、待命 {len(reserve)} 只；共 {len(steps)} 步：")
        for line in execute(a.account, a.password, steps, send=True):
            print(line)
    else:
        # dry-run 用假想的目标外还存在的精灵
        demo_formal = [1612627786, 1612658411, 1686900194, 1696702272, 1717550270]
        demo_reserve = [1622945994, 1611577149, 1653671443, 1616516844, 1612548787]
        steps = build(demo_formal, demo_reserve)
        print(f"共 {len(steps)} 步（dry-run，--send 真发）：")
        for line in execute(a.account, a.password, steps, send=False):
            print(line)


if __name__ == "__main__":
    main()