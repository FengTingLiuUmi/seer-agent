# -*- coding: utf-8 -*-
"""赛尔号 PVE 本体 —— 基准回归测试（stdlib unittest，无需 pytest）。
守护完整性：克制公式 / 昵称消歧 / Boss 结构不变量 / 类型表计数 / 技能魂印 / MCP 查询层。
运行（同 ing est 环境）：
    $env:PYTHONPATH="...\\seer\\seer-factor-kb\\.pylibs"; $env:PYTHONUTF8="1"
    python test_regression.py
"""
import os, sys, re, unittest

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
sys.path.insert(0, HERE)

from rdflib import Graph, RDF, RDFS, Namespace, SKOS

SEER = Namespace("http://example.org/seer#")
PVE = Namespace("http://example.org/seer/pve#")

import type_multiplier as tm
import seer_kb_mcp as kb

G = Graph()
G.parse(os.path.join(HERE, "seer-all.owl"), format="xml")


def ln(u):
    return str(u).rsplit("#", 1)[-1]


def label(node):
    for o in G.objects(node, RDFS.label):
        return str(o)
    return ln(node)


# ---------------- 克制公式 ----------------

class TestTypeChart(unittest.TestCase):
    CASES = [
        (["圣灵"], ["草"], 2.0),
        (["王"], ["自然"], 0.5),
        (["邪灵"], ["神灵"], 0.0),
        (["圣灵", "自然"], ["草"], 4.0),
        (["邪灵", "神秘"], ["神灵"], 0.5),
        (["王"], ["自然", "战斗"], 1.25),
        (["自然", "战斗"], ["光", "飞行"], 1.5),
        (["远古", "战斗"], ["龙", "暗影"], 2.375),
    ]

    def test_golden_multipliers(self):
        for a, d, exp in self.CASES:
            got = tm.by_names(a, d)
            self.assertIsNotNone(got, f"by_names({a},{d})=None")
            self.assertAlmostEqual(got, exp, places=9,
                                   msg=f"{a} vs {d} 期望 {exp} 实得 {got}")

    def test_stab_constant(self):
        self.assertEqual(tm.STAB, 1.5)

    def test_stab_is_set_equality_not_share(self):
        duals = {tc: e for tc, e in tm.TC2ELEMS.items() if len(e) == 2}
        for tc1, e1 in duals.items():
            for tc2, e2 in duals.items():
                if tc1 != tc2 and set(e1) & set(e2) and set(e1) != set(e2):
                    self.assertTrue(tm.share_element(tc1, tc2))
                    self.assertFalse(tm.is_same_type(tc1, tc2),
                                     f"{tc1}/{tc2} 共享单属性但组合不同，不应判为同型")
                    return
        self.fail("未找到共享单属性的两个不同双属性组合")


# ---------------- 昵称消歧 ----------------

class TestAlias(unittest.TestCase):
    GOLDEN = {
        "潘": "4344", "火潘": "4344", "草潘": "4606", "冰潘": "4463",
        "鲁斯王": "4648", "猩猩": "4649", "丽莎": "4647",
        "艾欧": "3437", "王哈": "3022", "村长": "4487", "眠酱": "4442",
        "幻境": "3460", "界皇": "3460",
    }

    def test_nickname_golden(self):
        for name, want in self.GOLDEN.items():
            ids = [m.get("id") for m in kb.tool_nick(name).get("matches", [])]
            self.assertIn(want, ids, f"昵称「{name}」应解析到 {want}，实得 {ids}")

    def test_pan_not_pandora(self):
        ids = [m.get("id") for m in kb.tool_nick("潘").get("matches", [])]
        self.assertIn("4344", ids)
        for bad in ("2518", "2965", "3396"):
            self.assertNotIn(bad, ids)

    def test_aiou_not_starlight(self):
        ids = [m.get("id") for m in kb.tool_nick("艾欧").get("matches", [])]
        self.assertIn("3437", ids)
        self.assertNotIn("4911", ids)


