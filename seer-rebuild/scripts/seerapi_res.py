import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.provider import SeerApiProvider

p = SeerApiProvider()
# 看 seerapi 有哪些资源
res = p.resources()
names = [r.get("name") or r.get("title") or str(r) for r in (res or [])]
print("resources:", names)