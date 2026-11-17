import json, re

d = json.load(open('data/commandid.json', encoding='utf-8'))
items = [(int(k), v) for k, v in d.items()] if isinstance(d, dict) and all(str(k).isdigit() for k in d) else []
if not items:
    # 结构可能是 {name: id}
    items = [(int(v), k) for k, v in d.items()]

groups = {
    '捕获/精灵球': r'CATCH|BALL|CAPTURE|SEAL',
    '精灵': r'PET',
    '战斗/关卡': r'FIGHT|BATTLE|WAR|LEVEL|GATE|INSTANCE|DUNGEON|BOSS',
    '地图/场景': r'MAP|SCENE|ROOM',
    '任务': r'TASK|MISSION|DAILY|JOB',
}
for label, pat in groups.items():
    print('====', label, '====')
    hits = sorted([(c, n) for c, n in items if re.search(pat, n or '', re.I)])
    print('  count', len(hits))
    for c, n in hits[:18]:
        print('   %5d  %s' % (c, n))