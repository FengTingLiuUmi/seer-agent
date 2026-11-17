import struct
from seer_rebuild.pets import run
from seer_rebuild.provider import SeerApiProvider

r = run("ACCOUNT", "PASSWORD", None)
b = None
for f in r["frames"]:
    if f["cmd"] == 1001:
        b = bytes.fromhex(f["body"])
        break

ids = [struct.unpack_from(">I", b, off)[0] for off in (0x18, 0x1C, 0x20, 0x24, 0x28)]
print("当前穿戴 5 部位 ID:", [hex(x) for x in ids])

p = SeerApiProvider()
for i in ids:
    d = p.get("equip", i)
    if d:
        pt = (d.get("part_type") or {}).get("id")
        bonus = ((d.get("bonus") or {}).get("desc") or "") if d.get("bonus") else ""
        print(f"  {i}  part={pt}  name={d.get('name')}  bonus={bonus}")
    else:
        print(f"  {i}  (not equip)")