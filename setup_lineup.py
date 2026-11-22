import sys
sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.team import execute, move_step, starter_step

ACCOUNT = sys.argv[1]
PASSWORD = sys.argv[2]

# 目标阵容：表姐1(首发) / 表姐2 / 御象 / 龙焉 / 魔钰 / 圣王
# 移除：斯克鲁恩 1674394140、潘克多斯 1688399333
# 加入：表姐1 1658369845、表姐2 1676555665
# 首发：表姐1 1658369845
steps = [
    move_step(1674394140, False),   # 斯克鲁恩 → 仓库
    move_step(1688399333, False),   # 潘克多斯 → 仓库
    move_step(1658369845, True),    # 表姐1 → 正式
    move_step(1676555665, True),    # 表姐2 → 正式
    starter_step(1658369845),       # 表姐1 首发
]
for line in execute(ACCOUNT, PASSWORD, steps, send=True):
    print(line)
print("=== setup done ===")