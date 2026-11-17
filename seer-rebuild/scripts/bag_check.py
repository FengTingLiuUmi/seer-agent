import struct

from seer_rebuild.battle_data import BattleData
from seer_rebuild.pets import parse_bag_43706

data = BattleData(r"F:\seer\seer_cfg\json")
body = open("seer-rebuild/tests/fixture_43706.bin", "rb").read()

count, pets = parse_bag_43706(body, data=data)
print("count =", count, "识别到", len(pets), "只:")
for p in pets:
    sp = data.species.get(p.species_id)
    print(f"  species={p.species_id:6d} {sp.name if sp else '?'}  catch_time={p.catch_time}")

# 用更宽的 scan 找所有「species + catch_time(合理)」对（不限定 148 字节）
print("\n宽扫描（species 后 4~200 字节内有 catch_time）：")
found = []
for o in range(0, len(body) - 4, 4):
    s = struct.unpack_from(">I", body, o)[0]
    if s not in data.species or not (1000 <= s <= 6000):
        continue
    # 只在 4 对齐处看
    for span in range(4, 220, 4):
        p2 = o + span
        if p2 + 4 > len(body):
            break
        c = struct.unpack_from(">I", body, p2)[0]
        if 0x54000000 <= c <= 0x6C000000:
            found.append((o, s, data.species[s].name, span, c))
            break
for o, s, name, span, c in found:
    print(f"  0x{o:04x} {s} {name} (catch@{span}={c})")