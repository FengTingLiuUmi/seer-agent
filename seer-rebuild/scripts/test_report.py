"""离线端到端验证战报（用 stage5_diag 的八四战 + 手工重建 C2S）。"""
import re
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")

from seer_rebuild.battle_report import build_report_from_timeline, report_to_text


def load_s2c(path):
    raw = open(path, 'rb').read()
    try:
        text = raw.decode('utf-16')
    except UnicodeDecodeError:
        text = raw.decode('utf-8', errors='replace')
    out = []
    for ln in text.splitlines():
        m = re.search(r'cmd=(\d+) result=(\S+) len=(\d+) body=([0-9a-f]+)', ln)
        if m:
            out.append({"cmd": int(m.group(1)), "result": 0, "len": int(m.group(3)),
                        "body": m.group(4)})
    return out


s2c = load_s2c(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\stage5_diag.txt")
sk2505 = [f for f in s2c if f['cmd'] == 2505]
print("2505 帧数:", len(sk2505))

def c2s(cmd, body_hex):
    return {"dir": "c2s", "cmd": cmd, "body": body_hex, "result": 0}

def s2c_ev(cmd, body_hex):
    return {"dir": "s2c", "cmd": cmd, "body": body_hex, "result": 0}

# 手工重建八四战 C2S（31505 -> 六界 -> 19314 -> 时空 -> 31253）
timeline = [
    c2s(2404, ""),
    s2c_ev(2503, s2c[0]['body']) if any(f['cmd']==2503 for f in s2c) else None,
    s2c_ev(2504, [f for f in s2c if f['cmd']==2504][0]['body']),
    c2s(2405, "%08x" % 31505),
]
timeline = [t for t in timeline if t is not None]
# 第1招后第1个2505
timeline.append(s2c_ev(2505, sk2505[0]['body']))
timeline.append(c2s(2407, "%08x" % 0x62ef6f18))
timeline.append(c2s(2405, "%08x" % 19314))
timeline.append(s2c_ev(2505, sk2505[1]['body']))
timeline.append(c2s(2407, "%08x" % 0x5ffd1dd6))
timeline.append(c2s(2405, "%08x" % 31253))
timeline.append(s2c_ev(2505, sk2505[2]['body']))
timeline.append(s2c_ev(2506, ""))

bag = {"uid": ACCOUNT, "正式": [
    {"species_id": 3512, "catch_time": 0x62d8b735},
    {"species_id": 2727, "catch_time": 0x600b3f8c},
    {"species_id": 3519, "catch_time": 0x600b3f86},
    {"species_id": 3045, "catch_time": 0x62ef6f18},
    {"species_id": 3463, "catch_time": 0x5ffd1dd6},
], "待命": []}

snap = {"equipment": [
    {"slot": "目镜", "name": "漫游者-AH", "bonus": "攻击+30 特攻+30 体力+40", "suit": "", "suit_bonus": "", "id": 1301040},
    {"slot": "足部", "name": "银翼骑士长靴", "bonus": "", "suit": "银翼骑士套装", "suit_bonus": "攻击伤害+30%", "id": 1300673},
], "titles": [{"name": "夏日狂想曲", "bonus": "攻击+60 体力+30", "id": 417}], "clothes": []}

rep = build_report_from_timeline(
    timeline, bag=bag, snap=snap,
    data_root=r"F:\seer\seer_cfg\json",
    factor_name="伊娜因子", design_id=266, stage_index=5, enemy_max_hp=10000,
)
print(report_to_text(rep))
print("\n--- JSON ---")
import json
print(json.dumps(rep.as_dict(), ensure_ascii=False, indent=2))