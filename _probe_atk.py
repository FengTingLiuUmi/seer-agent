# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.battle_data import BattleData, TYPE_NAMES

bd = BattleData(r"F:\seer\seer_cfg\json")
for sid in (4223, 3239):
    sp = bd.species.get(sid)
    print(f"===== {sid} {sp.name if sp else 'NOT FOUND'} =====")
    if not sp:
        continue
    for sk in sp.skills:
        m = bd.moves.get(sk)
        if not m:
            continue
        print(f"  [{sk}] {m.name} power={m.power} cat={m.category} type={TYPE_NAMES.get(m.type,'?')} prio={m.priority} accuracy={m.accuracy}")