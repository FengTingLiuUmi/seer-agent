"""全量测试：换装备 + 换称号 + 更换背包（清空现有，阿徒首发 / 艾夏拉第二 / 重生之翼待命）。"""
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
sys.path.insert(0, str(ROOT))

from seer_rebuild.team import (
    demote_step, equip_step, execute, move_step, starter_step, title_step,
)

ATU = 0x602886B7           # 阿徒（第一只，自行决策）
AIXIA = 0x601F36EB         # 艾夏拉
CHONGSHENG = 0x56ED2170    # 重生之翼

# 现有正式（除艾夏拉）→ 放回仓库
CUR_FORMAL = [1472551551, 1612627786, 1686900194, 1696702272, 1717550270]
# 现有待命（全部）→ 放回仓库
CUR_RESERVE = [1622945994, 1611577149, 1653671443, 1616516844, 1612548787]


def build() -> list:
    steps = []
    # 1) 换装备：银翼骑士套装 + 未来之瞳（头/目镜/腰/手/足）
    steps.append(equip_step([1300670, 1300838, 1300672, 1300671, 1300673]))
    # 2) 换称号：神话
    steps.append(title_step(300))
    # 3) 清空现有正式（除艾夏拉）与待命 → 放回仓库
    for c in CUR_FORMAL:
        steps.append(move_step(c, to_bag=False))
    for c in CUR_RESERVE:
        steps.append(move_step(c, to_bag=False))
    # 4) 阿徒、重生之翼加入背包
    steps.append(move_step(ATU, to_bag=True))
    steps.append(move_step(CHONGSHENG, to_bag=True))
    # 5) 排序：阿徒第1、艾夏拉第2
    steps.append(starter_step(ATU))
    steps.append(starter_step(AIXIA))
    steps.append(starter_step(ATU))
    # 6) 重生之翼降待命
    steps.append(demote_step(CHONGSHENG))
    return steps


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--account", default="ACCOUNT")
    ap.add_argument("--password", default="PASSWORD")
    a = ap.parse_args()

    steps = build()
    if a.send:
        for line in execute(a.account, a.password, steps, send=True):
            print(line)
    else:
        print(f"共 {len(steps)} 步（dry-run，--send 真发）：")
        for line in execute(a.account, a.password, steps, send=False):
            print(line)