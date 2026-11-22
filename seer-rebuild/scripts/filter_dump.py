import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

f = r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild\data\main_full_dump.json"
j = json.load(open(f, encoding="utf-8-sig"))

targets = {
    5000: "圣灵谱尼", 3022: "王之哈莫", 3512: "帝皇之御", 3045: "六界神王",
    3463: "时空界皇", 3866: "月照星魂", 3567: "魔钰", 4377: "蒂朵", 3329: "六界帝神",
    3865: "希瓦", 4169: "弑序神罗", 3409: "三藏", 2727: "蒙奇多克", 3519: "沙悟净",
    2735: "天河神将", 2987: "重生之翼", 3118: "索比斯", 3437: "艾欧丽娅",
    3322: "茉蕊儿", 3613: "芳馨·茉蕊儿", 3644: "蓝露", 3022: "王之哈莫",
}
# de-dup
targets = dict(targets)

print("=== BAG (43706) 全部 ===")
for p in j["bag"]:
    print(f"  {p['name']} species={p['species_id']} catch=0x{p['catch_time']:08X}")

print()
print("=== 目标精灵定位 ===")
for sid in sorted(targets, key=lambda s: targets[s]):
    tn = targets[sid]
    bagHits = [h for h in j["bag"] if h["species_id"] == sid]
    eliteHits = [h for h in j["elite"] if h["species_id"] == sid]
    normalHits = [h for h in j["normal"] if h["species_id"] == sid]
    print(f"[{sid} {tn}]")
    for h in bagHits:
        print(f"    BAG    catch=0x{h['catch_time']:08X}")
    for h in eliteHits:
        print(f"    ELITE  flag={h['flag']} catch=0x{h['catch_time']:08X}")
    for h in normalHits:
        print(f"    NORMAL lv={h['level']} flag={h['flag']} catch=0x{h['catch_time']:08X}")
    if not (bagHits or eliteHits or normalHits):
        print("    (未找到)")