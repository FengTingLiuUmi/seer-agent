import json, sys
sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.battle_report import build_report_from_timeline
from seer_rebuild.battle_data import BattleData
from seer_rebuild.provider import SeerApiProvider

bd = BattleData(r"F:\seer\seer_cfg\json")
skill_names = {sid: m.name for sid, m in bd.moves.items()}
species_names = {sid: s.name for sid, s in bd.species.items()}

timeline = [json.loads(l) for l in open(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\battle-records\timeline.jsonl", encoding="utf-8")]

# 第4关最终阵容（表姐1/表姐2/御象/龙焉/魔钰/圣王）
formal = [
    (3512, 1658369845),  # 表姐1
    (4002, 1624720755),  # 御象
    (3567, 1678553578),  # 魔钰
    (4373, 1654918859),  # 龙焉
    (3328, 1614431841),  # 圣王
    (3512, 1676555665),  # 表姐2
]
bag = {"正式": [{"species_id": sp, "catch_time": ct} for sp, ct in formal], "待命": [], "uid": 753949294}

prov = None
def resolve_skill(sid):
    global prov
    if prov is None:
        try:
            prov = SeerApiProvider()
        except Exception:
            prov = False
    if prov is False:
        return None
    try:
        return prov.name("skill", sid)
    except Exception:
        return None

rep = build_report_from_timeline(timeline, bag=bag, snap={"equipment": [], "titles": []},
                                 skill_names=skill_names, species_names=species_names,
                                 factor_name="伊娜因子", design_id=266, stage_index=4,
                                 resolve_skill=resolve_skill)
for t in rep.turns:
    print(f"turn{t.turn}: 我={t.active_name}({t.skill_name}) 敌技={t.enemy_skill_id}({t.enemy_skill_name}) "
          f"敌血={t.enemy_hp_prev}->{t.enemy_hp}/{t.enemy_hp_max} 伤害={t.damage} delta={t.enemy_hp_delta}")
print("result:", rep.result.as_dict())

# 用修复后的解析覆盖 latest.json（前端 dsh-seer-battle 直接读它渲染回合表）
out = rep.as_dict()
out["equipment"] = []
out["title_equipped"] = []
out_path = r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\battle-records\latest.json"
import io
with io.open(out_path, "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=2)
print("已覆盖 latest.json")