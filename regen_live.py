import json, sys
sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.battle_report import (
    _enemy_head_block, _enemy_action_by_eid, _discover_enemy_from_2505, _discover_enemy
)
from seer_rebuild.battle_data import BattleData
from seer_rebuild.provider import SeerApiProvider

REC = r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\battle-records"

bd = BattleData(r"F:\seer\seer_cfg\json")
skill_names = {sid: m.name for sid, m in bd.moves.items()}
prov = None
def resolve_skill(sid):
    global prov
    if prov is None:
        try: prov = SeerApiProvider()
        except Exception: prov = False
    if prov is False: return None
    try: return prov.name("skill", sid)
    except Exception: return None
def skill_label(sid):
    if sid is None: return None
    n = skill_names.get(sid)
    if n: return n
    n = resolve_skill(sid)
    return n or None

frames = [json.loads(l) for l in open(REC + r"\timeline.jsonl", encoding="utf-8")]

# 1) 发现敌方 eid + 满血（首个 2505 头块最稳，2504 兜底）
enemy_eid = None
enemy_max = None
s2c = [e for e in frames if e.get("dir") == "recv"]
for e in s2c:
    if e["cmd"] == 2505:
        enemy_eid, enemy_max = _discover_enemy_from_2505(bytes.fromhex(e["body"]), set())
        if enemy_max:
            break
if enemy_max is None:
    enemy_eid, enemy_max = _discover_enemy(s2c, set())
print("敌方 eid", hex(enemy_eid) if enemy_eid else None, "满血", enemy_max)

# 2) 重算每个 2505 的注入字段
fixed = []
for e in frames:
    if e.get("dir") == "recv" and e["cmd"] == 2505:
        en = _enemy_action_by_eid(bytes.fromhex(e["body"]), enemy_eid, enemy_max)
        if en is not None:
            e = dict(e)
            e["enemy_skill_id"] = en["skill_id"] if en["skill_id"] else None
            e["enemy_skill_name"] = skill_label(en["skill_id"]) if en["skill_id"] else None
            e["enemy_hp"] = en["hp"]
            e["enemy_max"] = en["max_hp"]
    fixed.append(e)

# 3) latest.timeline.jsonl = 只含战斗帧（2404 之后），与前端 buildLiveView 期望一致
battle_frames = [e for e in fixed if e.get("cmd") in (2404, 2405, 2407, 2503, 2504, 2505, 2506, 42390, 45827, 2595, 2394)]
with open(REC + r"\latest.timeline.jsonl", "w", encoding="utf-8") as fh:
    fh.write("\n".join(json.dumps(e, ensure_ascii=False) for e in battle_frames) + "\n")
print("已重写 latest.timeline.jsonl,", len(battle_frames), "帧")

# 打印校验
for e in battle_frames:
    if e.get("cmd") == 2505:
        print(f"2505 敌技={e.get('enemy_skill_id')}({e.get('enemy_skill_name')}) 敌血={e.get('enemy_hp')}/{e.get('enemy_max')}")