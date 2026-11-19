# -*- coding: utf-8 -*-
from seer_rebuild.battle_data import BattleData

bd = BattleData(r'F:\seer\seer_cfg\json')

def m(a, d):
    return bd.type_multiplier_name(a, d)

atk_types = ['草', '水', '冰', '光', '暗影', '次元', '虫', '虚空', '混沌', '神秘', '神灵', '圣灵', '超能', '自然', '轮回']
defs = ['地面', '超能', '地面·超能', '神秘', '战斗', '火', '龙']
print('=== 攻击类型 × 防御类型 克制 ===')
for d in defs:
    row = []
    for a in atk_types:
        try:
            row.append('%s=%.2f' % (a, m(a, d)))
        except Exception as e:
            row.append('%s=ERR' % a)
    print('%-10s | %s' % (d, '  '.join(row)))

print()
print('=== 双属性技能/物种是怎么存的（看 types 键）===')
print('types keys 样例:', list(bd.types.keys())[:40])