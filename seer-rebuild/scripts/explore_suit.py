import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.provider import SeerApiProvider

p = SeerApiProvider()

# 先看 suit 的结构：随便查一个
print("=== suit 资源结构（拿 suit_bonus 看看）===")
try:
    b = p._run("list", "suit", "--limit", "3")
    print(b)
except Exception as e:
    print("list suit err:", e)

print("\n=== suit_bonus 列表抽样 ===")
try:
    b = p._run("list", "suit_bonus", "--limit", "5")
    print(b)
except Exception as e:
    print("list suit_bonus err:", e)

print("\n=== title 列表抽样 ===")
try:
    b = p._run("list", "title", "--limit", "3")
    print(b)
except Exception as e:
    print("list title err:", e)