# ---------------- Boss 结构不变量 ----------------

class TestBossStructure(unittest.TestCase):
    def test_stage_iri_encodes_difficulty(self):
        pat = re.compile(r"^stage_.+_(hard|normal|easy)_\d+$")
        for st in G.subjects(RDF.type, SEER.FactorStage):
            self.assertRegex(ln(st), pat, f"关卡 IRI 未含难度档: {ln(st)}")

    def test_stage_enemy_bijection(self):
        stages = set(G.subjects(RDF.type, SEER.FactorStage))
        enemies = set(G.subjects(RDF.type, PVE.Enemy))
        for st in stages:
            ens = list(G.objects(st, PVE.hasEnemy))
            self.assertEqual(len(ens), 1, f"{ln(st)} 应恰好 1 个 enemy")
        self.assertEqual(len(stages), len(enemies),
                         f"stage={len(stages)} enemy={len(enemies)}")

    def test_jiulina_dual_difficulty(self):
        fam = SEER.factor_jiulina
        diffs = {G.value(st, PVE.difficulty) for st in G.objects(fam, SEER.hasStage)}
        self.assertEqual(diffs, {PVE.diff_hard, PVE.diff_normal})
        self.assertEqual(len(list(G.objects(fam, SEER.hasStage))), 10,
                         "玖莉娜应保留 地狱5关+困难5关 共10关")

    def test_stage_difficulty_vocab(self):
        for st in G.subjects(RDF.type, SEER.FactorStage):
            self.assertIn(G.value(st, PVE.difficulty),
                          {PVE.diff_easy, PVE.diff_normal, PVE.diff_hard})

    def test_stage_number_range(self):
        for st in G.subjects(RDF.type, SEER.FactorStage):
            n = G.value(st, PVE.stageNumber)
            self.assertIsNotNone(n)
            self.assertIn(int(n), range(1, 6))

    def test_countered_by_are_pets(self):
        for en in G.subjects(RDF.type, PVE.Enemy):
            for p in G.objects(en, PVE.counteredBy):
                self.assertIn((p, RDF.type, SEER.Pet), G, f"counteredBy 非 Pet: {p}")

    def test_ban_references(self):
        for fd in G.subjects(RDF.type, PVE.FactorDifficulty):
            self.assertIsNotNone(G.value(fd, PVE.forFactor), f"{ln(fd)} 缺 forFactor")
            for p in G.objects(fd, PVE.bannedPet):
                self.assertIn((p, RDF.type, SEER.Pet), G)


# ---------------- 类型表计数 ----------------

