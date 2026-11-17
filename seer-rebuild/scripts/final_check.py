from seer_rebuild.inventory import parse_frames_jsonl, resolve
from seer_rebuild.provider import SeerApiProvider

s = parse_frames_jsonl("seer-rebuild/feature1_frames.jsonl")
resolve(s, SeerApiProvider())

print("=== 装备（头盔/护甲/武器）===")
for e in s.equipment:
    b = e.bonus or "无"
    sb = e.suit_bonus or "无"
    print(f"  {e.slot}\t{e.name}\t单件:{b}\t套装[{e.suit}]:{sb}")

print("=== 装扮（时装/套装外观）===")
for e in s.clothes:
    print(f"  {e.slot}\t{e.name}")

print("=== 称号 ===")
for t in s.titles:
    print(f"  {t.name}\t{t.bonus}")