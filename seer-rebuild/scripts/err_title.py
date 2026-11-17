import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.provider import SeerApiProvider

p = SeerApiProvider()
for code in [1940033, 1940034, 1940035, 1940036]:
    try:
        d = p.get("error_code", code, fields=["id", "name", "desc"])
        print(code, "->", d)
    except Exception as e:
        print(code, "->", str(e).split(chr(10))[0])

# CAPTURE_EQUIP 里的 title_id=0x1A1=417 是什么
print("\ntitle 417:")
d = p.get("title", 417)
print("  ", d.get("name") if d else None, d.get("attr_bonus") if d else None, d.get("ability_desc") if d else None)

# 236 齐天小圣 + 272 吉光凤羽 的完整字段（含是否有 achievement/point等）
for tid in [236, 272]:
    d = p.get("title", tid)
    print(f"\ntitle {tid}: name={d.get('name')} attr={d.get('attr_bonus')} ability={d.get('ability_desc')} is_ability={d.get('is_ability_bonus')}")