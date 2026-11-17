"""反查用户要改的目标：精灵/装备/称号/套装 名字 -> ID。"""
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
sys.path.insert(0, str(ROOT))

from seer_rebuild.battle_data import BattleData
from seer_rebuild.ini_util import load_ini

DATA = BattleData(r"F:\seer\seer_cfg\json")

# 1) 精灵（species id）
pet_names = ["阿布", "艾夏拉", "重生之翼"]
name2id = {}
for sid, sp in DATA.species.items():
    name2id.setdefault(sp.name, []).append(sid)
print("=== 精灵 ===")
for n in pet_names:
    hits = name2id.get(n, [])
    print(f"  {n} -> {hits}")
    # 模糊
    for sid, sp in DATA.species.items():
        if n in sp.name and sid not in hits:
            print(f"     含「{n}」: {sid} {sp.name}")

# 2) 装备 equip.ini（含目镜/套装字段）
print("\n=== equip.ini 反查 ===")
eq = load_ini(r"F:\seer\seer_cfg\json\equip.ini")
for sec, kv in eq.sections:
    name = kv.get("Name", kv.get("name", ""))
    if name in ("银翼", "银翼套装", "未来之瞳", "银翼之靴") or "银翼" in name or "未来之" in name:
        print(f"  [{sec}] name={name} keys={ {k: str(v)[:40] for k, v in list(kv.items())[:8]} }")

# 3) 称号 AllTitle.ini
print("\n=== title 反查 ===")
tt = load_ini(r"F:\seer\seer_cfg\json\AllTitle.ini")
for sec, kv in tt.sections:
    name = kv.get("Name", kv.get("name", ""))
    if "神话" in name:
        print(f"  [{sec}] name={name} keys={ {k: str(v)[:40] for k, v in list(kv.items())[:6]} }")

# 4) 娜无 suit 单独文件时，从 equip.ini 的 SuitID 找套装名
print("\n=== 银翼套装相关 equip 条目（含 SuitID）===")
for sec, kv in eq.sections:
    name = kv.get("Name", kv.get("name", ""))
    sid = kv.get("SuitID", kv.get("suit", ""))
    if "银翼" in name or str(sid) in ("银翼", "SilverWing" ) or name in ("未来之瞳",):
        print(f"  [{sec}] name={name} SuitID={sid}")