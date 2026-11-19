# -*- coding: utf-8 -*-
from seer_rebuild.roster_cache import load, attackers

pets = load()
print('物种数', len(pets), '个体缓存数', sum(len(p['individuals']) for p in pets))
for st in ('草', '水', '冰', '光', '暗影', '次元', '虫', '虚空'):
    a = attackers(pets, stype=st, lv=100)
    print('--- %s系满级高攻 ---' % st)
    for p in a[:12]:
        inds = p['individuals']
        skills = p.get('skills') or []
        brief = [(i.get('catch_time'), i.get('level'), i.get('skills')) for i in inds][:3]
        print('  %d %-14s type=%-12s HP=%s atk=%s spa=%s 技能=%s 个体=%s' % (
            p['species_id'], p.get('name'), p.get('type'), p.get('hp'), p.get('atk'),
            p.get('sp_atk'), skills, brief))