class TestTypechartCounts(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(len(set(G.subjects(RDF.type, SEER.ElementType))), 26)
        self.assertEqual(len(set(G.subjects(RDF.type, SEER.TypeCombination))), 139)
        self.assertEqual(len(set(G.subjects(RDF.type, SEER.TypeRelation))), 676)

    def test_buckets(self):
        self.assertEqual(len(list(G.triples((None, SEER.counters, None)))), 127)
        self.assertEqual(len(list(G.triples((None, SEER.resisted, None)))), 137)
        self.assertEqual(len(list(G.triples((None, SEER.immune, None)))), 7)


# ---------------- 技能/魂印完整性 ----------------

class TestSkillStructure(unittest.TestCase):
    def test_skill_type_complete(self):
        for sk in G.subjects(RDF.type, SEER.Skill):
            self.assertIsNotNone(G.value(sk, SEER.skillType), f"skill 缺 skillType: {ln(sk)}")

    def test_skill_effect_complete(self):
        fxs = set(G.subjects(RDF.type, SEER.SkillEffect))
        self.assertGreater(len(fxs), 0)
        for fx in fxs:
            self.assertIsNotNone(G.value(fx, SEER.effectTypeOf), f"{ln(fx)} 缺 effectTypeOf")
            self.assertIsNotNone(G.value(fx, SEER.effectInfo), f"{ln(fx)} 缺 effectInfo")

    def test_role_vocab(self):
        valid = {PVE.attacker, PVE.support, PVE.tank, PVE.reflect, PVE.firstStrike}
        # 站场的细分机制：凡是 tank 的 rdfs:subClassOf 后代都算合法角色
        subs, stack = {}, [PVE.tank]
        for a, b in G.subject_objects(RDFS.subClassOf):
            subs.setdefault(b, set()).add(a)
        while stack:
            cur = stack.pop()
            for s in subs.get(cur, ()):
                if s not in valid:
                    valid.add(s)
                    stack.append(s)
        for r in G.objects(None, PVE.hasRole):
            self.assertIn(r, valid, f"非法角色: {r}")

    def test_tank_subroles(self):
        """站场子类必须挂在 tank 下，且必须能查到个体（否则就是死标签）。"""
        subs = {s for s in G.subjects(RDFS.subClassOf, PVE.tank)}
        self.assertGreaterEqual(len(subs), 4, f"tank 子类过少: {[ln(s) for s in subs]}")
        live = {r for r in G.objects(None, PVE.hasRole) if r in subs}
        self.assertGreater(len(live), 0, "所有 tank 子类都没有个体")
        self.assertIn(PVE["免伤站场"], live, "免伤站场 应至少挂一只（暴君史莱姆）")


# ---------------- 精灵补充表（supp）不变量 ----------------

class TestPetSupplement(unittest.TestCase):
    """守护 build_supp.py 可重入性：曾两次出现「只写 altLabel、label/type 丢失」。"""

    def test_every_pet_has_label_and_type(self):
        pets = set(G.subjects(RDF.type, SEER.Pet))
        self.assertGreaterEqual(len(pets), 343)
        for p in pets:
            self.assertIsNotNone(G.value(p, RDFS.label), f"{ln(p)} 缺 rdfs:label")
            self.assertIsNotNone(G.value(p, SEER.seerapiId), f"{ln(p)} 缺 seerapiId")

    def test_pet_type_combination_complete(self):
        # 有属性组合的精灵，其组合必须能拿到元素（否则 mult/nick 会拿到空属性）
        for p in G.subjects(RDF.type, SEER.Pet):
            tc = G.value(p, SEER.hasTypeCombination)
            if tc is not None:
                self.assertGreater(len(list(G.objects(tc, SEER.combinationOf))), 0,
                                   f"{ln(p)} 的属性组合 {ln(tc)} 无元素")

    def test_pen_name_typos_resolve(self):
        """攻略里的错写字必须能对回正确精灵（否则召回会挂空）。"""
        cases = {
            "阿克西亚": "50",     # 阿克希亚
            "西塔轮": "4636",     # 西塔伦
            "艾莫丽萨": "3573",   # 艾莫莉萨
            "圣奇·赫里斯": "3938",  # 圣骑·赫里斯
            "乌瑞亚": "3763",     # 乌瑞娅
            "万兽至尊·猛虎王": "3676",  # 万兽之尊·猛虎王
        }
        for tok, pid in cases.items():
            r = kb.tool_nick(tok)
            self.assertNotIn("error", r, f"{tok} 无法解析: {r}")
            hits = r.get("matches") or []
            self.assertTrue(hits, f"{tok} 无匹配: {r}")
            self.assertEqual(str(hits[0]["id"]), pid, f"{tok} 应为 {pid} 实得 {hits[0]}")


# ---------------- MCP 查询层 ----------------

class TestMCP(unittest.TestCase):
    def test_mult_golden(self):
        self.assertAlmostEqual(kb.tool_mult("圣灵", "草")["multiplier"], 2.0)
        self.assertAlmostEqual(kb.tool_mult("圣灵自然", "光飞行")["multiplier"], 1.5)
        self.assertAlmostEqual(kb.tool_mult("机械", "机械战斗")["multiplier"], 1.25)

    def test_boss_yita(self):
        r = kb.tool_boss("伊塔回溯型", "地狱")
        self.assertEqual(len(r["stages"]), 5)
        ban = {p["id"] for p in r["bannedPet"]}
        self.assertEqual(ban, {"3022", "3594", "4463"})

    def test_ban_yita(self):
        r = kb.tool_ban("伊塔回溯型", "地狱")
        self.assertEqual({p["id"] for p in r["bannedPet"]}, {"3022", "3594", "4463"})

    def test_role_attacker(self):
        r = kb.tool_role("attacker")
        self.assertGreater(len(r["pets"]), 0)
        for p in r["pets"]:
            self.assertTrue(any("强攻" in x for x in p["roles"]),
                            f"attacker 池里混入非强攻: {p}")

    def test_out_of_vocab(self):
        self.assertIn("error", kb.tool_role("不存在的定位"))
        self.assertIn("error", kb.tool_boss("不存在因子", "地狱"))


class TestGear(unittest.TestCase):
    """玩家装备/套装（2026-11-24 新增）。守护 v0.1 的 "None" label bug 不复现。"""

    def test_suit_labeled(self):
        suits = set(G.subjects(RDF.type, SEER.Suit))
        self.assertEqual(len(suits), 481)
        for s in suits:
            lab = G.value(s, RDFS.label)
            self.assertIsNotNone(lab, f"{ln(s)} 缺 label")
            self.assertNotEqual(str(lab), "None", f"{ln(s)} label 仍是 None（list 无 name 的旧 bug）")
            self.assertIsNotNone(G.value(s, SEER.seerapiId), f"{ln(s)} 缺 seerapiId")

    def test_title_nature_labeled(self):
        titles = set(G.subjects(RDF.type, SEER.Title))
        natures = set(G.subjects(RDF.type, SEER.Nature))
        self.assertEqual(len(titles), 597, f"Title 数变了: {len(titles)}")
        self.assertEqual(len(natures), 25, f"Nature 数变了: {len(natures)}")
        for cls, name in ((SEER.Title, "Title"), (SEER.Nature, "Nature")):
            for s in G.subjects(RDF.type, cls):
                lab = G.value(s, RDFS.label)
                self.assertIsNotNone(lab, f"{name} {ln(s)} 缺 label")
                self.assertNotEqual(str(lab), "None", f"{name} {ln(s)} label 仍是 None")

    def test_player_equip_complete(self):
        eqs = set(G.subjects(RDF.type, SEER.PlayerEquip))
        self.assertEqual(len(eqs), 2132, f"PlayerEquip 数变了: {len(eqs)}")
        for e in eqs:
            self.assertIsNotNone(G.value(e, RDFS.label), f"{ln(e)} 缺 label")
            self.assertIsNotNone(G.value(e, SEER.hasPart), f"{ln(e)} 缺 hasPart")
            self.assertIn((e, RDF.type, SEER.Equip), G, f"{ln(e)} 未双写 seer:Equip")

    def test_part_enum_and_bijection(self):
        parts = set(G.subjects(RDF.type, SEER.EquipPart))
        self.assertEqual(len(parts), 7, f"EquipPart 枚举数应 7，实得 {len(parts)}")
        total = 0
        for p in parts:
            n = len(list(G.subjects(SEER.hasPart, p)))
            self.assertGreater(n, 0, f"{ln(p)} 没有任何部件")
            total += n
        self.assertEqual(total, 2132, f"部位计数之和 {total} != 2132（有部件归属重复或缺失）")

    def test_suit_equips_links(self):
        triples = list(G.triples((None, SEER.suitEquips, None)))
        self.assertEqual(len(triples), 1947, f"suitEquips 应 1947 条，实得 {len(triples)}")
        for s, _, o in triples:
            self.assertIn((o, RDF.type, SEER.PlayerEquip), G, f"{ln(s)} 指向的 {ln(o)} 不是部件")
            self.assertIn((s, RDF.type, SEER.Suit), G)

    def test_suit_bonus_no_empty_shell(self):
        sbs = set(G.subjects(RDF.type, SEER.SuitBonus))
        self.assertEqual(len(sbs), 79, f"SuitBonus 应 79，实得 {len(sbs)}")
        for b in sbs:
            self.assertIsNotNone(G.value(b, SEER.bonusDesc), f"{ln(b)} 缺 bonusDesc")
        ebs = set(G.subjects(RDF.type, SEER.EquipBonus))
        self.assertGreater(len(ebs), 0, "EquipBonus 不应为空")
        for b in ebs:
            meaningful = (G.value(b, SEER.bonusDesc) is not None
                          or G.value(b, SEER.bonusEffect) is not None
                          or any((G.value(b, SEER[p]) or 0) for p in
                                 ("bonusAtk", "bonusDef", "bonusSpAtk", "bonusSpDef",
                                  "bonusSpd", "bonusHp"))
                          or any((G.value(b, SEER[p]) or 0) for p in
                                 ("otherHitRate", "otherDodgeRate", "otherCritRate")))
            self.assertTrue(meaningful, f"{ln(b)} 是空壳加成（不该建个体）")

    def test_equips_deprecated_but_present(self):
        # 只加注解、不删属性：seer:equips 仍在 TBox 里且被标 deprecated
        # （模块级只 import 了 RDF/RDFS/SKOS/Namespace，OWL 在此局部引入，不动既有 import 行）
        from rdflib import OWL
        self.assertIn((SEER.equips, RDF.type, OWL.ObjectProperty), G)
        self.assertIsNotNone(G.value(SEER.equips, OWL.deprecated))
        self.assertEqual(len(list(G.triples((None, SEER.equips, None)))), 0,
                         "seer:equips 不该有个体三元组（SeerAPI pet 无 equip 字段）")

    def test_gear_tool(self):
        r = kb.tool_gear_dispatch(name="漆黑")
        self.assertNotIn("error", r)
        self.assertGreaterEqual(len(r.get("suits") or []), 1)
        self.assertEqual(r["suits"][0]["id"], "448", f"漆黑应命中 448 漆黑天使，实得 {r['suits'][0]}")
        self.assertIn("bonus", r["suits"][0])
        r2 = kb.tool_gear_dispatch(part="足部")
        self.assertNotIn("error", r2)
        self.assertEqual(r2["part"]["count"], 482)
        r3 = kb.tool_gear_dispatch(pet="六界御神")
        self.assertNotIn("error", r3)
        self.assertEqual(len(r3.get("suits") or []), 1, f"六界御神应只命中 1 套，实得 {r3.get('suits')}")
        self.assertEqual(r3["suits"][0]["id"], "414")
        r4 = kb.tool_gear_dispatch()
        self.assertIn("error", r4)


class TestEffects(unittest.TestCase):
    """seer-effects-abox.ttl（buff / 魂印 / 特性 / 宝石 / 刻印 / 战斗效果）的结构与查询测试。"""

    EXPECT = {"Buff": 3555, "BattleEffect": 43, "FieldEffect": 3, "Soulmark": 2167,
              "SoulmarkTag": 20, "PetEffect": 300, "PetEffectGroup": 50, "EnergyBead": 48,
              "Gem": 245, "PetAdvance": 28, "Mintmark": 3843, "MintmarkClass": 98,
              "BattleEffectType": 5, "FieldEffectType": 2}

    def test_individual_counts(self):
        for cls, n in self.EXPECT.items():
            got = len(set(G.subjects(RDF.type, SEER[cls])))
            self.assertEqual(got, n, f"{cls} 个体数 {got} != {n}")

    def test_soulmark_has_desc_and_id(self):
        for s in G.subjects(RDF.type, SEER.Soulmark):
            self.assertIsNotNone(G.value(s, SEER.desc), f"{ln(s)} 缺 desc")
            self.assertIsNotNone(G.value(s, SEER.seerapiId), f"{ln(s)} 缺 seerapiId")

    def test_soulmark_label_not_ref_dump(self):
        for s in G.subjects(RDF.type, SEER.Soulmark):
            lab = G.value(s, RDFS.label)
            if lab is None:
                continue
            self.assertNotIn("http", str(lab), f"{ln(s)} 的 label 被写成引用列表（emit 的旧 bug）")
            self.assertNotIn("{", str(lab), f"{ln(s)} 的 label 被写成字典（emit 的旧 bug）")

    def test_soulmark_pet_links_are_pets(self):
        """affectsPet 的宾语必须是精灵个体（刻印表也用同一属性，主体可 Soulmark 可 Mintmark）。"""
        triples = list(G.triples((None, SEER.affectsPet, None)))
        self.assertGreater(len(triples), 2000, "魂印→精灵 连接太少")
        for s, _, o in triples:
            self.assertIn((o, RDF.type, SEER.Pet), G, f"{ln(s)} 指向的 {ln(o)} 不是精灵")
            self.assertTrue(
                (s, RDF.type, SEER.Soulmark) in G or (s, RDF.type, SEER.Mintmark) in G,
                f"affectsPet 的主体 {ln(s)} 既不是魂印也不是刻印")
        sm = [s for s, _, _ in triples if (s, RDF.type, SEER.Soulmark) in G]
        self.assertGreater(len(sm), 2000, "挂在魂印上的精灵连接过少")

    def test_no_property_mixes_object_and_literal(self):
        """同一属性不能既是对象属性又写字符串（tag/type 这类字段最容易踩）。"""
        kinds = {}
        for p, o in G.predicate_objects():
            if not str(p).startswith(str(SEER)):
                continue
            k = "obj" if isinstance(o, type(SEER.x)) else "lit"
            kinds.setdefault(p, set()).add(k)
        mixed = [ln(p) for p, ks in kinds.items() if len(ks) > 1]
        self.assertEqual(mixed, [], f"属性混用对象/字面量：{mixed}")

    def test_buff_tag_present(self):
        buffs = list(G.subjects(RDF.type, SEER.Buff))
        tagged = [b for b in buffs if G.value(b, SEER.tag) is not None]
        self.assertGreater(len(tagged), len(buffs) * 0.95, "超过 5% 的 buff 没有 tag")

    def test_soulmark_tool(self):
        r = kb.tool_soulmark(name="帝皇之御")
        self.assertNotIn("error", r)
        self.assertEqual(r["matches"][0]["pet"]["id"], "3512")
        descs = " ".join(x.get("desc") or "" for x in r["matches"][0]["soulmark"])
        self.assertIn("免疫异常状态", descs, f"帝皇之御魂印文本不对：{descs[:80]}")
        # pve_only 过滤
        r2 = kb.tool_soulmark(tag="PVE", pve_only=True, limit=5)
        self.assertNotIn("error", r2)
        self.assertTrue(r2["matches"])
        # 总览
        r3 = kb.tool_soulmark()
        self.assertIn("tags", r3)
        self.assertGreater(len(r3["tags"]), 5)

    def test_effect_tool(self):
        r = kb.tool_effect(name="吸血", limit=3)
        self.assertNotIn("error", r)
        self.assertTrue(r["matches"]["buff"])
        self.assertEqual(r["matches"]["buff"][0]["tag"], "吸血")
        r2 = kb.tool_effect()
        self.assertGreater(r2["total"], 3000)
        self.assertEqual(r2["counts"]["BattleEffect"], 43)


if __name__ == "__main__":
    unittest.main(verbosity=2)
